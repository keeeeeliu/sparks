# ADR-0001: Two ingestion paths — structured feeds vs. unstructured LLM extraction

- **Status:** Accepted
- **Date:** 2026-06-23 (revised 2026-06-24)

## Context
The tool must ingest events from many media forms: pasted text, forwarded emails,
newsletters, PDFs/flyers, and websites. Building a separate end-to-end pipeline per
source would be 4–5x the work and 4–5x the maintenance.

A second realization (2026-06-24): some sources are *unstructured* (free text), but
others are *already structured* (calendar JSON/iCal feeds, where title/date/location
are discrete fields). Forcing structured data through an LLM extractor is wasteful and
*less* accurate than just reading the fields.

## Decision
Two paths, both ending in the same `Event` type:

1. **Unstructured** (paste, email, PDF, arbitrary web HTML) → normalize to a single
   `SourceItem` (plain text) → LLM grounded extractor → `Event`.
2. **Structured feeds** (LiveWhale JSON, iCal) → deterministic field mapping → `Event`
   (no LLM).

Everything downstream (dedupe / curate / draft) only ever sees `Event`, so it never
cares which path produced it. Adding a new source = one new function.

## Alternatives considered
- **One pipeline, everything through the LLM.** Rejected: wasteful + adds hallucination
  risk to data that is already clean and structured.
- **A bespoke pipeline per source.** Rejected: high duplication and maintenance cost.

## Consequences
- Clean separation; new sources are cheap to add.
- Two code paths to maintain, and a judgment call per source ("is this structured?").
- The LLM is reserved for where it adds value (unstructured text and judgment), not for
  copying fields a feed already provides.

## Implementation
`backend/ingest.py` (both paths), `backend/models.py` (`SourceItem`, `Event`),
`backend/extract.py` (unstructured path).
