"""
Chat RAG sobre la colección de Qdrant.

Flujo por pregunta:
  pregunta -> bge-m3 (embed, Ollama) -> Qdrant (recupera top-k) -> Qwen (LM Studio) -> respuesta

Embeddings con el MISMO modelo que la ingesta (bge-m3) — es obligatorio: si el
vector de la pregunta no se genera igual que los de los chunks, la búsqueda no vale.
"""

import httpx
import ollama
from qdrant_client import QdrantClient

# --- Config ---
COLLECTION = "Physics"
EMBED_MODEL = "bge-m3"                       # Ollama, igual que en ingesta.py
TOP_K = 3                                    # nº de chunks que se recuperan (menos = prompt más corto y rápido)
MAX_TOKENS = 600                             # tope de longitud de la respuesta (lo que más acelera)

LM_BASE = "http://localhost:1234/v1"         # LM Studio (API estilo OpenAI)
# Para RAG conviene un modelo SIN "razonamiento" (responde directo y rápido).
# qwen3.6-35b-a3b es un modelo 'thinking': razona largo -> lento. Para extraer de
# un contexto no hace falta; usa un -instruct. Alternativas que ya tienes cargadas:
#   "qwen2.5-7b-instruct-1m"  (el más rápido)
#   "qwen2.5-14b-instruct-1m" (buen equilibrio)
LM_MODEL = "qwen2.5-7b-instruct-1m"

client = QdrantClient(url="http://localhost:6333")

SYSTEM = (
    "Eres un asistente que responde SOLO con la información del CONTEXTO que se te da. "
    "Si el contexto no contiene la respuesta, dilo claramente; no inventes. "
    "Cita la página entre paréntesis cuando uses un dato, p. ej. (pág. 5). "
    "Sé CONCISO: responde de forma directa, sin divagar ni repetir."
)


def embed(text: str) -> list[float]:
    """Embebe la pregunta con bge-m3 (idéntico al embedder de la ingesta)."""
    return ollama.embed(model=EMBED_MODEL, input=[text])["embeddings"][0]


def retrieve(question: str, k: int = TOP_K):
    """Devuelve los k chunks más parecidos a la pregunta."""
    hits = client.query_points(
        collection_name=COLLECTION,
        query=embed(question),
        limit=k,
        with_payload=True,
    ).points
    return [(h.payload, h.score) for h in hits]


def build_context(chunks) -> str:
    bloques = []
    for payload, score in chunks:
        libro = payload.get("book", "?")
        pag = payload.get("page", "?")
        texto = payload.get("text", "")
        bloques.append(f"[{libro} — pág. {pag} | score {score:.3f}]\n{texto}")
    return "\n\n---\n\n".join(bloques)


def ask_llm(question: str, context: str) -> str:
    """Llama a Qwen en LM Studio con la pregunta + el contexto recuperado, en streaming."""
    payload = {
        "model": LM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"CONTEXTO:\n{context}\n\nPREGUNTA: {question}"},
        ],
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
        "stream": True,
    }
    out = []
    reasoning = []   # algunos modelos 'thinking' mandan el texto aquí en vez de en content
    with httpx.stream("POST", f"{LM_BASE}/chat/completions", json=payload, timeout=None) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[len("data: "):]
            if data.strip() == "[DONE]":
                break
            import json
            delta = json.loads(data)["choices"][0]["delta"]
            content = delta.get("content") or ""
            if content:
                print(content, end="", flush=True)
                out.append(content)
            rc = delta.get("reasoning_content") or ""
            if rc:
                reasoning.append(rc)
    print()
    # Si el modelo solo razonó y no produjo respuesta (modelo 'thinking' + max_tokens corto),
    # muestra el razonamiento para no dejarlo en blanco.
    if not out and reasoning:
        print("⚠️  (el modelo solo generó razonamiento; usa un modelo -instruct para respuestas directas)")
        print("".join(reasoning))
    return "".join(out)


def main():
    print(f"RAG sobre '{COLLECTION}' — modelo {LM_MODEL}. Escribe tu pregunta (Ctrl+C para salir).\n")
    while True:
        try:
            question = input("❓ > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!")
            break
        if not question:
            continue

        chunks = retrieve(question)
        if not chunks:
            print("⚠️  No encontré nada en el RAG.\n")
            continue

        # Fuentes recuperadas (para que veas de dónde sale la respuesta)
        print("\n📚 Fuentes:")
        for payload, score in chunks:
            print(f"   - {payload.get('book')} pág. {payload.get('page')} (score {score:.3f})")
        print("\n💬 Respuesta:")
        ask_llm(question, build_context(chunks))
        print()


if __name__ == "__main__":
    main()
