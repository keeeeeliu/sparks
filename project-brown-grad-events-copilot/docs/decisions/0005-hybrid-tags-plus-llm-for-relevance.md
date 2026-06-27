# ADR-0005: Hybrid — source tags as features + LLM judgment for grad-relevance

- **Status:** Accepted
- **Date:** 2026-06-24

> Full source characterization + reproducible numbers: [data card](../data-sources/livewhale.md)
> (`python scripts/profile_livewhale.py`).

## Context
The Brown calendar *does* have structured tags (host department, event type, audience
group, topical tags). This raised the question: can we filter on tags alone and skip the
LLM for relevance? We measured tag coverage and vocabulary on the live feed before deciding.

## Evidence
Coverage across a 300-event sample:

| Field | Populated | Notes |
|---|---|---|
| `group_title` (host/department) | **100%** | always present, reliable |
| `tags` (topical) | **~80%** | e.g. `["Entrepreneurship"]` |
| `event_types` (type) | **~51%** | crude buckets |
| `event_types_audience` (audience) | **30% (summer)** | see vocabulary below |
| `event_types_campus` | **0%** | unused at Brown |

Audience tag vocabulary (400+ events): `1st–4th Year Students`, `Medical Students`,
`Campus/Hospital Faculty`, `All Staff`, academic divisions (`Humanities`, `Social
Sciences`, `Life Sciences`, `Physical Sciences`). **There is NO "graduate" audience
value — 0 grad-tagged events in 627 sampled.** A mid-semester window (Oct–Nov, 227
events) had audience tags on **~0%** of events.

Conclusion: the tags reliably answer **department / type / topic**, but **cannot answer
"is this relevant to a grad student?"** — there is no grad audience value, and audience
tagging collapses to near-zero during the school year.

### Follow-up finding (2026-06-24): audience tags are partly department defaults
While manually verifying one event (Joukowsky "Divine Afterlife" exhibit), the public web
page showed **no** audience, yet the API's `event_types_audience` listed 10 values
(1st–4th Year Students, Faculty, Staff, Medical Students, divisions). Investigation: a
**different** Joukowsky exhibit ("Scents of the Ancient Past") carries the **identical**
10-value set. Identical sets across unrelated events = a tag applied **department-wide as a
default**, not curated per event (also: Brown's public event page doesn't render this field,
so the API exposes more than the UI). Therefore `event_types_audience` is unreliable even as
a *hint*, and could mislead the model.

## Decision
Use a **hybrid**:
- **Deterministic on well-covered dimensions** — `Target` filters on `host_org`
  (department, 100%) and topical tags/keywords (~80%) directly, no LLM.
- **LLM judgment for grad-relevance and audience** — `enrich_event` reads the prose to
  infer `audience` + `grad_relevance`, since the tags structurally can't. The **reliable**
  tags (host, type, topic) are passed into the prompt as features/hints; **`audience_tags`
  are NOT passed** (department-default noise — see follow-up finding above). This covers the
  50–70% of events that lack tags while avoiding misleading the model.

This *reinforces* the LLM layer rather than replacing it (corrects the earlier momentary
assumption that tags might make the LLM unnecessary for relevance).

## Alternatives considered
- **Tags only, no LLM for relevance.** Rejected by the evidence: no grad audience value;
  sparse mid-semester coverage.
- **LLM only, ignore tags.** Rejected: wastes reliable 100%-coverage signal (department)
  and makes relevance judgments less grounded and more expensive.

## Consequences
- Cheap, reliable filtering where tags are good; LLM judgment where they aren't.
- Enrichment quality depends on description quality; events with empty descriptions get
  weaker relevance signal (a known limitation to watch in eval).

## Implementation
`backend/models.py` (`Event.audience_tags`, `Target.departments`), `backend/ingest.py`
(maps `event_types_audience`), `backend/curate.py` (tags fed into `enrich_event` prompt;
`_department_matches` in `filter_by_target`).
