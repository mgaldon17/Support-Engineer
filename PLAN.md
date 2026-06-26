# Plan: Reimplementar `agentcore` como agente Claude Code (Markdown + código solo para hooks, guardarraíles y DB)

## Context

`agentcore` (repo `AgentScalator`) es una app Python que **reimplementa a mano** lo que Claude Code
ya ofrece de serie: un bucle de tool-calling, subagentes, soporte MCP, y un sistema de prompts por
rol (triaje, objetivo, juez, actor, verificador). Esa reimplementación existe porque el runtime
es un LLM local pequeño (qwen 7B/14B/VL) sin orquestador propio — y de ahí vienen los problemas
observados (alucinación de URLs, bucles, plumbing de visión para screenshots).

El objetivo de **este repo (`Support Engineer`)** es invertir eso: **usar Claude Code como
runtime** y expresar toda la orquestación en archivos `.md`/config (CLAUDE.md, subagentes, skills,
slash-commands, hooks, `.mcp.json`). Así, el bucle, el razonamiento y la visión los aporta Claude
nativamente, y el **único código real** se concentra donde Claude Code no llega:

1. **DB** — memoria de lecciones en **el mismo Qdrant en Docker** que ahora (mem0 + colección
   `agentcore_lessons`), expuesta como **servidor MCP** + importable por los hooks.
2. **Guardarraíles** — veto de URLs inventadas/no-resolubles y comandos destructivos.
3. **Hooks** — auto-inyección de lecciones relevantes y aplicación de los guardarraíles.

Decisiones que fijan la arquitectura:
- **Claude Code primario** (Copilot = cliente degradado: solo tools MCP, sin hooks).
- **Memoria híbrida**: servidor MCP (`lesson_*` tools) + hook `UserPromptSubmit` que auto-inyecta
  el top-K de lecciones relevantes.
- **Guardarraíles vía hooks `PreToolUse`** (cobertura total, incluido `Bash` nativo).
- **Sin web alguna** (el panel de revisión se sustituye por slash-commands).

Beneficios colaterales (gratis al cambiar de runtime): **la visión es nativa** (Claude lee los
screenshots de `pw_browser_take_screenshot` directamente → se elimina el plumbing VL/`images`); y
el **bucle/anti-oscilación/no-progreso** los gestiona Claude → desaparecen `max_cycles`,
`max_tool_steps`, `stall_patience`, etc.

> Rutas "← portar" hacen referencia al repo hermano `../AgentScalator` (alias `agentcore`).

## Mapeo agentcore → Claude Code

| Concepto agentcore | Primitiva Claude Code | ¿Código? |
|---|---|---|
| System prompts / flujo (`triage_incident.py`) | `CLAUDE.md` | No |
| Triaje: intent+objetivo+criterios (`prompts/objective.py`) | instrucciones en `CLAUDE.md` (o skill `triage`) | No |
| Recuperar lecciones (`store.search`) | MCP `lesson_search` + hook `UserPromptSubmit` | **Sí (DB+hook)** |
| Juez "¿una lección cubre esto?" (`prompts/judge.py`) | instrucciones en `CLAUDE.md` | No |
| Bucle agéntico (`agent_loop.py`) | bucle nativo de Claude | No |
| Verificador grounded (`prompts/verifier.py`) | subagente `verifier` | No |
| Guardarraíles (`url_guardrail.py`, `# GATE_TOOL_GUARDRAIL`) | hook `PreToolUse` → código guardrail | **Sí (hook+guard)** |
| Persistencia: reinforce/record_failure/learned/human_authored | MCP `lesson_*` + instrucciones en `CLAUDE.md` | **Sí (DB)** |
| Tools `pw` / `dc` | `.mcp.json` (mismos servidores MCP) | No (config) |
| Escalado / revisión humana (era web) | slash-command `/review` sobre `pending_review` | Mínimo |
| Knobs de config (`config.yaml`) | mayoría N/A (los aporta Claude); resto → env/config del código | Mínimo |

## El código a construir (el foco de esfuerzo)

Paquete Python `src/agentmem/` (reutiliza directamente la lógica de `../AgentScalator`):

### 1. DB layer — portar de `agentcore`
- `lesson.py` ← portar `agentcore/domain/lesson.py` + `LessonOrigin` de `enums.py`. Campos:
  `lesson_id, title, content, origin, reuse, failure_count, pending_review, created_at`; factorías
  `learned()` (pending_review=True) y `human_authored()` (False); `reinforce()`/`record_failure()`.
