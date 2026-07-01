# Progress Log — Brown Grad Events & Newsletter Copilot

> Living document. Append as you build. Newest entries at the top of each section.
> Purpose: track **what's built, what's next, and current concerns** (the operational "where are we").
> The **newsletter workflow (human-in-the-loop)** is in [`docs/workflow.md`](docs/workflow.md).
> The **why behind technical decisions** lives in `docs/decisions/` (ADRs) — this file links to them.

- **Project:** Wave A — Newsletter wedge (ingest → extract → dedupe → curate → draft)
- **Owner:** Ke
- **Last updated:** 2026-06-30 (telemetry + eval harness; flexible date range; blurb voice tuning + Improve button)

---

## Status at a glance

| Wave A milestone | State |
|---|---|
| 1. Env + deps + LLM wrapper + `Event` schema; extract one event end-to-end | **Verified live (LiveWhale feed → 50 events; enrichment runs)** |
| 2. Batch-extract a real month of sources + dedupe | **Verified live (July: 331 instances → 105 unique; dedupe runs before enrichment)** |
| 3. Relevance scoring + curation + first newsletter draft | **Newsletter draft generator live** (`backend/newsletter.py`, `run_newsletter.py`); pilot on real cycle not started |
| 4. Editable frontend; pilot on a real cycle | **Streamlit MVP live** (`app/newsletter_editor.py`) — live fetch, select, relevance summaries, blurbs, export; **pilot not started** |
| 5. Eval (extraction accuracy + newsletter quality) + write up time saved | **Harness built** (`eval/evaluate.py`, `eval/label_events.py`) — ground-truth labeling + pilot "time saved" number still needed |

---

## What has been built

### Ingestion (`backend/ingest.py`)
- **Two-path model:** UNSTRUCTURED sources → `SourceItem` → LLM extractor → `Event`. STRUCTURED feeds → mapped directly to `Event` (no LLM). Both end as `Event`, so downstream is unchanged.
- `ingest_paste` — pasted/typed text. *Verified (no LLM needed).*
- `ingest_email` — forwarded/pasted email or newsletter body (manual, no live inbox). *Verified.*
- `ingest_pdf` — text-based PDFs via `pypdf`. *Not yet run on a real PDF.*
- `ingest_web` — single URL → readable text via `httpx` + `trafilatura`. Now **warns when <200 chars extracted** (JS-rendered page → look for a feed). *Verified: returns ~empty on JS calendars, as expected.*
- `ingest_web_sources` / `load_web_sources` — fetch every URL in the curated `sources.yaml`. Seed of the future scheduled monitor. *Not yet run.*
- `ingest_livewhale_events` (+ `build_livewhale_url`, `_html_to_text`) — **structured LiveWhale JSON feed → `Event` directly, no LLM.** Supports group/tag/date filters, **follows pagination via `links.next`**, skips canceled events, strips HTML, maps `registration` → `registration_url`, **`thumbnail` → `image_url`**, coerces numeric **`cost` → string**. *Verified live on May–August 2026.*

### Schemas (`backend/models.py`)
- `SourceItem`, `SourceType` (paste/pdf/image/email/newsletter/web).
- `Event` — README schema **+ provenance fields** (`source_ref`, `evidence`, `extraction_confidence`) **+ enrichment fields** (`audience`, `audience_evidence`, `relevance_reasoning`, `image_url`). Most fields `Optional` so unknowns stay null instead of being invented.
- `Target` — the personalization primitive: audience/categories/keywords/date-range/min_relevance. Powers newsletter sections, agent queries, notifications. *Verified.*
- `ExtractionResult` — `{ events: [...] }` wrapper the LLM returns. *Verified.*

### Dedupe (`backend/dedupe.py`) — runs BEFORE enrichment
- `dedupe_events` — groups by **normalized title + host**, keeps the richest-description instance as the representative, and records the **span** (`start`..`end`) + `occurrence_dates` / `occurrence_count`. Deterministic, no LLM/embeddings yet. *Verified live (2026-06-27): July 331 dated instances → 105 unique (a 39× exhibit, 31× building-access, 29× B-Lab each collapsed to one with a duration). This is what makes a full month affordable to enrich.*
- New `Event` fields: `occurrence_count`, `occurrence_dates` (set by dedupe).
- **Limits (future work):** exact-ish match only — won't merge typo/cross-source variants or same event listed under two different hosts; conservative by design (under-merge > over-merge).

