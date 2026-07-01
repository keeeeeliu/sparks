"""FastAPI layer for the Next.js frontend.

A thin wrapper over the existing pipeline — no business logic lives here. It maps
the backend `Event` to the UI's view contract (`EventOut`), runs the blocking,
LLM-heavy pipeline in a threadpool, and keeps the enriched events in memory so the
blurb endpoints can look them up by id (the frontend only holds the reduced view).

Run:
    uvicorn backend.api:app --reload --port 8000

Single-user/local by design: `_EVENT_CACHE` is a process-global, not per-session.
"""

from __future__ import annotations

import hashlib
import os

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import telemetry
from .models import Event
from .newsletter import generate_blurbs, improve_blurb
from .pipeline import curate_range
from .report import format_when, section_of

app = FastAPI(title="Grad Events Copilot API")

# Local dev origins are always allowed. In production, add your deployed frontend URL(s)
# via the ALLOWED_ORIGINS env var (comma-separated), e.g.
#   ALLOWED_ORIGINS=https://grad-events.vercel.app
_DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ENV_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS + _ENV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# id -> full enriched Event, populated by /api/curate so blurb endpoints can
# recover the description/date the reduced UI payload doesn't carry.
_EVENT_CACHE: dict[str, Event] = {}


# --------------------------------------------------------------------------- #
# Wire models (the UI view contract — mirrors frontend lib/types.ts EventItem)
# --------------------------------------------------------------------------- #

class EventOut(BaseModel):
    id: str
    title: str
    section: str
    date: str
    host: str
    tier: str  # "high" | "mid" | "low"
    reasoning: str
    mastersFacing: bool
    eventUrl: str
    imageUrl: str | None = None


class Usage(BaseModel):
    calls: int
    tokens_in: int
    tokens_out: int
    est_cost_usd: float


class CurateRequest(BaseModel):
    start: str
    end: str


class CurateResponse(BaseModel):
    events: list[EventOut]
    usage: Usage | None = None


class BlurbsRequest(BaseModel):
    ids: list[str]


class BlurbsResponse(BaseModel):
    blurbs: dict[str, str]  # id -> blurb


class ImproveRequest(BaseModel):
    text: str
    id: str | None = None


class ImproveResponse(BaseModel):
    blurb: str


# --------------------------------------------------------------------------- #
# Mapping helpers
# --------------------------------------------------------------------------- #

def _event_id(ev: Event) -> str:
    key = f"{ev.title}|{ev.start.isoformat() if ev.start else ''}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _tier(score: float | None) -> str:
    if score is None:
        return "low"
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "mid"
    return "low"


def _to_out(ev: Event, ev_id: str) -> EventOut:
    return EventOut(
        id=ev_id,
        title=ev.title,
        section=section_of(ev),
        date=format_when(ev),
        host=ev.host_org or "Brown",
        tier=_tier(ev.grad_relevance),
        reasoning=ev.relevance_reasoning or "",
        mastersFacing=ev.is_masters_facing(),
        eventUrl=ev.link_for_newsletter() or ev.event_page_url() or "",
        imageUrl=ev.image_url,
    )


def _usage() -> Usage:
    s = telemetry.summarize()
    return Usage(
        calls=s.calls,
        tokens_in=s.tokens_in,
        tokens_out=s.tokens_out,
        est_cost_usd=round(s.est_cost_usd, 4),
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/curate", response_model=CurateResponse)
async def curate(req: CurateRequest) -> CurateResponse:
    """Ingest + dedupe + enrich for the date range; return the ranked pool."""
    result = await run_in_threadpool(
        curate_range, req.start, req.end, max_enrich=None
    )
    _EVENT_CACHE.clear()
    out: list[EventOut] = []
    for ev in result.events:
        ev_id = _event_id(ev)
        _EVENT_CACHE[ev_id] = ev
        out.append(_to_out(ev, ev_id))
    return CurateResponse(events=out, usage=_usage())


@app.post("/api/blurbs", response_model=BlurbsResponse)
async def blurbs(req: BlurbsRequest) -> BlurbsResponse:
    """Generate a draft blurb for each requested event id."""
    pairs = [(i, _EVENT_CACHE[i]) for i in req.ids if i in _EVENT_CACHE]
    if not pairs:
        raise HTTPException(status_code=400, detail="No known events; re-fetch first.")
    events = [ev for _, ev in pairs]
    telemetry.reset()
    by_title = await run_in_threadpool(generate_blurbs, events)
    # generate_blurbs keys by title; remap to id (titles are unique in a pool).
    title_to_id = {ev.title: i for i, ev in pairs}
    result = {
        title_to_id[title]: text
        for title, text in by_title.items()
        if title in title_to_id
    }
    return BlurbsResponse(blurbs=result)


@app.post("/api/blurbs/improve", response_model=ImproveResponse)
async def improve(req: ImproveRequest) -> ImproveResponse:
    """Proofread + lightly rewrite an existing (human-edited) blurb."""
    ev = _EVENT_CACHE.get(req.id) if req.id else None
    telemetry.reset()
    improved = await run_in_threadpool(improve_blurb, req.text, ev)
    return ImproveResponse(blurb=improved)
