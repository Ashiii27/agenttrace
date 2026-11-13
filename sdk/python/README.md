# agenttrace (Python SDK)

Records an agent session as a hash-chained event log with a content-addressed blob store, and
verifies it offline.

## Install

```bash
pip install -e "sdk/python[langchain]"      # from the repository root
```

## Record a LangChain or LangGraph agent

```python
from agenttrace import Recorder
from agenttrace.adapters.langchain import AgentTraceCallbackHandler

with Recorder("runs", actor="email-assistant", attrs={"agent": "demo"}) as rec:
    handler = AgentTraceCallbackHandler(rec)
    rec.user_input(request)
    result = agent.invoke(inputs, config={"callbacks": [handler]})
```

The handler records `llm.request`, `llm.response`, `tool.call` and `tool.result` events through
LangChain callbacks, which LangGraph also uses. It is tested with a plain `langchain-core` agent
loop (see `demo/vuln-agent`); LangGraph graphs have not been tested yet.

## Record anything else

```python
with Recorder("runs") as rec:
    req = rec.emit("llm.request", content=params, content_trust="system", inputs=[seg1, seg2])
```

`Recorder.put_segment(obj, trust)` stores a piece of context and returns its `sha256:` ref.
An event's trust defaults to the lowest trust among its inputs.

## Verify and inspect

```bash
agenttrace verify runs/s_87f5075c64de8016          # exit code 1 if the chain is broken
agenttrace verify runs/s_87f5075c64de8016 --json
agenttrace show   runs/s_87f5075c64de8016
```

## What verify catches in phase 1

| Change to the record | Detected |
|---|---|
| Edit any field of an event | Yes — hash mismatch |
| Delete, insert or reorder events | Yes — sequence and chain link |
| Edit or delete a blob (prompt, page, tool output) | Yes — content hash mismatch |
| Truncate the tail | Only as a warning (no `session.end`) |
| Rewrite the whole chain from some event onward | **No** — needs signed checkpoints (phase 2) |

## Secrets

Secrets matching the patterns in `redact.py` (cloud keys, API tokens, JWTs, private keys) are
replaced with `[REDACTED:<type>:<tag>]` before anything is hashed or written. The tag is an HMAC
under a per-session key that is never stored.

## Development

```bash
pip install -e "sdk/python[langchain,dev]"
pytest sdk/python/tests demo/vuln-agent
ruff check sdk/python demo && ruff format --check sdk/python demo
python sdk/python/scripts/make_test_vectors.py   # only with a schema version bump
```