### Pipeline orchestration (`backend/pipeline.py`) — shared by CLI / future API / UI
- **`curate_range(...)`** — single entry point: ingest → dedupe → enrich → filter → rank. Returns `CurationResult` (ranked list, enriched cache, counts, target).
- **`rank_for_newsletter`**, **`default_grad_target`**, **`resolve_month_range`**, **`list_hosts_in_range`** — helpers callers reuse without duplicating logic.
- **`run_curate.py` is now a thin CLI wrapper** over this module (refactored 2026-06-27 so the frontend/API won't re-implement the flow).

### Presentation / sectioning (`backend/report.py`) — shared grouping for all views
- **`SECTIONS`**, **`group_into_sections`**, **`render_markdown`**, **`write_markdown_report`**, **`format_when`**, **`format_relevance_summary`** — one source of truth for section grouping and the curated-report relevance line (UI reuses `format_relevance_summary`).
- **`Event.is_masters_facing()` / `is_grad_facing()`** on the model — shared audience flags for ranking + display.

### Curation (`backend/curate.py`) — hybrid (ADR-0005)
- `enrich_event` / `enrich_events` — **LLM judgment pass**: reads the description **+ source tags as hints** (host, type, topic tags, audience tags) to infer `audience`, `grad_relevance`, `category`, `tags` (grounded: ["unspecified"] when not stated, with `audience_evidence`). One repair retry; batch isolates per-item failures. **`enrich_events` now runs calls concurrently** (`max_workers=8`, order-preserving — see ADR-0006). *Verified live (2026-06-27): full July month (105) in ~27s concurrent.*
- **Audience now supports degree-level granularity (2026-06-27):** enrichment prompt recognizes `"masters"` and `"doctoral"` when the prose **explicitly** states the degree level (always also adds `"graduate"`); never guessed from a department name. *Verified live on full July: 18 events correctly tagged master's (e.g. "Master's Career Services", "Financing Your Online Masters Degree", MBSR teacher training).*
- **Holistic scoring (2026-06-27):** `grad_relevance` prompt rewritten to value a WELL-ROUNDED grad life — social, wellness, arts, community, and fun count as much as career/academic; explicitly says don't down-rank events for being social/creative/recreational, with a 0.0–1.0 rubric. Added `relevance_reasoning` (one-sentence rationale) to `_Enrichment` + `Event` for transparency. *Verified live: category averages rebalanced (wellness 0.79, arts 0.77 now ≈ career 0.80, vs arts ~0.4 before). The LGBTQ Center "Crafting Queer Keepsakes" DIY journal workshop — previously invisible — now scores 0.80 ("creative/reflective space ... community and identity").*
- `filter_by_target` (+ helpers) — **deterministic selection** on well-covered dimensions: date / department (`host_org`, 100%) / audience / topic + min_relevance, ranked by `grad_relevance`. Keeps `all`/`unspecified` events so borderline ones aren't silently dropped. *Verified live: audience_tags captured (13/40), department filter exact.*
- `Event.audience_tags` now captures `event_types_audience` from the feed (raw hint; Brown has no "graduate" value). `Target.departments` filters on host org.

### Blurb voice + Improve writing (`backend/newsletter.py`) — 2026-06-30
- **Voice tuning:** `_BLURB_SYSTEM` rewritten from "one sentence, ~30 words" to the team's ACTUAL
  voice — warm/peer-to-peer, 2–3 sentences (~25–70 words), often opening with a hook question or
  inviting imperative, with **4 real past-newsletter blurbs as few-shot examples**. The old
  one-sentence constraint was why generated blurbs "sounded weird." `_BlurbOut` max_length 280 → 600.
- **`improve_blurb(text, ev=None)`** — proofread + lightly rewrite an existing (human-edited) blurb
  in the newsletter voice. Grounded (won't add facts beyond the text; event facts passed only as a
  guardrail). Returns the original unchanged on failure. Labeled `"improve"` in telemetry.
- **Streamlit:** each blurb in the draft tab now has an **✨ Improve writing** button (rewrites in
  place via `st.session_state` + `st.rerun()`).

### Newsletter draft (`backend/newsletter.py`) — copy-paste for shared Google Doc
- **Workflow doc:** [`docs/workflow.md`](docs/workflow.md) — roles, pipeline, human verdict gate, Streamlit-first steps.
- **Primary workflow (UI):** [`app/newsletter_editor.py`](../app/newsletter_editor.py) — fetch month live → checkbox selection → relevance summaries → blurbs → export markdown. No "Don't Miss" block — editorial highlighting happens in Google Docs.
- **CLI workflow:** `run_newsletter.py` + optional YAML selection (`data/selections/*.yaml`) for scripts.
- **`EventSelection`** — `{ month, events: [titles] }`. Example: `data/selections/july_2026_example.yaml`.
- **`build_draft_from_blurbs`**, **`prepare_draft_from_selection`** — human picks only; selected events included in all sections (incl. Other).
- **`run_newsletter.py`** — loads cache or uses selection YAML. *Verified: 8 selected → ~3s blurbs.*

### Streamlit UI (`app/newsletter_editor.py`) — 2026-06-27, updated 2026-06-30
- **Flexible date range (2026-06-30):** sidebar now has **From / To** `date_input` pickers (was a
  YYYY-MM month box), defaulting to the **15th-to-15th** window — because the newsletter publishes
  mid-month and covers ~mid-month to mid-next-month (see [[newsletter-coverage-window]] memory).
  Backend always supported arbitrary ISO ranges; only the UI was forcing calendar months.
- **Live fetch:** **Fetch events for this range** → `curate_range(..., max_enrich=None)` (enriches **all** unique events; no silent cap). Fetch note now shows token/cost estimate (telemetry).
- **Browse:** all events by section; `format_relevance_summary()` on each row; thumbnails + links on draft tab.
- **Select:** checkboxes (human verdict); optional search / master's-only / min-relevance filters.
- **Export:** generate/edit blurbs, **✨ Improve writing** button per blurb, download markdown. No YAML in UI.
- *Verified live: May/June/July/August 2026 fetches; August required `cost` int→string fix at ingest.*

### LLM wrapper (`backend/llm.py`)
- `complete_json(system, user)` — provider-agnostic (OpenAI `json_object` mode / Anthropic prefill). `temperature=0.0` for deterministic extraction. *Not yet run with a live key.*

### Extraction (`backend/extract.py`)
- `extract_events(item)` — grounded prompt → JSON → Pydantic validate → **one repair retry** on failure.
- **Evidence verifier** `_evidence_in_source` drops any event whose quoted evidence isn't actually in the source (whitespace/case-normalized containment). *Verified: real quote passes, fabricated quote rejected.*

### Telemetry (`backend/telemetry.py`) — 2026-06-30
- **In-process LLM cost + latency tracker.** Thread-safe (required: `enrich_events` is concurrent). Records `label`, `model`, `tokens_in`, `tokens_out`, `latency_ms` per call.
- `complete_json` now accepts a `label` param (`"enrich"`, `"extract"`, `"blurb"`, `"enrich-repair"`, `"extract-repair"`) — lets the summary break down cost by call type.
- `curate_range` calls `telemetry.reset()` at the start → `CurationResult.usage` is a `UsageSummary` snapshot for that run only.
- **Streamlit UI** (`_fetch_month`) appends `result.usage` to the fetch note (e.g. *"105 LLM calls · 48,320 in / 12,410 out tokens · 27.4s wall · est. $0.0218"*).
- **CLI scripts** (`run_curate.py`, `run_newsletter.py`) print a per-label breakdown after each run.
- Cost table: approximate mid-2026 pricing for `gpt-4o-mini`, `gpt-4o`, `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-8` — update `_COST_PER_M` if pricing changes.

### Eval harness (`eval/`) — 2026-06-30
- **Two-mode design:** *consistency eval* (no labeling needed) and *accuracy eval* (hand-labeled ground truth).
- `eval/evaluate.py` — main eval script:
  - **Consistency mode** (default): re-enriches a random sample from `enriched_events.json`, compares new output to the previous run's output. Detects prompt/model drift without any manual labeling. `python eval/evaluate.py --n 25`.
  - **Accuracy mode**: compares against `eval/labeled_events.json`. `python eval/evaluate.py --labels eval/labeled_events.json`.
  - Metrics: grad-facing accuracy, masters-facing accuracy, category exact match, relevance bucket (high/mid/low) match. Reports telemetry cost of the eval run.
- `eval/label_events.py` — interactive labeling CLI: walks through a random sample of cached events, shows cached enrichment, lets you confirm or correct each label, saves to `eval/labeled_events.json`. Supports `--append` to grow the label set over time.
- `eval/labeled_events.json` — empty starter (0 events). Run `python eval/label_events.py --n 25` to populate.
- **Why consistency eval first:** it runs immediately (no labeling), catches regressions if you change the enrichment prompt or switch models, and gives you a baseline before investing in ground-truth labeling.

### Next.js frontend + FastAPI (2026-06-30) — replacing Streamlit
- **`frontend/`** — Next.js 15 + TS + Tailwind v4. Design: Notion-clean, Fraunces serif headlines +
  Inter body, warm-neutral base + sage-green accent (see [`docs/frontend-plan.md`](docs/frontend-plan.md)).
- **Curate screen** (`/`): From/To date range → Fetch → **foldable category sections**, search /
  master's-only / min-relevance filters, selection, fetch-cost estimate.
- **Compose screen** (`/compose`): Generate blurbs → edit → **✨ Improve** → per-event one-click
  **Copy** for blurb / Event link / Image URL (the shared Google Doc has its own format, so we copy
  pieces — no pre-formatted markdown export). Shared Zustand store across pages.
- **`backend/api.py`** (FastAPI) — thin wrapper: `POST /api/curate` (→ `curate_range`), `/api/blurbs`
  (→ `generate_blurbs`), `/api/blurbs/improve` (→ `improve_blurb`), `/api/health`. Maps `Event`→`EventOut`,
  runs the blocking pipeline in a threadpool, keeps enriched events in a process cache so blurb
  endpoints resolve by id. CORS for `localhost:3000`. Deps added: `fastapi`, `uvicorn[standard]`.
- **Verified live end-to-end (2026-06-30):** `/api/curate` on 2026-07-08–09 → 19 events, all fields
  mapped, sections aligned, usage $0.0037; `/api/blurbs` + `/api/blurbs/improve` return voice-tuned text.
- **Run:** backend `uvicorn backend.api:app --reload --port 8000`; frontend `cd frontend && npm run dev`
  → http://localhost:3000. Streamlit kept as the internal fallback tool. See `frontend/README.md`.
- **Still mock-free but local-only:** `_EVENT_CACHE` is process-global (single-user); store resets on
  hard refresh (no persistence yet); blurb streaming/SSE + deploy are future work.

### Tooling / scaffolding
- `requirements.txt`, `.env.example`, `.gitignore`, `sources.example.yaml`.
- `run_extract.py` — end-to-end smoke test for Stage 1 (text / PDF / URL / feed).
- `run_curate.py` — thin CLI over **`backend.pipeline.curate_range`** + **`backend.report`**. Flags unchanged (`--month`, `--max`, `--workers`, `--save`, etc.). *Verified live on July 2026.*
- `data/raw/sample_event.txt` — realistic test event.
- `.venv/` created, deps installed.

**Verified live (2026-06-27, real `OPENAI_API_KEY`):** full pipeline on July — LiveWhale ingest (331 instances) → dedupe (→105 unique, with duration spans) → holistic enrichment (audience incl. master's, grad_relevance + reasoning) → master's-first ranking via `Target`. Demoable via `run_curate.py --month 2026-07`.

**Enrichment performance — RESOLVED via concurrency ([ADR-0006](docs/decisions/0006-concurrent-per-event-enrichment.md)).** Controlled A/B on the same 105-event July month, back-to-back, same code path:
- `--workers 1` (sequential): **206.9s** (1.97s/event). `--workers 8` (concurrent): **27.4s** (0.26s/event) → **~7.5× speedup**, well outside the ~25% API variance.
- Kept **one LLM call per event** for accuracy + per-item isolation; sped it up with a thread pool (default `--workers 8`), NOT by batching many events into one prompt. Cost ~unchanged (token-based, not per-call).
- `enrich_events(events, *, max_workers=8)` preserves input order + isolates failures (`_safe_enrich`).
- Artifacts: readable `data/output/curated_<range>.md`, structured `data/output/enriched_events.json`.

**Data contract for future UI/API (2026-06-27):**
- **Source of truth:** `Event` objects from `backend.pipeline.curate_range(...)` → `CurationResult`.
- **Machine-readable cache:** `enriched_events.json` (all enriched events; reuse to skip re-paying for LLM).
- **Human-readable preview:** `curated_<range>.md` (sectioned report via `backend.report.render_markdown`) — a *view*, not the foundation.
- **Section grouping:** always use `backend.report.group_into_sections()` so UI, report, and newsletter stay aligned.
**Still not exercised:** unstructured LLM *extraction* path on a live key (`run_extract.py` on pasted text/URL — only the structured feed path has been run), real PDF, real URL fetch.
**Env status:** `OPENAI_API_KEY` in `.env` works (gitignored, not tracked). Note: key has a leading space (`OPENAI_API_KEY= sk-...`) but `python-dotenv` strips it — confirmed working.

---

## What is yet to come

### Open design questions (to discuss — flagged by Ke 2026-06-27)
1. **How should we SCORE events? (`grad_relevance` methodology.)** Current single 0–1 scalar conflates two things — *audience fit* ("is this for grad students?") and *appeal/quality* — which causes clustering at 0.80 and makes the number hard to interpret. Options to weigh: (a) keep one scalar but rank *within category*; (b) split into sub-scores (fit vs appeal); (c) listwise/pairwise LLM ranking instead of absolute scores. **Can't judge "right" without the eval harness** — so this is coupled to the eval task. Ke wants to revisit; no decision yet.
2. **One global ranking vs. ranking BY CATEGORY/purpose.** **Leaning confirmed for UI + newsletter:** sectioned-by-purpose (Career / Academic / Wellness / Arts / Social / Other). UI browse order follows sections, not global score — see [`docs/workflow.md`](docs/workflow.md). Eval may still revisit whether absolute `grad_relevance` adds value within sections.

### Immediate next (recommended order)
> Reordered 2026-06-30: telemetry + eval harness DONE.
> **Next: pilot → label → run eval → record time-saved number.**

1. ~~**Newsletter draft (selection-driven)**~~ **DONE (2026-06-27)**
2. ~~**Streamlit MVP**~~ **DONE (2026-06-27)** — `app/newsletter_editor.py` (live fetch, checkboxes, relevance summaries, blurbs, export).
3. ~~**Telemetry (cost + latency)**~~ **DONE (2026-06-30)** — `backend/telemetry.py`; `CurationResult.usage`; CLI + UI display.
4. ~~**Eval harness**~~ **DONE (2026-06-30)** — `eval/evaluate.py` (consistency + accuracy modes); `eval/label_events.py`.
5. ~~**Flexible date range**~~ **DONE (2026-06-30)** — From/To pickers, 15th-to-15th default.
6. ~~**Voice tuning**~~ **DONE (2026-06-30)** — real voice + 4 few-shot examples in `_BLURB_SYSTEM`; `improve_blurb` + ✨ button.
7. **Pilot paste** into real Google Doc using UI output → record time saved before/after (qualitative result already in: hours → minutes, less distraction).
8. **Label events** for accuracy eval: `python eval/label_events.py --n 25` → then `python eval/evaluate.py --labels eval/labeled_events.json`.
9. **Next.js + FastAPI frontend** (greenlit 2026-06-30) — real designed UI to replace Streamlit; bake in date range + Improve button + (Wave B) approval gate. Needs an architecture/design plan.
10. **Dedupe upgrade** — fuzzy/cross-source matching (embeddings) when non-LiveWhale sources come online.
9. **Vision path** for scanned/image-only flyers (`SourceType.IMAGE` → vision model). *(Deferred.)*
10. **Scheduled web monitor** — APScheduler/cron over `sources.yaml`, *only after extraction is trusted via eval*.

### Later (Wave B/C — out of scope for now)
- Outreach assistant (LangGraph + approval gate). Live Gmail/IMAP inbox connector.
- Event-planning assist.

---

## Decisions (the "why" — full records in `docs/decisions/`)

Each major decision has an ADR with context, **evidence/data**, alternatives, and consequences. Summary:

- **[ADR-0001](docs/decisions/0001-normalized-ingestion-two-paths.md)** — Two ingestion paths: structured feeds map directly to `Event` (no LLM); unstructured text goes through the LLM extractor.
- **[ADR-0002](docs/decisions/0002-brown-calendar-via-livewhale-feed.md)** — Brown calendar via the LiveWhale JSON feed, not HTML scraping (JS-rendered page returned 153 chars).
- **[ADR-0003](docs/decisions/0003-grounded-anti-hallucination-extraction.md)** — Grounded extraction: prompt + null-for-unknown + verbatim evidence + schema validation + repair retry + evidence verifier.
- **[ADR-0004](docs/decisions/0004-reposition-to-curation-and-target-primitive.md)** — Reposition to curation + generation; the `Target` primitive powers newsletter sections, agent queries, and notifications.
- **[ADR-0005](docs/decisions/0005-hybrid-tags-plus-llm-for-relevance.md)** — Hybrid: source tags as features for the LLM + deterministic filtering on well-covered dimensions; LLM judges grad-relevance (no grad audience tag exists).
- **[ADR-0006](docs/decisions/0006-concurrent-per-event-enrichment.md)** — Concurrent per-event enrichment (not single-prompt batching): ~7.5× speedup (206.9s → 27.4s on 105 events); default `--workers 8`.

Smaller decisions not (yet) warranting a full ADR: email/newsletter = manual paste for Wave A (defer OAuth/privacy); websites = curated allowlist (`sources.yaml`); `temperature=0.0` for determinism; provider-agnostic hand-rolled LLM wrapper; pipeline + report modules shared by CLI/UI (2026-06-27); **Streamlit as Wave A UI** (not Next.js yet); **no enrich cap in UI fetch** after June happy hour was silently dropped at `--max 110` (2026-06-27); **aggregator selects via UI checkboxes**, not YAML (YAML remains for CLI only).

---

## Concerns / risks (watch these)

- **Web scraping of JS-rendered sites yields ~nothing.** CONFIRMED on events.brown.edu (153 chars). Mitigation in place: `ingest_web` now warns under 200 chars; Brown uses the LiveWhale feed path instead. Other JS-heavy sources will need either a feed/API or a JS-rendering fetcher (Playwright). Pipeline did NOT hallucinate on empty input — correct behavior.
- **LiveWhale feed assumptions.** `start_date`/`end_date` not passed yet (feed defaults to a rolling window). `registration_url` is set to the event page URL (or `online_url`) — it's a link to the event, not necessarily a true registration form. `on_campus` left null (feed doesn't state it). Other schools' LiveWhale field names may differ slightly.
- **`event_types_audience` is unreliable (department defaults).** Reproduced: 6 unrelated events share an identical audience set, and the values don't appear on the public event page. So the field is partly bulk department defaults, not per-event curation. Decision: still captured on `Event.audience_tags` for transparency, but **excluded from the enrichment prompt** so it can't mislead the LLM. Audience is judged from prose/title only. Full characterization: [data card](docs/data-sources/livewhale.md) (`python scripts/profile_livewhale.py`); decision: ADR-0005.
- **PDF ingester unproven on real inputs.** `pypdf` fails silently on scanned/image PDFs (returns empty text) → need the vision path.
- **Evidence verifier is a containment check, not semantic.** A model could quote a *real but irrelevant* sentence as "evidence." Mitigates fabrication, not misattribution. Eval is the real backstop.
- **~~Enrich cap silently drops late-month events.~~ MITIGATED in UI (2026-06-27).** `run_curate.py --max 110` enriches chronologically; June had 168 unique events — Master's Summer Happy Hour was #127 and never appeared. UI now uses `max_enrich=None`. **CLI still has `--max`** — omit or set high for full months.
- **UI scroll position ≠ global relevance rank.** Events listed by newsletter section order; a 0.9 social event can be row ~126 while a 0.6 arts event is row ~120. Within-section rank uses master's-first + score. Documented in [`docs/workflow.md`](docs/workflow.md).
- **~~LiveWhale `cost` as integer breaks ingest.~~ FIXED 2026-06-27.** August feed returns `cost: 15` for some events; `_coerce_optional_str` at ingest. See [livewhale data card](docs/data-sources/livewhale.md).
- **No dedupe across sources yet** → re-fetching the same web page will produce duplicate events. Don't enable scheduled monitoring before cross-source dedupe exists. **Within-feed dedupe IS live** (title+host collapse before enrichment).
- **~~`host_org` HTML entities not decoded.~~ FIXED 2026-06-27.** Added `_clean_inline` (HTML-unescape + tag-strip + whitespace-collapse, returns None when empty) and applied it to `title`, `host_org`, and `location` at ingest. `registration_url` also now `html.unescape`d (Eventbrite links came back with `&amp;`, which can break the link). `Alumni &amp; Friends` → `Alumni & Friends`; emoji entities in titles decoded. Verified live.
- **~~DEDUPE IS NOW THE TOP UNBLOCKER...~~ RESOLVED 2026-06-27.** `backend/dedupe.py` now runs before enrichment: July 331 instances → 105 unique, enriched once each. Recurring/multi-day events show as a single entry with a duration span. Remaining dedupe gap: fuzzy/cross-source matching not done yet (see Dedupe section).
- **`grad_relevance` still clusters at coarse values (0.8 / 0.4 / 0.1).** Holistic rubric rebalanced *across categories* (wellness/arts now ≈ career), but many events still land on the same 0.80, so within-tier ordering is weak. Master's-first + tiers is enough to highlight for now; eval should check whether finer scoring is worth prompting for. NOTE: scoring is non-deterministic enough that re-runs can shift a borderline event a tier — fine for a human-edited draft, worth knowing.
- **~~Cost/latency untracked.~~ RESOLVED (2026-06-30).** `backend/telemetry.py` records tokens + latency per call; `CurationResult.usage` summarizes per run; CLI + Streamlit display the estimate. Pricing table in `_COST_PER_M` — update if model pricing changes. No Langfuse yet (no persistent trace store), but per-run estimates are available immediately.
- **Timezones.** `start`/`end` parsed as ISO strings by the model; no explicit TZ normalization. Could produce off-by-hours dates. Needs a normalization pass + eval check.
- **Single repair retry only.** If the second attempt also fails, it raises — intentional (loud failure > silent garbage), but means a flaky source can hard-fail a batch run.
- **No batch-level error isolation in `extract`.** `ingest_web_sources` catches per-URL fetch errors, but a per-item *extraction* failure in a future batch loop needs its own try/except so one bad source doesn't kill the run.
- **Buy-in not yet secured.** README flags supervisor/team pilot approval — still a to-do before real use.
- **Work not yet committed to git.** As of 2026-06-27, only `README.md` is tracked; `backend/`, `docs/`, `PROGRESS.md`, scaffolding are all untracked. Solid, well-documented foundation sitting uncommitted — make an initial checkpoint commit before the next round of changes. (`.env` is correctly gitignored.)

---

## Assumptions (correct these if wrong)

- Sources are **English** and mostly **text-extractable** (digital flyers, emails, org pages).
- One `SourceItem` may contain **multiple events** (the extractor returns a list).
- `grad_relevance` is **not** set at extraction time — left null, scored later in curation.
- LLM JSON output is generally well-formed; one repair retry is enough for the common case.
- Provider/model set via `.env` (`LLM_PROVIDER`, `LLM_MODEL`); default `gpt-4o-mini`.
- Local dev only so far; no DB yet (events are in-memory / printed). Persistence comes with dedupe.

---

## How to resume quickly

```bash
cd project-brown-grad-events-copilot
source .venv/bin/activate          # deps already installed
# .env already exists with a live OPENAI_API_KEY (gitignored).
python run_extract.py              # sanity check on the sample event (live LLM)
streamlit run app/newsletter_editor.py   # UI: select events → blurbs → export
```

If something breaks: check this log's **Concerns** section first — the likely culprits
(empty PDF/web text, dedupe-less duplicates, timezone drift) are already listed.
