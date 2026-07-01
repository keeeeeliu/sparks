# Brown Grad Events & Newsletter Copilot

> Status: **Wave A live — Next.js + FastAPI deployed** · Owner: Ke · Last updated: 2026-07-01
> Track: **Real-world / work project** (separate from the personal-interest zero-proof trio)
>
> 🔗 **Live demo:** https://sparks-livid.vercel.app · Frontend on Vercel, backend (FastAPI) on Railway.
> Deploy steps: [`DEPLOY.md`](DEPLOY.md) · Frontend details: [`frontend/README.md`](frontend/README.md)

"Cut monthly newsletter prep from ~3 hours of manually scanning and de-duplicating the campus calendar to ~15 minutes of focused review — and surfaced relevant events I'd previously miss to scrolling fatigue."

A productivity + creativity tool for my graduate assistantship at **Brown University**, where I help with **event planning for the grad community** and **produce the monthly grad newsletter** (gathering on/off-campus events, and reaching out to organizations to inquire about theirs).

**Why this project is special:** it has **real users from day one** — me, fellow GAs, the event-planning team, and ultimately every grad student who reads the newsletter. That makes it the strongest possible portfolio piece *and* genuinely useful at work.

> Resume line to aim for: *"Built an AI tool used by Brown University's grad community team to aggregate campus events, draft the monthly newsletter, and manage event outreach."*

---

## The problem (my actual workflow)

1. **Gather** campus & off-campus events from scattered sources (calendars, forwarded emails, org pages, flyers/PDFs, social posts).
2. **Curate** what's relevant to grad students.
3. **Write** the monthly newsletter (repetitive formatting, takes real time).
4. **Outreach:** email organizations to inquire about their events (many similar emails).
5. **Plan** grad community events.

## What this demonstrates (resume signal)

Extraction + Pydantic validation · RAG / retrieval + dedupe + ranking · LLM generation · **agents + tool-calling** · **human-in-the-loop** (draft → approve → send) · observability · full-stack · **real adoption**.

---

## Scope: build in waves (don't build everything at once)

### Wave A — Newsletter wedge (start here; complete, demoable, saves time monthly)

Collect → extract & structure → dedupe & curate → **draft the newsletter** for human editing.

### Wave B — Outreach assistant

Agent **drafts** personalized inquiry emails to organizations → **I approve** → send. Never auto-send.

### Wave C — Event-planning assist (optional)

Menu / timeline / budget help for grad events (this is where my zero-proof interest can quietly show up).

---

## Architecture (as built — Wave A MVP)

> Decision rationale + evidence: [`docs/decisions/`](docs/decisions/) (ADRs) ·
> Data-source caveats: [`docs/data-sources/`](docs/data-sources/) ·
> Status + gotchas: [`PROGRESS.md`](PROGRESS.md) ·
> **Workflow (human-in-the-loop):** [`docs/workflow.md`](docs/workflow.md)

### Quick start (Streamlit)

```bash
cd project-brown-grad-events-copilot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY
streamlit run app/newsletter_editor.py
```

Sidebar: enter month (e.g. `2026-06`) → **Fetch events for this month** → select → blurbs → export.

**Two ingestion paths, both producing `Event`** (ADR-0001):

