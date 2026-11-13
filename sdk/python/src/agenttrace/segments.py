"""Segment formats. A segment is one unit of content in a context window (see ADR-0006).

Message segments are ``{"role", "content"[, "tool_calls"]}``. The same message always produces
the same segment, so a tool result recorded in ``tool.result`` has the same hash as the tool
message that later appears in an ``llm.request`` — that is what links the provenance graph.
"""

from __future__ import annotations

from typing import Any

ROLES = frozenset({"system", "user", "assistant", "tool"})


def message_segment(
    role: str, content: Any, tool_calls: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"unknown role: {role!r}")
    seg: dict[str, Any] = {"role": role, "content": content}
    if tool_calls:
        seg["tool_calls"] = [{"name": c["name"], "args": c.get("args", {})} for c in tool_calls]
    return seg


def tool_call_segment(name: str, args: Any) -> dict[str, Any]:
    return {"name": name, "args": args}
