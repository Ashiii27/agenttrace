# Threat model

Status: **Draft v0.1** · Last updated: 2026-11-13

## 1. What AgentTrace protects

| Asset | Property |
|---|---|
| The event record of a session | Integrity: no undetected edit, deletion, insertion or reordering |
| Recorded content (prompts, documents, tool outputs) | Confidentiality: it often contains personal data and business data |
| Signing keys of the collector | Secrecy: they anchor every integrity claim |
| Attribution results | Honesty: confidence must be stated, never implied |

## 2. Guarantees

These are the claims the project makes. Every component must say which ones it can break.

- **G1 — Sealed integrity.** For every event covered by a valid signed checkpoint, any modification,
  deletion, insertion or reordering is detected by `agenttrace verify`.
- **G2 — Visible unsealed tail.** Events after the last checkpoint are reported as *unsealed*, never
  as verified. The size of this window is bounded by the checkpoint interval.
- **G3 — Candidate completeness.** Given faithful recording, the structural candidate set for an
  event contains every segment that was in the producing context window.
- **G4 — Secrets stay local.** Content matching a redaction rule is replaced before hashing and
  never leaves the agent process.

## 3. Trust boundaries

```text
 untrusted content ─▶ [ agent process + SDK ] ─HTTPS─▶ [ collector ] ─▶ [ Postgres / blobs ]
                     ^ boundary A              ^ boundary B         ^ boundary C
```

- **A:** external content enters the agent. Expected to be hostile; AgentTrace records it, labels it
  `untrusted`, and does not try to sanitise it.
- **B:** the collector trusts nothing from the agent host except "these bytes arrived at this time".
- **C:** storage is assumed readable and writable by an insider; integrity rests on checkpoints, not
  on database permissions.

## 4. Adversaries

| ID | Adversary | Capability | In scope? | Mitigation |
|---|---|---|---|---|
| A1 | Prompt injector | Controls a web page, email or document the agent reads | Yes — **to attribute**, not to prevent | Trust labels, `why`, ATLAS rules |
| A2 | Post-incident host attacker | Gains code execution on the agent host after the incident and rewrites local logs | Yes | Events leave the host immediately; checkpoints signed and stored on the collector (G1, G2) |
| A3 | Insider with database access | Edits, deletes or reorders rows in Postgres or blobs | Yes | Hash chain + signed checkpoints; blobs are content-addressed so any change breaks the hash |
| A4 | Collector key thief | Steals the Ed25519 signing key | Partly | Key in a separate file/KMS, key IDs in checkpoints, rotation; optional external transparency log makes back-dated re-signing visible |
| A5 | Pre-incident host attacker | Controls the agent process before events are emitted | **No** for in-process mode | MCP proxy mode records out of process; documented limitation |
| A6 | Log reader | Gains read access to stored content | Yes | Redaction in SDK (G4), encryption at rest, retention limits |
| A7 | Collector flooder | Sends junk sessions or huge blobs | Yes | Per-client auth tokens, size limits, rate limits |
| A8 | Attribution gamer | Crafts injections spread over many segments to dilute attribution | Yes — measured | Delta debugging finds sets of segments, not only single ones; report this case in evaluation |

## 5. STRIDE pass on the collector

| Threat | Example | Control |
|---|---|---|
| Spoofing | Fake agent sends events for another session | Per-agent token bound to a session prefix |
| Tampering | Edit an event in transit | TLS; hash recomputed on ingest |
| Repudiation | "That event was never sent" | Signed checkpoints with receive timestamps |
| Information disclosure | Blob store bucket exposed | Encryption at rest, no public access |
| Denial of service | Oversized blobs | Size and rate limits; spooling on the SDK side |
| Elevation of privilege | Replay executes a real tool | Replay refuses any unrecorded tool call |

## 6. Known limitations

- A pre-incident compromise of the agent process (A5) can make the record lie from the start.
- Attribution reflects behaviour of the model *at replay time*; provider model updates can change it.
  Reports must record model version and replay date.
- Redaction is pattern-based and will miss secrets in unusual formats.
