"""Newsletter draft generation — copy-paste ready for the shared Google Doc.

Primary workflow (human-in-the-loop):
    curated report → AGGREGATOR selects worthwhile events → blurbs → paste into Google Doc

We do NOT assign "Don't Miss" / must-see — that is editorial work for whoever owns the
final newsletter in Google Docs. Our job: filter, pick, and draft blurbs for selected events.

Selection is stored in a YAML file (dev/CLI) or checkboxes (Streamlit). The model does
NOT auto-pick which events to include unless you explicitly use `prepare_draft_auto()`.

Blurbs: one LLM call per *selected* event (concurrent). `use_llm=False` uses description text.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from .curate import filter_by_target
from .llm import complete_json
from .models import Event
from .pipeline import default_grad_target, rank_for_newsletter
from .report import SECTIONS, format_when, group_into_sections, section_of

_SKIP_SECTIONS = {"Other / Administrative"}

_BLURB_SYSTEM = """You write one-sentence blurbs for a Brown University graduate-student newsletter.

Voice: warm, clear, concise — like a helpful peer, not corporate marketing. No clichés
("Don't miss", "mark your calendars"). One sentence only, max ~30 words.

Ground rules: use ONLY facts from the event fields provided. Do not invent details.

Return JSON: {"blurb": "..."}"""


class _BlurbOut(BaseModel):
    blurb: str = Field(..., min_length=5, max_length=280)


@dataclass
class EventSelection:
    """Aggregator picks for one newsletter cycle (YAML or Streamlit → same shape)."""

    month: str | None
    events: list[str]


@dataclass
class NewsletterDraft:
    span: str
    month_label: str
    sections: dict[str, list[tuple[Event, str]]]
    unmatched_titles: list[str] = field(default_factory=list)


def load_enriched_cache(path: str | Path) -> list[Event]:
    data = json.loads(Path(path).read_text())
    return [Event.model_validate(item) for item in data]


def load_selection(path: str | Path) -> EventSelection:
    """Load human picks from YAML. Same format Streamlit will write later."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return EventSelection(
        month=raw.get("month"),
        events=[str(t).strip() for t in raw.get("events") or [] if str(t).strip()],
    )


def _norm_title(text: str) -> str:
    text = text.strip().lower()
    for ch in ("\u2019", "\u2018", "`"):
        text = text.replace(ch, "'")
    return " ".join(text.split())


def match_event(pool: list[Event], title: str) -> Event | None:
    """Resolve a human-entered title against the curated pool."""
    want = _norm_title(title)
    if not want:
        return None
    for ev in pool:
        if _norm_title(ev.title) == want:
            return ev
    # Unique substring match (helps when YAML uses straight quotes vs curly in feed).
    partial = [
        ev for ev in pool
        if want in _norm_title(ev.title) or _norm_title(ev.title) in want
    ]
    if len(partial) == 1:
        return partial[0]
    return None


def resolve_selected(
    pool: list[Event], titles: list[str]
) -> tuple[list[Event], list[str]]:
    """Return (matched events in pick order, titles that did not match)."""
    matched: list[Event] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for title in titles:
        ev = match_event(pool, title)
        if ev is None:
            unmatched.append(title)
        elif ev.title not in seen:
            matched.append(ev)
            seen.add(ev.title)
    return matched, unmatched


def _first_sentence(text: str, max_len: int = 200) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    m = re.match(r"^(.+?[.!?])(\s|$)", text)
    sentence = (m.group(1) if m else text[:max_len]).strip()
    return sentence if len(sentence) <= max_len else sentence[: max_len - 1] + "…"


def fallback_blurb(ev: Event) -> str:
    if ev.description:
        s = _first_sentence(ev.description)
        if s:
            return s
    return f"Hosted by {ev.host_org or 'campus'} — see link for details."


def generate_blurb(ev: Event) -> str:
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


def generate_blurbs(
    events: list[Event], *, max_workers: int = 8, use_llm: bool = True
) -> dict[str, str]:
    if not events:
        return {}
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


def build_draft_from_blurbs(
    events: list[Event],
    blurbs: dict[str, str],
    span: str,
    month_label: str,
) -> NewsletterDraft:
    """Assemble a draft from selected events and human-edited blurbs (no LLM)."""
    grouped = group_into_sections(events)
    section_pairs = {
        name: [(ev, blurbs.get(ev.title, fallback_blurb(ev))) for ev in evs]
        for name, evs in grouped.items()
        if evs
    }
    return NewsletterDraft(
        span=span,
        month_label=month_label,
        sections=section_pairs,
    )


