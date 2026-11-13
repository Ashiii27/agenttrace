# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

AgentTrace makes security claims (see the [threat model](../threat_model.md)). Reviewers and future
contributors need to know why the integrity model, storage and attribution look the way they do,
not only what the code does.

## Decision

Keep short, numbered, immutable architecture decision records in `docs/adr/`. A changed decision gets
a new ADR that supersedes the old one.

## Alternatives considered

| Option | Why not |
|---|---|
| Decisions only in the design doc | The design doc shows the current state, and loses the rejected options and reasons |
| Decisions in issues / PR threads | Hard to find, not versioned with the code |

## Consequences

Every significant change costs one extra page of writing. In return, the reasoning behind every
security-relevant choice is reviewable.
