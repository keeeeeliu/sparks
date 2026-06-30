"""Curation pipeline orchestration — the single entry point CLI / API / UI all call.

Keeping this in the backend (not in a script) is deliberate: the expensive, valuable flow
(ingest → dedupe → enrich → filter → rank) lives in ONE place, so `run_curate.py`, a future
FastAPI endpoint, and the frontend never duplicate it. They just call `curate_range(...)`.

    feed (date range) ─▶ Event (facts, no LLM)        [ingest]
                      ─▶ collapse instances            [dedupe]
                      ─▶ audience + grad_relevance      [enrich, concurrent]
                      ─▶ select for a Target            [filter]
                      ─▶ master's-first, then relevance [rank]
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import telemetry
from .curate import enrich_events, filter_by_target
from .dedupe import dedupe_events
from .ingest import ingest_livewhale_events
from .models import Event, Target
from .telemetry import UsageSummary


@dataclass
class CurationResult:
    """The curated list plus counts/metadata callers (CLI / API / UI) need."""

    events: list[Event]       # ranked + filtered: master's-first, then grad_relevance
    enriched: list[Event]     # all enriched events (before filter); cache this for re-runs
    target: Target
    raw_count: int            # dated instances pulled from the feed
    unique_count: int         # after dedupe
    enriched_count: int       # actually enriched (after any cap)
    usage: UsageSummary | None = field(default=None)  # token/cost stats for this run


def resolve_month_range(month: str) -> tuple[str, str]:
    """Turn YYYY-MM into inclusive ISO start/end dates."""
    import calendar

    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    return f"{year:04d}-{mon:02d}-01", f"{year:04d}-{mon:02d}-{last:02d}"


def list_hosts_in_range(
    start_date: str | None,
    end_date: str | None,
    *,
    base_url: str = "https://events.brown.edu",
) -> list[tuple[str, int]]:
    """Host orgs (+counts) in a date range. No LLM — for discovering department names."""
    from collections import Counter

    raw = ingest_livewhale_events(
        base_url=base_url, start_date=start_date, end_date=end_date, max_events=None
    )
    counts = Counter(ev.host_org or "(unknown)" for ev in raw)
    return counts.most_common()


def default_grad_target(
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    departments: list[str] | None = None,
    keywords: list[str] | None = None,
    min_relevance: float = 0.0,
) -> Target:
    """A sensible default Target: grad/master's audience, optional dept/keyword filters."""
    return Target(
        name="Grad/master's — Student Affairs lens",
        audience=["graduate"],  # inclusive: keeps "all"/"unspecified" for human review
        departments=departments or [],
        keywords=keywords or [],
        start_date=start_date,
        end_date=end_date,
        min_relevance=min_relevance,
    )


def rank_for_newsletter(events: list[Event]) -> list[Event]:
    """Canonical curated ordering: master's-facing first, then by grad_relevance (desc)."""
    return sorted(
        events,
        key=lambda e: (e.is_masters_facing(), e.grad_relevance or 0.0),
        reverse=True,
    )


def curate_range(
    start_date: str | None,
    end_date: str | None,
    *,
    target: Target | None = None,
    base_url: str = "https://events.brown.edu",
    pull_cap: int | None = None,
    max_enrich: int | None = None,
    max_workers: int = 8,
    do_dedupe: bool = True,
) -> CurationResult:
    """Run the full curation flow for a date range and return a ranked `CurationResult`.

    - `pull_cap`   : cap raw instances fetched (None = all in range; the feed bounds it).
    - `max_enrich` : cap unique events enriched, to control LLM cost (None = all).
    - `max_workers`: enrichment concurrency (see ADR-0006).

    Resets telemetry at the start so `result.usage` reflects only this run's LLM cost.
    """
    telemetry.reset()

    raw = ingest_livewhale_events(
        base_url=base_url, start_date=start_date, end_date=end_date, max_events=pull_cap
    )
    unique = dedupe_events(raw) if do_dedupe else list(raw)

    # Enrich chronologically; timestamp key avoids tz/None comparison issues.
    unique.sort(key=lambda e: e.start.timestamp() if e.start else float("inf"))
    to_enrich = unique[:max_enrich] if max_enrich else unique

    enriched = enrich_events(to_enrich, max_workers=max_workers)

    target = target or default_grad_target(start_date, end_date)
    selected = filter_by_target(enriched, target)
    ranked = rank_for_newsletter(selected)

    return CurationResult(
        events=ranked,
        enriched=enriched,
        target=target,
        raw_count=len(raw),
        unique_count=len(unique),
        enriched_count=len(enriched),
        usage=telemetry.summarize(),
    )
