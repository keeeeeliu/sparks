# Frontend Plan — Next.js + FastAPI (replacing Streamlit)

> Status: **Plan / pre-build** · Drafted 2026-06-30 · Owner: Ke
> Wave A backend is complete and committed. This is the pivot to a real, designed product surface.

---

## Why we're doing this

Streamlit got us a working, validated tool — but it can't show the two things that matter most
for your goal:

1. **The "full-stack" hiring signal** — your target role (Full-Stack AI Engineer) screens for
   React/TypeScript/Tailwind + an API layer. Streamlit reads as "data scientist / internal tool."
2. **Your design taste** — your stated edge. Streamlit renders the same gray widgets for everyone;
   there's no room for craft. A custom frontend is where "I care how it feels" becomes visible.

The backend was built for this swap: `backend.pipeline.curate_range()` is the single entry point,
returning a clean `CurationResult` of Pydantic `Event`s. FastAPI wraps it; Next.js renders it.
**No backend rewrite — this is additive.**

---

## Stack (most hireable, and genuinely good)

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15 (App Router) + TypeScript** | The default for modern full-stack AI products |
| Styling | **Tailwind CSS** + **shadcn/ui** | Fast, beautiful, fully customizable (not a locked theme) |
| Server state | **TanStack Query** | Caching, loading/error states, retries — for free |
| Client state | **Zustand** (light) | Track selections + edited blurbs without ceremony |
| Backend | **FastAPI** (Python) | Thin wrapper over existing `curate_range` / blurb functions |
| LLM | unchanged | Reuses `backend/llm.py`, `curate.py`, `newsletter.py`, `telemetry.py` |
| Deploy | **Vercel** (frontend) + **Railway/Fly** (FastAPI) | Standard, free-tier friendly, live URLs |

Keep Streamlit as your **personal internal tool** during the transition. Don't delete it until the
Next.js app does everything you actually use.

---

## Architecture

```
Next.js (Vercel)                FastAPI (Railway/Fly)            Existing backend
─────────────────               ─────────────────────           ──────────────────
date range  ──POST /api/curate──▶ curate_range(start,end) ──────▶ ingest→dedupe→enrich
  ◀── events[] + usage ──────────                                 (telemetry per run)
select events (client state)
  ──POST /api/blurbs (stream)──▶ generate_blurbs() ─────────────▶ blurb LLM calls
  ◀── blurbs stream in ──────────
edit a blurb
  ──POST /api/blurbs/improve──▶ improve_blurb(text, ev) ────────▶ improve LLM call
  ◀── improved text ─────────────
export → copy/download markdown (client-side render or reuse render_newsletter)
```

