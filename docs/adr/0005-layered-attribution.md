# ADR-0005: Layered attribution — structural, lexical, counterfactual

- **Status:** Accepted
- **Date:** 2026-11-13

## Context

`agenttrace why` must name the input that caused an event. Options range from free (graph traversal)
to expensive (re-running the model many times). An LLM judge is cheap but can be fooled by the same
injection it is judging.

## Decision

Run three layers in order and report which layer produced each result:

1. **Structural** — reverse graph traversal; complete but coarse.
2. **Lexical** — fuzzy overlap between event arguments and candidate segments.
3. **Counterfactual ablation** — remove segments and re-run the producing model call, searching with
   delta debugging; temperature 0, *m* samples per run; report probabilities.

Ablation runs only on demand or on rule-flagged events. An LLM judge may be added later for display
only, never as evidence.

## Alternatives considered

| Option | Why not |
|---|---|
| LLM judge as the attribution method | Vulnerable to the injection being investigated; not evidence |
| Gradient / attention-based attribution | Needs model weights; does not work with hosted APIs |
| Ablate one segment at a time | *O(n)* model calls; delta debugging needs ≈ *O(k log n)* |

## Consequences

- Attribution results carry a confidence and the model version used; a provider model update can change
  the answer, so reports record the replay date.
- Cost is controlled by running ablation on local models (Ollama) during development.
- Injections split over several segments (A8) appear as a causal *set*; the evaluation must cover them.
