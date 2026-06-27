# Brown Grad Events & Newsletter Copilot

> Status: **Idea / pre-build** · Owner: Ke · Last updated: 2026-06-21
> Track: **Real-world / work project** (separate from the personal-interest zero-proof trio)

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

## Architecture (as built — Wave A in progress)

> This reflects the current implementation and supersedes parts of the original "Design"
> plan below. Decision rationale + evidence is in `**[docs/decisions/](docs/decisions/)`** (ADRs);
> external-source facts/caveats are in `**[docs/data-sources/](docs/data-sources/)**` (data cards);
> current status, what's verified, and open concerns are in `**[PROGRESS.md](PROGRESS.md)**`.

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
- **Frontend:** **Next.js + Tailwind** (or Streamlit for a fast MVP), with an editable newsletter preview
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
  frontend/          <- newsletter preview + editor, outreach approval UI
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

1. Env + deps + LLM wrapper + `Event` schema; extract one real event end-to-end.
2. Batch-extract from a real month of sources; add dedupe.
3. Relevance scoring + curation; generate a first newsletter draft.
4. Simple editable frontend; pilot it on an actual newsletter cycle.
5. Eval (extraction accuracy + newsletter quality); write up time saved.

## Next steps

- [ ] Observe my next newsletter cycle; note sources + where time goes (this is my requirements doc).
- [ ] Talk to the team/supervisor about piloting it.
- [ ] Scaffold the `Event` schema + extractor on real pasted event text.

## References

Mirrors the agentic pattern in `../project-3-event-copilot/README.md` and the high-level docs (`../AI-project-ideas.md`, `../AI-engineer-roadmap.md`). Kept intentionally **separate** from the personal-interest zero-proof projects.