### FastAPI endpoints (`backend/api.py` — new)
- `POST /api/curate` → body `{ start: date, end: date }` → `{ events: Event[], usage: UsageSummary }`.
  Runs the slow pipeline in a threadpool (it's blocking + concurrent internally).
- `POST /api/blurbs` → body `{ events: Event[] }` → blurbs. **Stream via SSE** so blurbs appear as
  each completes (the "streaming UI" signal; matches the existing concurrent generation).
- `POST /api/blurbs/improve` → body `{ text, event }` → `{ blurb }`.
- `GET /api/health` → smoke check.
- CORS allow the Vercel origin + `localhost:3000`.
- `Event` and `UsageSummary` are Pydantic, so FastAPI serializes them natively — the TS types mirror
  them 1:1.

### Pipeline timing note
`curate_range` takes ~30–60s for a full month. Two acceptable UX paths:
- **v1:** plain POST + a polished skeleton/loading state ("Fetching & enriching ~80 events…").
- **v2 (stretch):** SSE progress stream ("enriched 40 / 105") — a strong portfolio touch.

---

## Screens (the proven Streamlit workflow, redesigned)

A single, calm three-step flow. Could be one page with sections, or a stepper.

### 1. Setup
- **From / To** date pickers, defaulting to the **15th-to-15th** window (newsletter publishes
  mid-month — see `[[newsletter-coverage-window]]`). One **Fetch** action.

### 2. Curate (the hero screen — where taste shows)
- Events grouped by section (Career / Academic / Wellness / Arts / Social / Other).
- Each **event card**: title (plain), date · host · relevance, the one-line relevance reasoning,
  thumbnail when present, a quiet **↗ View event page** link, and a **select** toggle.
- Filters: search, master's-only, min-relevance.
- Persistent summary: "X events · Y selected · est. $Z to fetch" (reuse telemetry `usage`).

### 3. Compose & export
- Selected events → **Generate blurbs** (stream in).
- Inline-editable blurb per event + **✨ Improve writing** button (calls `improve_blurb`).
- Live **newsletter preview** (rendered markdown) beside the editor.
- **Copy markdown** / **Download** / per-event copy of link + image URL (for the Google Doc).

### Later (Wave B) — designed-in now, built later
- An **approval inbox**: agent-drafted outreach emails in a "draft → approve → send" queue.
  The frontend should leave a natural home for this (a second nav item / route).

---

## Design direction (LOCKED 2026-06-30)

**Notion-clean / minimal layout, elevated by serif headlines + one warm terracotta accent.**
Crisp, tidy, lots of whitespace — but not generic, thanks to editorial type and a confident accent.

- **Layout/mood:** Notion-clean — crisp, neutral, very tidy, content-first, quiet chrome. Familiar
  productivity feel, but refined.
- **Type:** **serif for headlines** (Fraunces or Source Serif 4) + **clean sans for body/UI** (Inter).
  The serif display type is what lifts it above a typical app.
- **Color:** warm-neutral base (warm white ~`#FBF9F6`, soft ink ~`#241F1B`, muted text ~`#6B635C`,
  hairline borders ~`#EAE4DC`) + **warm terracotta accent** (~`#C2613F`). Accent used sparingly
  (selected state, high-relevance chip, primary buttons) = premium.
- **Cards:** soft hairline borders, gentle radius, real spacing; relevance shown as a quiet **tier
  chip** (high/mid/low), not a loud number.
- **Motion:** subtle — fade/slide as blurbs stream in, a soft state on the Improve button. Restraint.
- **Details that delight:** thoughtful empty states, a satisfying "copied!" confirmation, a real
  loading state, keyboard-friendly selection.

---

## Recommended sequence: design the visuals FIRST (a spike)

Your instinct is right. For a design-led build, prototype the look before wiring data — it de-risks
the part you care about and is far more motivating than scaffolding plumbing.

**Step 0 — Visual spike (do this first):** Build a **static prototype of the Curate screen** with
*fake* events — no backend, no API. Iterate purely on look and feel until you love it. Pin the
typography, color, spacing, and card design. (Options for *how* below.)

**Then implement for real:**
1. **Scaffold (½ day):** Next.js + FastAPI talking, `GET /api/health`, typed API client, CORS,
   deploy a hello-world to Vercel + Railway. Always-runnable from commit #1.
2. **Curate screen with real data:** `POST /api/curate`, render the grouped cards from the spike
   design, filters, selection state.
3. **Compose screen:** streaming blurbs, inline edit, Improve button, live preview, export.
4. **Polish:** apply the full design language, loading/empty/error states, responsive, basic a11y.
5. **Ship:** deploy, README writeup (problem → architecture → **measurable results**: time saved,
   eval accuracy, cost/request), short demo video.

Keep the app always-runnable; commit small and often (your craft-doc rule).

---

## "Can we bring Claude to design the visuals first?" — yes. Three ways:

| Approach | Best for | How |
|---|---|---|
| **A. Claude.ai artifact** | Fastest pure look-iteration, zero setup | Ask Claude.ai to generate an interactive React/HTML mockup of the Curate screen with fake data. Tweak the prompt until the vibe is right. Then bring it here to implement. |
| **B. Claude Code builds the spike here** | Living in your real stack, real browser | I scaffold a Next.js page (or a single Tailwind HTML file) with mock events so you see it in *your* browser and we iterate together in-repo. |
| **C. Hybrid (recommended)** | Best of both | Explore the *vibe* fast in a Claude.ai artifact → once you love a direction, I rebuild it properly here as the real Next.js component, then we wire the API. |

Either way: **pin the design language on fake data first, then connect `curate_range`.**

---

## Decisions (locked 2026-06-30)
1. **Vibe:** Notion-clean / minimal.
2. **Typography:** serif headlines (Fraunces/Source Serif) + sans body (Inter).
3. **Accent:** warm terracotta (~`#C2613F`).
4. **Spike route:** **Hybrid** — explore the look in a Claude.ai artifact first, then Claude Code
   rebuilds the chosen direction as real Next.js and wires the API.

## Progress
- ✅ **Visual spike** (Claude.ai artifact) → design language locked (Notion-clean + Fraunces serif + sage-green accent).
- ✅ **Scaffold:** Next.js 15 + TS + Tailwind v4 in `frontend/`.
- ✅ **Curate screen** (`/`): date-range setup, Fetch, foldable category sections, filters, selection.
- ✅ **Compose screen** (`/compose`): generate blurbs, edit, ✨ Improve, copy-paste-ready Event/Image
  URL fields, Copy-markdown export. Shared Zustand store across pages.
- ✅ **Backend wired:** `backend/api.py` (FastAPI) over `curate_range` / `generate_blurbs` /
  `improve_blurb`; typed client in `lib/api.ts`. Verified end-to-end on a live date range
  (19 events, real blurbs, cost tracked).

## Next (later)
- Deploy (Vercel + Railway/Fly); persist store across hard refresh.
- **True fetch progress bar (SSE):** the fetch loader is currently a time-based staged
  spinner + indeterminate bar + elapsed timer (`components/FetchProgress.tsx`) — good enough
  and no backend change. Upgrade path: stream real progress from the backend via SSE
  (e.g. "enriched 40 / 105") so the bar reflects actual completion. Deferred by choice 2026-06-30.
- Streaming blurb generation (SSE).
- Wave B: agent + approval-inbox route.
- ~~Swap the "Flyer" placeholder for real feed thumbnails~~ (done); a11y + responsive polish.
