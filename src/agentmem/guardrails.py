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

import functools
import logging
import re
from abc import ABC, abstractmethod
from typing import Awaitable, Callable
from urllib.parse import urlparse

from pydantic import BaseModel

from .config import Config
from .constants import ToolName

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
# Typed as str (StrEnum members ARE str) so a plain runtime ``tool_name`` matches.
_URL_TOOLS: set[str] = {ToolName.PW_NAVIGATE, ToolName.PW_NAVIGATE_FLAT}

# Probe defaults when a UrlGuardrail is built without a Config (e.g. tests). Production
# values come from Config (probe_timeout / probe_user_agent) via build_chain.
_PROBE_TIMEOUT = 5.0
_PROBE_USER_AGENT = "Mozilla/5.0 (agentmem url-guardrail)"


async def _http_probe(
    url: str, *, timeout: float = _PROBE_TIMEOUT, user_agent: str = _PROBE_USER_AGENT
) -> bool:
    """Best-effort reachability: True unless DNS clearly fails or the page is 404/410."""
    import httpx

    headers = {"User-Agent": user_agent}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
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
        probe_timeout: float = _PROBE_TIMEOUT,
        probe_user_agent: str = _PROBE_USER_AGENT,
    ) -> None:
        self._tools = set(tools) if tools is not None else set(_URL_TOOLS)
        self._allow = [d.lower() for d in (allow_domains or [])]
        self._arg = url_arg
        self._check_reachable = check_reachable
        self._probe = probe or functools.partial(
            _http_probe, timeout=probe_timeout, user_agent=probe_user_agent
        )

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
_COMMAND_TOOLS: dict[str, str] = {
    ToolName.BASH: "command",
    ToolName.DC_START_PROCESS_FLAT: "command",
    ToolName.DC_START_PROCESS: "command",
}

# Patterns that almost never have a safe intent in an automated run. Kept narrow to
# avoid over-blocking; each carries a stable KEY (so the dashboard can disable it
# individually via Config.guard_disabled_patterns) and a human-readable reason.
_DESTRUCTIVE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("rm_root_home",
     re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf][a-zA-Z]*\s+(-[a-zA-Z]+\s+)*(/|~|\$HOME)(\s|$)"),
     "recursive/forced delete of a root or home path"),
    ("mkfs", re.compile(r"\bmkfs(\.[a-z0-9]+)?\b"), "filesystem format (mkfs)"),
    ("dd_to_device", re.compile(r"\bdd\b[^\n]*\bof=/dev/"), "raw write to a block device (dd of=/dev/...)"),
    ("redirect_to_disk", re.compile(r">\s*/dev/(sd|nvme|disk|hd)"), "redirect over a raw disk device"),
    ("fork_bomb", re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&?\s*\}\s*;\s*:"), "fork bomb"),
    # A force flag in any common spelling: --force, --force-with-lease, the short -f,
    # or a bundled short flag (-fu / -uf). The old patterns only matched the literal
    # "--force" and let the everyday `git push -f origin main` slip through.
    ("force_push_main",
     re.compile(r"\bgit\s+push\b[^\n]*\s(?:--force(?:-with-lease)?|-[a-zA-Z]*f[a-zA-Z]*)\b[^\n]*\b(origin\s+)?(main|master)\b"),
     "force-push to main/master (force flag before branch)"),
    ("force_push_main_alt",
     re.compile(r"\bgit\s+push\b[^\n]*\b(main|master)\b[^\n]*\s(?:--force(?:-with-lease)?|-[a-zA-Z]*f[a-zA-Z]*)\b"),
     "force-push to main/master (force flag after branch)"),
    ("chmod_777_root", re.compile(r"\bchmod\s+-R\s+0*7{3,4}\s+/"), "recursive chmod 777 on a root path"),
    # Anchored to a command position (start, after a ;/&&/|| separator, or after sudo) so
    # ordinary text like git commit -m "reboot the retry logic" is not vetoed.
    ("host_shutdown",
     re.compile(r"(?:^|[;&|]\s*|\bsudo\s+)(shutdown|reboot|halt|poweroff)\b"),
     "host shutdown/reboot"),
]


def destructive_pattern_catalog() -> list[dict]:
    """The full destructive blocklist as plain dicts — consumed by the dashboard."""
    return [
        {"key": key, "reason": reason, "regex": pattern.pattern}
        for key, pattern, reason in _DESTRUCTIVE_PATTERNS
    ]


def policed_tools() -> dict:
    """Which tools each guard inspects — read-only context for the dashboard."""
    return {"url": sorted(_URL_TOOLS), "command": sorted(_COMMAND_TOOLS)}


class DestructiveCommandGuardrail(Guardrail):
    def __init__(
        self,
        *,
        tools: dict[str, str] | None = None,
        patterns: list[tuple[str, re.Pattern[str], str]] | None = None,
        disabled: list[str] | set[str] | None = None,
    ) -> None:
        self._tools = dict(tools) if tools is not None else dict(_COMMAND_TOOLS)
        self._patterns = patterns if patterns is not None else list(_DESTRUCTIVE_PATTERNS)
        self._disabled = {k.lower() for k in (disabled or [])}

    async def check(self, tool_name: str, args: dict) -> GuardrailDecision:
        arg = self._tools.get(tool_name)
        if arg is None:
            return GuardrailDecision(allow=True)
        command = str(args.get(arg, "")).strip()
        if not command:
            return GuardrailDecision(allow=True)
        for key, pattern, reason in self._patterns:
            if key in self._disabled:
                continue
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


def _custom_patterns(cfg: Config) -> list[tuple[str, re.Pattern[str], str]]:
    """Compile the ENABLED user-defined rules (from the custom-rules JSON file)."""
    from .config import custom_rules_path
    from .rules_store import CustomRuleStore

    out: list[tuple[str, re.Pattern[str], str]] = []
    for rule in CustomRuleStore(custom_rules_path(cfg)).load():
        if not rule.enabled:
            continue
        try:
            out.append((rule.key, re.compile(rule.regex), rule.reason))
        except re.error:
            continue  # validated on write, but never let a bad rule wedge the guard
    return out


def build_chain(cfg: Config | None = None) -> GuardrailChain:
    cfg = cfg or Config.from_env()
    guards: list[Guardrail] = []
    if cfg.guard_url_enabled:
        guards.append(UrlGuardrail(
            allow_domains=cfg.guard_allow_domains,
            check_reachable=cfg.guard_check_reachable,
            probe_timeout=cfg.probe_timeout,
            probe_user_agent=cfg.probe_user_agent,
        ))
    if cfg.guard_destructive_enabled:
        patterns = list(_DESTRUCTIVE_PATTERNS) + _custom_patterns(cfg)
        guards.append(DestructiveCommandGuardrail(
            patterns=patterns, disabled=cfg.guard_disabled_patterns,
        ))
    return GuardrailChain(guards)


async def check(tool_name: str, args: dict, *, cfg: Config | None = None) -> GuardrailDecision:
    """One-shot helper the hook calls: build the chain and evaluate a single call."""
    return await build_chain(cfg).check(tool_name, args)
