# Newsletter workflow (Wave A)

How events move from the calendar feed to a paste-ready draft — and **where a human
must decide** what gets included.

This is operational documentation (how we work), not an architecture decision record
(why we chose X over Y). The goal is to make the **human-in-the-loop gate** obvious to
teammates, reviewers, and future-you.

---

## Roles

| Role | Who | Responsibility |
|------|-----|----------------|
| **Aggregator** | Ke (grad GA / newsletter team) | Review the curated pool, **choose which events belong** in this month's draft, generate blurbs for those picks only |
| **Editor** | Whoever owns the shared Google Doc | Final voice, formatting, images, **"Don't Miss" / hero placement**, send |

The tool assists aggregation and drafting. It does **not** replace editorial judgment on
what is must-see or how the newsletter reads when published.

---

## Pipeline overview

```
LiveWhale feed
    → ingest + dedupe + LLM enrichment + ranking
    → full event pool for the month (UI or curated report)
    → HUMAN SELECTS events          ← verdict lives here
    → blurbs for selected only
    → newsletter draft (.md)
    → HUMAN pastes + edits in Google Doc
    → published newsletter
```

**Automated:** ingest, dedupe, enrichment, section grouping, blurb generation for picks.  
**Human verdict required:** which events are in the draft at all.  
**Human edit required:** paste, proofread, images, editorial emphasis, publish.

---

## Primary workflow — Streamlit UI

```bash
cd project-brown-grad-events-copilot
source .venv/bin/activate
streamlit run app/newsletter_editor.py
```

Requires `.env` with `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` + `LLM_PROVIDER=anthropic`).

### Steps

1. **Sidebar → enter month** (e.g. `2026-06`) → **Fetch events for this month**
   - Pulls live from Brown's LiveWhale calendar, dedupes, enriches **every unique event**
     in that month (~30–60s depending on count; June ≈168, August ≈82).
   - Optional: **Save to disk after fetch** writes `data/output/enriched_events.json`.
2. **Select events tab** — browse all events grouped by section (Career, Academic, Wellness,
   Arts, Social, Other). Each row shows date/host, **relevance score + one-sentence summary**
   (same text as the curated report), thumbnail when available.
3. **Check events** you want in the newsletter (your aggregator verdict).
4. **Blurbs & export tab** → **Generate blurbs** → edit text → copy **links + image URLs**
   into the shared Google Doc, or **Download markdown**.

**Changing the month text does not auto-refresh** — click **Fetch events for this month**
again to load a new month.

### What the UI shows (and doesn't)

| Shown | Not shown |
|-------|-----------|
| All events in the fetched month | No "Don't Miss" / hero tier |
| Relevance summary per event | No auto-selection by score |
| Event link + image URL for copy-paste | No Google Docs API / auto-publish |
| Optional search / master's-only / min-relevance filters | |

### UI list order (important)

Events are grouped by **newsletter section** (Career → Academic → … → Social → Other),
then sorted **master's-facing first, then relevance score within each section**.

A high-scoring social event (e.g. 0.9) can appear **far down the scroll list** because
Social is the fifth section — that is **not** a low global rank. Within Social it may be #1.

---

## Alternate workflow — CLI (dev / scripts)

Useful for batch runs, cached re-runs, or automation without the UI.

### 1. Curate the month

```bash
python run_curate.py --month 2026-07 --save
```

Use `--max N` only to **limit LLM cost during experiments**. For a full newsletter month,
omit `--max` or set it high enough to cover all unique events — otherwise events late in
the chronological enrich queue are **silently dropped** (see PROGRESS.md gotcha).

**Outputs:**
- `data/output/curated_<start>_<end>.md` — full menu with scores + reasoning
- `data/output/enriched_events.json` — structured cache

### 2. Human selection (CLI)

YAML selection file (optional audit trail for scripts):

```yaml
month: "2026-07"
events:
  - "Master's Career Services | US Job Search: Insights for International Students"
```

Example: `data/selections/july_2026_example.yaml`

### 3. Generate draft

```bash
python run_newsletter.py --month 2026-07 --from-selection data/selections/july_2026_example.yaml
```

Output: `data/output/newsletter_<start>_<end>.md`

---

## What is automated vs. human

| Step | Automated? | Human verdict? |
|------|------------|----------------|
| Fetch + structure events | Yes | No |
| Grad relevance scoring + section grouping | Yes (LLM enrichment) | No — suggestions only |
| **Which events appear in the draft** | **No** | **Yes — checkboxes in UI (or YAML for CLI)** |
| Blurb text for selected events | Yes (LLM, editable) | Review + edit in Doc |
| "Don't Miss" / hero events | No | Yes — editor in Google Doc |
| Publish / send | No | Yes |

---

## Selection contract

```python
EventSelection = { month: str | None, events: list[str] }  # titles only, flat list
```

- **No highlights tier** — inclusion is binary: in the draft or not.
- Titles matched fuzzily (handles apostrophe variants).
- Human-selected events included in draft export even if category is "Other / Administrative".

---

## Commands (quick reference)

```bash
# UI (primary)
streamlit run app/newsletter_editor.py

# CLI curation + cache
python run_curate.py --month 2026-07 --save

# CLI draft from YAML selection
python run_newsletter.py --month 2026-07 --from-selection data/selections/july_2026_example.yaml

# Fast blurbs without LLM (dev)
python run_newsletter.py --month 2026-07 --no-llm

# NOT normal workflow — model auto-picks (experiments only)
python run_newsletter.py --month 2026-07 --auto
```

---

## Related docs

- **[PROGRESS.md](../PROGRESS.md)** — what's built, verified, gotchas, next
- **[docs/decisions/](decisions/)** — ADRs for ingestion, curation, concurrency
- **`backend/newsletter.py`** — blurb generation + draft assembly
- **`app/newsletter_editor.py`** — Streamlit UI
