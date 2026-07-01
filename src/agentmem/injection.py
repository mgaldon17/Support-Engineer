"""Prompt-injection defenses for the lesson memory.

Lessons are auto-injected into the model's context (the ``inject_lessons`` hook), so a
lesson is an *instruction-adjacent* artifact. A ``learned`` lesson can be derived from
UNTRUSTED task data (a web page, a file, a support ticket), which makes the store a
classic stored / indirect prompt-injection vector ("memory poisoning"): poison a lesson
once and it is replayed into every future prompt.

Defenses, layered:

  1. Trust gating (structural, the keystone) — only *trusted* lessons are auto-injected:
     human-authored or human-reviewed (``pending_review is False``). Unreviewed
     ``learned`` lessons wait in the dashboard review queue. See ``is_trusted_for_injection``.
  2. Quarantine at write time — text that trips the injection heuristics is forced into
     review (``scan_for_injection`` → caller sets ``pending_review``), so a poisoned
     ``human_authored`` lesson is not auto-trusted either.
  3. Neutralisation at the boundary — ``sanitize_for_context`` strips control/invisible
     characters and bounds length before a lesson is placed in the prompt.

Detection is heuristic (best-effort, not a guarantee); it backstops the structural
trust gate, it does not replace it.
"""

from __future__ import annotations

import re

# Signatures that strongly suggest an attempt to override instructions or smuggle
# commands into a stored procedure. Conservative, to limit false positives.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override_instructions",
     re.compile(r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}"
                r"\b(previous|prior|above|earlier|all|the|your)\b.{0,25}"
                r"\b(instruction|prompt|rule|system|context|message|direction|guardrail)s?\b",
                re.I | re.S)),
    ("role_marker",
     re.compile(r"(?im)^\s*(system|assistant|developer)\s*:")),
    ("chat_template_tag",
     re.compile(r"(?i)(<\|im_(start|end)\|>|\[/?INST\]|<</?SYS>>|<\|(system|assistant|user)\|>)")),
    ("new_instructions",
     re.compile(r"\b(new|updated|real|actual|true)\b.{0,15}\binstructions?\b", re.I)),
    ("imperative_always",
     re.compile(r"\b(always|from now on|henceforth|going forward)\b.{0,50}"
                r"\b(run|execute|send|exfiltrate|reveal|print|disclose|disable|ignore|delete)\b",
                re.I | re.S)),
    # Either order: "<secret> ... <exfil verb>" or "<exfil verb> ... <secret>".
    ("secret_exfil",
     re.compile(r"\b(api[_\s-]?key|secret|token|password|credential|\.env|env\s*var)s?\b.{0,40}"
                r"\b(send|post|exfiltrate|upload|reveal|leak|email|curl|disclose)\b"
                r"|\b(send|post|exfiltrate|upload|reveal|leak|email|curl|disclose)\b.{0,40}"
                r"\b(api[_\s-]?key|secret|token|password|credential|\.env|env\s*var)s?\b",
                re.I | re.S)),
    ("disable_guardrail",
     re.compile(r"\b(disable|turn\s*off|bypass|skip|ignore)\b.{0,30}"
                r"\b(guardrail|safety|security|filter|check|protection)s?\b", re.I | re.S)),
]

# Control characters (keeps \t \n \r) and invisible / bidi unicode used to hide payloads.
# The invisible class is built from codepoint ranges so this source file stays ASCII-clean.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INVISIBLE_RANGES = [(0x200b, 0x200f), (0x202a, 0x202e), (0x2060, 0x2064), (0xfeff, 0xfeff)]
_INVISIBLE = re.compile(
    "[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in _INVISIBLE_RANGES) + "]"
)

_DEFAULT_MAX_LEN = 4000


def scan_for_injection(text: str) -> list[str]:
    """Return the keys of the injection heuristics that match ``text`` (empty == clean)."""
    if not text:
        return []
    hits = [key for key, pat in _INJECTION_PATTERNS if pat.search(text)]
    if _INVISIBLE.search(text):
        hits.append("invisible_unicode")
    return hits


def looks_like_injection(text: str) -> bool:
    return bool(scan_for_injection(text))


def sanitize_for_context(text: str, *, max_len: int = _DEFAULT_MAX_LEN) -> str:
    """Neutralise a lesson before it enters the prompt: strip control/invisible chars and
    bound the length so one record cannot flood the context or hide directives in it."""
    if not text:
        return ""
    text = _CONTROL_CHARS.sub("", text)
    text = _INVISIBLE.sub("", text)
    if len(text) > max_len:
        text = text[:max_len].rstrip() + " […truncated]"
    return text


def is_trusted_for_injection(lesson: object) -> bool:
    """A lesson may be auto-injected only if a human has vetted it (not pending review)
    AND its text does not trip the injection heuristics (belt-and-suspenders)."""
    if getattr(lesson, "pending_review", False):
        return False
    title = getattr(lesson, "title", "") or ""
    content = getattr(lesson, "content", "") or ""
    return not looks_like_injection(f"{title}\n{content}")


def select_injectable(lessons: list) -> list:
    """Filter a recalled list down to the lessons that are safe to auto-inject."""
    return [lesson for lesson in lessons if is_trusted_for_injection(lesson)]