- `store.py` ← portar `agentcore/infrastructure/mem0_store.py` **tal cual** (mem0 `infer=False`,
  Qdrant host/port/collection, embedder OpenAI-compat). Métodos async: `add/get/update/delete/
  search/list/reinforce/record_failure` (reinforce y record_failure son read-modify-write vía
  `get→mutar→update`). `_metadata()` mapea title/origin/reuse/failure_count/pending_review.
- `config.py` — lee de **env vars** (no YAML): `QDRANT_HOST/PORT`, `MEM_COLLECTION`,
  `EMBEDDER_MODEL/BASE_URL/API_KEY`, `GUARD_ALLOW_DOMAINS`, `GUARD_CHECK_REACHABLE`,
  `LESSON_SEARCH_LIMIT` (def. 8). Defaults = los de `config.yaml` actual.

### 2. Servidor MCP de memoria — `mcp_server.py`
Servidor MCP stdio (SDK `mcp`, patrón de `agentcore/infrastructure/mcp_client.py` a la inversa)
que envuelve `store.py` y expone tools (funcionan en Claude Code **y** Copilot):
- `lesson_search(query, limit=8)` → lista {id, title, content, reuse, failure_count}.
- `lesson_add(title, content)` → crea `learned` (pending_review).
- `lesson_inject(title, content)` → crea `human_authored` (sustituye `scripts/seed_lessons.py`).
- `lesson_reinforce(lesson_id)` / `lesson_record_failure(lesson_id)`.
- `lesson_list(pending_review?)` / `lesson_resolve(lesson_id)` (flip pending_review) / `lesson_delete(lesson_id)`.

### 3. Guardarraíles — `guardrails.py`
- Portar `agentcore/infrastructure/url_guardrail.py`: validación sintáctica http(s), allowlist de
  dominios, y probe de alcanzabilidad (`_http_probe`: veta 404/410 y fallo DNS; no sobre-bloquea
  timeouts/TLS). Reutilizar `GuardrailDecision(allow, reason)`.
- **Nuevo guard de comandos destructivos** (cubre el `# GATE_TOOL_GUARDRAIL` que estaba vacío):
  blocklist de patrones (`rm -rf /`, `mkfs`, `dd of=/dev/...`, `:(){ :|: };:`, `git push --force`
  a main, etc.) sobre `Bash` y `dc_start_process`/`command`.
- Función `check(tool_name, args) -> GuardrailDecision` que el hook invoca.

### 4. Hooks — `hooks/`
- `inject_lessons.py` (evento **`UserPromptSubmit`**): lee el prompt de stdin (JSON), llama a
  `store.search(prompt, limit=K)` **importando `agentmem` directamente** (sin pasar por MCP),
  e imprime las lecciones top como contexto adicional (stdout / `additionalContext`). Es la mitad
  "auto" del modo híbrido.
- `guardrail_check.py` (evento **`PreToolUse`**, matcher sobre `mcp__pw__browser_navigate`,
  `Bash`, `mcp__dc__*`): lee el tool-input de stdin, llama a `guardrails.check(...)`, y deniega con
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":<reason>}}`
  (o exit code 2 + stderr) cuando hay veto.

## Los archivos Markdown/config (orquestación, esfuerzo bajo)

- **`CLAUDE.md`** — el "system prompt" + flujo, portando los textos de `prompts/*.py`:
  1. Derivar **intent (info/action) + objetivo + criterios observables** (texto de `objective.py`).
  2. Recuperar memoria: confiar en la auto-inyección del hook y/o llamar `lesson_search`; **juez**
     por significado, no literal (texto de `judge.py`).
  3. Si una lección cubre la tarea, **seguirla**; si no, resolver de cero. Reglas de navegación web
     (URL_RULE de `agent_step.py`: no inventar URLs, buscar en Google, leer con
     `pw_browser_evaluate`, aceptar cookies, screenshot si hace falta — Claude lo ve nativo).
  4. Para **ACTION**, invocar el subagente `verifier`; para INFO, responder con lo reunido.
  5. Persistencia (vía tools MCP): lección reutilizada que funcionó → `lesson_reinforce`; que falló
     → `lesson_record_failure`; camino nuevo verificado → `lesson_add` (learned).
- **`.claude/agents/verifier.md`** — subagente verificador grounded (textos de `verifier.py`):
  diseña checks **read-only**, los ejecuta con las tools, y compara observado-vs-criterios →
  veredicto graduado (criterios cumplidos + confianza ≥0.6 ≈ pass). Skip de probes en INFO.
- **`.mcp.json`** — tres servidores: `pw` (`npx @playwright/mcp@latest`, mismos `include`), `dc`
  (Desktop Commander, mismos `include`) y `memory` (`python -m agentmem.mcp_server`).
