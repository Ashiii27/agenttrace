# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Python SDK (`sdk/python`): recorder with hash-chained event log, content-addressed blob store,
  trust-label propagation and secret redaction.
- `agenttrace verify` and `agenttrace show` commands.
- LangChain callback adapter.
- Vulnerable demo agent (`demo/vuln-agent`) with a hidden-text prompt injection.
- Hashing test vectors (`schema/test-vectors/chain-v1.json`) and ADR-0006 on message segments.
- Python CI: lint, tests on Python 3.10–3.13, and the demo attack end to end.
- Design document, threat model, event schema (v1) and JSON Schemas.
- ADRs 0001–0005 covering the record format, integrity model, storage and attribution.
- Documentation CI: markdownlint, link check, schema check, strict MkDocs build.
