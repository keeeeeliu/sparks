"""Ingestion layer.

There are TWO kinds of sources, and they take two different paths:

1. UNSTRUCTURED sources (paste, email, PDF, arbitrary web HTML) have no fields —
   they return a normalized `SourceItem` (plain text), which the LLM extractor
   then turns into `Event`s. Contract: these functions return `SourceItem`.

2. STRUCTURED feeds (LiveWhale JSON, iCal) already ARE fields. We map them
   directly to `Event` — deterministically, with no LLM call. This is more
   accurate, free, instant, and carries zero hallucination risk. Contract: these
   functions return `list[Event]`.

Either way the rest of the pipeline (dedupe / curate / draft) only ever sees
`Event`s, so nothing downstream cares which path produced them.

Wave A decisions:
- email / newsletter  -> manual: you paste/forward the text (same as `ingest_paste`).
- website             -> curated allowlist in sources.yaml, fetched on demand
                         (graduates to a scheduled monitor once extraction is trusted).
- Brown calendar      -> use the LiveWhale JSON feed, NOT HTML scraping (the public
                         calendar is JavaScript-rendered, so a plain fetch sees nothing).

Heavier deps (pypdf, httpx, trafilatura, yaml) are imported lazily so the core
pipeline runs even if you haven't installed them yet.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import quote

from .models import Event, SourceItem, SourceType


def ingest_paste(text: str, source_ref: str = "manual") -> SourceItem:
    """Pasted/typed event text. The simplest source and the test harness for all others."""
    return SourceItem(content=text.strip(), source_type=SourceType.PASTE, source_ref=source_ref)


def ingest_email(text: str, source_ref: str = "email") -> SourceItem:
    """A forwarded/pasted email or newsletter body. Manual for Wave A (no live inbox)."""
    return SourceItem(content=text.strip(), source_type=SourceType.EMAIL, source_ref=source_ref)


def ingest_pdf(path: str | Path) -> SourceItem:
    """Text-based PDF (most digital event flyers/announcements).

    Note: scanned/image-only flyers won't yield text here — those go through the
    vision path (SourceType.IMAGE) instead, which we'll wire up next increment.
    """
    from pypdf import PdfReader

    path = Path(path)
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return SourceItem(content=text, source_type=SourceType.PDF, source_ref=path.name)


def ingest_web(url: str, timeout: float = 20.0) -> SourceItem:
    """Fetch a single URL and extract its readable text (strips nav/ads/boilerplate).

    Only call this on URLs from your curated sources.yaml — respect each site's terms.
    """
    import httpx
    import trafilatura

    headers = {"User-Agent": "BrownGradEventsCopilot/0.1 (+personal assistantship tool)"}
    resp = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
    resp.raise_for_status()
    content = (trafilatura.extract(resp.text, url=url) or "").strip()
    if len(content) < 200:
        print(
            f"[ingest_web] WARNING: only {len(content)} chars extracted from {url}. "
            "This page is likely JavaScript-rendered. Look for a JSON/iCal feed or API "
            "(e.g. LiveWhale calendars expose /live/json/v2/events/) instead of scraping."
        )
    return SourceItem(content=content, source_type=SourceType.WEB, source_ref=url)


def load_web_sources(path: str | Path = "sources.yaml") -> list[str]:
    """Read the curated allowlist of URLs to monitor."""
    import yaml

    data = yaml.safe_load(Path(path).read_text()) or {}
    return list(data.get("sources", []))


def ingest_web_sources(path: str | Path = "sources.yaml") -> list[SourceItem]:
    """Fetch every URL in the curated list. The basis of the (later) scheduled monitor."""
    items: list[SourceItem] = []
    for url in load_web_sources(path):
        try:
            items.append(ingest_web(url))
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't kill the batch
            print(f"[ingest_web] failed for {url}: {exc}")
    return items


# ---------------------------------------------------------------------------
# Structured feeds (LiveWhale) -> Event directly, no LLM.
# ---------------------------------------------------------------------------

_LIVEWHALE_FIELDS = "location,summary,description,group_title,tags,event_types,registration,thumbnail"
# NOTE: event_types_audience comes back by default. It is sparse (~30% summer, ~0% mid-semester)
# and has NO "graduate" value at Brown, so we keep it only as a hint for enrichment (ADR-0005).


def _clean_inline(raw: str | None) -> str | None:
    """Decode HTML entities / strip stray tags from a SHORT inline field (host, location).

    Unlike `_html_to_text` (which is for multi-line descriptions), this collapses to a single
    line and returns None when empty, so Optional fields stay null instead of "".
    e.g. 'Alumni &amp; Friends' -> 'Alumni & Friends'.
    """
    if not raw:
        return None
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text).replace("\xa0", " ")
    text = " ".join(text.split())
    return text or None


def _html_to_text(raw: str | None) -> str:
    """Strip HTML tags/entities from a LiveWhale description into clean plain text."""
    if not raw:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)          # drop remaining tags
    text = html.unescape(text)                    # &#160; -> nbsp, &amp; -> & etc.
    text = text.replace("\xa0", " ")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def build_livewhale_url(
    base_url: str = "https://events.brown.edu",
    *,
    group: str | None = None,
    tag: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    paginate: int = 50,
) -> str:
    """Build a LiveWhale JSON v2 REST URL. See https://support.livewhale.com."""
    path = base_url.rstrip("/") + "/live/json/v2/events"
    params: list[tuple[str, str]] = [("response_fields", _LIVEWHALE_FIELDS)]
    if group:
        params.append(("group", group))
    if tag:
        params.append(("tag", tag))
    if start_date:
        params.append(("start_date", start_date))
    if end_date:
        params.append(("end_date", end_date))
    if paginate:
        params.append(("paginate", str(paginate)))
    for key, value in params:
        path += f"/{key}/{quote(value, safe='')}"
    return path + "/"


