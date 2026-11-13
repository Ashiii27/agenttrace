# ADR-0004: Align attributes with OpenTelemetry GenAI conventions

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

Teams already collect agent telemetry with OpenTelemetry. A private attribute vocabulary would make
AgentTrace another silo.

## Decision

Use OpenTelemetry GenAI semantic-convention names (`gen_ai.*`) in `attrs` wherever one exists, and
`agenttrace.*` only for concepts they do not cover (trust labels, segment refs, hashes). Plain HTTPS
JSON ingest comes first; an OTLP receiver comes later.

## Alternatives considered

| Option | Why not |
|---|---|
| Own vocabulary only | No interoperability with existing tracing |
| Store events purely as OTel spans | Spans have no place for the hash chain and are routinely sampled or dropped, which breaks G1 |

## Consequences

The GenAI conventions are still evolving; pin the version we follow in the schema docs and update it
deliberately.
