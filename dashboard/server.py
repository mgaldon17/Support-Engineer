#!/usr/bin/env python3
"""Support Engineer — control panel backend (stdlib-only HTTP server).

Exposes the user-controllable surface of the agent so a level-3 engineer can inspect
and change it from a browser, with NO extra dependencies (offline, Python stdlib):

  * Guardrails    — master switches, the URL allowlist/probe, and the full destructive
                    blocklist (built-in patterns toggled on/off + custom rules the user
                    ADDS, edits and deletes here).
  * Commands      — allowed list (.claude/settings.json) ⇆ blocked list, move either way.
  * Lessons       — live counts and the pending-review queue (Approve / Reject).
  * Memory        — Qdrant / embedder / retrieval settings.

This module is the *transport + persistence* layer only: HTTP routing, reading/writing
``config.env`` (comment-preserving), ``.claude/settings.json`` (permissions.allow) and
delegating custom rules to ``agentmem.rules_store`` and lessons to ``agentmem.store``.
The UI lives in ``index.html`` + ``assets/`` (served statically).

Run:  python dashboard/server.py            # -> http://localhost:8787
      python dashboard/server.py --port 9000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from agentmem.config import Config, custom_rules_path, load as load_config  # noqa: E402
from agentmem import guardrails as gr  # noqa: E402
from agentmem.rules_store import CustomRuleStore  # noqa: E402

_CONFIG_FILE = Path(os.environ.get("AGENTMEM_CONFIG", _REPO_ROOT / "config.env"))
_SETTINGS_FILE = _REPO_ROOT / ".claude" / "settings.json"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2", ".map": "application/json",
}


# --------------------------------------------------------------------------- #
# config.env read / write (comment-preserving)
# --------------------------------------------------------------------------- #
def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        text = _CONFIG_FILE.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def _write_env(updates: dict[str, str]) -> None:
    """Update existing KEY= lines in place; append new keys. Comments preserved."""
    try:
        lines = _CONFIG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    seen: set[str] = set()
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.partition("=")[0].strip()
        if key in updates:
            lines[i] = f"{key}={updates[key]}"
            seen.add(key)
    extra = [f"{k}={v}" for k, v in updates.items() if k not in seen]
    if extra:
        lines += ["", "# --- added by control panel ---", *extra]
    _CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _disabled_set() -> set[str]:
    raw = _read_env().get("GUARD_DISABLED_PATTERNS", "")
    return {k.strip().lower() for k in raw.split(",") if k.strip()}


def _set_builtin_enabled(key: str, enabled: bool) -> None:
    disabled = _disabled_set()
    disabled.discard(key) if enabled else disabled.add(key)
    _write_env({"GUARD_DISABLED_PATTERNS": ",".join(sorted(disabled))})


# --------------------------------------------------------------------------- #
# settings.json permissions (allowed list)
# --------------------------------------------------------------------------- #
def _settings_read() -> dict:
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _settings_write(data: dict) -> None:
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")


def _allow_list() -> list[str]:
    return list(_settings_read().get("permissions", {}).get("allow", []))


def _set_allow_list(entries: list[str]) -> None:
    data = _settings_read()
    data.setdefault("permissions", {})["allow"] = entries
    _settings_write(data)


def _bash_inner(entry: str) -> str | None:
    m = re.fullmatch(r"Bash\((.*)\)", entry.strip())
    return m.group(1) if m else None


def _glob_to_regex(glob: str) -> str:
    """A shell-permission glob (`rm -rf *`) -> an anchored-ish regex for the blocklist."""
    return r"\b" + ".*".join(re.escape(p) for p in glob.split("*"))


# --------------------------------------------------------------------------- #
# rules (built-in + custom), merged for the UI
# --------------------------------------------------------------------------- #
def _store() -> CustomRuleStore:
    return CustomRuleStore(custom_rules_path(load_config()))


def _merged_patterns() -> list[dict]:
    disabled = _disabled_set()
    builtin = [
        {**p, "enabled": p["key"] not in disabled, "source": "builtin", "deletable": False}
        for p in gr.destructive_pattern_catalog()
    ]
    custom = [
        {"key": r.key, "reason": r.reason, "regex": r.regex,
         "enabled": r.enabled, "source": "custom", "deletable": True}
        for r in _store().load()
    ]
    return builtin + custom


# --------------------------------------------------------------------------- #
# lessons (live store) — degrades gracefully if Qdrant is down
# --------------------------------------------------------------------------- #
def _lessons_snapshot() -> dict:
    try:
        from agentmem.store import build_store

        lessons = asyncio.run(build_store(load_config()).list())
        items = [{
            "id": l.lesson_id, "title": l.title or "(sin título)", "content": l.content,
            "origin": str(l.origin), "reuse": l.reuse,
            "failure_count": l.failure_count, "pending_review": l.pending_review,
        } for l in lessons]
        pending = [i for i in items if i["pending_review"]]
        return {
            "ok": True, "total": len(items), "pending_count": len(pending),
            "approved_count": len(items) - len(pending),
            "items": sorted(items, key=lambda i: (not i["pending_review"], i["title"].lower())),
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "total": 0, "pending_count": 0, "approved_count": 0, "items": []}


def _lesson_action(action: str, lesson_id: str) -> dict:
    from agentmem.store import build_store

    store = build_store(load_config())
    if action == "resolve":
        return {"ok": asyncio.run(store.resolve(lesson_id)) is not None}
    if action == "delete":
        return {"ok": asyncio.run(store.delete(lesson_id))}
    return {"ok": False, "error": f"unknown action {action!r}"}


# --------------------------------------------------------------------------- #
# state + bulk config save
# --------------------------------------------------------------------------- #
def _state() -> dict:
    cfg = load_config()
    allow = _allow_list()
    return {
        "app": "Support Engineer",
        "config": {
            "guard_url_enabled": cfg.guard_url_enabled,
            "guard_destructive_enabled": cfg.guard_destructive_enabled,
            "guard_check_reachable": cfg.guard_check_reachable,
            "guard_allow_domains": ", ".join(cfg.guard_allow_domains),
            "probe_timeout": cfg.probe_timeout,
            "probe_user_agent": cfg.probe_user_agent,
            "qdrant_host": cfg.qdrant_host, "qdrant_port": cfg.qdrant_port,
            "collection": cfg.collection, "mem_user": cfg.mem_user,
            "embedder_provider": cfg.embedder_provider, "embedder_model": cfg.embedder_model,
            "embedder_base_url": cfg.embedder_base_url, "embedder_dims": cfg.embedder_dims,
            "lesson_search_limit": cfg.lesson_search_limit,
            "lesson_list_limit": cfg.lesson_list_limit,
        },
        "patterns": _merged_patterns(),
        "policed_tools": gr.policed_tools(),
        "permissions": [{"entry": e, "bash": _bash_inner(e) is not None} for e in allow],
        "config_file": str(_CONFIG_FILE),
        "lessons": _lessons_snapshot(),
    }


_BOOL_FIELDS = {
    "guard_url_enabled": "GUARD_URL_ENABLED",
    "guard_destructive_enabled": "GUARD_DESTRUCTIVE_ENABLED",
    "guard_check_reachable": "GUARD_CHECK_REACHABLE",
}
_SCALAR_FIELDS = {
    "guard_allow_domains": "GUARD_ALLOW_DOMAINS", "probe_timeout": "PROBE_TIMEOUT",
    "probe_user_agent": "PROBE_USER_AGENT", "qdrant_host": "QDRANT_HOST",
    "qdrant_port": "QDRANT_PORT", "collection": "MEM_COLLECTION", "mem_user": "MEM_USER",
    "embedder_provider": "EMBEDDER_PROVIDER", "embedder_model": "EMBEDDER_MODEL",
    "embedder_base_url": "EMBEDDER_BASE_URL", "embedder_dims": "EMBEDDER_DIMS",
    "lesson_search_limit": "LESSON_SEARCH_LIMIT", "lesson_list_limit": "LESSON_LIST_LIMIT",
}


def _save(payload: dict) -> dict:
    updates: dict[str, str] = {}
    for field, key in _BOOL_FIELDS.items():
        if field in payload:
            updates[key] = "true" if payload[field] else "false"
    for field, key in _SCALAR_FIELDS.items():
        if field in payload:
            updates[key] = str(payload[field]).strip()
    _write_env(updates)
    return {"ok": True, "written": updates}


# --------------------------------------------------------------------------- #
# command actions (the routes that mutate rules / allowlist)
# --------------------------------------------------------------------------- #
def _rule_add(payload: dict) -> dict:
    rule = _store().add(reason=payload.get("reason", ""), regex=payload.get("regex", ""))
    return {"ok": True, "rule": rule.model_dump()}


def _rule_toggle(payload: dict) -> dict:
    key, enabled, source = payload.get("key", ""), bool(payload.get("enabled")), payload.get("source")
    if source == "custom":
        return {"ok": _store().set_enabled(key, enabled)}
    _set_builtin_enabled(key, enabled)
    return {"ok": True}


def _rule_delete(payload: dict) -> dict:
    return {"ok": _store().delete(payload.get("key", ""))}


def _allowed_add(payload: dict) -> dict:
    entry = str(payload.get("entry", "")).strip()
    if not entry:
        return {"ok": False, "error": "empty entry"}
    allow = _allow_list()
    if entry not in allow:
        allow.append(entry)
        _set_allow_list(allow)
    return {"ok": True}


def _allowed_remove(payload: dict) -> dict:
    entry = str(payload.get("entry", "")).strip()
    _set_allow_list([e for e in _allow_list() if e != entry])
    return {"ok": True}


def _allowed_to_blocked(payload: dict) -> dict:
    """Move an allowed Bash command into the blocklist as a custom rule."""
    entry = str(payload.get("entry", "")).strip()
    inner = _bash_inner(entry)
    if inner is None:
        return {"ok": False, "error": "only Bash(...) permissions can become a blocked command"}
    rule = _store().add(reason=f"moved from allowlist: {inner}", regex=_glob_to_regex(inner))
    _set_allow_list([e for e in _allow_list() if e != entry])
    return {"ok": True, "rule": rule.model_dump()}


def _blocked_to_allowed(payload: dict) -> dict:
    """Move a CUSTOM blocked rule back to the allowlist (best-effort) and delete it."""
    key = str(payload.get("key", "")).strip()
    rule = next((r for r in _store().load() if r.key == key), None)
    if rule is None:
        return {"ok": False, "error": "custom rule not found"}
    inner = re.sub(r"\\(.)", r"\1", rule.regex.replace(r"\b", "").replace(".*", "*"))
    allow = _allow_list()
    candidate = f"Bash({inner})"
    if candidate not in allow:
        allow.append(candidate)
        _set_allow_list(allow)
    _store().delete(key)
    return {"ok": True, "entry": candidate}


_POST_ROUTES = {
    "/api/save": _save,
    "/api/lesson": lambda p: _lesson_action(p.get("action", ""), p.get("id", "")),
    "/api/rules/add": _rule_add,
    "/api/rules/toggle": _rule_toggle,
    "/api/rules/delete": _rule_delete,
    "/api/allowed/add": _allowed_add,
    "/api/allowed/remove": _allowed_remove,
    "/api/allowed/to-blocked": _allowed_to_blocked,
    "/api/blocked/to-allowed": _blocked_to_allowed,
}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _serve_file(self, rel: str) -> None:
        target = (_HERE / rel.lstrip("/")).resolve()
        if _HERE not in target.parents and target != _HERE / rel.lstrip("/"):
            return self._json({"error": "forbidden"}, 403)
        try:
            ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            self._send(200, target.read_bytes(), ctype)
        except OSError:
            self._json({"error": "not found"}, 404)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif self.path == "/api/state":
            self._json(_state())
        elif self.path.startswith("/assets/"):
            self._serve_file(self.path)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        handler = _POST_ROUTES.get(self.path)
        if handler is None:
            return self._json({"error": "not found"}, 404)
        try:
            self._json(handler(self._body()))
        except ValueError as exc:           # validation errors -> 400 with message
            self._json({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 500)


def main() -> None:
    ap = argparse.ArgumentParser(description="Support Engineer control panel")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Support Engineer · control panel → http://{args.host}:{args.port}")
    print(f"  config: {_CONFIG_FILE}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
