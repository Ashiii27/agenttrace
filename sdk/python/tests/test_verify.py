"""Tamper matrix for `agenttrace verify` (threat model A2/A3, guarantees G1-G2)."""

from __future__ import annotations

import json

import pytest
from conftest import read_events, write_events

from agenttrace import Recorder, verify_session
from agenttrace.blobs import BlobStore
from agenttrace.chain import event_hash
from agenttrace.cli import main


def test_clean_session_verifies(session):
    report = verify_session(session)
    assert report.ok, report.findings
    assert report.events == 7
    assert report.unsealed == 7 and report.sealed == 0
    assert any("no signed checkpoints" in w for w in report.warnings)


def kinds(report):
    return {f.kind for f in report.findings}


def test_edited_field_is_detected(session):
    events = read_events(session)
    events[4]["attrs"]["args"] = {"u": 2}
    write_events(session, events)
    report = verify_session(session)
    assert not report.ok and report.first_break_line == 5
    assert "hash_mismatch" in kinds(report)


def test_deleted_event_is_detected(session):
    events = read_events(session)
    del events[3]
    write_events(session, events)
    report = verify_session(session)
    assert report.first_break_line == 4
    assert {"sequence", "chain_link"} <= kinds(report)


def test_reordered_events_are_detected(session):
    events = read_events(session)
    events[2], events[3] = events[3], events[2]
    write_events(session, events)
    assert verify_session(session).first_break_line == 3


def test_forged_insertion_is_detected(session):
    events = read_events(session)
    forged = dict(events[2], seq=3, prev_hash=events[2]["hash"])
    forged["hash"] = event_hash(forged)  # attacker recomputes the hash of the forged event
    events.insert(3, forged)
    write_events(session, events)
    report = verify_session(session)
    assert not report.ok
    assert report.first_break_line == 5  # the original event no longer links


def test_tampered_blob_is_detected(session):
    ref = read_events(session)[5]["content_ref"]
    BlobStore(session / "blobs").path(ref).write_bytes(b'{"role":"tool","content":"benign"}')
    report = verify_session(session)
    assert report.first_break_line == 6
    assert "blob_tampered" in kinds(report)


def test_missing_blob_is_detected(session):
    ref = read_events(session)[1]["content_ref"]
    BlobStore(session / "blobs").path(ref).unlink()
    assert "blob_missing" in kinds(verify_session(session))


def test_malformed_line_is_detected(session):
    path = session / "events.jsonl"
    lines = path.read_text("utf-8").splitlines()
    lines[2] = lines[2][:-5]
    path.write_text("\n".join(lines) + "\n", "utf-8")
    assert verify_session(session).first_break_line == 3


def test_truncated_tail_is_flagged_but_not_a_break(session):
    """Without checkpoints, truncation is only visible as a missing session.end (G2)."""
    write_events(session, read_events(session)[:-2])
    report = verify_session(session)
    assert report.ok
    assert any("no session.end" in w for w in report.warnings)


def test_full_rewrite_is_not_detected_without_checkpoints(session):
    """Documents the phase 1 limit: rewriting the chain from the edit onward passes verify.
    Signed checkpoints held by the collector (phase 2, ADR-0002) close this gap."""
    events = read_events(session)
    events[4]["attrs"]["args"] = {"u": "rewritten"}
    for i in range(4, len(events)):
        events[i]["prev_hash"] = events[i - 1]["hash"]
        events[i]["hash"] = event_hash(events[i])
    write_events(session, events)
    assert verify_session(session).ok


def test_recorder_refuses_to_overwrite(tmp_path):
    with Recorder(tmp_path, session_id="s_fixed01") as rec:
        rec.user_input("hi")
    with pytest.raises(FileExistsError):
        Recorder(tmp_path, session_id="s_fixed01")


def test_cli_exit_codes(session, capsys):
    assert main(["verify", str(session)]) == 0
    assert "OK" in capsys.readouterr().out
    events = read_events(session)
    events[1]["trust"] = "system"
    write_events(session, events)
    assert main(["verify", str(session), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_show(session, capsys):
    assert main(["show", str(session)]) == 0
    out = capsys.readouterr().out
    assert "fetch_url" in out and "!untrusted" in out
