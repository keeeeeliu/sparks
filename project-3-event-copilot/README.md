# Project 3 — The Event Copilot (Flagship Agent)

> Status: **Not started** · Owner: Ke · Last updated: 2026-06-21 · Depends on: Project 2 (RAG layer)

The portfolio centerpiece — and a potential seed for a future mobile-bar / event-design business.

A user describes their event in plain language; the agent drafts a **complete plan** (theme & mood, zero-proof menu, run-of-show timeline, prep/shopping list, vendor shortlist, budget) and **pauses for human approval before any consequential action** (sending a vendor inquiry, finalizing a quote, emailing a client).

The impressive engineering is **workflow persistence**: the agent pauses at the approval step, waits (minutes or hours), and resumes exactly where it left off (**draft → approve → execute**).

---

## What this demonstrates (resume signal)
Agents + **tool calling** · multi-step orchestration · **RAG** (reuses Project 2) · **human-in-the-loop** · **state persistence / pause-resume** · evaluation · observability (tracing, cost, latency) · **full-stack** · beautiful UI.

## Tech stack
- **Frontend:** **Next.js + TypeScript + Tailwind**, streaming UI, auth — make it genuinely beautiful
- **Agent/back end:** Python **FastAPI** + **LangGraph**
- **Data:** **Postgres + pgvector** (RAG + checkpoints), **Redis** (cache)
- **Observability:** **Langfuse** (traces, token cost, latency)
- **Deploy:** **Docker** → Railway/Fly/Render (backend) + Vercel (frontend)

---

## Design

### Agent graph (LangGraph)
Nodes:
1. `classify_event` — parse the user's request into structured event details.
2. `retrieve_context` — pull menu/playbook context via Project 2's RAG layer.
3. `draft_plan` — compose the plan, calling tools as needed.
4. `approval_gate` — **`interrupt()`**: pause and surface the draft for human approval.
5. `execute` — only after approval, run gated tools.

### Tools (typed, permission-scoped — never raw DB access)
| Tool | Gated? | Purpose |
|------|--------|---------|
| `generate_menu` | no | Zero-proof menu from RAG + event details |
| `build_timeline` | no | Run-of-show schedule |
| `estimate_budget` | no | Cost breakdown |
| `draft_vendor_inquiry` | **yes** | Drafts vendor outreach (approval before send) |
| `compose_client_email` | **yes** | Drafts client email (approval before send) |

### State schema (sketch)
```python
class EventState(TypedDict):
    request: str
    event: EventDetails        # parsed: type, guests, date, vibe, constraints
    retrieved: list[Chunk]
    plan: EventPlan | None     # menu, timeline, budget, vendors
    approval: Literal["pending", "approved", "rejected"]
    messages: list[Message]
```

### Persistence (the standout feature)
- Use a **LangGraph checkpointer backed by Postgres** so the graph state survives the pause at `approval_gate` and across restarts.
- Resume exactly where it left off when the human approves/rejects.

### Observability + evaluation
- **Langfuse** tracing on every run: latency (p50/p95), token cost, step traces.
- **Eval harness:** a golden set of sample events; score plan quality with an LLM-as-judge; run in CI as a regression gate.
- **Resilience:** timeouts, graceful fallbacks, and a **replay mode** (feed recorded inputs back through the pipeline for debugging).

### Suggested folder structure
```
project-3-event-copilot/
  README.md
  docker-compose.yml      <- postgres + redis + backend + frontend
  backend/
    graph.py              <- LangGraph definition (nodes + edges)
    state.py              <- state schema
    tools/                <- typed tools (gated + ungated)
    rag.py                <- reuse Project 2 retrieval
    checkpoint.py         <- Postgres checkpointer
    api.py                <- FastAPI (run, approve, resume)
  frontend/               <- Next.js app (intake form, streaming plan, approval UI)
  eval/
    events_golden.json
    judge_eval.py
```

---

## Milestones (~8-10 weeks)
1. **Foundation:** repo scaffold, Next.js + FastAPI talking, Postgres + pgvector, auth, Dockerized, live "hello world" deploy.
2. **RAG core:** wire in Project 2's retrieval (hybrid + rerank + citations).
3. **Agent layer:** LangGraph controller + typed tools + human-in-the-loop `approval_gate`.
4. **Differentiator:** Postgres checkpointer (pause/resume), Langfuse tracing, eval harness + CI gate, graceful degradation, replay mode.
5. **Polish + story:** beautiful UI, README + architecture diagram + measurable outcomes, short writeup, resume bullets.

## Next steps
- [ ] Finish Project 2 (the RAG layer this depends on).
- [ ] Scaffold the Next.js + FastAPI + Postgres foundation.

## References
See root `AI-project-ideas.md` (Project 3 section) and `AI-engineer-roadmap.md` (Phase 4). Architecture mirrors the "Atlas" deep-dive in `AI-career-analysis-and-project-plan.md`.
