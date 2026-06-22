"""EnvFile — comment-preserving read/write of a KEY=VALUE config file (config.env).

Single responsibility: own the config.env file. Reading skips blanks/comments and
strips surrounding quotes; writing updates existing ``KEY=`` lines in place (comments
preserved) and appends unseen keys. Writes are atomic (temp file + rename).
"""

from __future__ import annotations

from pathlib import Path

from agentmem.atomicio import atomic_write_text


class EnvFile:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def read(self) -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError:
            return out
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
        return out

    def write(self, updates: dict[str, str]) -> None:
        """Update existing KEY= lines in place; append new keys. Comments preserved."""
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
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
        atomic_write_text(self._path, "\n".join(lines) + "\n")