- **Structured feeds** (e.g. Brown's LiveWhale calendar JSON) → mapped *directly* to `Event`,
deterministically, no LLM (ADR-0002). This is the primary source.
- **Unstructured text** (paste, email, PDF, arbitrary web HTML) → `SourceItem` → **grounded
LLM extractor** with anti-hallucination guardrails (ADR-0003).

**Curation = facts + judgment, hybrid** (ADR-0004, ADR-0005):

- *Facts* (title/date/location/host) come from the source.
- *Judgment* (`audience`, `grad_relevance`, `category`) is inferred by an LLM **enrichment**
pass that reads the description, using the calendar's structured tags as hints — because
the calendar has **no "graduate" audience tag** and audience tags are sparse.
- Deterministic filtering handles the well-covered dimensions (department 100%, topic ~80%).

`**Target` — the personalization primitive** (ADR-0004): a saved "what I'm looking for"
(audience + categories + departments + keywords + date range + min relevance). One engine,
`(enriched events) × Target → ranked list`, powers newsletter sections, agent queries, and
notifications. Different users/section owners just keep different Targets.

```
feed ─▶ Event (facts)  ─┐
                        ├─▶ enrich_event (LLM judgment) ─▶ filter_by_target ─▶ newsletter / agent answer
text ─▶ extract (LLM) ──┘
```

Pipeline modules: `backend/ingest.py` · `backend/extract.py` · `backend/curate.py` · `backend/models.py`.

---

## How a "Fetch events" click flows end-to-end

The full journey of a single click, from the browser to the LLM and back — a good mental model
for how the whole full-stack app fits together.

### The 30-second map

```
 YOU click "Fetch events"
        │
   ┌────▼─────────────────────────────────────┐
   │  FRONTEND  (Next.js, on Vercel)           │
   │  button → store → fetch() ───────────────┐│
   └───────────────────────────────────────── ││
                                               ▼▼   HTTPS request over the internet
   ┌───────────────────────────────────────────────┐
   │  BACKEND  (FastAPI/Python, on Railway)         │
   │  CORS check → /api/curate → curate_range():    │
   │     ingest (Brown calendar) → dedupe →         │
   │     enrich (OpenAI LLM ×N) → rank → cache      │
   └───────────────────────────────────────────────┘
                                               ▲▲   JSON response back
   ┌────────────────────────────────────────── ││
   │  FRONTEND re-renders with the events ──────┘│
   └─────────────────────────────────────────────┘
```

### Step by step

**In the browser (frontend — Next.js on Vercel):**

1. You click the button in [`frontend/components/DateRangeBar.tsx`](frontend/components/DateRangeBar.tsx). Its `onClick` calls `fetchEvents()`.
2. `fetchEvents()` lives in the **Zustand store** ([`frontend/lib/store.ts`](frontend/lib/store.ts)). It flips `loading = true` (this shows the spinner) and calls `curate(start, end)`.
3. `curate()` in [`frontend/lib/api.ts`](frontend/lib/api.ts) makes the network call — an **HTTPS request** leaves the browser for the Railway backend:

   ```
   fetch(`${NEXT_PUBLIC_API_URL}/api/curate`, { method: "POST", body: { start, end } })
   ```

**Over the network → the server (backend — FastAPI on Railway):**

4. The request arrives. **CORS middleware** checks the origin against `ALLOWED_ORIGINS`. Allowed → it proceeds.
5. The `/api/curate` handler in [`backend/api.py`](backend/api.py) runs `curate_range(start, end)` **in a threadpool** (the work is slow + blocking, so this keeps the server responsive).
6. `curate_range()` in [`backend/pipeline.py`](backend/pipeline.py) runs the pipeline:
   - **ingest** — fetches events from **Brown's LiveWhale calendar** (server→Brown HTTP call). No AI.
   - **dedupe** — collapses duplicate/recurring events. Pure logic.
   - **enrich** — for each unique event, a **concurrent OpenAI LLM call** to score relevance/audience/category. **The slow part (~30–60s)**, and where the **API key is used** — server-side, secret, never in the browser.
   - **rank** — orders them (master's-first, then relevance).
7. The handler maps each internal `Event` → a slim `EventOut`, **stashes them in an in-memory cache** (`_EVENT_CACHE`) so the later "generate blurbs" call can find them by id, and returns JSON: `{ events: [...], usage: {tokens...} }`.

**Back over the network → the browser:**

8. The JSON returns; `curate()` parses it.
9. The store sets `events`, `usage`, `loaded = true`, `loading = false`.
10. **React re-renders automatically** (state changed): the spinner disappears and [`frontend/app/page.tsx`](frontend/app/page.tsx) paints the events into foldable sections with cards, and the summary bar shows "X events · N tokens used."

### The three ideas that make it click

- **Client / server split:** the browser holds *no secrets and does no AI* — it just asks the server. The **OpenAI key stays on Railway**, server-side. (A key in frontend code would be public — never do it.)
- **Why a separate Python backend:** the AI pipeline is Python; the LLM call and key belong on a server, not in the user's browser.
- **Why it's slow, and why that's OK:** wall-clock time is almost entirely the **per-event LLM enrichment** — so those calls run **concurrently**, and the staged loading UI gives honest feedback for a genuinely long operation.

---

## Design (Wave A) — original plan (kept for reference)

### Event schema (Pydantic)

```python
class Event(BaseModel):
    title: str
    description: str
    start: datetime
    end: datetime | None
    location: str
    on_campus: bool
    host_org: str | None
    category: str            # e.g. "career", "social", "academic", "wellness"
    grad_relevance: float    # 0-1 score for grad-student relevance
    registration_url: str | None
    cost: str | None
    source: str
    tags: list[str]
```

### Pipeline

1. **Ingest** — paste/upload event text, forwarded emails, flyers/PDFs (later: source connectors).
2. **Extract** — LLM + structured output → `Event`, with a **repair retry** on validation failure.
3. **Dedupe** — embedding similarity to merge the same event from multiple sources.
4. **Curate/rank** — score `grad_relevance`; sort/group for the audience.
5. **Draft newsletter** — generate an on-brand, nicely formatted draft (template + community voice) for me to edit.

### Wave B addition (agent + HITL)

- LangGraph workflow with a tool `draft_org_inquiry` that composes a personalized email.
- `**approval_gate` (interrupt):** pause, show me the draft, resume only on approval → then send.

### Observability & evaluation

- **Eval:** did extraction capture events correctly (field accuracy)? Newsletter quality via human rating + LLM-as-judge.
- **Tracing:** latency + token cost per run (Langfuse).

---

## Tech stack

- **Backend/agent:** Python **FastAPI** + **LangGraph**
- **Data:** Pydantic schemas; **Postgres + pgvector** (or Chroma to start) for dedupe/relevance
- **LLM:** provider-agnostic wrapper (OpenAI/Anthropic)
- **Frontend (Wave A):** **Streamlit** — `app/newsletter_editor.py` (live fetch, select, blurbs, export). Next.js deferred.
- **Observability:** Langfuse · **Deploy:** Docker → Railway/Fly + Vercel

### Suggested folder structure

```
project-brown-grad-events-copilot/
  README.md
  pyproject.toml
  .env.example
  backend/
    models.py        <- Event schema
    extract.py       <- ingest + extract + repair retry
    dedupe.py        <- embedding-based dedupe
    curate.py        <- relevance scoring / ranking
    newsletter.py    <- draft generation (template + voice)
    outreach.py      <- (Wave B) draft inquiry + approval tool
    api.py           <- FastAPI endpoints
  app/
    newsletter_editor.py   <- Streamlit UI (Wave A)
  run_curate.py, run_newsletter.py, run_extract.py
  eval/
    labeled_events.json
    evaluate.py
  data/
    raw/ output/
```

---

## Important considerations (read before building)

- **Get supervisor / team buy-in early.** Pitch it as "a tool to make our newsletter process faster — can I pilot it?" Official use = a much stronger story and avoids stepping on toes.
- **Respect data & privacy.** Only use event info I'm authorized to handle; store nothing sensitive. Be respectful of external sites' terms if scraping.
- **Never auto-send.** Human approval before any email goes out under my/Brown's name — it's both correct and a great HITL portfolio feature.
- **Start small.** Wave A first; it's a complete project on its own.
- **Visa note:** building a tool to do my assistantship job better is normal work. Commercializing/spinning it out later would need work-authorization care.

---

## Milestones (Wave A)

1. ~~Env + deps + LLM wrapper + `Event` schema; extract one event end-to-end.~~
2. ~~Batch-extract a real month; dedupe.~~
3. ~~Relevance scoring + curation; newsletter draft.~~
4. ~~Streamlit UI~~ — **pilot on a real newsletter cycle** ← next
5. Eval (extraction accuracy + newsletter quality); write up time saved

## Next steps

- [ ] **Pilot:** one real month through Streamlit → paste into shared Google Doc
- [ ] Talk to supervisor/team about piloting
- [ ] Voice tuning (paste past newsletter into blurb prompt)
- [ ] Eval harness + initial commit to git

## References

Mirrors the agentic pattern in `../project-3-event-copilot/README.md` and the high-level docs (`../AI-project-ideas.md`, `../AI-engineer-roadmap.md`). Kept intentionally **separate** from the personal-interest zero-proof projects.