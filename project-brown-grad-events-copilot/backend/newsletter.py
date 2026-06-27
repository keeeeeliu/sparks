"""Newsletter draft generation — copy-paste ready for the shared Google Doc.

Unlike `report.py` (internal curator view with scores/reasoning), this produces
**editor-facing** text: short blurbs, clean sections, links — no grad_relevance numbers.

Workflow (human-in-the-loop):
    curate_range / cached enriched_events.json → select + blurbs → paste into Google Doc
    → human adds images & final formatting → hand off for send.

Blurbs: one LLM call per *selected* event (concurrent, like enrichment). Use
`use_llm=False` for a fast draft from the event description.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from .curate import filter_by_target
from .llm import complete_json
from .models import Event
from .pipeline import default_grad_target, rank_for_newsletter
from .report import SECTIONS, format_when, group_into_sections, section_of

# Sections we skip in the public-facing draft (admin noise, calendar notices).
_SKIP_SECTIONS = {"Other / Administrative"}

_BLURB_SYSTEM = """You write one-sentence blurbs for a Brown University graduate-student newsletter.

Voice: warm, clear, concise — like a helpful peer, not corporate marketing. No clichés
("Don't miss", "mark your calendars"). One sentence only, max ~30 words.

Ground rules: use ONLY facts from the event fields provided. Do not invent details.

