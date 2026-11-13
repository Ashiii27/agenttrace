"""Secret redaction, applied before content is hashed (threat model G4).

A secret becomes ``[REDACTED:<type>:<8 hex>]`` where the hex is an HMAC of the secret under a
per-session key that is never written to disk. The same secret gets the same marker within a
session (so attribution can still link it), but markers cannot be linked across sessions or
brute-forced from the record.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from typing import Any

# Order matters: more specific patterns first.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}=*")),
]


class Redactor:
    def __init__(self, key: bytes | None = None) -> None:
        self._key = key if key is not None else secrets.token_bytes(32)
        self.count = 0

    def _marker(self, kind: str, secret: str) -> str:
        tag = hmac.new(self._key, secret.encode(), hashlib.sha256).hexdigest()[:8]
        return f"[REDACTED:{kind}:{tag}]"

    def redact_text(self, text: str) -> str:
        for kind, pattern in PATTERNS:

            def repl(m: re.Match[str], kind: str = kind) -> str:
                self.count += 1
                return self._marker(kind, m.group(0))

            text = pattern.sub(repl, text)
        return text

    def redact(self, obj: Any) -> Any:
        """Redact every string inside a JSON-like value (dict keys included)."""
        if isinstance(obj, str):
            return self.redact_text(obj)
        if isinstance(obj, dict):
            return {self.redact(k): self.redact(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.redact(v) for v in obj]
        return obj


class NoRedaction(Redactor):
    """For tests and benchmarks only — records secrets verbatim."""

    def redact_text(self, text: str) -> str:
        return text
