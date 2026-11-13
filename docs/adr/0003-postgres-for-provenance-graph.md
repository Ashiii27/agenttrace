# ADR-0003: Postgres (not a graph database) for the provenance graph

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

Attribution needs reverse traversal from an event to every segment that could have influenced it.
Sessions are small graphs (hundreds to low thousands of nodes). Events, checkpoints and edges must be
stored transactionally together.

## Decision

Store events, edges and checkpoints in Postgres. Traverse with recursive CTEs. Store raw content in a
separate content-addressed blob store (local disk, later MinIO), referenced by `sha256:` hash.

## Alternatives considered

| Option | Why not |
|---|---|
| Neo4j or another graph database | A second database to run and secure for graphs that are small; no transactional link to the events table |
| SQLite | Fine for phase 1 local mode, but weak for concurrent multi-agent ingest |
| Content inside Postgres rows | Bloats the database, and blobs need separate encryption and retention rules |

## Consequences

One database to operate. If cross-session queries ("every session that read this page") become slow,
add indexes on `inputs` or revisit a graph store with a new ADR.
