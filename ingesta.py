import uuid
from pathlib import Path

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf

# --- Config ---
COLLECTION = "Physics"
EMBED_MODEL = "bge-m3"
PDF_PATH = Path("/Users/galdon/Downloads/Language_Agents.pdf")   # <-- CAMBIA ESTO

EMBED_BATCH = 32     # nº de chunks que se embeben de una vez
UPSERT_BATCH = 100   # nº de puntos que se suben a Qdrant de una vez

client = QdrantClient(url="http://localhost:6333")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=3000,
    chunk_overlap=250,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embebe una lista de textos en una sola llamada a Ollama."""
    return ollama.embed(model=EMBED_MODEL, input=texts)["embeddings"]


def ensure_collection() -> None:
    """Crea la colección si no existe, con la dimensión real del embedder."""
    if client.collection_exists(COLLECTION):
        return
    dim = len(embed_batch(["dimension probe"])[0])
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    print(f"  colección '{COLLECTION}' creada (dim={dim}, cosine)")


# --- Extraer texto y trocear cruzando páginas (conservando la página) ---
def extract_full_text(pdf_path: Path):
    """Devuelve el texto completo y un mapa offset_de_carácter -> página."""
    doc = pymupdf.open(pdf_path)
    parts: list[str] = []
    page_starts: list[tuple[int, int]] = []  # (offset_inicial, nº de página)
    offset = 0
    total_pages = 0
    for page_num, page in enumerate(doc, start=1):
        total_pages = page_num
        text = page.get_text("text").strip()
        if not text:
            continue
        page_starts.append((offset, page_num))
        block = text + "\n\n"
        parts.append(block)
        offset += len(block)
    doc.close()
    return "".join(parts), page_starts, total_pages


def page_of(offset: int, page_starts: list[tuple[int, int]]) -> int:
    """Página a la que pertenece un offset de carácter dado."""
    page = page_starts[0][1] if page_starts else 1
    for start, num in page_starts:
        if start > offset:
            break
        page = num
    return page


# --- Ingesta ---
def flush(points: list[PointStruct]) -> None:
    if points:
        client.upsert(collection_name=COLLECTION, points=points)
        points.clear()


def ingest(pdf_path: Path) -> None:
    book = pdf_path.stem.replace("_", " ")
    full_text, page_starts, total_pages = extract_full_text(pdf_path)

    # Trocear sobre el texto completo (los chunks pueden cruzar páginas)
    chunks: list[tuple[str, int]] = []  # (texto, página)
    search_from = 0
    for chunk in splitter.split_text(full_text):
        if len(chunk.strip()) < 50:
            continue
        idx = full_text.find(chunk, search_from)
        if idx == -1:
            idx = full_text.find(chunk)
        if idx != -1:
            search_from = idx + 1
        chunks.append((chunk, page_of(idx if idx != -1 else 0, page_starts)))

    # Embeber en lote y subir en streaming (sin acumular todo en memoria)
    points: list[PointStruct] = []
    total = 0
    for i in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[i:i + EMBED_BATCH]
        vectors = embed_batch([c for c, _ in batch])
        for (text, page), vector in zip(batch, vectors):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"text": text, "book": book, "page": page},
                )
            )
            total += 1
            if len(points) >= UPSERT_BATCH:
                flush(points)
        print(f"  procesados {min(i + EMBED_BATCH, len(chunks))}/{len(chunks)} chunks...")

    flush(points)  # resto final
    print(f"\n✅ {book}: {total} chunks de {total_pages} páginas")


if __name__ == "__main__":
    if not PDF_PATH.exists():
        print(f"❌ No encuentro el fichero: {PDF_PATH}")
    else:
        print(f"Ingestando {PDF_PATH.name}...")
        ensure_collection()
        ingest(PDF_PATH)
