# SOLID Audit Report — 2026-06-22

## Language(s): Python (12 files, primary), JavaScript (7 files, ES modules)
## Project type: Local agent-memory toolkit + stdlib HTTP control-panel dashboard
  - `src/agentmem/` — library: lesson store (mem0/Qdrant), guardrails, config, MCP server
  - `dashboard/` — stdlib HTTP server (`server.py`) + vanilla-JS SPA (`assets/js/`)
  - `hooks/` — Claude Code `PreToolUse` / `UserPromptSubmit` hooks

## Summary
| Severity | Count |
|----------|-------|
| CRITICAL | 2     |
| HIGH     | 3     |
| MEDIUM   | 5     |
| LOW      | 3     |

---

## Findings

### [CRITICAL] Dashboard never reflects config edits it writes (stale `os.environ`)
- **File**: src/agentmem/config.py:45 (root cause) · dashboard/server.py:198,239-248 (impact)
- **Principle**: Bug
- **Snippet**:
  ```python
  # config.py — _load_env_file
  if key:
      os.environ.setdefault(key, value)   # never overrides an already-set var
  ...
  # config.py — load()
  def load() -> Config:
      _load_env_file(...)        # setdefault: first request wins forever
      return Config.from_env()   # reads os.environ
  ```
- **Description**: The dashboard server is a long-running process. On the first request, `_load_env_file` copies `config.env` into `os.environ` with `setdefault`. When the user later saves a change, `_write_env` rewrites the **file**, but `os.environ` still holds the original value. The next `load_config()` call (e.g. from `_state()` building `/api/state`) runs `setdefault` again, which is a no-op because the key already exists — so `Config.from_env()` returns the **old** value. Result: the user edits a field, sees "Guardado", and the panel reverts to the stale value. This breaks the read-after-write contract that is the dashboard's entire purpose. (Note: the actual guardrail *behaviour* is unaffected because the hook runs in a fresh process each time and reads the file cleanly — only the long-lived dashboard is stale. Built-in pattern toggles happen to work because `_disabled_set()` reads the file directly, making the bug inconsistent and confusing.)
- **Fix sketch**: In `_save`/`_write_env`, after writing the file also update `os.environ` for the changed keys (`os.environ[key] = value`). Better: change `load()` to read the file directly into a `Config` (don't round-trip through `os.environ` with `setdefault`), or have `_load_env_file` accept an `override=True` mode for the server. The cleanest fix is for the dashboard to read config straight from the file (it already has `_read_env()`), not via the env-precedence `load_config()`.

### [CRITICAL] Force-push guardrail bypassed by the common `-f` short flag
- **File**: src/agentmem/guardrails.py:156-161
- **Principle**: Bug
- **Snippet**:
  ```python
  ("force_push_main",
   re.compile(r"\bgit\s+push\b[^\n]*--force[^\n]*\b(origin\s+)?(main|master)\b"),
   "force-push to main/master (--force before branch)"),
  ("force_push_main_alt",
   re.compile(r"\bgit\s+push\b[^\n]*\b(main|master)\b[^\n]*--force"),
   "force-push to main/master (--force after branch)"),
  ```
- **Description**: Both patterns require the literal long flag `--force`. The everyday short form `git push -f origin main` (and `-fu`, `--force-with-lease` spelled differently, etc.) is **not** matched, so the guardrail silently allows exactly the destructive operation it claims to block. A protection that misses the most common spelling of the attack is worse than none, because it creates false confidence.
- **Fix sketch**: Broaden the flag alternation to `(--force(-with-lease)?|-\w*f\w*)` so both `-f` and bundled short flags (`-fu`) are caught, e.g. `\bgit\s+push\b[^\n]*(--force\S*|\s-\w*f\w*)[^\n]*\b(origin\s+)?(main|master)\b` plus the mirrored alt. Add `git push -f origin main` to the parametrized veto test in `tests/test_guardrails.py`.

---

### [HIGH] Unsynchronised read-modify-write on shared files under a threaded server
- **File**: dashboard/server.py:71-89 (`_write_env`), 113-125 (`_settings_write`/`_set_allow_list`), 391 (`ThreadingHTTPServer`) · src/agentmem/rules_store.py:64-78
- **Principle**: Bug (mutable shared state without synchronisation)
- **Snippet**:
  ```python
  srv = ThreadingHTTPServer((args.host, args.port), Handler)  # concurrent threads
  ...
  def _set_allow_list(entries):
      data = _settings_read()                  # read
      data.setdefault("permissions", {})["allow"] = entries
      _settings_write(data)                    # write — no lock between
  ```
- **Description**: `ThreadingHTTPServer` serves each request on its own thread. `config.env`, `.claude/settings.json` and `custom_guardrails.json` are all mutated via read → modify → write with no locking. A browser routinely fires parallel requests (e.g. toggling several rules, or a save coinciding with a state refresh), so two writers can interleave and one update silently clobbers the other, or a reader can observe a half-written file. This is a classic lost-update / torn-write bug.
- **Fix sketch**: Guard every file mutation with a single module-level `threading.Lock()` held across the read-modify-write (one lock is fine given low traffic), and write atomically (write to a temp file in the same dir, then `os.replace`). `CustomRuleStore._save` should also write-temp-then-replace.

### [HIGH] `dashboard/server.py` concentrates too many responsibilities (SRP)
- **File**: dashboard/server.py (whole module, 401 lines)
- **Principle**: SRP
- **Snippet**:
  ```python
  def _read_env() / _write_env()            # config.env persistence
  def _settings_read() / _set_allow_list()  # settings.json persistence
  def _glob_to_regex() / _bash_inner()      # glob<->regex translation
  def _lessons_snapshot() / _lesson_action()# lesson store orchestration
  class Handler(BaseHTTPRequestHandler)     # HTTP routing + static file serving
  ```
- **Description**: One module owns: comment-preserving env-file persistence, JSON settings persistence, regex/glob translation, custom-rule merging, lesson-store orchestration, bulk config validation, HTTP transport, and static-file serving. Each is a separate reason to change; a tweak to the allowlist format and a change to the HTTP layer both edit this one file. It is also hard to unit-test the persistence logic without standing up the HTTP server.
- **Fix sketch**: Extract the persistence concerns into small modules mirroring the library style: an `EnvFile` class (read/write/update), a `SettingsFile` class (allow-list CRUD), and a `Translation` helper (`glob_to_regex`/`regex_to_glob`/`bash_inner`). Leave `server.py` as thin routing that delegates. The `_POST_ROUTES` dict is already a good seam — route handlers should call injected services instead of module-level functions.

### [HIGH] No `LessonStore` abstraction — consumers bind to the concrete `Mem0LessonStore` (DIP)
- **File**: src/agentmem/store.py:56,145 · src/agentmem/mcp_server.py:36-39 · dashboard/server.py:162-191 · hooks/inject_lessons.py:27-30
- **Principle**: DIP
- **Snippet**:
  ```python
  # three independent high-level consumers all reach for the concrete class/factory:
  return build_store(load())                 # mcp_server._store
  lessons = asyncio.run(build_store(load_config()).list())   # server._lessons_snapshot
  store = build_store(cfg)                    # inject_lessons._recall
  ```
- **Description**: The module docstrings reference an `agentcore` *port* (interface), but no `LessonStore` Protocol/ABC exists here. The MCP server, the dashboard, and the prompt hook each depend directly on the concrete `Mem0LessonStore` via `build_store`, which hard-binds them to mem0 + Qdrant. Swapping the backend (e.g. an in-memory store for tests, or a different vector DB) means editing every call site, and unit-testing the dashboard's lesson endpoints requires monkeypatching the concrete class.
- **Fix sketch**: Define a `LessonStore` Protocol (the async methods `add/get/update/delete/search/list/reinforce/record_failure/resolve`) and type all consumers against it. `build_store` stays the single composition point that returns a concrete `Mem0LessonStore`. Tests then pass a trivial fake implementing the Protocol.

---

### [MEDIUM] Dashboard rebuilds the mem0 store (and reloads the embedder) on every `/api/state`
- **File**: dashboard/server.py:162-166
- **Principle**: Bug (performance) / DIP
- **Snippet**:
  ```python
  def _lessons_snapshot() -> dict:
      try:
          from agentmem.store import build_store
          lessons = asyncio.run(build_store(load_config()).list())
  ```
- **Description**: Every `/api/state` request (page load **and** every action's refresh) calls `build_store`, which constructs a fresh `mem0.Memory` — re-initialising the Qdrant client and re-loading the sentence-transformers embedder model. That is expensive and pointless per-request work; the MCP server already learned this lesson and caches via `@lru_cache(maxsize=1)`. The dashboard does not.
- **Fix sketch**: Cache the store the same way the MCP server does (`@lru_cache` on a `_store()` helper, or a module-level lazily-initialised singleton), invalidating only if memory config fields change.

### [MEDIUM] `host_shutdown` pattern over-blocks ordinary text
- **File**: src/agentmem/guardrails.py:163
- **Principle**: Bug (false positives)
- **Snippet**:
  ```python
  ("host_shutdown", re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b"),
   "host shutdown/reboot"),
  ```
- **Description**: The alternation matches the bare words anywhere in the command, with no requirement that they be the executed program. Innocuous commands are vetoed: `git commit -m "reboot the retry logic"`, `echo "graceful shutdown"`, `grep halt log.txt`, `kubectl delete pod reboot-x`. Over-blocking trains users to disable the guardrail, defeating its purpose.
- **Fix sketch**: Anchor to a command position — require the keyword at the start of a command or after a `;`/`&&`/`|`/`sudo`, e.g. `(?:^|[;&|]\s*|\bsudo\s+)(shutdown|reboot|halt|poweroff)\b`. Keep it narrow like the other patterns.

### [MEDIUM] Front-end has no error handling on state fetch (unhandled rejection)
- **File**: dashboard/assets/js/app.js:86-95 · dashboard/assets/js/api.js:14-15
- **Principle**: Bug
- **Snippet**:
  ```js
  async function refresh() {
    state = await Api.getState();   // no try/catch; rejects if server down
    h('#cfgfile').textContent = state.config_file;  // throws if state undefined
    ...
  }
  // api.js
  getState: () => fetch('/api/state').then((r) => r.json()),  // ignores r.ok
  ```
- **Description**: `Api.getState` neither checks `res.ok` nor handles a network failure, and `refresh()` has no `try/catch`. If the server is down or returns a non-JSON error, the promise rejects, the UI is left half-rendered, and the only signal is an uncaught error in the console. The initial `refresh()` at module load has the same exposure.
- **Fix sketch**: Wrap `refresh()` in `try/catch` and `toast()` the failure; in `post`/`getState`, check `res.ok` and throw a typed error with the status so the caller can surface it. Render an inline "panel offline" state instead of a blank screen.

### [MEDIUM] Static-file path-traversal guard is convoluted and fragile
- **File**: dashboard/server.py:345-353
- **Principle**: Bug (security hardening)
- **Snippet**:
  ```python
  target = (_HERE / rel.lstrip("/")).resolve()
  if _HERE not in target.parents and target != _HERE / rel.lstrip("/"):
      return self._json({"error": "forbidden"}, 403)
  ```
- **Description**: The guard compares a `.resolve()`-d path against a **non-resolved** `Path`, and the two-clause `and` makes the intent unclear. It happens to block `../` traversal today (because a legit file always has `_HERE` in `target.parents`), but the second clause is effectively dead and the check would not survive a symlink inside `assets/` (resolve escapes `_HERE`, and the unresolved comparison can't help). It is one refactor away from a real traversal hole.
- **Fix sketch**: Use a single, well-known containment check: `target = (_HERE / rel.lstrip("/")).resolve()`; then `if not target.is_relative_to(_HERE): return 403` (Python 3.9+ `Path.is_relative_to`). That is exact, symlink-safe after `resolve()`, and self-documenting.

### [MEDIUM] Destructive blocklist is a hardcoded in-code list (OCP — partial)
- **File**: src/agentmem/guardrails.py:148-164
- **Principle**: OCP
- **Snippet**:
  ```python
  _DESTRUCTIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
      ("rm_root_home", re.compile(...), "..."),
      ("mkfs", re.compile(...), "..."),
      ... # adding a built-in pattern means editing this module
  ]
  ```
- **Description**: Adding a new *built-in* dangerous pattern requires editing this literal list and shipping code. Mitigated by the `CustomRuleStore` extension mechanism (users add rules without code changes), so this is only a partial OCP smell — but the built-in set is closed for extension. Acceptable at current scale; flagged so it is a conscious choice.
- **Fix sketch**: Optionally move the built-in catalogue to a shipped data file (JSON) loaded the same way custom rules are, so built-in and custom rules share one extension path. Low priority given the existing custom-rule seam.

---

### [LOW] Dead ternary — both branches identical
- **File**: dashboard/assets/js/views/settings.js:39
- **Principle**: Bug (smell)
- **Snippet**:
  ```js
  <span class="chip">${c.qdrant_host ? 'config.env' : 'config.env'}</span>
  ```
- **Description**: The conditional expression returns the same string `'config.env'` in both branches — a copy-paste leftover that computes nothing and misleads the reader into thinking the label is dynamic.
- **Fix sketch**: Replace with the literal `config.env`.

### [LOW] `Mem0LessonStore.update` passes metadata positionally
- **File**: src/agentmem/store.py:75-78
- **Principle**: Bug (uncertain — depends on mem0 version)
- **Snippet**:
  ```python
  await asyncio.to_thread(
      self._mem.update, lesson.lesson_id, lesson.content, _metadata(lesson)
  )
  ```
- **Description**: `mem0.Memory.update` is commonly `update(memory_id, data=...)` and does not always accept a third positional metadata argument; passing `_metadata(lesson)` positionally may raise a `TypeError` or be silently ignored depending on the installed `mem0ai` version, in which case `reinforce`/`record_failure`/`resolve` would not persist the counter/flag change. Could not verify against the pinned version offline.
- **Fix sketch**: Confirm the installed `mem0ai` signature; pass metadata via its documented keyword (e.g. `metadata=...`) or fold it into the `data` payload. Add a round-trip test (`update` then `get`) once a backend is available.

### [LOW] Docstring typo in lesson entity
- **File**: src/agentmem/lesson.py:8
- **Principle**: Bug (cosmetic)
- **Snippet**:
  ```python
  # "... Origin tells ``learned`` Ha(derived by the agent ..."
  ```
- **Description**: Stray `Ha(` fragment in the module docstring — a typo that reads as corruption.
- **Fix sketch**: Remove `Ha(` so it reads "tells ``learned`` (derived by the agent…".

---

## Fix Log — 2026-06-22

| File | Change | Principle |
|------|--------|-----------|
| `src/agentmem/guardrails.py` | Force-push regex now catches `-f`/`--force-with-lease`/bundled short flags (was `--force`-only) | Bug (CRITICAL) |
| `dashboard/server.py` | `_write_env` syncs `os.environ` after writing so saved config is reflected without restart | Bug (CRITICAL) |
| `src/agentmem/atomicio.py` *(new)* | `atomic_write_text` (temp file + `os.replace`) for torn-write-free saves | Bug (HIGH, concurrency) |
| `src/agentmem/rules_store.py` | `_save` uses atomic write | Bug (HIGH, concurrency) |
| `dashboard/server.py` | Module-level `_WRITE_LOCK` serialises all mutating POST handlers | Bug (HIGH, concurrency) |
| `dashboard/envfile.py` *(new)* | Extracted `EnvFile` (config.env read/write) | SRP (HIGH) |
| `dashboard/settings_store.py` *(new)* | Extracted `SettingsStore` (settings.json allowlist) | SRP (HIGH) |
| `dashboard/translation.py` *(new)* | Extracted glob↔regex helpers (`bash_inner`/`glob_to_regex`/`regex_to_glob`) | SRP (HIGH) |
| `dashboard/server.py` | Reduced to a thin HTTP coordinator delegating to the above | SRP (HIGH) |
| `src/agentmem/ports.py` *(new)* | `LessonStore` Protocol abstraction | DIP (HIGH) |
| `src/agentmem/store.py` | `build_store` returns `LessonStore`; consumers depend on the Protocol | DIP (HIGH) |
| `src/agentmem/mcp_server.py` | `_store()` typed to `LessonStore`, concrete import dropped | DIP (HIGH) |
| `dashboard/server.py` | Lesson store cached by memory-config tuple (was rebuilt per `/api/state`) | Bug (MEDIUM, perf) |
| `src/agentmem/guardrails.py` | `host_shutdown` anchored to a command position (no more text false-positives) | Bug (MEDIUM) |
| `dashboard/assets/js/api.js` | `asJson` checks `res.ok`, throws on non-2xx | Bug (MEDIUM) |
| `dashboard/assets/js/app.js` | `refresh()` try/catch + `run()` error runner around actions | Bug (MEDIUM) |
| `dashboard/server.py` | `_serve_file` uses `Path.is_relative_to` (symlink-safe containment) | Bug (MEDIUM, security) |
| `dashboard/assets/js/views/settings.js` | Removed dead ternary (`config.env` both branches) | LOW |
| `src/agentmem/store.py` | `update` passes `metadata=` as keyword | LOW |
| `src/agentmem/lesson.py` | Fixed `Ha(` docstring typo | LOW |
| `tests/test_guardrails.py` | Added force-push `-f` veto cases + `host_shutdown` false-positive cases | test |

### Left unfixed (by design)
- **MEDIUM — OCP, hardcoded built-in destructive blocklist** (`guardrails.py:_DESTRUCTIVE_PATTERNS`): not externalized. Moving a safety-critical blocklist into a mutable JSON data file would make the built-in guards fail **open** if that file is missing/corrupt — a net safety regression. The existing custom-rule store already provides a no-code extension path, so the part that should be open for extension already is. Documented as a conscious trade-off.

### Verification
- Tests: **22 passing** (was 18; +4 new guardrail cases), no regressions.
- Smoke test: server boots; `/api/state` serves; `/api/save` → read-back reflects the new value (CRITICAL #1 confirmed); path-traversal `…/../../etc/passwd` → 403, legit asset → 200 (MEDIUM #9 confirmed); lesson store degrades gracefully when Qdrant is down.
- JS: `node --check` passes on all changed files.
