"""Guardrail unit tests — URL veto + destructive-command veto (offline, no Qdrant)."""

from __future__ import annotations

import pytest

from agentmem.guardrails import (
    DestructiveCommandGuardrail,
    GuardrailChain,
    UrlGuardrail,
    build_chain,
)
from agentmem.config import Config


@pytest.mark.asyncio
async def test_url_invalid_is_vetoed():
    g = UrlGuardrail(check_reachable=False)
    d = await g.check("mcp__pw__browser_navigate", {"url": "not a url"})
    assert d.allow is False and "URL" in d.reason


@pytest.mark.asyncio
async def test_url_valid_is_allowed():
    g = UrlGuardrail(check_reachable=False)
    d = await g.check("mcp__pw__browser_navigate", {"url": "https://example.com/x"})
    assert d.allow is True


@pytest.mark.asyncio
async def test_url_allowlist_blocks_other_domains():
    g = UrlGuardrail(allow_domains=["example.com"], check_reachable=False)
    assert (await g.check("mcp__pw__browser_navigate", {"url": "https://evil.test"})).allow is False
    assert (await g.check("mcp__pw__browser_navigate", {"url": "https://sub.example.com"})).allow is True


@pytest.mark.asyncio
async def test_url_unreachable_is_vetoed_with_fake_probe():
    async def probe(_url: str) -> bool:
        return False  # simulate DNS failure / 404

    g = UrlGuardrail(check_reachable=True, probe=probe)
    d = await g.check("mcp__pw__browser_navigate", {"url": "https://made-up-host.test"})
    assert d.allow is False and "404" in d.reason


@pytest.mark.asyncio
async def test_url_guard_ignores_unrelated_tools():
    g = UrlGuardrail(check_reachable=False)
    assert (await g.check("Bash", {"command": "ls"})).allow is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "sudo rm -rf ~",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda bs=1M",
        "git push --force origin main",
        "git push -f origin main",
        "git push origin master -f",
        "shutdown -h now",
    ],
)
async def test_destructive_commands_are_vetoed(command):
    g = DestructiveCommandGuardrail()
    assert (await g.check("Bash", {"command": command})).allow is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "git push origin feature",
        "rm note.txt",
        'git commit -m "reboot the retry logic"',   # word "reboot" in text, not a command
        "grep halt /var/log/syslog",                # word "halt" as an argument
    ],
)
async def test_safe_commands_are_allowed(command):
    g = DestructiveCommandGuardrail()
    assert (await g.check("Bash", {"command": command})).allow is True


@pytest.mark.asyncio
async def test_chain_first_veto_wins_and_build_chain():
    chain: GuardrailChain = build_chain(Config())
    assert (await chain.check("Bash", {"command": "rm -rf /"})).allow is False
    assert (await chain.check("Bash", {"command": "echo ok"})).allow is True
