"""Presentation helpers shared by every view of a curated list.

The curated `Event` list is the data; this module turns it into reader-friendly groupings
and text. Keeping sectioning here (not in the CLI) means the Markdown report, the future
newsletter draft, and the frontend all group events IDENTICALLY — one source of truth, no
drift between the developer preview and what users eventually see.
"""

from __future__ import annotations

from datetime import date as _date

from .models import Event

# Reader-friendly sections, each mapping to one or more enrichment categories.
# Anything unmatched (incl. None) falls into the final "Other" bucket.
SECTIONS: list[tuple[str, set[str]]] = [
    ("Career & Professional", {"career", "professional"}),
    ("Academic & Research", {"academic"}),
    ("Wellness & Well-being", {"wellness"}),
    ("Arts & Culture", {"arts"}),
    ("Social & Community", {"social"}),
    ("Other / Administrative", {"other"}),
]


def section_of(ev: Event) -> str:
    cat = (ev.category or "").lower()
    for name, cats in SECTIONS:
        if cat in cats:
            return name
    return SECTIONS[-1][0]


def group_into_sections(events: list[Event]) -> dict[str, list[Event]]:
    """Group events into the SECTIONS order; within each, master's-first then relevance."""
    buckets: dict[str, list[Event]] = {name: [] for name, _ in SECTIONS}
    for ev in events:
        buckets[section_of(ev)].append(ev)
    for evs in buckets.values():
        evs.sort(key=lambda e: (e.is_masters_facing(), e.grad_relevance or 0.0), reverse=True)
    return {name: buckets[name] for name, _ in SECTIONS if buckets[name]}


def format_when(ev: Event) -> str:
    """Human date/time, collapsing a recurring/multi-day event into a span."""
    if not ev.start:
        return "(no date)"
    if ev.occurrence_count > 1 and ev.end and ev.end.date() > ev.start.date():
        return f"{ev.start:%a %m/%d}–{ev.end:%m/%d} ({ev.occurrence_count}× dates)"
    return ev.start.strftime("%a %m/%d %H:%M")


def format_relevance_summary(ev: Event) -> str:
    """One-line relevance score + reasoning — same text as the curated report."""
    rel = f"{ev.grad_relevance:.2f}" if ev.grad_relevance is not None else "n/a"
    reason = ev.relevance_reasoning or "(no reasoning)"
    return f"Relevance {rel} — {reason}"


def _event_md(ev: Event) -> str:
    """One event as a Markdown block — FULL text, nothing truncated."""
    star = " ⭐ master's-facing" if ev.is_masters_facing() else ""
    lines = [
        f"### {ev.title}{star}",
        f"- **When:** {format_when(ev)}",
        f"- **Host:** {ev.host_org or 'unknown'}",
        f"- **Audience:** {', '.join(ev.audience) or 'unspecified'}",
        f"- **{format_relevance_summary(ev)}**",
    ]
    if ev.audience_evidence:
        lines.append(f'- **Audience evidence:** "{ev.audience_evidence}"')
    if ev.registration_url:
        lines.append(f"- **Link:** {ev.registration_url}")
    if ev.image_url:
        lines.append(f"- **Image:** {ev.image_url}")
    return "\n".join(lines)


def render_markdown(events: list[Event], span: str, *, generated: str | None = None) -> str:
    """Render the curated list as a Markdown report grouped by purpose."""
    n_masters = sum(e.is_masters_facing() for e in events)
    sections = group_into_sections(events)
    out = [
        f"# Curated grad events — {span}",
        f"_{len(events)} events · {n_masters} master's-facing · "
        f"generated {generated or _date.today().isoformat()}_",
        "",
        "> Grouped by purpose. Within each section: master's-facing first, then by relevance.",
        "",
    ]
    for name, evs in sections.items():
        out.append(f"## {name} ({len(evs)})\n")
        for ev in evs:
            out.append(_event_md(ev))
            out.append("")
    return "\n".join(out)


def write_markdown_report(path, events: list[Event], span: str) -> None:
    """Write the sectioned Markdown report to disk."""
    from pathlib import Path

    Path(path).write_text(render_markdown(events, span))
