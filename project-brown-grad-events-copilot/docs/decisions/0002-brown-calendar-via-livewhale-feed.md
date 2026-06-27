# ADR-0002: Use the LiveWhale JSON feed for Brown's calendar, not HTML scraping

- **Status:** Accepted
- **Date:** 2026-06-24

## Context
The primary event source is `events.brown.edu`. The first attempt fetched the page
HTML and extracted readable text with `trafilatura`.

## Evidence
- Scraping the rendered page returned **153 characters** — just "submit an event"
  boilerplate. The event list is **JavaScript-rendered**, so a plain HTTP fetch never
  sees it.
- The extractor correctly produced **0 events** (no text → no events; it did not
  hallucinate). The fetcher was the weak link, not the extractor.
- Brown runs **LiveWhale**, which exposes a REST API:
  - JSON: `https://events.brown.edu/live/json/v2/events/`
  - iCal: `https://events.brown.edu/live/ical/events/`
  - Filters: `/group/<name>/`, `/tag/<name>/`, `/start_date/YYYY-MM-DD/`, `/end_date/`, `/paginate/<n>/`
- The feed is fully structured (title, date_iso, location, group_title, cost,
  event_types, url, …) and paginated: **~1,161 events across 233 pages**.

## Decision
Ingest Brown's calendar via the **LiveWhale JSON feed**, mapped directly to `Event`
(per ADR-0001's structured path). Follow `links.next` pagination with a `max_events`
safety cap. Use `start_date`/`end_date` to pull a single month for the monthly newsletter.

Also: `ingest_web` now **warns when it extracts < 200 chars**, so a silent JS-render
failure is loud next time.

## Alternatives considered
- **Headless-browser scraping (Playwright)** to run the page JS. Rejected for Brown:
  heavier dependency and fragile vs. a clean official API. Still the fallback for other
  JS-heavy sites that lack a feed.
- **Scraping the rendered HTML.** Rejected: returns ~nothing (see evidence).

## Consequences
- Reliable, fast, free, structured ingestion of Brown events; no LLM needed for them.
- Coupled to LiveWhale's API shape (other schools' fields may differ slightly).
- Recurring events arrive as separate dated instances → dedupe required (see PROGRESS).

## Implementation
`backend/ingest.py`: `ingest_livewhale_events`, `build_livewhale_url`, `_html_to_text`.
