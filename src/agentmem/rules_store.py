"""CustomRuleStore — persistence for user-defined destructive-command rules.

Single responsibility: own the JSON file that holds the *custom* blocklist patterns a
human added from the dashboard (the built-in patterns live in code, in
``guardrails._DESTRUCTIVE_PATTERNS``). The guardrail engine merges both at build time.

A rule is ``{key, reason, regex, enabled}``. ``regex`` is validated (compiled) on write
so a malformed pattern can never reach the live guard. The file is a plain JSON array,
created lazily; a missing/corrupt file reads as an empty list (fail-safe: no custom
rules rather than a crash).
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from pydantic import BaseModel, field_validator


class CustomRule(BaseModel):
    key: str
    reason: str
    regex: str
    enabled: bool = True

    @field_validator("regex")
    @classmethod
    def _valid_regex(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
        return v


def _new_key() -> str:
    return f"cust_{uuid.uuid4().hex[:8]}"


class CustomRuleStore:
    """CRUD over the custom-rules JSON file. All methods are synchronous + atomic-ish."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    # ---- read ---------------------------------------------------------- #
    def load(self) -> list[CustomRule]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        rules: list[CustomRule] = []
        for item in data if isinstance(data, list) else []:
            try:
                rules.append(CustomRule(**item))
            except Exception:
                continue  # skip a corrupt entry, keep the rest
        return rules

    # ---- write --------------------------------------------------------- #
    def _save(self, rules: list[CustomRule]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.model_dump() for r in rules]
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    def add(self, *, reason: str, regex: str, enabled: bool = True) -> CustomRule:
        reason = (reason or "").strip()
        regex = (regex or "").strip()
        if not reason or not regex:
            raise ValueError("both 'reason' and 'regex' are required")
        rule = CustomRule(key=_new_key(), reason=reason, regex=regex, enabled=enabled)
        rules = self.load()
        rules.append(rule)
        self._save(rules)
        return rule

    def set_enabled(self, key: str, enabled: bool) -> bool:
        rules = self.load()
        hit = False
        for r in rules:
            if r.key == key:
                r.enabled = enabled
                hit = True
        if hit:
            self._save(rules)
        return hit

    def delete(self, key: str) -> bool:
        rules = self.load()
        kept = [r for r in rules if r.key != key]
        if len(kept) == len(rules):
            return False
        self._save(kept)
        return True
