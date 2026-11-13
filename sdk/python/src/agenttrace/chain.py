"""Hash chain rules from docs/schema.md section 4.

genesis     = SHA256("agenttrace/v1:genesis:" || session_id)
hash_i      = SHA256(raw32(prev_hash_i) || JCS(event_i without "hash"))
"""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785

SCHEMA = "agenttrace/v1"

TRUST_LEVELS = ("untrusted", "user", "system")  # lowest first
_TRUST_RANK = {name: rank for rank, name in enumerate(TRUST_LEVELS)}

EVENT_TYPES = frozenset(
    {
        "session.start",
        "user.input",
        "llm.request",
        "llm.response",
        "tool.call",
        "tool.result",
        "retrieval",
        "chain.break",
        "session.end",
    }
)


def canonical(obj: Any) -> bytes:
    """RFC 8785 (JCS) canonical JSON bytes."""
    return rfc8785.dumps(obj)


def content_ref(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def genesis(session_id: str) -> str:
    return hashlib.sha256(f"{SCHEMA}:genesis:{session_id}".encode()).hexdigest()


def event_hash(event: dict[str, Any]) -> str:
    """Hash of an event. Ignores any existing "hash" field."""
    body = {k: v for k, v in event.items() if k != "hash"}
    prev = bytes.fromhex(event["prev_hash"])
    if len(prev) != 32:
        raise ValueError("prev_hash must be 32 bytes of hex")
    return hashlib.sha256(prev + canonical(body)).hexdigest()


def lowest_trust(levels: list[str] | tuple[str, ...], default: str = "system") -> str:
    """The least trusted label among `levels` (untrusted < user < system)."""
    if not levels:
        return default
    for level in levels:
        if level not in _TRUST_RANK:
            raise ValueError(f"unknown trust label: {level!r}")
    return min(levels, key=_TRUST_RANK.__getitem__)
