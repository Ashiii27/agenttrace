"""Offline verification of a recorded session (docs/schema.md section 5).

Phase 1 has no collector, so there are no signed checkpoints yet. Every intact event is therefore
reported as **unsealed** (guarantee G2): edits, deletions, insertions and reordering in the middle
of the log are detected, but an attacker who rewrites the whole chain from some point onward, or
truncates the tail, is not. Signed checkpoints in phase 2 close that gap.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .blobs import BlobStore
from .chain import EVENT_TYPES, SCHEMA, TRUST_LEVELS, event_hash, genesis

REQUIRED = ("schema", "session_id", "seq", "ts", "type", "actor", "inputs", "trust", "prev_hash")


@dataclass
class Finding:
    line: int
    seq: int | None
    kind: str
    detail: str


@dataclass
class Report:
    session_id: str | None
    events: int = 0
    unsealed: int = 0
    sealed: int = 0
    first_break_line: int | None = None
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.first_break_line is None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _check_event(ev: Any) -> str | None:
    if not isinstance(ev, dict):
        return "event is not a JSON object"
    missing = [k for k in (*REQUIRED, "hash") if k not in ev]
    if missing:
        return f"missing fields: {', '.join(missing)}"
    if ev["schema"] != SCHEMA:
        return f"unsupported schema {ev['schema']!r}"
    if ev["type"] not in EVENT_TYPES:
        return f"unknown event type {ev['type']!r}"
    if ev["trust"] not in TRUST_LEVELS:
        return f"unknown trust label {ev['trust']!r}"
    if not isinstance(ev["seq"], int) or not isinstance(ev["inputs"], list):
        return "bad field types"
    return None


def verify_session(session_dir: str | Path) -> Report:
    session_dir = Path(session_dir)
    events_path = session_dir / "events.jsonl"
    blobs = BlobStore(session_dir / "blobs")
    report = Report(session_id=None)

    if not events_path.is_file():
        report.findings.append(Finding(0, None, "missing_log", f"{events_path} not found"))
        report.first_break_line = 0
        return report

    lines = events_path.read_text(encoding="utf-8").splitlines()
    expected_prev: str | None = None
    last_type: str | None = None

    def brk(line: int, seq: int | None, kind: str, detail: str) -> None:
        report.findings.append(Finding(line, seq, kind, detail))
        if report.first_break_line is None:
            report.first_break_line = line

    for lineno, raw in enumerate(lines, start=1):
        if not raw.strip():
            brk(lineno, None, "malformed", "blank line")
            continue
        report.events += 1
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError as e:
            brk(lineno, None, "malformed", f"invalid JSON: {e.msg}")
            continue
        problem = _check_event(ev)
        if problem:
            brk(lineno, ev.get("seq") if isinstance(ev, dict) else None, "malformed", problem)
            continue

        seq = ev["seq"]
        if report.session_id is None:
            report.session_id = ev["session_id"]
            expected_prev = genesis(ev["session_id"])
        elif ev["session_id"] != report.session_id:
            brk(lineno, seq, "session_mismatch", f"session_id {ev['session_id']!r}")

        if seq != lineno - 1:
            brk(lineno, seq, "sequence", f"expected seq {lineno - 1}, found {seq}")
        if ev["prev_hash"] != expected_prev:
            brk(lineno, seq, "chain_link", "prev_hash does not match the previous event")
        try:
            recomputed = event_hash(ev)
        except ValueError as e:
            brk(lineno, seq, "malformed", str(e))
            recomputed = None
        if recomputed is not None and recomputed != ev["hash"]:
            brk(lineno, seq, "hash_mismatch", "event content does not match its hash")

        refs = ([ev["content_ref"]] if "content_ref" in ev else []) + list(ev["inputs"])
        for ref in refs:
            try:
                status = blobs.check(ref)
            except ValueError as e:
                status = str(e)
            if status:
                brk(lineno, seq, f"blob_{status.split()[0]}", f"{ref}: {status}")

        expected_prev = ev["hash"]
        if last_type is None and ev["type"] != "session.start":
            report.warnings.append("first event is not session.start")
        last_type = ev["type"]
        if report.first_break_line is None:
            report.unsealed += 1

    if report.events == 0:
        brk(0, None, "empty_log", "no events recorded")
    if report.events and last_type != "session.end":
        report.warnings.append(
            "no session.end: the agent crashed, is still running, or the tail was truncated"
        )
    if report.ok:
        report.warnings.append(
            "no signed checkpoints yet (phase 2): a full rewrite or tail truncation "
            "would not be detected"
        )
    return report
