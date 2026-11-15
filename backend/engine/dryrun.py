"""Recognising a final "submit application" control (used by test mode)."""
from __future__ import annotations

import logging
import re

_log = logging.getLogger("engine")

SUBMIT_RX = re.compile(
    r"\b(submit|send\s+(my\s+)?application|finish(\s+application)?|complete\s+(my\s+)?application|"
    r"confirm\s+and\s+(submit|apply)|apply\s+and\s+submit|send)\b",
    re.IGNORECASE,
)

def element_label(node) -> str:
    try:
        text = node.get_all_children_text() or ""
    except Exception:
        text = ""
    attrs = getattr(node, "attributes", None) or {}
    extra = " ".join(str(attrs.get(k, "")) for k in ("value", "aria-label", "title", "data-testid"))
    return f"{text} {extra}".strip()


def looks_like_final_submit(label: str) -> bool:
    return bool(SUBMIT_RX.search(label or ""))
