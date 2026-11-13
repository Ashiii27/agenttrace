# Design

Status: **Draft v0.1** · Last updated: 2026-11-13

## 1. Problem

LLM agents read untrusted content (web pages, emails, tool outputs, retrieved documents) and act on
it with real tools. When an agent is hijacked by an indirect prompt injection, today's tooling shows
*what* the agent did, but not:

- **which input caused it** — the context window held 40 segments; which one carried the attack?
- **whether the record is trustworthy** — logs on a compromised host can be rewritten.

Incident responders need both before they can scope an incident, notify anyone, or fix the agent.

## 2. Goals and non-goals

### Goals

1. Record every model call, tool call, tool result, retrieval and user input of an agent session,
   with the full content each step saw.
2. Make the record **tamper-evident** (see [threat model](threat_model.md), G1–G2).
3. Attribute a chosen event to the input segments that caused it, with a stated confidence.
4. Replay a session exactly, or counterfactually (one variable changed), without running real tools.
5. Detect known-bad agent behaviour with rules mapped to MITRE ATLAS.
6. Produce an incident report with chain of custody.

### Non-goals

- **Prevention.** AgentTrace observes; it does not block. (A taint-tracking policy engine is a
  separate, later project that will consume AgentTrace's trust labels.)
- **Recording agents that bypass the SDK.** If the agent process is compromised *before* events are
  emitted, nothing in-process can help. MCP proxy mode (phase 5) records out of process to narrow
  this gap.
- Model interpretability. Attribution is behavioural (what changes the output), not mechanistic.

## 3. Architecture

```text
┌──────────────── agent host ────────────────┐        ┌──────────── collector host ────────────┐
│ Agent ──▶ agenttrace SDK                   │        │ Collector (Go)                         │
│            • capture events                │ HTTPS  │  • verify chain on ingest              │
│            • redact secrets                │──────▶ │  • sign checkpoints (Ed25519)          │
│            • hash content, chain events    │        │  • Postgres: events, edges, checkpoints│
│            • local spool if offline        │        │  • Blob store: content by SHA-256      │
└────────────────────────────────────────────┘        └───────────────┬────────────────────────┘
                                                                      │
                                       Analysis: why · rules · replay · report
                                                                      │
                                                       CLI  ·  Web UI (timeline + graph)
```

The trust boundary that matters is between the two hosts: the collector must not trust the agent host
beyond "these bytes arrived at this time" ([ADR-0002](adr/0002-hash-chain-with-signed-checkpoints.md)).

## 4. Components

### 4.1 SDK (Python)

- **Adapters:** LangGraph/LangChain callback handler first; thin wrappers for the OpenAI-compatible
  and Anthropic clients; MCP proxy mode later (reusing mcpguard's transport code).
- **Segmentation:** every piece of content entering a context window is split into *segments*
  (one message, one retrieved chunk, one tool result). Each segment is stored once, addressed by
  `sha256` of its bytes. Segments are the unit of attribution.
- **Trust labels:** each segment gets `system`, `user` or `untrusted` from its source
  (see [schema](schema.md#3-trust-labels)). Model outputs inherit the lowest trust of their inputs.
- **Redaction:** secret patterns are replaced with `[REDACTED:<type>:<hmac-prefix>]` *before*
  hashing, so the hash commits to the redacted text and secrets never leave the process.
- **Chaining:** the SDK computes `hash` per event ([schema §4](schema.md#4-hash-chain)). If the
  collector is unreachable, events are spooled to disk and sent in order later.

### 4.2 Collector (Go)

- Ingest over HTTPS (JSON) first; OTLP later ([ADR-0004](adr/0004-otel-genai-semantic-conventions.md)).
- On ingest: validate schema, recompute the hash, check `seq` is contiguous and `prev_hash` matches
  the stored head. A mismatch is stored as a **chain break** event, never silently dropped.
- Every `N` events or `T` seconds (default 50 events / 5 s), sign a checkpoint over the session head.
  Optionally publish checkpoints to an external transparency log.
- Storage: Postgres for events, edges and checkpoints
  ([ADR-0003](adr/0003-postgres-for-provenance-graph.md)); blobs on disk or MinIO, encrypted at rest.

### 4.3 Provenance graph

Nodes are segments and events. Edges:

| Edge | Meaning |
|---|---|
| `in_context(segment → llm.request)` | segment was in the context window |
| `produced(llm.response → tool.call)` | the model output requested this tool call |
| `returned(tool.call → segment)` | the tool result became a new segment |
| `derived(segment → segment)` | e.g. a summary written from a page |

"Which inputs could have caused event *E*" is a reverse traversal from *E* — a recursive CTE.

### 4.4 Attribution — `agenttrace why <event>`

Three layers, cheapest first ([ADR-0005](adr/0005-layered-attribution.md)):

1. **Structural** — candidate set = all segments reachable backwards from *E*. Complete (contains
   the true cause, given faithful recording) but coarse.
2. **Lexical** — rank candidates by fuzzy overlap between *E*'s arguments and segment text
   (e.g. the recipient address appears in a web page).
3. **Counterfactual ablation** — re-run the producing model call with candidate segments removed;
   a segment is causal if removing it makes *E* disappear or change. Uses delta debugging over
   segments (≈ *O(k log n)* model calls for *k* causal segments among *n*), temperature 0 and
   *m* samples per run; reports `P(E | segment present)` vs `P(E | segment removed)`.

Output: ranked segments with layer, score and evidence. Ablation only runs on demand or on
rule-flagged events, because it costs model calls.

### 4.5 Replay

- **Exact replay** feeds recorded model responses and tool results back through the agent graph and
  checks every step matches — a consistency check on the recording.
- **Counterfactual replay** changes one variable (model, system prompt, removed segment, policy)
  and calls the real model, while tools return recorded results. A tool call with no recording is
  **refused**, never executed. Output is a step-by-step diff.

### 4.6 Detection rules

Sigma-style YAML over events, each mapped to MITRE ATLAS technique IDs. Examples:

- `send_email` whose recipient domain never appears in any `user` segment.
- `shell` or `write_file` within 2 steps of an `untrusted` `fetch_url` result.
- A tool call whose arguments contain text from an `untrusted` segment verbatim.

### 4.7 Interfaces

CLI first (`verify`, `why`, `replay`, `report`), then a React UI: incident timeline, provenance graph
(React Flow), counterfactual diff view, and an integrity badge per session.

## 5. Evaluation

Measured on AgentDojo and the demo agent:

| Metric | Definition |
|---|---|
| Attribution top-1 | share of successful injections where the injected segment ranks first, per layer |
| Overhead | added latency per event (p50/p99) and storage per session |
| Tamper detection | random edit / delete / insert / reorder of stored events; `verify` must catch 100 % of covered events |
| Ablation cost | model calls and tokens per `why` |

## 6. Open questions

- How to segment very long single tool outputs (one 30 KB web page) without losing the
  injection boundary — sentence-level sub-segments only during ablation?
- Multi-agent sessions: one chain per agent with cross-links, or one chain per session?
- How much of the nondeterminism in counterfactual replay can be removed by provider seeds?
