# Grad Events — Frontend (Next.js)

The designed web UI for the Brown Grad Events Copilot. Replaces the Streamlit app with a
Next.js 15 + TypeScript + Tailwind v4 frontend that talks to the FastAPI backend.

Design: Notion-clean layout, Fraunces serif headlines + Inter body, warm-neutral base with a
single sage-green accent. See [`../docs/frontend-plan.md`](../docs/frontend-plan.md).

## Run it (two servers)

**1. Backend (FastAPI)** — from the project root, with the venv + `OPENAI_API_KEY`:

```bash
cd project-brown-grad-events-copilot
source .venv/bin/activate
uvicorn backend.api:app --reload --port 8000
```

**2. Frontend (Next.js)** — in a second terminal:

```bash
cd project-brown-grad-events-copilot/frontend
npm run dev
```

Open **http://localhost:3000**. The frontend calls the backend at `http://localhost:8000`
by default; override with `NEXT_PUBLIC_API_URL` in `.env.local` if needed.

## Workflow (mirrors the Streamlit tool)

1. **Curate (`/`)** — set a From/To date range → **Fetch events** → foldable category sections,
   search / master's-only / min-relevance filters, select events. Shows fetch cost estimate.
2. **Compose (`/compose`)** — **Generate blurbs** → edit → **✨ Improve writing** → per-event
   one-click **Copy** for the blurb, Event link, and Image URL, to paste into the shared Google
   Doc (which has its own format — so we copy pieces, not a pre-formatted export).

## Structure

```
app/page.tsx            Curate screen
app/compose/page.tsx    Compose / export screen
app/global-error.tsx    Top-level error boundary
lib/api.ts              Typed client for the FastAPI endpoints
lib/store.ts            Zustand store (range, events, selection, blurbs) — shared across pages
lib/dates.ts, types.ts  Date helpers + the EventItem view contract
components/              DateRangeBar, SectionPanel (foldable), EventCard, RelevanceChip, CopyField
```

The backend endpoints (`/api/curate`, `/api/blurbs`, `/api/blurbs/improve`) live in
[`../backend/api.py`](../backend/api.py) — a thin wrapper over `curate_range` / `generate_blurbs`
/ `improve_blurb`.
