"""Regenerate schema/test-vectors/chain-v1.json.

The vectors pin the hashing rules (docs/schema.md section 4) so the Go collector can be checked
against the Python SDK byte for byte. Only regenerate them together with a schema version bump.
"""

from __future__ import annotations

import json
from pathlib import Path

from agenttrace.chain import SCHEMA, canonical, event_hash, genesis

OUT = Path(__file__).resolve().parents[3] / "schema" / "test-vectors" / "chain-v1.json"
SESSION = "s_testvector01"
REF = "sha256:" + "ab" * 32

CANONICAL_CASES = [
    {"b": 2, "a": 1, "c": {"z": [3, 1], "y": None}},
    {"float": 0.1, "big": 1e21, "small": 1e-7, "neg_zero": -0.0, "int_float": 4.0},
    {"unicode": "é \U0001f600  ", "escape": 'quote" backslash\\ tab\t'},
    # JCS sorts keys by UTF-16 code units, not code points: U+1F600 (surrogate D83D) sorts
    # before U+FF61, although its code point is larger.
    {"｡": 1, "\r": 2, "1": 3, "\U0001f600": 4, "ü": 5},
]

BODIES = [
    {"type": "session.start", "inputs": [], "trust": "system", "attrs": {"agent": "demo"}},
    {"type": "user.input", "inputs": [], "trust": "user", "attrs": {}, "content_ref": REF},
    {
        "type": "tool.call",
        "inputs": [REF],
        "trust": "untrusted",
        "attrs": {"gen_ai.tool.name": "send_email", "args": {"to": "x@evil.test", "n": 1.5}},
        "content_ref": "sha256:" + "cd" * 32,
    },
]


def main() -> None:
    prev = genesis(SESSION)
    events = []
    for seq, body in enumerate(BODIES):
        ev = {
            "schema": SCHEMA,
            "session_id": SESSION,
            "seq": seq,
            "ts": f"2026-11-13T10:00:0{seq}.000Z",
            "actor": "demo",
            **body,
            "prev_hash": prev,
        }
        ev["hash"] = event_hash(ev)
        prev = ev["hash"]
        events.append(ev)
    doc = {
        "description": "AgentTrace v1 hashing test vectors. See docs/schema.md section 4.",
        "canonical": [{"input": c, "jcs": canonical(c).decode("utf-8")} for c in CANONICAL_CASES],
        "session_id": SESSION,
        "genesis": genesis(SESSION),
        "events": events,
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
