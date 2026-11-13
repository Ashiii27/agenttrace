# AgentTrace

**A tamper-evident flight recorder for AI agents.**

When an agent does something it should not — emails out a file, runs a shell command, deletes data —
AgentTrace answers two questions an incident responder actually needs answered:

1. **Why did it happen?** Which input (web page, email, tool output, retrieved document) caused this
   tool call? AgentTrace traces the call back to the exact segment and confirms it by counterfactual
   replay.
2. **Can I trust this record?** Every event is hash-chained and periodically sealed with a signed
   checkpoint stored off the agent host, so edits, deletions and reordering are detectable.

> **Status:** phase 1. The Python SDK records and verifies sessions locally; the collector,
> signed checkpoints and attribution come next. See the [roadmap](docs/roadmap.md).

## Try it in one minute

```bash
pip install -e "sdk/python[langchain]"
python demo/vuln-agent/agent.py --out runs      # a hidden instruction on a web page hijacks the agent
agenttrace show   runs/s_*                      # every step after the page is marked untrusted
agenttrace verify runs/s_*                      # OK — now edit events.jsonl and run it again
```

## How it works

```text
Agent (LangGraph / MCP / raw SDK)
   │  agenttrace SDK (Python): record → hash content → chain events
   ▼
Collector (Go): verify chain → sign checkpoints → store
   ├── Postgres: events, provenance edges
   └── Blob store: prompts, documents, tool outputs (content-addressed, SHA-256)
   ▼
Analysis: `why` attribution · detection rules (MITRE ATLAS) · replay engine
   ▼
CLI + web UI: incident timeline, provenance graph, incident report
```

## Planned CLI

```bash
agenttrace verify  <session>          # check hash chain + signed checkpoints
agenttrace why     <event-id>         # rank the inputs that caused this event
agenttrace replay  <session> --policy taint.yaml   # counterfactual re-run
agenttrace report  <session> --format md           # incident report with chain of custody
```

## Documentation

Read online: **<https://ashiii27.github.io/agenttrace/>**

| Document | What it covers |
|---|---|
| [Design](docs/design.md) | Architecture, components, attribution and replay |
| [Threat model](docs/threat_model.md) | Adversaries, trust boundaries, what AgentTrace does and does not guarantee |
| [Event schema](docs/schema.md) | Event format, hashing and checkpoint rules ([JSON Schema](schema/event.schema.json)) |
| [Decisions (ADRs)](docs/adr/README.md) | Why the design is the way it is |
| [Roadmap](docs/roadmap.md) | Phases and milestones |
| [Contributing](CONTRIBUTING.md) | Dev setup and the documentation process |

## Repository layout

```text
sdk/python/        recorder, LangGraph + MCP adapters, redaction
collector/         Go: ingest, verify, checkpoint signing, storage
analysis/          why, ablation, replay, rules/ (ATLAS-mapped YAML)
ui/                React + React Flow
demo/vuln-agent/   deliberately hijackable agent + attack pages
bench/agentdojo/   evaluation harness and results
schema/            JSON Schema for events and checkpoints
docs/              design, threat model, ADRs, roadmap
```

## License

[MIT](LICENSE)
