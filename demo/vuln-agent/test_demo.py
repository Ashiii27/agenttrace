"""End-to-end: the demo attack is recorded, verifies, and a hand edit breaks verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent import DEFAULT_REQUEST, run_agent  # noqa: E402
from agenttrace import verify_session  # noqa: E402
from agenttrace.chain import event_hash  # noqa: E402
from models import NaiveScriptedModel  # noqa: E402


def events_of(session: Path) -> list[dict]:
    return [json.loads(x) for x in (session / "events.jsonl").read_text("utf-8").splitlines()]


def test_attack_is_recorded_and_verifiable(tmp_path):
    result = run_agent(NaiveScriptedModel(), DEFAULT_REQUEST, tmp_path)

    sent = [json.loads(x) for x in result.outbox.read_text("utf-8").splitlines()]
    assert sent[0]["to"] == "billing-verify@evil.test"

    events = events_of(result.session_dir)
    calls = [e for e in events if e["type"] == "tool.call"]
    exfil = next(e for e in calls if e["attrs"]["gen_ai.tool.name"] == "send_email")
    assert exfil["trust"] == "untrusted"
    assert exfil["attrs"]["args"]["to"] == "billing-verify@evil.test"
    # the fake portal key from the inbox was redacted in the record
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(events)

    assert verify_session(result.session_dir).ok


def test_hand_edit_hiding_the_attack_fails_verify(tmp_path):
    result = run_agent(NaiveScriptedModel(), DEFAULT_REQUEST, tmp_path)
    path = result.session_dir / "events.jsonl"
    path.write_text(
        path.read_text("utf-8").replace("billing-verify@evil.test", "billing@northwind.example"),
        "utf-8",
    )
    report = verify_session(result.session_dir)
    assert not report.ok
    assert {f.kind for f in report.findings} >= {"hash_mismatch"}


def test_chain_is_consistent(tmp_path):
    result = run_agent(NaiveScriptedModel(), DEFAULT_REQUEST, tmp_path)
    for ev in events_of(result.session_dir):
        assert event_hash(ev) == ev["hash"]
