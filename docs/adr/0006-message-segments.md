# ADR-0006: Message segments are canonical role + content

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

The provenance graph is linked by content hashes: a tool result must be recognisable when it
reappears inside the next model request. Frameworks attach volatile metadata to messages
(message IDs, timestamps, token counts, provider fields) that changes between the moment a result is
produced and the moment it is sent back to the model.

## Decision

A message segment is the JCS encoding of `{"role", "content"}`, plus `"tool_calls"` as a list of
`{"name", "args"}` for assistant messages. Roles are `system`, `user`, `assistant` and `tool`.
Nothing else from the framework message is hashed. Redaction is applied before encoding.

A tool result is stored as a `tool` message segment, so the `tool.result` event and the matching
message in the next `llm.request` share one `content_ref`.

## Alternatives considered

| Option | Why not |
|---|---|
| Hash the framework's full serialised message | IDs and metadata differ between the result and the replayed message, so links break |
| Hash raw text only | Loses the role, so a tool output and a user message with the same text would collide and share a trust label |
| Link by tool-call ID | Not every framework or model provides IDs, and IDs can be spoofed by the model output |

## Consequences

- Two identical tool outputs in one session share a segment. The recorder then keeps the lowest
  trust label it has seen for that segment, which is the safe direction.
- Tool-call IDs are still recorded in `attrs` for display, but are not part of the link.
