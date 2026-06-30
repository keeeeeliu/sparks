"""Dedupe: collapse one event's many dated instances into a single canonical Event.

Why this runs BEFORE enrichment (the expensive LLM step):
The LiveWhale feed returns recurring / multi-day events as a SEPARATE item per date — a
month-long exhibit shows up ~30 times, a weekly series 4 times. Enriching each instance
wastes LLM budget and floods the newsletter with the same event on different dates.

Strategy (deliberately simple, deterministic — no LLM, no embeddings yet):
  group by (normalized title + normalized host) → keep the richest instance as the
  representative → record the overall span (`start`..`end`) and the distinct occurrence
  dates, so the newsletter can say "Exhibit · Jul 1–31" or list the dates of a series.

This is intentionally conservative: it merges things that are clearly the same titled event
from the same host. Fuzzy/near-duplicate matching (typos, cross-source variants) is a later
upgrade — see PROGRESS. Better to under-merge (a stray duplicate) than over-merge (two
genuinely different events silently combined).
"""

from __future__ import annotations

import re

from .models import Event

_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def _norm(text: str | None) -> str:
    """Lowercase, drop punctuation, collapse whitespace — a stable grouping key."""
    if not text:
        return ""
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def _dedupe_key(ev: Event) -> tuple[str, str]:
    return (_norm(ev.title), _norm(ev.host_org))


def _merge_group(group: list[Event]) -> Event:
    """Merge several instances of the same event into one, recording span + occurrences."""
    if len(group) == 1:
        return group[0]

    # Representative = the instance with the richest description (most info to enrich on).
    rep = max(group, key=lambda e: len(e.description or ""))
    merged = rep.model_copy(deep=True)

    starts = sorted({e.start for e in group if e.start is not None})
    if starts:
        merged.start = starts[0]
        merged.occurrence_dates = starts
        explicit_ends = [e.end for e in group if e.end is not None]
        span_end = max([*explicit_ends, starts[-1]])
        # Only record an end if it actually extends beyond the start (a real span).
        merged.end = span_end if span_end > starts[0] else rep.end

    merged.occurrence_count = len(group)

    # Backfill useful fields from any instance if the representative is missing them.
    for e in group:
        if not merged.registration_url and e.registration_url:
            merged.registration_url = e.registration_url
        if not merged.location and e.location:
            merged.location = e.location
        if not merged.cost and e.cost:
            merged.cost = e.cost
        if not merged.image_url and e.image_url:
            merged.image_url = e.image_url

    return merged


def dedupe_events(events: list[Event]) -> list[Event]:
    """Collapse same-title/same-host instances into one canonical Event each.

    Order-preserving by first appearance. Returns a new list; inputs are not mutated.
    """
    groups: dict[tuple[str, str], list[Event]] = {}
    order: list[tuple[str, str]] = []
    for ev in events:
        key = _dedupe_key(ev)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(ev)

    return [_merge_group(groups[key]) for key in order]
