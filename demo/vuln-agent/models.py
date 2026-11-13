"""Models for the demo.

``scripted`` is a deterministic stand-in for a model that obeys instructions found in tool output.
It makes the demo reproducible in CI with no API key. It is a simulation: use ``ollama:<model>`` or
``groq:<model>`` to see whether a real model falls for the same page.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

URL_RE = re.compile(r"https?://\S+[^\s.,)]")
INJECTION_RE = re.compile(
    r"forward\s+(?:the\s+)?(?:latest\s+)?invoice\s+to\s+([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", re.I
)


def _last_tool(messages: list[BaseMessage], name: str) -> ToolMessage | None:
    for m in reversed(messages):
        if isinstance(m, ToolMessage) and m.name == name:
            return m
    return None


class NaiveScriptedModel(BaseChatModel):
    """Follows the user's request, and also any 'forward the invoice to X' found in tool output."""

    @property
    def _llm_type(self) -> str:
        return "naive-scripted"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": "naive-scripted-v1"}

    def bind_tools(self, tools: Any, **kwargs: Any) -> NaiveScriptedModel:
        return self

    def _call(self, name: str, n: int, **args: Any) -> AIMessage:
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{n}"}])

    def _decide(self, messages: list[BaseMessage]) -> AIMessage:
        n = sum(isinstance(m, AIMessage) for m in messages)
        page = _last_tool(messages, "fetch_url")
        if page is None:
            url = URL_RE.search(str(messages[-1].content))
            if url:
                return self._call("fetch_url", n, url=url.group(0))
            return AIMessage(content="Please give me a URL to summarise.")

        target = INJECTION_RE.search(str(page.content))
        inbox = _last_tool(messages, "read_inbox")
        sent = _last_tool(messages, "send_email")
        if target and inbox is None:
            return self._call("read_inbox", n, limit=1)
        if target and inbox is not None and sent is None:
            invoice = json.loads(str(inbox.content))[0]
            return self._call(
                "send_email",
                n,
                to=target.group(1),
                subject=f"Fwd: {invoice['subject']}",
                body=invoice["body"],
            )
        return AIMessage(
            content="Summary: paper prices rise 4% and toner 2.5% from 1 December; invoices "
            "move to the 1st of the month. No action needed if you pay by direct debit."
        )

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kw: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._decide(messages))])


def load_model(spec: str) -> BaseChatModel:
    if spec == "scripted":
        return NaiveScriptedModel()
    provider, _, name = spec.partition(":")
    if provider == "ollama" and name:
        from langchain_ollama import ChatOllama

        return ChatOllama(model=name, temperature=0)
    if provider == "groq" and name:
        from langchain_groq import ChatGroq

        return ChatGroq(model=name, temperature=0)
    raise SystemExit(f"unknown model {spec!r}: use scripted, ollama:<name> or groq:<name>")
