"""Dashboard tests — the persistence/translation units extracted from server.py, plus
the server route handlers that mutate config / permissions / custom rules.

All offline: importing ``server`` pulls only agentmem.{config,guardrails,rules_store}
(pydantic), never mem0/qdrant, so no Qdrant is needed. Handlers are redirected to temp
files via the ``temp_server`` fixture so the real repo config is never touched.

``dashboard/`` and ``src/`` are on the pytest path (see [tool.pytest.ini_options]).
"""

from __future__ import annotations

import json
import os
import re

import pytest

import server
import translation
from envfile import EnvFile
from settings_store import SettingsStore
from agentmem.atomicio import atomic_write_text
from agentmem.rules_store import CustomRuleStore


# --------------------------------------------------------------------------- #
# translation — pure glob <-> regex helpers
# --------------------------------------------------------------------------- #
def test_bash_inner_extracts_command():
    assert translation.bash_inner("Bash(npm test)") == "npm test"
    assert translation.bash_inner("  Bash(rm -rf *)  ") == "rm -rf *"


def test_bash_inner_rejects_non_bash():
    assert translation.bash_inner("mcp__pw__browser_click") is None
    assert translation.bash_inner("Read(*)") is None


def test_glob_to_regex_matches_the_command():
    rx = re.compile(translation.glob_to_regex("npm test*"))
    assert rx.search("npm test --watch")
    assert not rx.search("npm run build")


def test_glob_regex_roundtrip_recovers_the_glob():
    rx = translation.glob_to_regex("rm -rf *")
    assert translation.regex_to_glob(rx) == "rm -rf *"


# --------------------------------------------------------------------------- #
# EnvFile — comment-preserving, atomic config.env IO
# --------------------------------------------------------------------------- #
def test_envfile_write_then_read_roundtrip(tmp_path):
    env = EnvFile(tmp_path / "config.env")
    env.write({"QDRANT_HOST": "db", "QDRANT_PORT": "1234"})
    assert env.read() == {"QDRANT_HOST": "db", "QDRANT_PORT": "1234"}


def test_envfile_updates_in_place_and_preserves_comments(tmp_path):
    f = tmp_path / "config.env"
    f.write_text("# header\nQDRANT_HOST=old\n\n# section\nQDRANT_PORT=6333\n", encoding="utf-8")
    EnvFile(f).write({"QDRANT_HOST": "new"})
    text = f.read_text(encoding="utf-8")
    assert "# header" in text and "# section" in text          # comments preserved
    assert "QDRANT_HOST=new" in text and "QDRANT_HOST=old" not in text  # updated in place
    assert "QDRANT_PORT=6333" in text                          # untouched key kept


def test_envfile_appends_unknown_keys(tmp_path):
    f = tmp_path / "config.env"
    f.write_text("EXISTING=1\n", encoding="utf-8")
    EnvFile(f).write({"NEWKEY": "2"})
    d = EnvFile(f).read()
    assert d["EXISTING"] == "1" and d["NEWKEY"] == "2"


def test_envfile_strips_quotes_and_skips_comments_on_read(tmp_path):
    f = tmp_path / "config.env"
    f.write_text('# c\nA="quoted"\nB=plain\n', encoding="utf-8")
    assert EnvFile(f).read() == {"A": "quoted", "B": "plain"}


def test_envfile_missing_file_reads_empty(tmp_path):
    assert EnvFile(tmp_path / "nope.env").read() == {}


def test_envfile_write_is_atomic_no_tmp_leftover(tmp_path):
    EnvFile(tmp_path / "config.env").write({"A": "1"})
    assert [p.name for p in tmp_path.iterdir()] == ["config.env"]


# --------------------------------------------------------------------------- #
# SettingsStore — permissions allowlist in settings.json
# --------------------------------------------------------------------------- #
def test_settings_allow_list_roundtrip(tmp_path):
    s = SettingsStore(tmp_path / "settings.json")
    s.set_allow_list(["Bash(ls)", "Bash(npm test)"])
    assert s.allow_list() == ["Bash(ls)", "Bash(npm test)"]


def test_settings_preserves_other_keys(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"hooks": {"x": 1}, "permissions": {"allow": []}}), encoding="utf-8")
    SettingsStore(f).set_allow_list(["Bash(ls)"])
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["hooks"] == {"x": 1}                       # untouched
    assert data["permissions"]["allow"] == ["Bash(ls)"]