Return JSON: {"blurb": "..."}"""


class _BlurbOut(BaseModel):
    blurb: str = Field(..., min_length=5, max_length=280)


@dataclass
class NewsletterDraft:
    """Selected events + blurbs, ready to render."""

    span: str
    month_label: str
    highlights: list[tuple[Event, str]]
    sections: dict[str, list[tuple[Event, str]]]  # section name → (event, blurb)
    skipped_count: int = 0


def load_enriched_cache(path: str | Path) -> list[Event]:
    data = json.loads(Path(path).read_text())
    return [Event.model_validate(item) for item in data]


def _first_sentence(text: str, max_len: int = 200) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    m = re.match(r"^(.+?[.!?])(\s|$)", text)
    sentence = (m.group(1) if m else text[:max_len]).strip()
    return sentence if len(sentence) <= max_len else sentence[: max_len - 1] + "…"


def fallback_blurb(ev: Event) -> str:
    """No-LLM blurb: first sentence of description, or a trimmed host/when line."""
    if ev.description:
        s = _first_sentence(ev.description)
        if s:
            return s
    host = ev.host_org or "campus"
    return f"Hosted by {host} — see link for details."


def generate_blurb(ev: Event) -> str:
    """One LLM call → newsletter-voice one-liner."""
    user = (
        f"TITLE: {ev.title}\n"
        f"WHEN: {format_when(ev)}\n"
        f"HOST: {ev.host_org or 'unknown'}\n"
        f"DESCRIPTION:\n{(ev.description or '(none)')[:800]}"
    )
    raw = complete_json(_BLURB_SYSTEM, user)
    try:
        return _BlurbOut.model_validate(json.loads(raw)).blurb.strip()
    except (json.JSONDecodeError, ValidationError):
        return fallback_blurb(ev)


def generate_blurbs(events: list[Event], *, max_workers: int = 8, use_llm: bool = True) -> dict[str, str]:
    """Return {event.title: blurb} for each event (title key is fine post-dedupe)."""
    if not use_llm:
        return {ev.title: fallback_blurb(ev) for ev in events}

    blurbs: dict[str, str] = {}
    if max_workers <= 1 or len(events) <= 1:
        for ev in events:
            blurbs[ev.title] = generate_blurb(ev)
        return blurbs

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(generate_blurb, ev): ev for ev in events}
        for fut in as_completed(futures):
            ev = futures[fut]
            try:
                blurbs[ev.title] = fut.result()
            except Exception:  # noqa: BLE001
                blurbs[ev.title] = fallback_blurb(ev)
    return blurbs


def pick_highlights(
    events: list[Event],
    *,
    max_count: int = 8,
    min_relevance: float = 0.5,
) -> list[Event]:
    """Don't Miss: master's picks + a well-rounded mix (wellness/arts/social)."""
    eligible = [e for e in events if (e.grad_relevance or 0) >= min_relevance]
    eligible = [e for e in eligible if section_of(e) not in _SKIP_SECTIONS]
    if not eligible:
        return []

    picked: list[Event] = []
    seen: set[str] = set()

    def add(ev: Event) -> None:
        if ev.title in seen or len(picked) >= max_count:
            return
        picked.append(ev)
        seen.add(ev.title)

    for ev in sorted(eligible, key=lambda e: (e.is_masters_facing(), e.grad_relevance or 0), reverse=True):
        if ev.is_masters_facing():
            add(ev)
        if len(picked) >= max(4, max_count // 2):
            break

    for section in ("Wellness & Well-being", "Arts & Culture", "Social & Community"):
        candidates = [
            e for e in eligible
            if section_of(e) == section and e.title not in seen
        ]
        candidates.sort(key=lambda e: e.grad_relevance or 0, reverse=True)
        if candidates:
            add(candidates[0])

    for ev in sorted(eligible, key=lambda e: e.grad_relevance or 0, reverse=True):
        add(ev)
        if len(picked) >= max_count:
            break
    return picked


def select_for_newsletter(
    events: list[Event],
    *,
    min_relevance: float = 0.4,
    max_per_section: int = 6,
) -> tuple[dict[str, list[Event]], int]:
    """Filter + cap per section. Returns (sections dict, skipped count)."""
    filtered = [
        e for e in events
        if (e.grad_relevance or 0) >= min_relevance and section_of(e) not in _SKIP_SECTIONS
    ]
    skipped = len(events) - len(filtered)
    grouped = group_into_sections(filtered)
    capped = {name: evs[:max_per_section] for name, evs in grouped.items() if name not in _SKIP_SECTIONS}
    return capped, skipped


def prepare_draft(
    events: list[Event],
    span: str,
    month_label: str,
    *,
    min_relevance: float = 0.4,
    max_per_section: int = 6,
    max_highlights: int = 8,
    use_llm: bool = True,
    max_workers: int = 8,
) -> NewsletterDraft:
    """Select events, generate blurbs, build a NewsletterDraft."""
    section_events, skipped = select_for_newsletter(
        events, min_relevance=min_relevance, max_per_section=max_per_section
    )
    all_selected: list[Event] = []
    for evs in section_events.values():
        all_selected.extend(evs)
    highlights = pick_highlights(events, max_count=max_highlights, min_relevance=min_relevance)

    to_blurb = {ev.title: ev for ev in all_selected}
    for ev in highlights:
        to_blurb[ev.title] = ev
    blurbs = generate_blurbs(list(to_blurb.values()), max_workers=max_workers, use_llm=use_llm)

    hl_pairs = [(ev, blurbs[ev.title]) for ev in highlights]
    section_pairs = {
        name: [(ev, blurbs[ev.title]) for ev in evs]
        for name, evs in section_events.items()
    }
    return NewsletterDraft(
        span=span,
        month_label=month_label,
        highlights=hl_pairs,
        sections=section_pairs,
        skipped_count=skipped,
    )


def events_from_cache_for_month(
    cache_path: str | Path,
    start_date: str,
    end_date: str,
    *,
    min_relevance: float = 0.0,
) -> list[Event]:
    """Load cache → filter/rank like the curation pipeline (no re-enrichment)."""
    enriched = load_enriched_cache(cache_path)
    target = default_grad_target(start_date, end_date, min_relevance=min_relevance)
    selected = filter_by_target(enriched, target)
    return rank_for_newsletter(selected)


def _format_event_block(ev: Event, blurb: str) -> str:
    lines = [
        f"**{ev.title}**",
        f"{format_when(ev)} · {ev.host_org or 'Brown'}",
        blurb,
    ]
    if ev.registration_url:
        lines.append(f"Link: {ev.registration_url}")
    lines.append("[Add image if available]")
    return "\n".join(lines)


def render_newsletter(draft: NewsletterDraft) -> str:
    """Copy-paste-friendly Markdown for the shared Google Doc."""
    out = [
        f"# Grad Events — {draft.month_label}",
        "",
        "_Draft for the shared Google Doc. Review, paste, add images, adjust formatting._",
        f"_{draft.span} · generated {date.today().isoformat()}_",
        "",
        "---",
        "",
        "## Don't Miss",
        "",
    ]
    if draft.highlights:
        for ev, blurb in draft.highlights:
            out.append(_format_event_block(ev, blurb))
            out.append("")
    else:
        out.append("_(No highlights selected — lower `--min-relevance` or add events manually.)_")
        out.append("")

    for name, _ in SECTIONS:
        pairs = draft.sections.get(name)
        if not pairs:
            continue
        out.append(f"## {name}")
        out.append("")
        for ev, blurb in pairs:
            out.append(_format_event_block(ev, blurb))
            out.append("")

    if draft.skipped_count:
        out.append(
            f"---\n\n_{draft.skipped_count} lower-relevance / administrative events omitted "
            f"(see curated report for the full list)._"
        )
    return "\n".join(out)


def write_newsletter(path: str | Path, draft: NewsletterDraft) -> None:
    Path(path).write_text(render_newsletter(draft))
