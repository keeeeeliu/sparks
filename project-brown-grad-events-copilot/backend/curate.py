"""Curation: turn a pile of events into a targeted, ranked list.

Two stages, mirroring the "facts vs judgment" split:

1. enrich_event() — the JUDGMENT stage (LLM). Facts (title/date/location) already
   came from the source. Here we READ the description to infer what isn't a
   structured field: `audience`, `grad_relevance`, `category`, `tags`. Same
   grounding discipline as extraction — infer only from the text; if the audience
   isn't stated, say ["unspecified"] rather than guessing.

2. filter_by_target() — the SELECTION stage (deterministic, no LLM). Given enriched
   events and a `Target` (a saved "what I'm looking for"), return the matching,
   ranked subset. This one engine powers newsletter sections, agent queries, and
   notifications — they only differ by which Target they pass in.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from pydantic import BaseModel, Field, ValidationError

from .llm import complete_json
from .models import Event, Target


# ---------------------------------------------------------------------------
# Stage 1: enrichment (LLM judgment)
# ---------------------------------------------------------------------------

class _Enrichment(BaseModel):
    audience: list[str] = Field(default_factory=lambda: ["unspecified"])
    audience_evidence: str | None = None
    grad_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_reasoning: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


_ENRICH_SYSTEM = """You curate a single university event for a GRADUATE-STUDENT newsletter whose
goal is a WELL-ROUNDED student life — not only career and academics, but also social connection,
community & belonging, wellness/mental health, arts & culture, and simply fun things to do.

You are given the event's title, description, and a few structured hints from the source
calendar (host department, event type, topic tags). Use BOTH the prose and these hints, but
judge AUDIENCE and grad-relevance mainly from the prose/title — the calendar's own audience
tags are unreliable (often applied as department-wide defaults) and are deliberately withheld.

