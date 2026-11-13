# ADR-0002: Hash chain per session with collector-signed checkpoints

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

Guarantee G1 requires detecting any edit, deletion, insertion or reordering of recorded events.
Adversary A2 can take over the agent host after an incident, and A3 can write to the database.
A hash chain alone fails against A2: whoever holds the whole chain can recompute it from genesis.

## Decision

1. The SDK chains each session's events: `hash_i = SHA256(prev_hash || JCS(event_i))`.
2. Events are sent off the agent host as soon as possible.
3. The **collector** — not the agent — signs checkpoints over the session head with Ed25519 every
   50 events or 5 seconds, and stores them separately from events.
4. Checkpoints can optionally be published to an external transparency log.

## Alternatives considered

| Option | Why not |
|---|---|
| Hash chain only | Rewritable end to end by A2 |
| Agent signs each event | The key lives on the host A2 controls |
| Merkle tree per session | Gives efficient inclusion proofs we do not need yet; a chain is simpler to verify and explain. Revisit for very long sessions |
| Append-only database / WORM storage | Depends on the operator's infrastructure; does not protect against A3 with admin rights |

## Consequences

- Events after the last checkpoint are only "unsealed" (G2). The checkpoint interval is a trade-off
  between collector load and the size of that window.
- Collector key management becomes critical (A4).
- Canonical JSON (RFC 8785) must be implemented identically in Python and Go — needs shared test
  vectors from phase 1.
