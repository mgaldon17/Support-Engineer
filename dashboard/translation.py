"""Translation — shell-permission glob <-> blocklist regex helpers (pure functions).

Single responsibility: the small, side-effect-free string conversions the dashboard uses
to move a command between the allowlist (globs) and the blocklist (regexes).
"""

from __future__ import annotations

import re


def bash_inner(entry: str) -> str | None:
    """The ``X`` in a ``Bash(X)`` permission entry, or None if it isn't one."""
    m = re.fullmatch(r"Bash\((.*)\)", entry.strip())
    return m.group(1) if m else None


def glob_to_regex(glob: str) -> str:
    """A shell-permission glob (`rm -rf *`) -> an anchored-ish regex for the blocklist."""
    return r"\b" + ".*".join(re.escape(p) for p in glob.split("*"))


def regex_to_glob(regex: str) -> str:
    """Best-effort (lossy) inverse of glob_to_regex, for moving a rule back to allow."""
    return re.sub(r"\\(.)", r"\1", regex.replace(r"\b", "").replace(".*", "*"))
