"""agenttrace command line: verify and show recorded sessions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .blobs import BlobStore
from .verify import verify_session

_TRUST_MARK = {"system": " ", "user": " ", "untrusted": "!"}


def _preview(value: Any, width: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _summary(ev: dict[str, Any], blobs: BlobStore, width: int) -> str:
    attrs = ev.get("attrs", {})
    t = ev["type"]
    if t == "tool.call":
        return f"{attrs.get('gen_ai.tool.name', '?')}({_preview(attrs.get('args', {}), width)})"
    if t == "llm.request":
        model = attrs.get("gen_ai.request.model", "?")
        return f"{model} · {len(ev['inputs'])} segments in context"
    if "content_ref" in ev:
        try:
            seg = json.loads(blobs.get(ev["content_ref"]))
        except (OSError, ValueError):
            return "<content unavailable>"
        if isinstance(seg, dict) and "content" in seg:
            calls = seg.get("tool_calls")
            body = _preview(seg["content"], width) if seg["content"] else ""
            if calls:
                body = (body + " " if body else "") + "→ " + ", ".join(c["name"] for c in calls)
            return body
        return _preview(seg, width)
    return _preview(attrs, width) if attrs else ""


def cmd_show(args: argparse.Namespace) -> int:
    session = Path(args.session)
    blobs = BlobStore(session / "blobs")
    width = 200 if args.full else 72
    print(" seq  type           trust      summary")
    for raw in (session / "events.jsonl").read_text(encoding="utf-8").splitlines():
        ev = json.loads(raw)
        mark = _TRUST_MARK.get(ev["trust"], "?")
        print(
            f"{ev['seq']:>4}  {ev['type']:<13}  {mark}{ev['trust']:<9}  "
            f"{_summary(ev, blobs, width)}"
        )
    print("\n! = untrusted: influenced by content from outside the system/user")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    report = verify_session(args.session)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.ok else 1
    if report.ok:
        print(
            f"OK   chain intact: {report.events} events "
            f"({report.sealed} sealed, {report.unsealed} unsealed)"
        )
    else:
        print(f"FAIL chain broken at line {report.first_break_line}")
        for f in report.findings:
            where = f"line {f.line}" + (f" (seq {f.seq})" if f.seq is not None else "")
            print(f"     {where}: {f.kind} — {f.detail}")
    for w in report.warnings:
        print(f"note {w}")
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agenttrace", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("verify", help="check a session's hash chain and blobs")
    p.add_argument("session", help="session directory (contains events.jsonl)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("show", help="print a session timeline")
    p.add_argument("session", help="session directory (contains events.jsonl)")
    p.add_argument("--full", action="store_true", help="wider previews")
    p.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
