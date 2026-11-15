"""Atomic file replace that survives Windows' brief file locks."""
from __future__ import annotations

import os
import time
from pathlib import Path


def replace_file(src: Path, dst: Path, attempts: int = 25, delay: float = 0.04) -> None:
    """os.replace(src, dst), retried on Windows sharing violations.

    On Windows, replacing a file fails with "Access is denied" while any other
    process has it open for a moment: antivirus and the search indexer scan a
    file right after it is written. Seen in the test suite on secrets.json;
    for users it made saving a key or "Delete all data" fail at random. The
    lock lasts milliseconds, so a short retry is enough.
    """
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or i == attempts - 1:
                raise
            time.sleep(delay * (1 + i // 5))
