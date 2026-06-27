# Architecture Decision Records (ADRs)

This folder is the **canonical record of *why* the project is built the way it is.**

Each ADR captures one significant decision with its evidence and trade-offs, so a
future maintainer can understand the reasoning — and reverse it knowingly if the
context changes. Decisions are **dated, numbered, and immutable**: instead of
editing an old ADR, add a new one that supersedes it.

### Where things live (doc map)
- **`README.md`** (project root) — what the project is and how to use it (current state).
- **`PROGRESS.md`** (project root) — operational running log: status, what's built, concerns, assumptions.
- **`docs/decisions/`** (here) — the *why* behind decisions, with evidence. The durable decision history.
- **`docs/data-sources/`** — *data cards*: facts/caveats about external data sources (ADRs cite these).

### ADR format
Each record has: **Context → Decision → Evidence → Alternatives considered → Consequences → Status.**

### Index
| # | Decision | Status |
|---|---|---|
| [0001](0001-normalized-ingestion-two-paths.md) | Two ingestion paths: structured feeds vs. unstructured LLM extraction | Accepted |
| [0002](0002-brown-calendar-via-livewhale-feed.md) | Use the LiveWhale JSON feed for Brown's calendar, not HTML scraping | Accepted |
| [0003](0003-grounded-anti-hallucination-extraction.md) | Grounded extraction + provenance + repair retry (anti-hallucination) | Accepted |
| [0004](0004-reposition-to-curation-and-target-primitive.md) | Reposition from "aggregator" to curation + the `Target` primitive | Accepted |
| [0005](0005-hybrid-tags-plus-llm-for-relevance.md) | Hybrid: source tags as features + LLM judgment for grad-relevance | Accepted |
| [0006](0006-concurrent-per-event-enrichment.md) | Concurrent per-event enrichment (not single-prompt batching) | Accepted |
