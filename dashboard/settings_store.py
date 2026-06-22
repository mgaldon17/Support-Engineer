"""SettingsStore — the harness permissions allowlist in ``.claude/settings.json``.

Single responsibility: own settings.json (read/write + the ``permissions.allow`` list).
A missing/corrupt file reads as an empty object; writes are atomic (temp file + rename).
"""

from __future__ import annotations

import json
from pathlib import Path

from agentmem.atomicio import atomic_write_text


class SettingsStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def write(self, data: dict) -> None:
        atomic_write_text(self._path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def allow_list(self) -> list[str]:
        return list(self.read().get("permissions", {}).get("allow", []))

    def set_allow_list(self, entries: list[str]) -> None:
        data = self.read()
        data.setdefault("permissions", {})["allow"] = entries
        self.write(data)