def test_settings_missing_or_corrupt_reads_empty(tmp_path):
    assert SettingsStore(tmp_path / "nope.json").read() == {}
    assert SettingsStore(tmp_path / "nope.json").allow_list() == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert SettingsStore(bad).read() == {}


# --------------------------------------------------------------------------- #
# atomicio
# --------------------------------------------------------------------------- #
def test_atomic_write_overwrites_and_leaves_no_tmp(tmp_path):
    f = tmp_path / "x.txt"
    atomic_write_text(f, "one")
    atomic_write_text(f, "two")
    assert f.read_text(encoding="utf-8") == "two"
    assert [p.name for p in tmp_path.iterdir()] == ["x.txt"]


# --------------------------------------------------------------------------- #
# server route handlers — redirected to temp files
# --------------------------------------------------------------------------- #
@pytest.fixture
def temp_server(tmp_path, monkeypatch):
    cfg = tmp_path / "config.env"
    cfg.write_text("PROBE_TIMEOUT=5.0\n", encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {"allow": []}}) + "\n", encoding="utf-8")
    rules = tmp_path / "custom_guardrails.json"
    monkeypatch.setattr(server, "_ENV", EnvFile(cfg))
    monkeypatch.setattr(server, "_SETTINGS", SettingsStore(settings))
    monkeypatch.setattr(server, "_store", lambda: CustomRuleStore(rules))
    return {"cfg": cfg, "settings": settings, "rules": rules}


def test_save_writes_file_and_syncs_environ(temp_server, monkeypatch):
    monkeypatch.setenv("PROBE_TIMEOUT", "5.0")  # tracked by monkeypatch -> removed on teardown
    res = server._save({"probe_timeout": "9.5"})
    assert res["ok"] is True
    assert "PROBE_TIMEOUT=9.5" in temp_server["cfg"].read_text(encoding="utf-8")
    # Regression for the CRITICAL os.environ-staleness bug: the long-running process must
    # observe the new value immediately, not the value loaded once at startup.
    assert os.environ["PROBE_TIMEOUT"] == "9.5"


def test_save_serialises_bool_fields(temp_server):
    server._save({"guard_url_enabled": False, "guard_destructive_enabled": True})
    text = temp_server["cfg"].read_text(encoding="utf-8")
    assert "GUARD_URL_ENABLED=false" in text
    assert "GUARD_DESTRUCTIVE_ENABLED=true" in text


def test_allowed_add_is_idempotent_and_remove(temp_server):
    server._allowed_add({"entry": "Bash(ls)"})
    server._allowed_add({"entry": "Bash(ls)"})           # duplicate ignored
    assert server._allow_list() == ["Bash(ls)"]
    server._allowed_remove({"entry": "Bash(ls)"})
    assert server._allow_list() == []


def test_allowed_add_rejects_empty(temp_server):
    assert server._allowed_add({"entry": "  "})["ok"] is False


def test_allowed_to_blocked_moves_bash_entry(temp_server):
    server._allowed_add({"entry": "Bash(rm -rf *)"})
    res = server._allowed_to_blocked({"entry": "Bash(rm -rf *)"})
    assert res["ok"] is True
    assert server._allow_list() == []                    # removed from allowlist
    rules = CustomRuleStore(temp_server["rules"]).load()
    assert len(rules) == 1 and rules[0].enabled          # added as an enabled blocked rule


def test_allowed_to_blocked_rejects_non_bash(temp_server):
    assert server._allowed_to_blocked({"entry": "mcp__pw__browser_click"})["ok"] is False


def test_blocked_to_allowed_moves_custom_rule_back(temp_server):
    store = CustomRuleStore(temp_server["rules"])
    rule = store.add(reason="x", regex=translation.glob_to_regex("npm run build"))
    res = server._blocked_to_allowed({"key": rule.key})
    assert res["ok"] is True
    assert res["entry"] == "Bash(npm run build)"
    assert "Bash(npm run build)" in server._allow_list()
    assert CustomRuleStore(temp_server["rules"]).load() == []  # rule deleted


def test_blocked_to_allowed_unknown_key(temp_server):
    assert server._blocked_to_allowed({"key": "does-not-exist"})["ok"] is False


def test_rule_toggle_builtin_disables_via_env(temp_server):
    server._rule_toggle({"key": "mkfs", "enabled": False, "source": "builtin"})
    assert "mkfs" in server._disabled_set()
    server._rule_toggle({"key": "mkfs", "enabled": True, "source": "builtin"})
    assert "mkfs" not in server._disabled_set()
