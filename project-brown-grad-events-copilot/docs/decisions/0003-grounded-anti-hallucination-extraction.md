# ADR-0003: Grounded extraction + provenance + repair retry (anti-hallucination)

- **Status:** Accepted
- **Date:** 2026-06-23

## Context
The unstructured path uses an LLM to turn free text into structured `Event`s. LLMs can
invent dates, locations, or whole events. For a tool that goes out under Brown's name,
fabricated event details are unacceptable. We need extraction we can *trust and verify*.

## Decision
Five layered defenses on the unstructured extraction path:

1. **Grounded prompt** — extract only what is literally in the source; if a field isn't
   stated, return `null`; never infer or invent.
2. **Provenance** — every event must carry a verbatim `evidence` quote + `source_ref`.
3. **Schema validation** — output is validated against Pydantic; malformed/invented
   shapes fail.
4. **Repair retry** — on a parse/validation failure, feed the error back to the model
   once for self-correction; if it fails again, raise (loud failure > silent garbage).
5. **Evidence verifier** — drop any event whose `evidence` snippet is not actually found
   in the source text (whitespace/case-normalized containment).

Schema choice supporting this: most `Event` fields are `Optional` so "unknown" is
representable as `null` instead of forcing the model to fabricate a value.

## Evidence
- Verifier behaves as intended: a real quote passes; a fabricated quote
  ("free pizza at midnight") is rejected.

## Alternatives considered
- **Trust the model + temperature 0.** Insufficient alone; provides no verifiability.
- **A heavy framework (e.g. instructor).** Rejected for now: hand-rolled is transparent
  and good for learning/portfolio.

## Consequences
- Strong, verifiable extraction; provenance enables human spot-checking and future eval.
- The evidence check is *containment*, not semantics — it catches fabricated quotes, not
  a real-but-misattributed quote. The eval harness (planned) is the deeper backstop.

## Implementation
`backend/extract.py` (prompt, repair retry, `_evidence_in_source`), `backend/models.py`
(`Event` provenance fields).