Return a single JSON object:
{
  "audience": [str],          // who it's for. Use "graduate" for general grad-student-facing events.
                              // ALSO add "masters" if the event EXPLICITLY targets master's /
                              // professional master's students (MA, MS, MPH, MBA, etc.), and
                              // "doctoral" if it EXPLICITLY targets PhD/doctoral students.
                              // Whenever you include "masters" or "doctoral", also include "graduate".
                              // Other values: "undergraduate", "faculty", "staff", "all".
                              // e.g. ["graduate","masters"], ["graduate"], ["undergraduate","graduate"], ["all"].
                              // If neither text nor tags state an audience, return ["unspecified"].
  "audience_evidence": str|null,  // verbatim snippet (from description or a tag) you used; null if unspecified.
                              // If you tagged "masters"/"doctoral", quote the phrase that justifies it.
  "grad_relevance": float,    // 0-1: how VALUABLE or ENRICHING this event is for a graduate
                              // student's life, interpreted BROADLY. A great social mixer, a
                              // hands-on creative workshop, a wellness session, or a fun cultural
                              // event can score JUST AS HIGH as a career talk. Do NOT down-rank an
                              // event merely for being social, creative, recreational, or "just fun".
                              // Reason about who would actually enjoy or benefit, then score:
                              //   0.8-1.0  broadly appealing/valuable to many grad students
                              //            (strong talk, funding/career help, welcoming social or
                              //            community event, hands-on workshop, wellness program,
                              //            notable arts/cultural event open to grads).
                              //   0.4-0.7  relevant but niche, or open-to-all with moderate appeal.
                              //   0.1-0.3  mostly administrative/logistical or aimed elsewhere
                              //            (building access, room bookings, undergrad-only orientation).
                              //   0.0      not a real event for people (holiday notices, closures).
  "relevance_reasoning": str|null,  // ONE short sentence: why this score / who would value it.
  "category": str|null,       // one of: career, social, academic, wellness, arts, professional, other
  "tags": [str]               // a few short topical tags
}
Rules: never invent an audience that isn't supported by the text or tags. Only use "masters"/"doctoral"
when the degree level is explicitly stated — do NOT guess it from a department name. Output ONLY the JSON object."""


def enrich_event(event: Event) -> Event:
    """Add audience/relevance/category/tags from description + source tags. One repair retry."""
    # NOTE: audience_tags are intentionally NOT passed — they're unreliable department
    # defaults (see ADR-0005). Only host/type/topic tags + prose are given to the model.
    user = (
        f"TITLE: {event.title}\n"
        f"HOST/DEPARTMENT: {event.host_org or 'unknown'}\n"
        f"CALENDAR EVENT TYPE: {event.category or 'unknown'}\n"
        f"CALENDAR TOPIC TAGS: {', '.join(event.tags) or 'none'}\n\n"
        f"DESCRIPTION:\n{event.description or '(no description)'}"
    )

    raw = complete_json(_ENRICH_SYSTEM, user)
    try:
        enr = _Enrichment.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as err:
        repair = (
            f"{user}\n\nYour previous response was invalid:\n{type(err).__name__}: {err}\n\n"
            "Return ONLY a corrected JSON object matching the schema."
        )
        enr = _Enrichment.model_validate(json.loads(complete_json(_ENRICH_SYSTEM, repair)))

    updated = event.model_copy(deep=True)
    updated.audience = enr.audience or ["unspecified"]
    updated.audience_evidence = enr.audience_evidence
    updated.grad_relevance = enr.grad_relevance
    updated.relevance_reasoning = enr.relevance_reasoning
    updated.category = enr.category or event.category
    if enr.tags:
        updated.tags = sorted(set(event.tags) | set(enr.tags))
    return updated


def enrich_events(events: list[Event], *, max_workers: int = 8) -> list[Event]:
    """Enrich a batch, preserving input order.

    Each event is one independent LLM call (see ADR-0006: we keep per-event calls for
    accuracy + isolation rather than batching many events into one prompt). Calls are
    I/O-bound, so we run them concurrently with a thread pool to cut wall-clock time.

    - `max_workers=1` → sequential (the original behavior; useful as a latency baseline).
    - One bad item logs and is kept un-enriched rather than killing the whole run.
    """
    if max_workers <= 1 or len(events) <= 1:
        out: list[Event] = []
        for ev in events:
            out.append(_safe_enrich(ev))
        return out

    results: list[Event] = [events[0]] * len(events)  # placeholder, overwritten below
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {pool.submit(_safe_enrich, ev): i for i, ev in enumerate(events)}
        for future in as_completed(future_to_idx):
            results[future_to_idx[future]] = future.result()
    return results


def _safe_enrich(event: Event) -> Event:
    """enrich_event with per-item error isolation (returns the original on failure)."""
    try:
        return enrich_event(event)
    except Exception as exc:  # noqa: BLE001
        print(f"[curate] enrichment failed for {event.title!r}: {exc}")
        return event


# ---------------------------------------------------------------------------
# Stage 2: selection (deterministic, no LLM)
# ---------------------------------------------------------------------------

_INCLUSIVE_AUDIENCES = {"all", "unspecified"}


def _parse_day(value: str) -> date:
    return datetime.fromisoformat(value).date()


def _audience_matches(event: Event, target: Target) -> bool:
    if not target.audience:
        return True  # target doesn't care about audience
    ev_aud = {a.lower() for a in event.audience} or {"unspecified"}
    if ev_aud & _INCLUSIVE_AUDIENCES:
        return True  # "all"/"unspecified" events are kept for human review, not dropped
    return bool(ev_aud & {a.lower() for a in target.audience})


def _topic_matches(event: Event, target: Target) -> bool:
    if not target.categories and not target.keywords:
        return True  # no topic constraint
    if target.categories and event.category and event.category.lower() in {
        c.lower() for c in target.categories
    }:
        return True
    if target.keywords:
        haystack = " ".join([event.title, event.description, *event.tags]).lower()
        if any(kw.lower() in haystack for kw in target.keywords):
            return True
    return False


def _department_matches(event: Event, target: Target) -> bool:
    if not target.departments:
        return True  # target doesn't care about department
    host = (event.host_org or "").lower()
    return any(dept.lower() in host for dept in target.departments)


def _date_in_range(event: Event, target: Target) -> bool:
    if event.start is None:
        return True  # can't filter undated events out; keep for human review
    day = event.start.date()
    if target.start_date and day < _parse_day(target.start_date):
        return False
    if target.end_date and day > _parse_day(target.end_date):
        return False
    return True


def filter_by_target(events: list[Event], target: Target) -> list[Event]:
    """Return events matching the target, ranked by grad_relevance (desc).

    Deterministic. Audience/topic 'unspecified' is kept rather than dropped, so the
    human editor never silently loses a borderline event.
    """
    matched = [
        ev
        for ev in events
        if _date_in_range(ev, target)
        and _department_matches(ev, target)
        and _audience_matches(ev, target)
        and _topic_matches(ev, target)
        and (ev.grad_relevance is None or ev.grad_relevance >= target.min_relevance)
    ]
    return sorted(matched, key=lambda e: (e.grad_relevance if e.grad_relevance is not None else -1.0), reverse=True)
