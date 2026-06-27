# ADR-0006: Concurrent per-event enrichment (not single-prompt batching)

- **Status:** Accepted
- **Date:** 2026-06-27

## Context
Curation enriches each event with one LLM call (audience, grad_relevance, reasoning, etc.).
A full deduped month is ~100+ events, so the batch's wall-clock time matters for a usable
tool. Two questions arose:
1. Should we send **one call per event**, or cram many events into **one big prompt**?
2. If we keep per-event calls, they were running **sequentially** — can we make that faster?

We wanted the decision backed by a measurement, not intuition (measure before optimizing).

## Decision
- **Keep one LLM call per event** (do NOT batch many events into a single prompt).
- **Run those per-event calls concurrently** with a thread pool (I/O-bound HTTP), default
  `max_workers=8`, preserving input order and per-item error isolation. `max_workers=1`
  remains available as a sequential baseline.

## Evidence
Controlled A/B on the **same** full deduped July month (105 unique events), same code path,
run back-to-back to minimize API time-of-day variance (`run_curate.py --month 2026-07 --max 110`):

| Mode | Total | Per-event |
|---|---|---|
| `--workers 1` (sequential) | **206.9s** | 1.97s |
| `--workers 8` (concurrent) | **27.4s** | 0.26s |

**~7.5× speedup** — far outside the ~25% run-to-run variance previously observed on sequential
runs (166.6s vs 208.8s on identical input), so the improvement is real, not noise.

Cost is ~unchanged: OpenAI bills per token, not per call; concurrency changes *when* calls
happen, not how many tokens are sent.

## Alternatives considered
- **Single prompt with all N events.** Rejected: large batches make models skip/merge events,
  misalign outputs to the wrong event, or truncate at the output-token limit; one malformed
  JSON breaks the whole batch and the repair retry re-runs everything. This directly undermines
  the project's grounding/anti-hallucination posture (ADR-0003). Token savings (system prompt
  sent once) are negligible on `gpt-4o-mini`.
- **Mini-batches (5–10 events/call).** Rejected for now: a middle ground that reintroduces some
  alignment/robustness risk for modest gain over concurrency, which already solves the latency.
- **Async (asyncio) client.** Viable, but a thread pool over the existing sync client is simpler
  and sufficient for an I/O-bound workload at this scale.

## Consequences
- Full-month enrichment drops from ~3.5 min to ~30s → the tool feels interactive; cheap to re-run.
- Per-event accuracy, evidence attribution, and per-item failure isolation are all preserved.
- New knob to respect provider **rate limits**: if a higher tier or a larger model hits limits,
  lower `--workers`. (At 8 concurrent on `gpt-4o-mini` no limiting was observed.)
- Thread logs can interleave; acceptable for a CLI.

## Implementation
`backend/curate.py` (`enrich_events(events, *, max_workers=8)` via `ThreadPoolExecutor`,
`_safe_enrich` for isolation), `run_curate.py` (`--workers` flag; default 8).