def save_selection(path: str | Path, selection: EventSelection) -> None:
    """Persist aggregator picks — same YAML shape as `load_selection` reads."""
    payload = {"month": selection.month, "events": selection.events}
    Path(path).write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def prepare_draft_from_selection(
    pool: list[Event],
    selection: EventSelection,
    span: str,
    month_label: str,
    *,
    use_llm: bool = True,
    max_workers: int = 8,
) -> NewsletterDraft:
    """Build a draft from aggregator-selected titles only."""
    body_events, unmatched = resolve_selected(pool, selection.events)
    blurbs = generate_blurbs(body_events, max_workers=max_workers, use_llm=use_llm)

    grouped = group_into_sections(body_events)
    section_pairs = {
        name: [(ev, blurbs[ev.title]) for ev in evs if ev.title in blurbs]
        for name, evs in grouped.items()
        if evs
    }

    return NewsletterDraft(
        span=span,
        month_label=month_label,
        sections=section_pairs,
        unmatched_titles=unmatched,
    )


def events_from_cache_for_month(
    cache_path: str | Path,
    start_date: str,
    end_date: str,
    *,
    min_relevance: float = 0.0,
) -> list[Event]:
    enriched = load_enriched_cache(cache_path)
    target = default_grad_target(start_date, end_date, min_relevance=min_relevance)
    selected = filter_by_target(enriched, target)
    return rank_for_newsletter(selected)


# ---------------------------------------------------------------------------
# Legacy auto-select path (model picks events) — use `--auto` only for experiments
# ---------------------------------------------------------------------------


def prepare_draft_auto(
    events: list[Event],
    span: str,
    month_label: str,
    *,
    min_relevance: float = 0.4,
    max_per_section: int = 6,
    use_llm: bool = True,
    max_workers: int = 8,
) -> NewsletterDraft:
    """Auto-pick by relevance caps. Prefer `prepare_draft_from_selection` for real use."""
    filtered = [
        e for e in events
        if (e.grad_relevance or 0) >= min_relevance and section_of(e) not in _SKIP_SECTIONS
    ]
    grouped = group_into_sections(filtered)
    section_events = {
        name: evs[:max_per_section]
        for name, evs in grouped.items()
        if name not in _SKIP_SECTIONS
    }
    body = [ev for evs in section_events.values() for ev in evs]
    sel = EventSelection(month=None, events=[e.title for e in body])
    return prepare_draft_from_selection(
        events, sel, span, month_label, use_llm=use_llm, max_workers=max_workers
    )


def _format_event_block(ev: Event, blurb: str) -> str:
    lines = [
        f"**{ev.title}**",
        f"{format_when(ev)} · {ev.host_org or 'Brown'}",
        blurb,
    ]
    link = ev.link_for_newsletter()
    if link:
        lines.append(f"Link: {link}")
    page = ev.event_page_url()
    if page and page != link:
        lines.append(f"Event page: {page}")
    if ev.image_url:
        lines.append(f"Image: {ev.image_url}")
    else:
        lines.append("[Add image if available]")
    return "\n".join(lines)


def render_newsletter(draft: NewsletterDraft) -> str:
    out = [
        f"# Grad Events — {draft.month_label}",
        "",
        "_Draft for the shared Google Doc. Review, paste, add images, adjust formatting._",
        f"_{draft.span} · generated {date.today().isoformat()}_",
        "",
        "---",
        "",
    ]
    for name, _ in SECTIONS:
        pairs = draft.sections.get(name)
        if not pairs:
            continue
        out.append(f"## {name}")
        out.append("")
        for ev, blurb in pairs:
            out.append(_format_event_block(ev, blurb))
            out.append("")

    if draft.unmatched_titles:
        out.append("---")
        out.append("")
        out.append("_Could not match these selection titles to the curated pool:_")
        for t in draft.unmatched_titles:
            out.append(f"- {t}")
    return "\n".join(out)


def write_newsletter(path: str | Path, draft: NewsletterDraft) -> None:
    Path(path).write_text(render_newsletter(draft))
