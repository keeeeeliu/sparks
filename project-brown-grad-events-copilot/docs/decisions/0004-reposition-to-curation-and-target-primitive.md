# ADR-0004: Reposition from "aggregator" to curation + the `Target` primitive

- **Status:** Accepted
- **Date:** 2026-06-24

## Context
A fair challenge: if `events.brown.edu` already lists essentially all events, is an
"event aggregator" even needed?

## Evidence
From a 300-event sample of the live feed:
- The calendar is a comprehensive **listing** but is **not curated for grad students**:
  only **1 of 300** events carried any "grad" signal in group/type.
- Audience/category tags are crude and under-applied (e.g. `Open to the Public` 107,
  `Free Food` 5, `Social/Study Break` 2).
- Raw volume is overwhelming for a reader: ~1,161 events / 233 pages.

## Decision
Reframe the project. The work has three distinct jobs; the calendar only solves one:
1. **Aggregation** (gather) — largely solved by the feed.
2. **Curation** (decide what's relevant to grad students) — NOT solved by the calendar.
3. **Production** (write the voiced, formatted newsletter) — NOT done by the calendar.

The product's center of gravity is **curation + generation**, with the feed as the
primary structured input. Introduce one unifying primitive:

**`Target`** = a saved "what I'm looking for" (audience + categories + departments +
keywords + date range + min_relevance). The engine is `(enriched events) × Target →
ranked list`. The same primitive powers:
- a newsletter **section** (one Target per section / section owner),
- an agent **query** ("social events for grad students in July" → an ad-hoc Target),
- a scheduled **notification** (a Target on a timer),
- **personalization** (each user saves their own Targets).

## Scope discipline
Build the **enrichment + Target-filter core first** (it is simultaneously the newsletter
engine and the agent-query engine). Defer multi-user accounts, notifications, and the
natural-language-query agent layer until the core is trusted.

## Alternatives considered
- **Shelve the project** (calendar is "good enough"). Rejected: the calendar provides no
  grad curation and no digest; the team already chooses to send a curated newsletter,
  evidencing demand for a digest over a database.
- **Stay framed as a multi-source aggregator.** Demoted: aggregation is mostly solved;
  it's now a secondary input feature, not the core value.

## Consequences
- Clear, defensible value (curation + generation) and a stronger agentic portfolio story.
- Open question to validate with a real cycle: where does newsletter time actually go
  (gathering vs. judging vs. writing)? The design bets on "judging + writing."

## Implementation
`backend/models.py` (`Target`, enrichment fields on `Event`), `backend/curate.py`
(`enrich_event`, `filter_by_target`).
