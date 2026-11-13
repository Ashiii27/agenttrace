"""LangChain / LangGraph adapter: a callback handler that records chat-model and tool runs.

Usage::

    from agenttrace import Recorder
    from agenttrace.adapters.langchain import AgentTraceCallbackHandler

    with Recorder("runs", attrs={"agent": "email-assistant"}) as rec:
        handler = AgentTraceCallbackHandler(rec)
        graph.invoke(state, config={"callbacks": [handler]})

Trust labels for messages in a context window:

* ``SystemMessage`` → ``system``; ``HumanMessage`` → ``user``
* ``ToolMessage`` and anything unknown → ``untrusted``
* ``AIMessage`` → the trust its ``llm.response`` was recorded with (``untrusted`` if unseen)
"""

from __future__ import annotations

import json
import threading
from typing import Any
from uuid import UUID

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import BaseMessage
    from langchain_core.outputs import LLMResult
except ImportError as e:  # pragma: no cover
    raise ImportError("install the extra: pip install 'agenttrace[langchain]'") from e

from ..chain import canonical
from ..recorder import Recorder
from ..segments import message_segment, tool_call_segment

_ROLE = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
_FIXED_TRUST = {"system": "system", "human": "user"}


def _args_key(name: str, args: Any) -> bytes:
    return canonical(json.loads(json.dumps({"n": name, "a": args}, default=str)))


class AgentTraceCallbackHandler(BaseCallbackHandler):
    """Records ``llm.request``, ``llm.response``, ``tool.call`` and ``tool.result`` events.

    Recording errors are raised (``raise_error = True``): a security recorder that silently
    drops events would give a false sense of completeness.
    """

    raise_error = True

    def __init__(self, recorder: Recorder, actor: str | None = None) -> None:
        self.rec = recorder
        self.actor = actor
        self._lock = threading.Lock()
        self._request_inputs: dict[UUID, list[str]] = {}
        self._request_model: dict[UUID, str] = {}
        self._pending_calls: dict[bytes, list[tuple[str, str | None]]] = {}
        self._last_response: str | None = None
        self._tool_runs: dict[UUID, tuple[str, str | None, str]] = {}

    # -- messages ---------------------------------------------------------------------------

    def _segment(self, msg: BaseMessage) -> dict[str, Any]:
        role = _ROLE.get(msg.type)
        if role is None:  # function/chat/custom messages: treat as tool-like external content
            role = "tool"
        calls = getattr(msg, "tool_calls", None) if role == "assistant" else None
        return message_segment(role, msg.content, calls or None)

    def _message_ref(self, msg: BaseMessage) -> str:
        seg = self._segment(msg)
        trust = _FIXED_TRUST.get(msg.type)
        if trust is None and msg.type == "ai":
            trust = self.rec.trust_of(self.rec.ref_for(seg))
        return self.rec.put_segment(seg, trust or "untrusted")

    # -- model runs -------------------------------------------------------------------------

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        params = kwargs.get("invocation_params") or {}
        model = (
            (metadata or {}).get("ls_model_name")
            or params.get("model")
            or params.get("model_name")
            or (serialized or {}).get("name")
            or "unknown"
        )
        with self._lock:
            refs = [self._message_ref(m) for batch in messages for m in batch]
            self._request_inputs[run_id] = refs
            self._request_model[run_id] = str(model)
            self.rec.emit(
                "llm.request",
                content={"invocation_params": params},
                content_trust="system",
                inputs=refs,
                attrs={
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": str(model),
                    "gen_ai.provider.name": (metadata or {}).get("ls_provider"),
                    "run_id": str(run_id),
                },
                actor=self.actor,
            )

    def on_llm_end(
        self, response: LLMResult, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        with self._lock:
            inputs = self._request_inputs.pop(run_id, [])
            model = self._request_model.pop(run_id, "unknown")
            for gens in response.generations:
                for gen in gens:
                    msg = getattr(gen, "message", None)
                    if msg is None:
                        seg = message_segment("assistant", gen.text)
                        calls: list[dict[str, Any]] = []
                    else:
                        seg = self._segment(msg)
                        calls = list(getattr(msg, "tool_calls", None) or [])
                    usage = getattr(msg, "usage_metadata", None) or {}
                    ev = self.rec.emit(
                        "llm.response",
                        content=seg,
                        inputs=inputs,
                        attrs={
                            "gen_ai.request.model": model,
                            "gen_ai.usage.input_tokens": usage.get("input_tokens"),
                            "gen_ai.usage.output_tokens": usage.get("output_tokens"),
                            "tool_calls": [c["name"] for c in calls],
                            "run_id": str(run_id),
                        },
                        actor=self.actor,
                    )
                    ref = ev["content_ref"]
                    self._last_response = ref
                    for c in calls:
                        key = _args_key(c["name"], c.get("args", {}))
                        self._pending_calls.setdefault(key, []).append((ref, c.get("id")))

    # -- tool runs --------------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = (serialized or {}).get("name") or kwargs.get("name") or "unknown"
        args: Any = inputs if inputs is not None else input_str
        with self._lock:
            queue = self._pending_calls.get(_args_key(name, args))
            matched = bool(queue)
            if queue:
                response_ref, call_id = queue.pop(0)
            else:  # tool called outside a model turn, or args were rewritten by the agent
                response_ref, call_id = self._last_response, None
            ev = self.rec.emit(
                "tool.call",
                content=tool_call_segment(name, args),
                inputs=[response_ref] if response_ref else [],
                trust=None if response_ref else "untrusted",
                attrs={
                    "gen_ai.tool.name": name,
                    "gen_ai.tool.call.id": call_id,
                    "args": args,
                    "matched_model_call": matched,
                    "run_id": str(run_id),
                },
                actor=self.actor,
            )
            self._tool_runs[run_id] = (name, call_id, ev["content_ref"])

    def _tool_result(self, run_id: UUID, content: Any, error: bool) -> None:
        with self._lock:
            name, call_id, call_ref = self._tool_runs.pop(run_id, ("unknown", None, None))
            self.rec.emit(
                "tool.result",
                content=message_segment("tool", content),
                content_trust="untrusted",
                inputs=[call_ref] if call_ref else [],
                trust="untrusted",
                attrs={
                    "gen_ai.tool.name": name,
                    "gen_ai.tool.call.id": call_id,
                    "error": error,
                    "run_id": str(run_id),
                },
                actor=self.actor,
            )

    def on_tool_end(
        self, output: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        content = output.content if isinstance(output, BaseMessage) else output
        if not isinstance(content, (str, list, dict)):
            content = str(content)
        self._tool_result(run_id, content, error=False)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._tool_result(run_id, f"{type(error).__name__}: {error}", error=True)
