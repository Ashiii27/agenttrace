# Roadmap

| Phase | Weeks | Deliverable | Done when |
|---|---|---|---|
| 0 | 0 | Design, threat model, schema, ADRs, docs CI | Docs site builds strictly; schema validates |
| 1 | 1–2 | Python SDK + LangGraph adapter, local hash-chained JSONL, `verify` CLI, vulnerable demo agent | Demo attack recorded; a hand-edited log fails `verify` |
| 2 | 3–4 | Go collector: ingest, chain check, Postgres + blobs, signed checkpoints, Docker Compose | `verify` reports verified / unsealed / broken against the collector |
| 3 | 5–6 | Provenance graph, `why` (structural + lexical), ATLAS-mapped rules | Demo attack ranked top-3 by lexical layer; rule fires |
| 4 | 7–8 | Replay engine, counterfactual ablation with delta debugging (Ollama) | Demo attack ranked top-1 with ablation evidence |
| 5 | 9–10 | Web UI, incident report, MCP proxy mode, AgentDojo benchmark, demo GIF, blog post | Benchmark table published in README |

## Phase 0 checklist

- [x] Design document
- [x] Threat model with guarantees G1–G4
- [x] Event and checkpoint JSON Schemas
- [x] ADRs 0001–0005
- [x] Docs CI
- [ ] Review the open questions in the [design](design.md#6-open-questions)
- [ ] Publish the repository and enable GitHub Pages for the docs site