- **`.claude/settings.json`** — hooks (`UserPromptSubmit` → `inject_lessons.py`; `PreToolUse` →
  `guardrail_check.py`) + permissions (allowlist de las tools MCP y Bash de lectura).
- **`.claude/commands/`** — `/review` (lista/aprueba/borra `pending_review` vía tools MCP, sustituye
  el panel web), `/learn` (captura manual de procedimiento → `lesson_add`).
- **`docker-compose.yml`** — Qdrant idéntico al actual (volumen persistente).
- **`pyproject.toml`** — deps: `mem0ai>=0.1`, `qdrant-client`, `mcp`, `httpx`.

## Estructura del repo

```
support-engineer/
├── CLAUDE.md
├── PLAN.md                      # este documento
├── .mcp.json
├── docker-compose.yml          # Qdrant (igual que ahora)
├── pyproject.toml
├── .claude/
│   ├── settings.json           # hooks + permissions
│   ├── agents/verifier.md
│   └── commands/{review.md,learn.md}
├── src/agentmem/
│   ├── lesson.py               # ← portar domain/lesson.py + enums
│   ├── store.py                # ← portar infrastructure/mem0_store.py
│   ├── config.py               # env vars (defaults de config.yaml)
│   ├── guardrails.py           # ← portar url_guardrail.py + guard destructivo
│   └── mcp_server.py           # servidor MCP de lesson_* tools
└── hooks/
    ├── inject_lessons.py       # UserPromptSubmit
    └── guardrail_check.py      # PreToolUse
```

## Qué se elimina a propósito

- **Toda la web** (`agentcore/web/`, endpoints FastAPI) → fuera; revisión vía `/review`.
- **Plumbing de visión** (`ToolResult.images`, multimodal en prompts, rol VL) → Claude es
  multimodal nativo; los screenshots MCP llegan solos.
- **Bucle Python** (`agent_loop.py`) y knobs asociados (`max_cycles`, `max_tool_steps`,
  `no_progress_patience`, `stall_patience`) → bucle nativo de Claude.
- **Providers LLM locales + ModelSwapCoordinator** → el modelo es Claude.
- **FastAPI/uvicorn, review_queue, DTOs** → innecesarios sin web ni API HTTP.

## Verificación (end-to-end)

1. **Infra**: `docker compose up -d` → Qdrant en `localhost:6333`.
2. **DB/guardrails (unit)**: tests portando los del repo actual — `store` contra una colección de
   test (add→search→reinforce→get confirma `reuse++`; record_failure; learned vs human_authored);
   `guardrails` (URL inválida/404/dominio no permitido → deny; comando destructivo → deny).
3. **MCP server aislado**: lanzar `python -m agentmem.mcp_server`, `list_tools`, y probar
   `lesson_inject`/`lesson_search` (verificar persistencia reiniciando Qdrant).
4. **En Claude Code**:
   - Hacer una pregunta → confirmar que `UserPromptSubmit` inyecta lecciones relevantes.
   - Intentar navegar a una URL inventada → `PreToolUse` la **veta** con el motivo; idem un
     `rm -rf` en Bash.
   - Tarea de ACTION → el subagente `verifier` corre checks read-only y emite veredicto.
   - Tras resolver algo nuevo → el modelo llama `lesson_add`; reiniciar sesión y confirmar que
     `lesson_search` la recupera (persistió en Qdrant).
   - `lesson_inject` de la **lección de navegación** (la de `scripts/seed_lessons.py`).
5. **Copilot (degradado)**: confirmar que las tools `lesson_*` y `pw_*`/`dc_*` funcionan (sin
   hooks: sin auto-inyección ni guardarraíles — esperado).

## Punteros de reutilización (`../AgentScalator` → este repo)

- `agentcore/infrastructure/mem0_store.py` → `src/agentmem/store.py`
- `agentcore/domain/lesson.py` + `agentcore/domain/enums.py` (LessonOrigin) → `src/agentmem/lesson.py`
- `agentcore/infrastructure/url_guardrail.py` + `ports/guardrail.py` → `src/agentmem/guardrails.py`
- `agentcore/application/prompts/objective.py`, `judge.py`, `agent_step.py` → texto de `CLAUDE.md`
- `agentcore/application/prompts/verifier.py` → `.claude/agents/verifier.md`
- `agentcore/config.yaml` (`memory.*`, `tools.mcp_servers`, `guardrails`) → `config.py` env + `.mcp.json`
- `scripts/seed_lessons.py` → tool MCP `lesson_inject`
- `docker-compose.yml` → copiar tal cual
