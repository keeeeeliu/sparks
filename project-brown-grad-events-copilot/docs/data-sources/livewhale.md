# Data card: Brown LiveWhale Events Calendar

- **Source:** `events.brown.edu` (LiveWhale Calendar platform)
- **Used by:** `backend/ingest.py` → `ingest_livewhale_events` (primary structured source)
- **Last profiled:** 2026-06-24 · **Reproduce:** `python scripts/profile_livewhale.py`

## Access
- **JSON API (used):** `https://events.brown.edu/live/json/v2/events/`
- **iCal:** `https://events.brown.edu/live/ical/events/`
- **Filters (REST path segments):** `/group/<name>/`, `/tag/<name>/`,
  `/start_date/YYYY-MM-DD/`, `/end_date/YYYY-MM-DD/`, `/paginate/<n>/`,
  `/response_fields/<csv>/`
- **Extra fields must be requested** via `/response_fields/` (e.g. `description,location,
  group_title,tags,event_types,registration`).
- **Response shape:** `{ "meta": {...}, "links": {...}, "data": [ ...events ] }`.
- **Pagination:** follow `links.next` until null. `meta.total_results` ≈ **1,161** across
  **233 pages** (whole calendar).
- **Quirks:** a trailing-slashless URL 301-redirects (must follow redirects); a
  `User-Agent` is advisable; responses are cached server-side; `Access-Control-Allow-Origin: *`.

## Field reference & reliability
Coverage from a 300-event sample (2026-06-24; reproduce with the profiling script):

| Field | Coverage | Reliability | Notes |
|---|---|---|---|
| `title` | 100% | high | |
| `date_iso` / `date2_iso` | high | high | ISO 8601 w/ tz; `date2_iso` = end (often null) |
| `group_title` | **100%** | **high** | host department/org — our `host_org`; used for deterministic dept filtering |
| `location` | high | medium | free text (e.g. "111 Thayer Street") |
| `description` | high | medium | **HTML** (entities + `<div>`/`<br>`); we strip to text |
| `tags` (topical) | **80%** | medium-high | e.g. `["Entrepreneurship"]` — our `tags` |
| `event_types` (type) | **52%** | medium | crude buckets; may include access markers like "Open to the Public"; **leading whitespace seen** (we `.strip()`) |
| `event_types_audience` | **30%** | **LOW — do not trust** | see Known issue #2 |
| `event_types_campus` | **0%** | n/a | unused at Brown |
| `registration` | rare | high when present | true reg link; we fall back to event `url` |
| `is_canceled` | sparse | high | we skip these |
| `url` | 100% | high | canonical event page (slug sometimes truncated) |

## Known issues / gotchas
1. **Public calendar HTML is JavaScript-rendered.** Plain scraping of `events.brown.edu`
   returns ~**153 chars** of boilerplate (no events). → Use the JSON feed, not scraping.
   (ADR-0002.)
2. **`event_types_audience` is unreliable — partly department-wide defaults.**
   - Brown's public event page **does not display** this field, so the API exposes data the
     UI hides.
   - The vocabulary has **no "graduate" value** (0 grad-tagged in 300; 0 in an Oct–Nov 227
     sample). Values are undergrad class-years, faculty, staff, medical students, divisions.
   - **Reproduced finding:** 6 *unrelated* events (a lit-review workshop, an AI-tools
     session, a research-methods talk, a summer lunch break, a Pride ice-cream party…) share
     the **identical** audience set. Identical sets across unrelated events ⇒ a default
     applied per-department, not curated per-event.
   - **Consequence:** captured on `Event.audience_tags` for transparency, but **excluded
     from enrichment** (would mislead the model). Audience is judged from prose/title.
     (ADR-0005.)
3. **Recurring events appear as separate dated instances.** A 130-event pull had only 62
   unique titles (exhibitions/weekly series). → Dedupe must handle same-title/different-date.
4. **`event_types` may carry leading whitespace** (e.g. `" Open to the Public"`) → stripped
   at ingest.
5. **General principle:** this API exposes more fields than the website renders; never
   assume a feed field is shown to (or curated by) humans.

## Implications for our design
- **Trust:** `group_title` (dept) and `tags` (topic) → safe for deterministic filtering.
- **Don't trust:** `event_types_audience` for audience/grad-relevance → use the LLM over the
  prose (mirrors what a human curator reads on the front end).
- See ADR-0005 for the resulting hybrid decision.