def _livewhale_display_image(thumbnail: str | None, *, width: int = 480) -> str | None:
    """Upscale a LiveWhale thumbnail URL for UI preview / copy-paste into Google Docs."""
    if not thumbnail or not str(thumbnail).strip():
        return None
    url = html.unescape(str(thumbnail).strip())
    return re.sub(r"/width/\d+/height/\d+/", f"/width/{width}/height/{width}/", url)


def _coerce_optional_str(value: object | None) -> str | None:
    """LiveWhale sometimes returns numbers (e.g. cost=15) where we store strings."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _livewhale_item_to_event(item: dict, source_url: str) -> Event:
    """Deterministic field mapping. We copy what's there; absent -> None (never invented)."""
    event_types = [t.strip() for t in (item.get("event_types") or []) if t and t.strip()]
    tags = item.get("tags") or []
    audience_tags = item.get("event_types_audience") or []
    return Event(
        title=_clean_inline(item.get("title")) or "(untitled)",
        description=_html_to_text(item.get("description") or item.get("summary")),
        start=item.get("date_iso"),
        end=item.get("date2_iso"),
        location=_clean_inline(item.get("location") or item.get("location_title")),
        on_campus=None,  # feed doesn't state this; don't guess
        host_org=_clean_inline(item.get("group_title")),
        category=event_types[0] if event_types else None,
        registration_url=html.unescape(
            item.get("registration") or item.get("online_url") or item.get("url") or ""
        ) or None,
        image_url=_livewhale_display_image(item.get("thumbnail")),
        cost=_coerce_optional_str(item.get("cost")),
        tags=list(tags) if isinstance(tags, list) else [],
        audience_tags=list(audience_tags) if isinstance(audience_tags, list) else [],
        source_ref=item.get("url") or source_url,
        evidence=None,  # not LLM-quoted; provenance is the canonical event URL above
        extraction_confidence=1.0,  # deterministic mapping, not a model guess
    )


def ingest_livewhale_events(
    base_url: str = "https://events.brown.edu",
    *,
    group: str | None = None,
    tag: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    paginate: int = 100,
    max_events: int | None = 200,
) -> list[Event]:
    """Fetch a LiveWhale calendar JSON feed and map it directly to Event objects.

    Structured feed -> deterministic mapping. No LLM, no hallucination risk.
    Follows the feed's pagination (`links.next`) across pages until exhausted or
    `max_events` is reached. Skips events the feed marks as canceled.

    - `paginate`   : events requested per page (LiveWhale caps this, ~100 max).
    - `max_events` : hard cap on total events pulled, so you don't accidentally
                     fetch all ~1000+ at once. Set to None to fetch everything.
    """
    import httpx

    url = build_livewhale_url(
        base_url, group=group, tag=tag, start_date=start_date, end_date=end_date, paginate=paginate
    )
    headers = {"User-Agent": "BrownGradEventsCopilot/0.1 (+personal assistantship tool)"}

    events: list[Event] = []
    with httpx.Client(timeout=25.0, headers=headers, follow_redirects=True) as client:
        while url:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", []):
                if item.get("is_canceled"):
                    continue
                events.append(_livewhale_item_to_event(item, source_url=url))
                if max_events is not None and len(events) >= max_events:
                    return events

            url = (data.get("links") or {}).get("next")  # None on the last page -> stop
    return events
