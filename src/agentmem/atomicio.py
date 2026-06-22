"""Atomic text-file writes — write a temp file in the same dir, then ``os.replace``.

A reader never observes a half-written file (the rename is atomic on POSIX/NTFS), and
paired with a lock held across a read-modify-write sequence this prevents the lost-update
/ torn-write races that a threaded server otherwise hits on its config files.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, text: str, *, encoding: str = "utf-8") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
