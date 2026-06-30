"""Streamlit UI — human-in-the-loop newsletter drafting.

Run from project root:
    streamlit run app/newsletter_editor.py

Click **Fetch events for this month** to pull live from Brown's calendar + run LLM
enrichment (~30s for a full month). Requires .env with OPENAI_API_KEY (or Anthropic).
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models import Event  # noqa: E402
from backend.newsletter import build_draft_from_blurbs, generate_blurbs, render_newsletter  # noqa: E402
from backend.pipeline import curate_range, default_grad_target, resolve_month_range  # noqa: E402
from backend.report import format_relevance_summary, format_when, group_into_sections  # noqa: E402

CACHE_PATH = ROOT / "data" / "output" / "enriched_events.json"
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass
class PoolVisibility:
    in_pool: int
    listed: int
    hidden_by_filters: int
    selected: int
    filters_active: bool


def _month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def _validate_month(month: str) -> str | None:
    month = month.strip()
    if not _MONTH_RE.match(month):
        return "Use YYYY-MM format (e.g. 2026-08)."
    return None


def _init_state() -> None:
    defaults = {
        "month": "2026-07",
        "loaded_month": "",
        "pool": [],
        "selected": set(),
        "blurbs": {},
        "span": "",
        "month_label": "",
        "last_fetch_note": "",
    }
    for key, val in defaults.items():
        st.session_state.setdefault(key, val)


def _set_pool(month: str, pool: list[Event], *, note: str = "") -> None:
    start, end = resolve_month_range(month)
    st.session_state.pool = pool
    st.session_state.span = f"{start} → {end}"
    st.session_state.month_label = _month_label(month)
    st.session_state.month = month
    st.session_state.loaded_month = month
    st.session_state.selected = set()
    st.session_state.blurbs = {}
    st.session_state.last_fetch_note = note


def _fetch_month(month: str, *, workers: int, save_cache: bool) -> list[Event]:
    """LiveWhale ingest + dedupe + LLM enrich for the requested month."""
    start, end = resolve_month_range(month)
    target = default_grad_target(start, end, min_relevance=0.0)
    result = curate_range(
        start,
        end,
        target=target,
        max_enrich=None,  # enrich every unique event in the month (no silent cap)
        max_workers=workers,
    )
    if save_cache:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps(
                [json.loads(e.model_dump_json()) for e in result.enriched],
                indent=2,
            )
        )
    note = (
        f"Fetched live · {result.raw_count} calendar instances → "
        f"{result.unique_count} unique → {len(result.events)} in your pool"
    )
    _set_pool(month, result.events, note=note)
    return result.events


def _selected_events(pool: list[Event], selected: set[str]) -> list[Event]:
    title_to_ev = {ev.title: ev for ev in pool}
    return [title_to_ev[t] for t in selected if t in title_to_ev]


def _filter_pool(
    pool: list[Event],
    *,
    query: str,
    masters_only: bool,
    min_relevance: float,
) -> list[Event]:
    q = query.strip().lower()
    out: list[Event] = []
    for ev in pool:
        if masters_only and not ev.is_masters_facing():
            continue
        if (ev.grad_relevance or 0) < min_relevance:
            continue
        if q:
            hay = " ".join(
                filter(
                    None,
                    [
                        ev.title,
                        ev.host_org,
                        ev.description,
                        ev.relevance_reasoning,
                        " ".join(ev.audience or []),
                    ],
                )
            ).lower()
            if q not in hay:
                continue
        out.append(ev)
    return out


def _visibility_stats(
    pool: list[Event],
    listed: list[Event],
    *,
    query: str,
    masters_only: bool,
    min_relevance: float,
) -> PoolVisibility:
    filters_active = bool(query.strip()) or masters_only or min_relevance > 0.0
    return PoolVisibility(
        in_pool=len(pool),
        listed=len(listed),
        hidden_by_filters=max(0, len(pool) - len(listed)),
        selected=len(st.session_state.selected),
        filters_active=filters_active,
    )


def _render_pool_summary(stats: PoolVisibility) -> None:
    if st.session_state.last_fetch_note:
        st.caption(st.session_state.last_fetch_note)

    c1, c2, c3 = st.columns(3)
    c1.metric("Events this month", stats.in_pool)
    c2.metric("Showing in list", stats.listed)
    c3.metric("You selected", stats.selected)

    if stats.hidden_by_filters:
        st.caption(
            f"**{stats.hidden_by_filters}** event(s) hidden by your search or filters "
            "(master's-facing only, min relevance). Clear filters to see all "
            f"{stats.in_pool}."
        )
    elif stats.in_pool and stats.listed == stats.in_pool:
        st.caption(f"All **{stats.in_pool}** events are listed below, grouped by section.")


def _event_card(ev: Event) -> str:
    rel = f"{ev.grad_relevance:.2f}" if ev.grad_relevance is not None else "n/a"
    bits = [format_when(ev), ev.host_org or "Brown", f"relevance {rel}"]
    if ev.is_masters_facing():
        bits.append("master's-facing")
    return " · ".join(bits)


def _render_event_media(ev: Event) -> None:
    img_col, meta_col = st.columns([1, 2.2])
    with img_col:
        if ev.image_url:
            st.image(ev.image_url, use_container_width=True)
        else:
            st.caption("_No image in feed_")

    with meta_col:
        st.caption(_event_card(ev))
        st.markdown(f"_{format_relevance_summary(ev)}_")
        link = ev.link_for_newsletter()
        if link:
            st.text_input(
                "Link (paste into Google Doc)",
                value=link,
                key=f"link_{hash(ev.title) & 0xFFFFFF}",
            )
        page = ev.event_page_url()
        if page and page != link:
            st.text_input(
                "Event page",
                value=page,
                key=f"page_{hash(ev.title) & 0xFFFFFF}",
            )
        if ev.image_url:
            st.text_input(
                "Image URL (insert in Google Doc)",
                value=ev.image_url,
                key=f"imgurl_{hash(ev.title) & 0xFFFFFF}",
            )


def _render_select_row(ev: Event, section_name: str, index: int) -> None:
    has_image = bool(ev.image_url)
    if has_image:
        chk_col, thumb_col, title_col = st.columns([0.06, 0.12, 0.82])
    else:
        chk_col, title_col = st.columns([0.06, 0.94])
        thumb_col = None

    with chk_col:
        checked = st.checkbox(
            " ",
            value=ev.title in st.session_state.selected,
            key=f"sel_{section_name}_{index}_{hash(ev.title) & 0xFFFF}",
            label_visibility="collapsed",
        )
    if thumb_col is not None:
        with thumb_col:
            st.image(ev.image_url, width=72)
    with title_col:
        st.markdown(f"**{ev.title}**")
        st.caption(_event_card(ev))
        st.markdown(f"_{format_relevance_summary(ev)}_")

    if checked:
        st.session_state.selected.add(ev.title)
    else:
        st.session_state.selected.discard(ev.title)


def _render_sidebar() -> tuple[str, int, bool]:
    st.sidebar.title("Month")
    month = st.sidebar.text_input(
        "YYYY-MM",
        value=st.session_state.month,
        help="e.g. 2026-08 for August. Then click Fetch below.",
    )

    enrich_workers = st.sidebar.slider(
        "Enrichment speed (workers)",
        1,
        16,
        8,
        help="Parallel LLM calls when fetching a month. Larger months take longer.",
    )
    save_cache = st.sidebar.toggle(
        "Save to disk after fetch",
        value=True,
        help=f"Writes {CACHE_PATH.name} so run_curate.py can reuse it.",
    )

    if st.sidebar.button("Fetch events for this month", type="primary", use_container_width=True):
        err = _validate_month(month)
        if err:
            st.sidebar.error(err)
        else:
            with st.spinner(f"Fetching {month} from calendar + enriching… (may take ~1 min)"):
                try:
                    pool = _fetch_month(
                        month, workers=enrich_workers, save_cache=save_cache
                    )
                    st.sidebar.success(f"Loaded {len(pool)} events for {month}.")
                except Exception as exc:  # noqa: BLE001
                    st.sidebar.error(f"Fetch failed: {exc}")

    if st.sidebar.button("Clear picks", use_container_width=True):
        st.session_state.selected = set()
        st.session_state.blurbs = {}

    st.sidebar.divider()
    st.sidebar.caption(
        "Changing the month does not auto-refresh. Click **Fetch events for this month** "
        "to load a new month from the live calendar."
    )

    use_llm = st.sidebar.toggle("LLM blurbs", value=True)
    blurb_workers = st.sidebar.slider("Blurb workers", 1, 16, 8)

    return month, blurb_workers, use_llm


def _render_select_tab(
    filtered: list[Event],
    stats: PoolVisibility,
    *,
    month_input: str,
) -> None:
    st.subheader("Pick events for this month's draft")
    st.caption(
        "You are the aggregator — check what belongs in the newsletter. "
        "Editorial highlights happen later in Google Docs."
    )

    if not st.session_state.pool:
        st.info(
            "Enter a month in the sidebar (e.g. **2026-08**) and click "
            "**Fetch events for this month** to load events from the live calendar."
        )
        return

    if month_input.strip() != st.session_state.loaded_month:
        st.warning(
            f"You typed **{month_input.strip()}** but the list shows "
            f"**{st.session_state.loaded_month}** ({st.session_state.month_label}). "
            "Click **Fetch events for this month** in the sidebar to switch months."
        )

    _render_pool_summary(stats)

    grouped = group_into_sections(filtered)
    for section_name, evs in grouped.items():
        if not evs:
            continue
        with st.expander(f"{section_name} ({len(evs)})", expanded=stats.selected < 12):
            for i, ev in enumerate(evs):
                _render_select_row(ev, section_name, i)


def _render_draft_tab(workers: int, use_llm: bool) -> None:
    st.subheader("Blurbs & export")
    events = _selected_events(st.session_state.pool, st.session_state.selected)

    if not events:
        st.info("Select at least one event on the **Select events** tab.")
        return

    col_a, col_b = st.columns([3, 1])
    with col_a:
        gen = st.button("Generate blurbs", type="primary", use_container_width=True)
    with col_b:
        st.write(f"**{len(events)}** picked")

    if gen:
        with st.spinner("Writing blurbs…"):
            new_blurbs = generate_blurbs(events, max_workers=workers, use_llm=use_llm)
            st.session_state.blurbs.update(new_blurbs)
            for title, text in new_blurbs.items():
                st.session_state[f"blurb_{hash(title) & 0xFFFFFF}"] = text
        st.success(f"Generated {len(new_blurbs)} blurb(s).")

    st.divider()
    st.markdown("**Edit blurbs** — image and links are ready to copy into the Google Doc.")

    grouped = group_into_sections(events)
    for section_name, evs in grouped.items():
        if not evs:
            continue
        st.markdown(f"#### {section_name}")
        for ev in evs:
            with st.container(border=True):
                _render_event_media(ev)
                blurb_key = f"blurb_{hash(ev.title) & 0xFFFFFF}"
                if blurb_key not in st.session_state and ev.title in st.session_state.blurbs:
                    st.session_state[blurb_key] = st.session_state.blurbs[ev.title]
                blurb = st.text_area(
                    "Blurb",
                    height=80,
                    key=blurb_key,
                    label_visibility="collapsed",
                    placeholder="One-sentence newsletter blurb…",
                )
                if blurb.strip():
                    st.session_state.blurbs[ev.title] = blurb.strip()

    if st.session_state.blurbs:
        draft = build_draft_from_blurbs(
            events,
            st.session_state.blurbs,
            st.session_state.span,
            st.session_state.month_label,
        )
        md = render_newsletter(draft)
        st.divider()
        st.markdown("**Preview**")
        st.markdown(md)
        st.download_button(
            "Download markdown",
            data=md,
            file_name=f"newsletter_{st.session_state.month}.md",
            mime="text/markdown",
            use_container_width=True,
        )


def main() -> None:
    st.set_page_config(
        page_title="Grad Events Newsletter",
        page_icon="📬",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _init_state()

    st.title("Grad Events Newsletter")
    st.caption(
        "Pick a month → fetch live from calendar → select events → blurbs → paste into Google Doc"
    )

    month_input, blurb_workers, use_llm = _render_sidebar()

    query = st.text_input("Search events", placeholder="career, wellness, Fulbright…")
    filt_col1, filt_col2 = st.columns(2)
    with filt_col1:
        masters_only = st.toggle("Master's-facing only", value=False)
    with filt_col2:
        min_rel = st.slider("Min relevance", 0.0, 1.0, 0.0, 0.05)

    filtered = _filter_pool(
        st.session_state.pool,
        query=query,
        masters_only=masters_only,
        min_relevance=min_rel,
    )
    stats = _visibility_stats(
        st.session_state.pool,
        filtered,
        query=query,
        masters_only=masters_only,
        min_relevance=min_rel,
    )

    tab_select, tab_draft = st.tabs(["Select events", "Blurbs & export"])
    with tab_select:
        _render_select_tab(filtered, stats, month_input=month_input)
    with tab_draft:
        _render_draft_tab(blurb_workers, use_llm)


if __name__ == "__main__":
    main()
