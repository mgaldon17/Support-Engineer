
<div align="center">

# 🤖 Support Engineer

### A self-improving automation agent for enterprise support — built _on_ Claude Code, not just _with_ it.

**The loop, the reasoning and the vision are native. The only real code is a memory that lets the agent _learn_.**

[![Runs on Claude Code](https://img.shields.io/badge/runs%20on-Claude%20Code-6E56CF?style=flat-square)](https://claude.com/claude-code)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Vector store: Qdrant](https://img.shields.io/badge/vectors-Qdrant-DC244C?style=flat-square)](https://qdrant.tech/)
[![Memory: mem0](https://img.shields.io/badge/memory-mem0-00C2A8?style=flat-square)](https://mem0.ai/)
[![MCP](https://img.shields.io/badge/protocol-MCP-000000?style=flat-square)](https://modelcontextprotocol.io/)

[**English**](#-english) · [**Español**](#-español)

</div>

---

<a name="-english"></a>

## 🇬🇧 English

### What is this?

**Support Engineer is an automation agent for enterprise support tasks.** It runs on
**Claude Code**: the agent loop, the reasoning, and the vision (reading screenshots) are
all _native_ to the model — there is no orchestration framework to maintain.

The repository contributes **two things on top of Claude Code**:

| Piece | What it adds |
|-------|--------------|
| 🧠 **`agentmem`** — a lesson memory over Qdrant, exposed as the `memory` MCP server | The agent **remembers procedures** that worked and **reuses them by meaning**, so it gets better every time. |
| 🪝 **Two hooks** — auto-inject lessons + apply guardrails | Relevant memory is **fed in automatically**, and dangerous actions are **vetoed in code** before they run. |

> Everything else — the operating flow — is **instructions**, not code. They live in
> [`CLAUDE.md`](./CLAUDE.md) and steer the model directly. The "scalator" idea: the agent
> _scales its own competence_ by turning each solved task into reusable memory.

### The big picture

```mermaid
flowchart TB
    subgraph user [" "]
        ENG([👩‍💻 Support engineer<br/>request])
    end

    subgraph cc ["🤖 Claude Code — the native agent loop"]
        BRAIN["Reasoning · Vision · Tool use<br/><i>steered by CLAUDE.md</i>"]
    end

    subgraph hooks ["🪝 Hooks (deterministic, in code)"]
        H1["UserPromptSubmit<br/>inject relevant lessons"]
        H2["PreToolUse<br/>guardrails / veto"]
    end

    subgraph tools ["🛠️ Tools"]
        T1["🧠 memory MCP<br/>lesson_*"]
        T2["🌐 Playwright<br/>browser"]
        T3["💻 Desktop Commander<br/>shell / files"]
        T4["✅ verifier<br/>subagent"]
    end

    subgraph mem ["🗄️ agentmem (the only real code)"]
        STORE["Mem0LessonStore"]
        EMB["Local embedder<br/>multilingual MiniLM · 384d"]
        QDR[("Qdrant<br/>vector DB")]
    end

    ENG --> H1 --> BRAIN
    BRAIN <-->|every tool call| H2
    BRAIN --> T1 & T2 & T3 & T4
    T1 --> STORE
    H1 -.recall.-> STORE
    STORE --> EMB --> QDR

    classDef brain fill:#6E56CF,stroke:#4A3AA0,color:#fff
    classDef hook fill:#F5A623,stroke:#C77F00,color:#000
    classDef store fill:#DC244C,stroke:#9E1535,color:#fff
    class BRAIN brain
    class H1,H2 hook
    class QDR store
```

### How a request flows

Every request follows a five-step flow defined in `CLAUDE.md`:

```mermaid
flowchart TD
    START([📨 Request arrives]) --> TRIAGE

    TRIAGE["<b>1. Triage</b><br/>derive intent + objective<br/>+ observable success criteria"]
    TRIAGE --> INTENT{intent?}

    INTENT -->|info<br/>answer a question| RECALL
    INTENT -->|action<br/>change the system| RECALL

    RECALL["<b>2. Recall memory</b><br/>match a lesson by MEANING,<br/>not wording (any language)"]
    RECALL --> HASLESSON{lesson<br/>covers it?}

    HASLESSON -->|yes| FOLLOW["<b>3. Execute</b><br/>follow the lesson<br/>step by step"]
    HASLESSON -->|no| SCRATCH["<b>3. Execute</b><br/>resolve from scratch"]

    FOLLOW --> VERIFY
    SCRATCH --> VERIFY

    VERIFY{"<b>4. Verify / answer</b><br/>action → verifier subagent<br/>info → answer directly"}

    VERIFY -->|passed| PERSIST
    VERIFY -->|failed| PERSIST

    PERSIST["<b>5. Persist learning</b><br/>reinforce ✅ / record failure ❌ /<br/>add new lesson 📝 (→ /review)"]
    PERSIST --> DONE([✔️ Done])

    classDef step fill:#EEF2FF,stroke:#6E56CF,color:#1E1B4B
    class TRIAGE,RECALL,FOLLOW,SCRATCH,PERSIST step
```

- **`intent = info`** → the engineer wants an _answer_; nothing changes. Reply with the concrete facts.
- **`intent = action`** → the engineer wants the system _changed_; execute, then **prove it** with the `verifier` subagent before claiming success.
- When unsure, treat it as **action** (the conservative execute-and-verify path).

### The memory: how lessons live and grow

A **lesson** is a reusable, step-by-step procedure (`title` + `content`) plus two
counters the agent folds back. Search is **purely semantic** (dense-vector cosine
similarity in Qdrant) — a Spanish lesson matches an English task and vice-versa.

```mermaid
stateDiagram-v2
    [*] --> learned: agent solves a NEW task<br/>(lesson_add)
    [*] --> human_authored: a human curates one<br/>(lesson_inject / /learn)

    learned --> pending_review: awaits approval
    pending_review --> trusted: /review accepts<br/>(lesson_resolve)
    pending_review --> [*]: rejected (delete)

    human_authored --> trusted

    trusted --> trusted: reused & worked<br/>reuse++ (reinforce)
    trusted --> trusted: reused & failed<br/>failure_count++ (record_failure)
```

> 🔒 **Trust model:** lessons the agent invents start as `learned / pending_review` and
> surface in **`/review`** for a human to accept — they never silently become trusted
> guidance. Human-authored lessons are trusted immediately.

### Guardrails — policy enforced in code, not in prompts

A `PreToolUse` hook runs **before every tool call** and can veto it. This is the
anti-hallucination and anti-destruction backstop.

```mermaid
sequenceDiagram
    participant M as 🤖 Claude
    participant H as 🪝 PreToolUse hook
    participant G as 🛡️ GuardrailChain
    participant T as 🛠️ Tool

    M->>H: tool call (name + args)
    H->>G: check(name, args)
    Note over G: URL guard → valid? allowed host?<br/>reachable (no guessed 404s)?
    Note over G: Destructive guard → rm -rf /, mkfs,<br/>dd of=/dev/…, force-push main, shutdown…
    alt allowed
        G-->>H: allow
        H-->>T: ✅ run
        T-->>M: result
    else vetoed
        G-->>H: deny + reason
        H-->>M: ❌ blocked — choose a legitimate path
    end
```

Both guards **fail open**: a bug or missing dependency never wedges the agent.

### Project layout

```
support-engineer/
├── CLAUDE.md                 # the operating flow (instructions = behaviour)
├── config.yaml               # all settings (nested YAML) — single source of config
├── .env.example              # template for the gitignored .env (API keys + DC_MCP_HOME)
├── docker-compose.yml        # Qdrant on localhost:6333
├── .mcp.json                 # wires 3 MCP servers: memory (local), pw, dc (${DC_MCP_HOME})
├── start_dashboard.sh        # launch the control panel + open the browser
├── hooks/
│   ├── inject_lessons.py     # UserPromptSubmit → auto-recall lessons
│   └── guardrail_check.py    # PreToolUse → veto bad URLs / destructive cmds
├── dashboard/                # the control panel (stdlib HTTP server + web UI)
│   ├── server.py             # thin HTTP coordinator: routing + dispatch
│   ├── configfile.py         # config.yaml read/write (atomic, comment-preserving)
│   ├── settings_store.py     # settings.json permissions allowlist (atomic)
│   ├── translation.py        # glob ↔ blocklist-regex helpers (pure)
│   └── assets/               # layered front-end (api, dom, views, app)
└── src/agentmem/             # ← the only real code
    ├── config.py             # config layer (config.yaml → env vars → defaults)
    ├── lesson.py             # Lesson entity + origin / counters
    ├── ports.py              # LessonStore Protocol (the store abstraction)
    ├── store.py              # Mem0LessonStore over Qdrant (semantic)
    ├── atomicio.py           # atomic text-file writes (temp file + rename)
    ├── guardrails.py         # URL + destructive-command guards
    ├── rules_store.py        # custom (user-defined) blocked-command rules
    └── mcp_server.py         # exposes lesson_* as MCP tools
```

### Quick start

```bash
docker compose up -d        # 1. start Qdrant (the lesson store) on :6333
pip install -e .            # 2. install agentmem (mem0 + qdrant-client + mcp + httpx + ruamel.yaml)
# 3. open the repo in Claude Code — the `memory` MCP server + hooks load automatically
```

The embedder runs **locally, in-process** (sentence-transformers, multilingual MiniLM) —
no API key, fully offline after the one-time model download.

### MCP servers

Claude Code wires the agent's tools from [`.mcp.json`](./.mcp.json) — **three** servers:

| Server | Tools | Origin |
|--------|-------|--------|
| `memory` | `lesson_*` | **This repo** — `python -m agentmem.mcp_server`. |
| `pw` | Playwright browser | npm on demand — `npx @playwright/mcp@latest`. |
| `dc` | Desktop Commander (shell / files) | A **local sibling checkout** at `${DC_MCP_HOME}`. |

`dc` is **not** vendored here — it runs from a separate Desktop Commander checkout on your
machine. For security and portability its path is **not hardcoded** in the committed
`.mcp.json`; instead it expands the `${DC_MCP_HOME}` environment variable:

```json
"dc": {
  "command": "node",
  "args": ["${DC_MCP_HOME}/dist/index.js"],
  "cwd": "${DC_MCP_HOME}"
}
```

Set `DC_MCP_HOME` to your clone (an **absolute** path — `.mcp.json` does not tilde-expand).
Keep the value in the gitignored `.env` (see `.env.example`), but note Claude Code expands
`.mcp.json` from the **process environment**, so export it before launching:

```bash
set -a; source .env; set +a     # load DC_MCP_HOME (and the API keys) into the env
claude                          # then launch Claude Code
```

If `DC_MCP_HOME` is unset the `dc` server simply fails to start; `memory` and `pw` are
unaffected. (You don't have Desktop Commander? Drop the `dc` block from `.mcp.json`.)

### Configuration

All settings live in [`config.yaml`](./config.yaml) (nested by section). Resolution order:

> **real environment variable** ⟶ **`config.yaml`** ⟶ **built-in defaults**

Each `section.key` maps to a flat env name via `config._FIELD_MAP` (e.g.
`embedder.provider` ⟶ `EMBEDDER_PROVIDER`), so any setting can be overridden per-deploy
with that env var. Point at another file with `AGENTMEM_CONFIG=/path/to/file`.

**Secrets live in `.env`, not in `config.yaml`.** API keys sit in a gitignored
[`.env`](./.env.example) (KEY=VALUE) and the YAML references them as `${EMBEDDER_API_KEY}`
/ `${LLM_API_KEY}`; the loader reads `.env` first and expands those placeholders. Copy
`.env.example` ⟶ `.env` and fill in real keys (override the file with
`AGENTMEM_DOTENV=/path/to/.env`).

#### Full `config.yaml` reference

| `section.key` | Env name | Default | Meaning |
|---------------|----------|---------|---------|
| `memory.qdrant_host` | `QDRANT_HOST` | `localhost` | Qdrant host. |
| `memory.qdrant_port` | `QDRANT_PORT` | `6333` | Qdrant port. |
| `memory.collection` | `MEM_COLLECTION` | `agentcore_lessons` | Qdrant collection holding the lessons. |
| `memory.mem_user` | `MEM_USER` | `agentcore` | mem0 identity namespace shared by all lessons. |
| `embedder.provider` | `EMBEDDER_PROVIDER` | `huggingface` | Embedder backend: `huggingface`/`fastembed` (local), or `openai`/`lmstudio`/`ollama` (remote). |
| `embedder.model` | `EMBEDDER_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding model name. |
| `embedder.base_url` | `EMBEDDER_BASE_URL` | `""` | Endpoint for remote embedder providers only. |
| `embedder.api_key` | `EMBEDDER_API_KEY` | `${EMBEDDER_API_KEY}` → `.env` | Key for OpenAI-compatible embedders; empty for local. |
| `embedder.dims` | `EMBEDDER_DIMS` | `384` | Vector dimension — **must** match the model (changing it needs a fresh collection). |
| `embedder.check_reachable` | `EMBEDDER_CHECK_REACHABLE` | `true` | Preflight a remote embedder (ollama/openai/lmstudio) before building the store — for ollama, also that the model is pulled — so a down embedder fails loudly instead of writing empty vectors. No-op for local providers. |
| `llm.infer` | `INFER` | `false` | `true` ⟶ mem0's LLM rewrites/reconciles a lesson on write; `false` ⟶ stored verbatim, LLM never called. |
| `llm.provider` | `LLM_PROVIDER` | `openai` | LLM provider (OpenAI-compatible). |
| `llm.model` | `LLM_MODEL` | `qwen2.5-7b-instruct-1m` | LLM model (only used when `infer: true`). |
| `llm.base_url` | `LLM_BASE_URL` | `http://localhost:1234/v1` | LLM endpoint (default = local LM Studio). |
| `llm.api_key` | `LLM_API_KEY` | `${LLM_API_KEY}` → `.env` | LLM key (only used when `infer: true`). |
| `llm.temperature` | `LLM_TEMPERATURE` | `0.1` | Sampling temperature — **only** the `infer: true` write path; never affects search. |
| `llm.top_p` | `LLM_TOP_P` | `1.0` | Nucleus sampling — same scope as `temperature`. |
| `llm.max_tokens` | `LLM_MAX_TOKENS` | `2000` | Max tokens for the write-time rewrite. |
| `guardrails.url_enabled` | `GUARD_URL_ENABLED` | `true` | Master switch for the URL guard. |
| `guardrails.destructive_enabled` | `GUARD_DESTRUCTIVE_ENABLED` | `true` | Master switch for the destructive-command guard. |
| `guardrails.allow_domains` | `GUARD_ALLOW_DOMAINS` | `""` | Comma-separated host allowlist for browsing; empty = any host. |
| `guardrails.check_reachable` | `GUARD_CHECK_REACHABLE` | `true` | Probe that a URL is reachable before allowing navigation. |
| `guardrails.disabled_patterns` | `GUARD_DISABLED_PATTERNS` | `""` | Comma-separated keys of built-in destructive patterns to disable. |
| `guardrails.custom_rules_file` | `GUARD_CUSTOM_RULES_FILE` | `""` | JSON file of user rules; empty = `<repo>/custom_guardrails.json`. |
| `guardrails.probe_timeout` | `PROBE_TIMEOUT` | `5.0` | URL-reachability probe timeout (seconds). |
| `guardrails.probe_user_agent` | `PROBE_USER_AGENT` | `Mozilla/5.0 (agentmem url-guardrail)` | User-Agent for the probe. |
| `retrieval.search_limit` | `LESSON_SEARCH_LIMIT` | `8` | Default `top_k` for semantic recall. |
| `retrieval.list_limit` | `LESSON_LIST_LIMIT` | `1000` | `top_k` cap when enumerating all lessons. |

### Control panel

A visual control panel for a level-3 engineer to inspect and change everything the agent
exposes — no terminal needed. It is a **stdlib HTTP server** (config IO via ruamel.yaml) +
a layered web UI (Tailwind); the embedder/Qdrant aside, it runs fully offline.

```bash
./start_dashboard.sh            # starts the server and opens http://localhost:8787
./start_dashboard.sh 9000       # custom port
# or, manually:
python dashboard/server.py --port 8787
```

> Qdrant must be up (`docker compose up -d`) for the **Lessons** tab; the rest works without it.

| Tab | What you control |
|-----|------------------|
| **Guardrails** | URL guard on/off, reachability probe, domain allowlist, probe timeout/UA; destructive-guard master switch; how each guard works. |
| **Commands** | The full blocklist (built-in + **custom rules you add**, each toggled on/off or deleted) and the allowlist — **move commands either way** (allowed ⇆ blocked). |
| **Lessons** | Live counts (total / pending / approved) and the pending-review queue with **Validate** / **Reject**. |
| **Memory** | Qdrant host/port/collection/namespace, embedder provider/model/dims, retrieval limits. |

Edits are written back to [`config.yaml`](./config.yaml), `.claude/settings.json`
(permissions only) and `custom_guardrails.json` (user rules) — and apply on the agent's
next tool call. The dashboard edits the YAML in place (comments preserved) under
`guardrails.*` / `memory.*` / `embedder.*` / `retrieval.*`.

### Slash commands

| Command | Does |
|---------|------|
| `/review` | Triage the lessons the agent learned that await human approval. |
| `/learn <procedure>` | Manually capture a procedure into memory. |

---

<a name="-español"></a>

## 🇪🇸 Español

### ¿Qué es esto?

**Support Engineer es un agente de automatización para tareas de soporte
empresarial.** Funciona sobre **Claude Code**: el bucle del agente, el razonamiento y la
visión (leer capturas) son _nativos_ del modelo — no hay framework de orquestación que
mantener.

El repositorio aporta **dos cosas encima de Claude Code**:

| Pieza | Qué añade |
|-------|-----------|
| 🧠 **`agentmem`** — una memoria de lecciones sobre Qdrant, expuesta como el servidor MCP `memory` | El agente **recuerda procedimientos** que funcionaron y los **reutiliza por significado**, así que mejora cada vez. |
| 🪝 **Dos hooks** — auto-inyectar lecciones + aplicar guardarraíles | La memoria relevante se **inyecta automáticamente**, y las acciones peligrosas se **vetan en código** antes de ejecutarse. |

> Todo lo demás — el flujo operativo — son **instrucciones**, no código. Viven en
> [`CLAUDE.md`](./CLAUDE.md) y guían al modelo directamente. La idea "scalator": el agente
> _escala su propia competencia_ convirtiendo cada tarea resuelta en memoria reutilizable.

### La visión de conjunto

```mermaid
flowchart TB
    subgraph user [" "]
        ENG([👩‍💻 Petición del<br/>ingeniero de soporte])
    end

    subgraph cc ["🤖 Claude Code — el bucle de agente nativo"]
        BRAIN["Razonamiento · Visión · Uso de tools<br/><i>guiado por CLAUDE.md</i>"]
    end

    subgraph hooks ["🪝 Hooks (deterministas, en código)"]
        H1["UserPromptSubmit<br/>inyecta lecciones relevantes"]
        H2["PreToolUse<br/>guardarraíles / veto"]
    end

    subgraph tools ["🛠️ Herramientas"]
        T1["🧠 memory MCP<br/>lesson_*"]
        T2["🌐 Playwright<br/>navegador"]
        T3["💻 Desktop Commander<br/>shell / ficheros"]
        T4["✅ verifier<br/>subagente"]
    end

    subgraph mem ["🗄️ agentmem (el único código real)"]
        STORE["Mem0LessonStore"]
        EMB["Embedder local<br/>MiniLM multilingüe · 384d"]
        QDR[("Qdrant<br/>BD vectorial")]
    end

    ENG --> H1 --> BRAIN
    BRAIN <-->|cada tool call| H2
    BRAIN --> T1 & T2 & T3 & T4
    T1 --> STORE
    H1 -.recuerda.-> STORE
    STORE --> EMB --> QDR

    classDef brain fill:#6E56CF,stroke:#4A3AA0,color:#fff
    classDef hook fill:#F5A623,stroke:#C77F00,color:#000
    classDef store fill:#DC244C,stroke:#9E1535,color:#fff
    class BRAIN brain
    class H1,H2 hook
    class QDR store
```

### Cómo fluye una petición

Cada petición sigue un flujo de cinco pasos definido en `CLAUDE.md`:

```mermaid
flowchart TD
    START([📨 Llega una petición]) --> TRIAGE

    TRIAGE["<b>1. Triaje</b><br/>deriva intención + objetivo<br/>+ criterios de éxito observables"]
    TRIAGE --> INTENT{¿intención?}

    INTENT -->|info<br/>responder una pregunta| RECALL
    INTENT -->|acción<br/>cambiar el sistema| RECALL

    RECALL["<b>2. Recordar memoria</b><br/>casa una lección por SIGNIFICADO,<br/>no por literalidad (cualquier idioma)"]
    RECALL --> HASLESSON{¿hay lección<br/>que lo cubra?}

    HASLESSON -->|sí| FOLLOW["<b>3. Ejecutar</b><br/>sigue la lección<br/>paso a paso"]
    HASLESSON -->|no| SCRATCH["<b>3. Ejecutar</b><br/>resuelve desde cero"]

    FOLLOW --> VERIFY
    SCRATCH --> VERIFY

    VERIFY{"<b>4. Verificar / responder</b><br/>acción → subagente verifier<br/>info → responde directo"}

    VERIFY -->|pasa| PERSIST
    VERIFY -->|falla| PERSIST

    PERSIST["<b>5. Persistir lo aprendido</b><br/>reforzar ✅ / registrar fallo ❌ /<br/>añadir lección nueva 📝 (→ /review)"]
    PERSIST --> DONE([✔️ Hecho])

    classDef step fill:#EEF2FF,stroke:#6E56CF,color:#1E1B4B
    class TRIAGE,RECALL,FOLLOW,SCRATCH,PERSIST step
```

- **`intención = info`** → el ingeniero quiere una _respuesta_; nada cambia. Responde con los datos concretos.
- **`intención = acción`** → quiere _cambiar_ el sistema; ejecuta y luego **demuéstralo** con el subagente `verifier` antes de declarar éxito.
- En caso de duda, trátalo como **acción** (la vía conservadora: ejecutar y verificar).

### La memoria: cómo viven y crecen las lecciones

Una **lección** es un procedimiento reutilizable, paso a paso (`title` + `content`), más
dos contadores que el agente realimenta. La búsqueda es **puramente semántica**
(similitud de coseno sobre vectores densos en Qdrant) — una lección en español casa con
una tarea en inglés y viceversa.

```mermaid
stateDiagram-v2
    [*] --> learned: el agente resuelve una tarea NUEVA<br/>(lesson_add)
    [*] --> human_authored: un humano la cura<br/>(lesson_inject / /learn)

    learned --> pending_review: espera aprobación
    pending_review --> trusted: /review la acepta<br/>(lesson_resolve)
    pending_review --> [*]: rechazada (borrar)

    human_authored --> trusted

    trusted --> trusted: reusada y funcionó<br/>reuse++ (reinforce)
    trusted --> trusted: reusada y falló<br/>failure_count++ (record_failure)
```

> 🔒 **Modelo de confianza:** las lecciones que el agente inventa empiezan como
> `learned / pending_review` y aparecen en **`/review`** para que un humano las acepte —
> nunca se convierten en guía de confianza en silencio. Las creadas por humanos son de
> confianza al instante.

### Guardarraíles — política aplicada en código, no en prompts

Un hook `PreToolUse` se ejecuta **antes de cada llamada a herramienta** y puede vetarla.
Es la red de seguridad anti-alucinación y anti-destrucción.

```mermaid
sequenceDiagram
    participant M as 🤖 Claude
    participant H as 🪝 Hook PreToolUse
    participant G as 🛡️ GuardrailChain
    participant T as 🛠️ Herramienta

    M->>H: tool call (nombre + args)
    H->>G: check(nombre, args)
    Note over G: Guard URL → ¿válida? ¿host permitido?<br/>¿alcanzable (sin 404 inventados)?
    Note over G: Guard destructivo → rm -rf /, mkfs,<br/>dd of=/dev/…, force-push a main, shutdown…
    alt permitida
        G-->>H: allow
        H-->>T: ✅ ejecutar
        T-->>M: resultado
    else vetada
        G-->>H: deny + motivo
        H-->>M: ❌ bloqueada — elige una vía legítima
    end
```

Ambos guards **fallan en abierto** (_fail-open_): un bug o una dependencia ausente nunca
bloquean al agente.

### Estructura del proyecto

```
support-engineer/
├── CLAUDE.md                 # el flujo operativo (instrucciones = comportamiento)
├── config.yaml               # todos los ajustes (YAML por secciones) — fuente única de config
├── .env.example              # plantilla del .env gitignored (API keys + DC_MCP_HOME)
├── docker-compose.yml        # Qdrant en localhost:6333
├── .mcp.json                 # cablea 3 servidores MCP: memory (local), pw, dc (${DC_MCP_HOME})
├── start_dashboard.sh        # arranca el panel de control + abre el navegador
├── hooks/
│   ├── inject_lessons.py     # UserPromptSubmit → auto-recuerda lecciones
│   └── guardrail_check.py    # PreToolUse → veta URLs malas / comandos destructivos
├── dashboard/                # el panel de control (servidor HTTP stdlib + UI web)
│   ├── server.py             # coordinador HTTP fino: enrutado + dispatch
│   ├── configfile.py         # lectura/escritura de config.yaml (atómica, conserva comentarios)
│   ├── settings_store.py     # allowlist de permisos en settings.json (atómica)
│   ├── translation.py        # helpers glob ↔ regex de bloqueo (puros)
│   └── assets/               # front-end por capas (api, dom, views, app)
└── src/agentmem/             # ← el único código real
    ├── config.py             # capa de config (config.yaml → env vars → defaults)
    ├── lesson.py             # entidad Lesson + origen / contadores
    ├── ports.py              # Protocol LessonStore (la abstracción del almacén)
    ├── store.py              # Mem0LessonStore sobre Qdrant (semántico)
    ├── atomicio.py           # escrituras atómicas de ficheros (temp + rename)
    ├── guardrails.py         # guards de URL + comandos destructivos
    ├── rules_store.py        # reglas de comandos bloqueados definidas por el usuario
    └── mcp_server.py         # expone lesson_* como tools MCP
```

### Arranque rápido

```bash
docker compose up -d        # 1. arranca Qdrant (la memoria) en :6333
pip install -e .            # 2. instala agentmem (mem0 + qdrant-client + mcp + httpx + ruamel.yaml)
# 3. abre el repo en Claude Code — el servidor MCP `memory` + los hooks cargan solos
```

El embedder corre **localmente, en el proceso** (sentence-transformers, MiniLM
multilingüe) — sin API key, totalmente offline tras la descarga única del modelo.

### Servidores MCP

Claude Code cablea las tools del agente desde [`.mcp.json`](./.mcp.json) — **tres** servidores:

| Servidor | Tools | Origen |
|----------|-------|--------|
| `memory` | `lesson_*` | **Este repo** — `python -m agentmem.mcp_server`. |
| `pw` | Navegador Playwright | npm bajo demanda — `npx @playwright/mcp@latest`. |
| `dc` | Desktop Commander (shell / ficheros) | Un **checkout hermano local** en `${DC_MCP_HOME}`. |

`dc` **no** está incluido en este repo — corre desde un checkout aparte de Desktop
Commander en tu máquina. Por seguridad y portabilidad su ruta **no está hardcodeada** en el
`.mcp.json` versionado; en su lugar expande la variable de entorno `${DC_MCP_HOME}`:

```json
"dc": {
  "command": "node",
  "args": ["${DC_MCP_HOME}/dist/index.js"],
  "cwd": "${DC_MCP_HOME}"
}
```

Pon `DC_MCP_HOME` apuntando a tu clon (ruta **absoluta** — `.mcp.json` no expande `~`).
Guarda el valor en el `.env` gitignored (ver `.env.example`), pero ten en cuenta que Claude
Code expande `.mcp.json` desde el **entorno del proceso**, así que expórtalo antes de
arrancar:

```bash
set -a; source .env; set +a     # carga DC_MCP_HOME (y las API keys) en el entorno
claude                          # luego arranca Claude Code
```

Si `DC_MCP_HOME` no está definida, el servidor `dc` simplemente no arranca; `memory` y `pw`
no se ven afectados. (¿No tienes Desktop Commander? Quita el bloque `dc` de `.mcp.json`.)

### Configuración

Todos los ajustes viven en [`config.yaml`](./config.yaml) (YAML por secciones). Orden de
resolución:

> **variable de entorno real** ⟶ **`config.yaml`** ⟶ **defaults del código**

Cada `section.key` mapea a un nombre de env plano vía `config._FIELD_MAP` (p. ej.
`embedder.provider` ⟶ `EMBEDDER_PROVIDER`), así cualquier ajuste se puede sobrescribir por
despliegue con esa env var. Apunta a otro fichero con `AGENTMEM_CONFIG=/ruta/al/fichero`.

**Los secretos viven en `.env`, no en `config.yaml`.** Las API keys están en un `.env`
gitignored (KEY=VALUE) y el YAML las referencia como `${EMBEDDER_API_KEY}` /
`${LLM_API_KEY}`; el loader lee primero el `.env` y expande esos placeholders. Copia
`.env.example` ⟶ `.env` y pon las keys reales (cambia el fichero con
`AGENTMEM_DOTENV=/ruta/al/.env`).

#### Referencia completa de `config.yaml`

| `section.key` | Nombre env | Default | Significado |
|---------------|------------|---------|-------------|
| `memory.qdrant_host` | `QDRANT_HOST` | `localhost` | Host de Qdrant. |
| `memory.qdrant_port` | `QDRANT_PORT` | `6333` | Puerto de Qdrant. |
| `memory.collection` | `MEM_COLLECTION` | `agentcore_lessons` | Colección de Qdrant con las lecciones. |
| `memory.mem_user` | `MEM_USER` | `agentcore` | Namespace de identidad de mem0 (compartido por todas). |
| `embedder.provider` | `EMBEDDER_PROVIDER` | `huggingface` | Backend del embedder: `huggingface`/`fastembed` (local), o `openai`/`lmstudio`/`ollama` (remoto). |
| `embedder.model` | `EMBEDDER_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings. |
| `embedder.base_url` | `EMBEDDER_BASE_URL` | `""` | Endpoint, solo para embedders remotos. |
| `embedder.api_key` | `EMBEDDER_API_KEY` | `${EMBEDDER_API_KEY}` → `.env` | Key para embedders OpenAI-compatibles; vacía en local. |
| `embedder.dims` | `EMBEDDER_DIMS` | `384` | Dimensión del vector — **debe** coincidir con el modelo (cambiarla exige colección nueva). |
| `embedder.check_reachable` | `EMBEDDER_CHECK_REACHABLE` | `true` | Preflight de un embedder remoto (ollama/openai/lmstudio) antes de construir el store — para ollama, también que el modelo esté pulled — para que un embedder caído falle ruidosamente en vez de escribir vectores vacíos. No-op en local. |
| `llm.infer` | `INFER` | `false` | `true` ⟶ el LLM de mem0 reescribe/reconcilia la lección al guardar; `false` ⟶ verbatim, LLM nunca llamado. |
| `llm.provider` | `LLM_PROVIDER` | `openai` | Provider del LLM (OpenAI-compatible). |
| `llm.model` | `LLM_MODEL` | `qwen2.5-7b-instruct-1m` | Modelo del LLM (solo con `infer: true`). |
| `llm.base_url` | `LLM_BASE_URL` | `http://localhost:1234/v1` | Endpoint del LLM (default = LM Studio local). |
| `llm.api_key` | `LLM_API_KEY` | `${LLM_API_KEY}` → `.env` | Key del LLM (solo con `infer: true`). |
| `llm.temperature` | `LLM_TEMPERATURE` | `0.1` | Temperatura — **solo** la ruta de escritura `infer: true`; nunca afecta la búsqueda. |
| `llm.top_p` | `LLM_TOP_P` | `1.0` | Nucleus sampling — mismo ámbito que `temperature`. |
| `llm.max_tokens` | `LLM_MAX_TOKENS` | `2000` | Máx. tokens de la reescritura al guardar. |
| `guardrails.url_enabled` | `GUARD_URL_ENABLED` | `true` | Interruptor maestro del guard de URL. |
| `guardrails.destructive_enabled` | `GUARD_DESTRUCTIVE_ENABLED` | `true` | Interruptor maestro del guard de comandos destructivos. |
| `guardrails.allow_domains` | `GUARD_ALLOW_DOMAINS` | `""` | Allowlist de hosts (coma-separada) para navegar; vacío = cualquiera. |
| `guardrails.check_reachable` | `GUARD_CHECK_REACHABLE` | `true` | Comprueba que la URL es accesible antes de permitir navegar. |
| `guardrails.disabled_patterns` | `GUARD_DISABLED_PATTERNS` | `""` | Keys (coma-separadas) de patrones destructivos built-in a desactivar. |
| `guardrails.custom_rules_file` | `GUARD_CUSTOM_RULES_FILE` | `""` | Fichero JSON de reglas de usuario; vacío = `<repo>/custom_guardrails.json`. |
| `guardrails.probe_timeout` | `PROBE_TIMEOUT` | `5.0` | Timeout (s) del probe de accesibilidad de URL. |
| `guardrails.probe_user_agent` | `PROBE_USER_AGENT` | `Mozilla/5.0 (agentmem url-guardrail)` | User-Agent del probe. |
| `retrieval.search_limit` | `LESSON_SEARCH_LIMIT` | `8` | `top_k` por defecto en la recuperación semántica. |
| `retrieval.list_limit` | `LESSON_LIST_LIMIT` | `1000` | Tope de `top_k` al enumerar todas las lecciones. |

### Panel de control

Un panel visual para que un ingeniero de nivel 3 inspeccione y cambie todo lo que el
agente expone — sin tocar la terminal. Es un **servidor HTTP de la stdlib** (IO de config
vía ruamel.yaml) + una UI web por capas (Tailwind); salvo el embedder/Qdrant, funciona 100%
offline.

```bash
./start_dashboard.sh            # arranca el servidor y abre http://localhost:8787
./start_dashboard.sh 9000       # puerto a medida
# o, manualmente:
python dashboard/server.py --port 8787
```

> Qdrant debe estar arriba (`docker compose up -d`) para la pestaña **Lecciones**; el resto funciona sin él.

| Pestaña | Qué controlas |
|---------|---------------|
| **Guardrails** | Guard de URL on/off, probe de accesibilidad, allowlist de dominios, timeout/UA; interruptor maestro del guard destructivo; cómo funciona cada guard. |
| **Comandos** | La blocklist completa (built-in + **reglas custom que añades**, cada una activable o eliminable) y la allowlist — **mueve comandos en ambos sentidos** (permitido ⇆ bloqueado). |
| **Lecciones** | Conteos en vivo (total / por revisar / aprobadas) y la cola pendiente con **Validar** / **Rechazar**. |
| **Memoria** | Host/puerto/colección/namespace de Qdrant, provider/modelo/dims del embedder, límites de recuperación. |

Los cambios se escriben en [`config.yaml`](./config.yaml), `.claude/settings.json` (solo
permisos) y `custom_guardrails.json` (reglas de usuario) — y aplican en la siguiente
llamada del agente. El panel edita el YAML in situ (conservando comentarios) bajo
`guardrails.*` / `memory.*` / `embedder.*` / `retrieval.*`.

### Comandos slash

| Comando | Hace |
|---------|------|
| `/review` | Tría las lecciones que el agente aprendió y esperan aprobación humana. |
| `/learn <procedimiento>` | Captura manualmente un procedimiento en memoria. |

---

<div align="center">

**Built on 🤖 [Claude Code](https://claude.com/claude-code) · Powered by 🧠 [mem0](https://mem0.ai/) + [Qdrant](https://qdrant.tech/)**

</div>
=======

