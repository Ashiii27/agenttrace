# AgentTrace

A tamper-evident flight recorder for AI agents: it records every model call and tool call, traces a
harmful action back to the input that caused it, and proves the record was not altered.

Start here:

- [Design](design.md) — architecture and how attribution and replay work
- [Threat model](threat_model.md) — what AgentTrace guarantees, and what it does not
- [Event schema](schema.md) — the record format, hash chain and checkpoints
- [Decisions](adr/README.md) — architecture decision records
- [Roadmap](roadmap.md) — phases and status
