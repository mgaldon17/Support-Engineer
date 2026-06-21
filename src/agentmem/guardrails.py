"""Guardrails — a CODE policy layer that vetoes a tool call before it runs.

Two guards, both invoked from the ``PreToolUse`` hook (``hooks/guardrail_check.py``):

  1. UrlGuardrail (ported from ``agentcore/infrastructure/url_guardrail.py``) — for a
     tool call carrying a ``url`` argument: syntax (well-formed http(s)), allowlist
     (host must be on it, if configured) and reachability (probe; veto a clear DNS
     failure or 404/410). Reachability is fail-OPEN on ambiguous errors (timeouts,
     TLS, sites blocking probes) so real pages are not wrongly blocked.
  2. DestructiveCommandGuardrail (NEW — fills the empty ``# GATE_TOOL_GUARDRAIL``) —
     a blocklist of dangerous shell patterns over ``Bash`` and the Desktop Commander
     process tools (``dc_start_process`` / ``mcp__dc__start_process``).

``GuardrailDecision(allow, reason)`` is ported from ``agentcore/ports/guardrail.py``.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Awaitable, Callable
from urllib.parse import urlparse

from pydantic import BaseModel

from .config import Config

_log = logging.getLogger("agentmem.guardrail")


class GuardrailDecision(BaseModel):
    allow: bool = True
    reason: str = ""


class Guardrail(ABC):
    @abstractmethod
    async def check(self, tool_name: str, args: dict) -> GuardrailDecision:
        """Allow or veto a single tool call."""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# 1. URL guardrail
# --------------------------------------------------------------------------- #
Probe = Callable[[str], Awaitable[bool]]   # url -> reachable?

# Tools whose URL argument we police. Claude Code namespaces MCP tools as
# ``mcp__<server>__<tool>``; the sibling repo used the flat ``pw_browser_navigate``.
_URL_TOOLS = {"mcp__pw__browser_navigate", "pw_browser_navigate"}


async def _http_probe(url: str) -> bool:
    """Best-effort reachability: True unless DNS clearly fails or the page is 404/410."""
    import httpx

    headers = {"User-Agent": "Mozilla/5.0 (agentmem url-guardrail)"}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
            try:
                resp = await client.head(url, headers=headers)
                if resp.status_code == 405:  # HEAD not allowed -> retry GET
                    resp = await client.get(url, headers=headers)
            except httpx.HTTPError:
                resp = await client.get(url, headers=headers)
        return resp.status_code not in (404, 410)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False        # DNS / host does not resolve -> guessed URL
    except httpx.HTTPError:
        return True         # ambiguous (timeout, TLS, blocked) -> don't over-block


class UrlGuardrail(Guardrail):
    def __init__(
        self,
        *,
        tools: set[str] | None = None,
        allow_domains: list[str] | None = None,
        url_arg: str = "url",
        check_reachable: bool = False,
        probe: Probe | None = None,
    ) -> None:
        self._tools = set(tools) if tools is not None else set(_URL_TOOLS)
        self._allow = [d.lower() for d in (allow_domains or [])]
        self._arg = url_arg
        self._check_reachable = check_reachable
        self._probe = probe or _http_probe

    async def check(self, tool_name: str, args: dict) -> GuardrailDecision:
        if self._tools and tool_name not in self._tools:
            return GuardrailDecision(allow=True)
        url = str(args.get(self._arg, "")).strip()
        if not url:
            return GuardrailDecision(allow=True)

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return GuardrailDecision(
                allow=False,
                reason=f"'{url}' is not a valid URL. Do NOT guess URLs — open a search "
                       "URL https://www.google.com/search?q=<terms> and follow a real link.",
            )

        host = parsed.netloc.lower().split("@")[-1].split(":")[0]
        if self._allow and not any(host == d or host.endswith("." + d) for d in self._allow):
            return GuardrailDecision(
                allow=False,
                reason=f"domain '{host}' is not allowed. Use a search "
                       f"(https://www.google.com/search?q=...) or one of {self._allow}.",
            )

        if self._check_reachable and not await self._probe(url):
            _log.info("url guardrail vetoed unreachable URL: %s", url)
            return GuardrailDecision(
                allow=False,
                reason=f"'{url}' does not resolve / returns 404 — it was likely guessed. "
                       "Open a search URL https://www.google.com/search?q=<terms> instead.",
            )
        return GuardrailDecision(allow=True)


# --------------------------------------------------------------------------- #
# 2. Destructive-command guardrail (NEW)
# --------------------------------------------------------------------------- #
# Tools that run a shell command, and the arg holding the command string.
_COMMAND_TOOLS = {
    "Bash": "command",
    "dc_start_process": "command",
    "mcp__dc__start_process": "command",
}

# Patterns that almost never have a safe intent in an automated run. Kept narrow to
# avoid over-blocking; each comes with a human-readable reason.
_DESTRUCTIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf][a-zA-Z]*\s+(-[a-zA-Z]+\s+)*(/|~|\$HOME)(\s|$)"),
     "recursive/forced delete of a root or home path"),
    (re.compile(r"\bmkfs(\.[a-z0-9]+)?\b"), "filesystem format (mkfs)"),
    (re.compile(r"\bdd\b[^\n]*\bof=/dev/"), "raw write to a block device (dd of=/dev/...)"),
    (re.compile(r">\s*/dev/(sd|nvme|disk|hd)"), "redirect over a raw disk device"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&?\s*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\bgit\s+push\b[^\n]*--force[^\n]*\b(origin\s+)?(main|master)\b"),
     "force-push to main/master"),
    (re.compile(r"\bgit\s+push\b[^\n]*\b(main|master)\b[^\n]*--force"),
     "force-push to main/master"),
    (re.compile(r"\bchmod\s+-R\s+0*7{3,4}\s+/"), "recursive chmod 777 on a root path"),
    (re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b"), "host shutdown/reboot"),
]


class DestructiveCommandGuardrail(Guardrail):
    def __init__(
        self,
        *,
        tools: dict[str, str] | None = None,
        patterns: list[tuple[re.Pattern[str], str]] | None = None,
    ) -> None:
        self._tools = dict(tools) if tools is not None else dict(_COMMAND_TOOLS)
        self._patterns = patterns if patterns is not None else list(_DESTRUCTIVE_PATTERNS)

    async def check(self, tool_name: str, args: dict) -> GuardrailDecision:
        arg = self._tools.get(tool_name)
        if arg is None:
            return GuardrailDecision(allow=True)
        command = str(args.get(arg, "")).strip()
        if not command:
            return GuardrailDecision(allow=True)
        for pattern, reason in self._patterns:
            if pattern.search(command):
                _log.info("destructive guardrail vetoed command: %s", command)
                return GuardrailDecision(
                    allow=False,
                    reason=f"command vetoed ({reason}). Refusing to run: {command!r}. "
                           "If this is genuinely required, do it manually outside the agent.",
                )
        return GuardrailDecision(allow=True)


# --------------------------------------------------------------------------- #
# Chain + entry point used by the hook
# --------------------------------------------------------------------------- #
class GuardrailChain:
    """Applies guardrails in order; the first veto wins. Empty chain = allow all."""

    def __init__(self, guardrails: list[Guardrail] | None = None) -> None:
        self._guardrails = list(guardrails or [])

    async def check(self, tool_name: str, args: dict) -> GuardrailDecision:
        for guard in self._guardrails:
            decision = await guard.check(tool_name, args)
            if not decision.allow:
                return decision
        return GuardrailDecision(allow=True)


def build_chain(cfg: Config | None = None) -> GuardrailChain:
    cfg = cfg or Config.from_env()
    return GuardrailChain([
        UrlGuardrail(
            allow_domains=cfg.guard_allow_domains,
            check_reachable=cfg.guard_check_reachable,
        ),
        DestructiveCommandGuardrail(),
    ])


async def check(tool_name: str, args: dict, *, cfg: Config | None = None) -> GuardrailDecision:
    """One-shot helper the hook calls: build the chain and evaluate a single call."""
    return await build_chain(cfg).check(tool_name, args)
