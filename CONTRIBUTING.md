# Contributing

## Documentation process

AgentTrace is a security tool, so its guarantees have to be written down before they are coded.
The rule is simple: **docs change in the same pull request as the behaviour they describe.**

### Where things go

| You are… | Update |
|---|---|
| Changing the event format, hashing or checkpoint rules | [`docs/schema.md`](docs/schema.md) **and** [`schema/event.schema.json`](schema/event.schema.json) |
| Making a choice someone will later ask "why?" about | A new ADR in [`docs/adr/`](docs/adr/README.md) |
| Adding a component, trust boundary or data flow | [`docs/design.md`](docs/design.md) and [`docs/threat_model.md`](docs/threat_model.md) |
| Shipping a milestone | [`docs/roadmap.md`](docs/roadmap.md) and [`CHANGELOG.md`](CHANGELOG.md) |

### Writing an ADR

1. Copy [`docs/adr/0000-template.md`](docs/adr/0000-template.md) to the next number,
   e.g. `0006-short-title.md`.
2. Fill in context, decision, alternatives and consequences. Keep it under a page.
3. Add it to the index in [`docs/adr/README.md`](docs/adr/README.md).
4. ADRs are never edited after they are accepted. To change a decision, write a new ADR and mark
   the old one `Superseded by ADR-NNNN`.

### Threat model changes

Every new component must answer, in `docs/threat_model.md`: what does it trust, what can an attacker
who controls it do, and which guarantee (G1–G4) could it break?

### Checks

CI runs on every pull request that touches docs:

- `markdownlint` — consistent Markdown style ([`.markdownlint.yaml`](.markdownlint.yaml))
- `lychee` — no broken links
- `check-jsonschema` — the event schema is valid JSON Schema
- `mkdocs build --strict` — the docs site builds with no warnings

Run them locally:

```bash
pip install -r docs/requirements.txt
mkdocs serve                     # preview at http://127.0.0.1:8000
mkdocs build --strict
check-jsonschema --check-metaschema schema/event.schema.json schema/checkpoint.schema.json
```

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat(sdk): …`, `fix(collector): …`,
`docs(adr): …`.
