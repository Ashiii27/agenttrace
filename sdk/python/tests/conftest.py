from __future__ import annotations

import json
from pathlib import Path

import pytest

from agenttrace import Recorder
from agenttrace.segments import message_segment, tool_call_segment

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def session(tmp_path: Path) -> Path:
    """A small recorded session: user asks, model calls a tool, tool returns, model answers."""
    with Recorder(tmp_path, actor="test-agent", attrs={"agent": "fixture"}) as rec:
        user = rec.user_input("summarise https://vendor.example/q4-update")["content_ref"]
        sys_ref = rec.put_segment(message_segment("system", "be helpful"), "system")
        rec.emit("llm.request", content={"p": 1}, content_trust="system", inputs=[sys_ref, user])
        resp = rec.emit(
            "llm.response",
            content=message_segment("assistant", "", [{"name": "fetch_url", "args": {"u": 1}}]),
            inputs=[sys_ref, user],
        )["content_ref"]
        call = rec.emit(
            "tool.call",
            content=tool_call_segment("fetch_url", {"u": 1}),
            inputs=[resp],
            attrs={"gen_ai.tool.name": "fetch_url", "args": {"u": 1}},
        )["content_ref"]
        rec.emit(
            "tool.result",
            content=message_segment("tool", "page text"),
            content_trust="untrusted",
            inputs=[call],
            trust="untrusted",
        )
    return rec.dir


def read_events(session_dir: Path) -> list[dict]:
    lines = (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def write_events(session_dir: Path, events: list[dict]) -> None:
    text = "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in events)
    (session_dir / "events.jsonl").write_text(text, encoding="utf-8")
