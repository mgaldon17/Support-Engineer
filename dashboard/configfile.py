"""ConfigFile — comment-preserving read/write of the nested ``config.yaml``.

Single responsibility: own the config.yaml file for the control panel. The dashboard
thinks in FLAT ENV names (``QDRANT_HOST``, ``PROBE_TIMEOUT``, …); this class is the
adapter that maps those to the nested ``section.key`` layout via ``config._FIELD_MAP``
(the one source of truth shared with the loader). ``read()`` returns a flat
``{ENV_NAME: str}`` dict; ``write()`` takes the same shape, updating values IN PLACE so
the YAML's comments, ordering and untouched keys survive. Writes are atomic (temp file +
rename) and scalars are coerced to native YAML types (bool/int/float) for legibility.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from agentmem.atomicio import atomic_write_text
from agentmem.config import _FIELD_MAP, _flatten


def _coerce(value: str) -> object:
    """Render a flat string value as the native YAML scalar it represents, so the file
    reads cleanly (``probe_timeout: 5.0``, not ``"5.0"``). Non-numeric text (user agent,
    comma lists, empty) stays a string."""
    s = value.strip()
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return value


class ConfigFile:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._yaml = YAML()  # round-trip: preserves comments/order on load->dump
        self._yaml.preserve_quotes = True

    def _load_doc(self) -> CommentedMap:
        try:
            data = self._yaml.load(self._path.read_text(encoding="utf-8"))
        except OSError:
            data = None
        return data if isinstance(data, CommentedMap) else CommentedMap()

    def read(self) -> dict[str, str]:
        doc = self._load_doc()
        out: dict[str, str] = {}
        for env_name, (section, key) in _FIELD_MAP.items():
            sect = doc.get(section)
            if isinstance(sect, dict) and key in sect:
                out[env_name] = _flatten(sect[key]) or ""
        return out

    def write(self, updates: dict[str, str]) -> None:
        """Set each flat ENV value at its nested path, creating sections as needed, then
        dump preserving comments. Unknown keys (not in _FIELD_MAP) are stored flat at the
        top level so nothing is silently dropped."""
        doc = self._load_doc()
        for env_name, value in updates.items():
            coerced = _coerce(value)
            mapping = _FIELD_MAP.get(env_name)
            if mapping is None:
                doc[env_name] = coerced
                continue
            section, key = mapping
            sect = doc.get(section)
            if not isinstance(sect, CommentedMap):
                sect = CommentedMap()
                doc[section] = sect
            sect[key] = coerced
        buf = io.StringIO()
        self._yaml.dump(doc, buf)
        atomic_write_text(self._path, buf.getvalue())
