"""Data schemas for Wave A.

Two ideas to keep in mind:

1. `SourceItem` is the *normalized* unit of ingestion. Every source — pasted
   text, a PDF flyer, a forwarded email, a monitored website — is converted into
   this single shape. Everything downstream (extract / dedupe / curate / draft)
   only ever sees `SourceItem`, so it never has to care where the content came
   from. Adding a new source later = writing one ingester, nothing else changes.

2. `Event` is the structured output of extraction. It extends the README schema
   with provenance fields (`evidence`, `extraction_confidence`, `source_ref`) so
   every extracted fact can be traced back to the source text. This is the
   backbone of the anti-hallucination strategy.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# Audience-classification vocab, shared by ranking + sectioning (CLI, report, future UI/API).
_MASTERS_AUDIENCE = {"masters", "master's", "master"}
_GRAD_AUDIENCE = _MASTERS_AUDIENCE | {"graduate", "doctoral", "phd"}


class SourceType(str, Enum):
    PASTE = "paste"
    PDF = "pdf"
    IMAGE = "image"          # flyer image -> read via vision model
    EMAIL = "email"
    NEWSLETTER = "newsletter"
    WEB = "web"


class SourceItem(BaseModel):
    """Normalized ingestion unit. One per document/page/message."""

    content: str = Field(..., description="Cleaned plain text / markdown of the source.") # ... means: required field, no default value
    source_type: SourceType
    source_ref: str = Field(
        ...,
        description="Where it came from: filename, URL, email message-id, or 'manual'.",
    )
    images: Optional[list[bytes]] = Field(
        default=None,
        description="Raw image bytes for flyers when text extraction is weak (vision path).",
    )
    received_at: datetime = Field(default_factory=datetime.now)


class Event(BaseModel):
    """A structured event extracted from a SourceItem.

    Grounding rule: every non-null field MUST be supported by the source text.
    If a value is not present in the source, it stays null — never inferred.
    """

    title: str
    description: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None

    # --- Recurrence / duration (set by dedupe when many dated instances collapse to one) ---
    occurrence_count: int = Field(
        default=1,
        description="How many dated instances were merged into this event (1 = single instance).",
    )
    occurrence_dates: Optional[list[datetime]] = Field(
        default=None,
        description="Distinct start datetimes for a recurring/multi-day event (set by dedupe). "
        "`start`..`end` then describe the overall span.",
    )
    on_campus: Optional[bool] = None
    host_org: Optional[str] = None
    category: Optional[str] = Field(
        default=None,
        description='e.g. "career", "social", "academic", "wellness"',
    )
    grad_relevance: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="0-1 score for how valuable/enriching this is to a grad student's life — "
        "interpreted BROADLY (career + social + wellness + arts + community + fun), not just "
        "academic/professional. Set during curation, not extraction.",
    )
    relevance_reasoning: Optional[str] = Field(
        default=None,
        description="One short sentence on why the grad_relevance score / who would value it. "
        "Set during enrichment; gives the human curator a transparent rationale.",
    )
    registration_url: Optional[str] = None
    image_url: Optional[str] = Field(
        default=None,
        description="Event image from the source feed (e.g. LiveWhale thumbnail URL).",
    )
    cost: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    # --- Source tags (raw signal from the calendar; sparse but reliable when present) ---
    audience_tags: list[str] = Field(
        default_factory=list,
        description="Audience tags straight from the source calendar (e.g. LiveWhale "
        "event_types_audience). Captured for transparency only — UNRELIABLE (often applied "
        "as department-wide defaults; Brown also has no 'graduate' value) and NOT fed to "
        "enrichment. See ADR-0005.",
    )

    # --- Enrichment / judgment fields (set by curate.enrich_event, NOT extraction) ---
    # Facts + source tags come first; these are INFERRED by reading the description (+ tags as hints).
    audience: list[str] = Field(
        default_factory=list,
        description='Who the event is for, judged from description + source tags. '
        'e.g. ["graduate"], ["all"], ["undergraduate", "graduate"], or ["unspecified"] if not stated.',
    )
    audience_evidence: Optional[str] = Field(
        default=None,
        description="Verbatim snippet the audience was inferred from. None if audience is unspecified.",
    )

    # --- Provenance / anti-hallucination fields ---
    source_ref: str = Field(
        default="unknown",
        description="Traces back to the originating SourceItem.source_ref.",
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Verbatim snippet from the source supporting this event. Lets a human verify.",
    )
    extraction_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model's self-reported confidence that this is a real, correctly-read event.",
    )

    def is_masters_facing(self) -> bool:
        """True if enrichment explicitly tagged this for master's students."""
        return any(a.strip().lower() in _MASTERS_AUDIENCE for a in self.audience)

    def is_grad_facing(self) -> bool:
        """True if enrichment tagged this for grad students (incl. master's/doctoral)."""
        return any(a.strip().lower() in _GRAD_AUDIENCE for a in self.audience)

    def event_page_url(self) -> str | None:
        """Canonical event page on the source calendar, when known."""
        ref = (self.source_ref or "").strip()
        if ref and ref != "unknown" and ref.startswith("http"):
            return ref
        return None

    def link_for_newsletter(self) -> str | None:
        """Best reader-facing link — registration when set, else event page."""
        return self.registration_url or self.event_page_url()


class ExtractionResult(BaseModel):
    """Wrapper the LLM returns: a list of events found in one SourceItem."""

    events: list[Event] = Field(default_factory=list)


class Target(BaseModel):
    """A curation target: a saved 'what I'm looking for'.

    This is the personalization primitive. The same object powers three things:
      - a newsletter SECTION (e.g. "Grad Social", "Career Services"),
      - an agent QUERY ("social events for grad students in July" -> an ad-hoc Target),
      - a scheduled NOTIFICATION (a Target run on a timer).

    Filtering is `(enriched events) x (Target) -> curated list`. Different users /
    section owners just keep different Targets.
    """

    name: str
    owner: Optional[str] = None
    audience: list[str] = Field(
        default_factory=list,
        description='Audiences this target wants, e.g. ["graduate"]. Empty = any audience.',
    )
    categories: list[str] = Field(
        default_factory=list,
        description='Categories to include, e.g. ["social", "wellness"]. Empty = any category.',
    )
    departments: list[str] = Field(
        default_factory=list,
        description="Host departments/orgs to include, matched against Event.host_org "
        "(group_title, ~100% populated). Substring, case-insensitive. Empty = any department.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Free-text keywords matched against title/description/tags. Empty = no keyword filter.",
    )
    start_date: Optional[str] = Field(default=None, description="YYYY-MM-DD inclusive lower bound.")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM-DD inclusive upper bound.")
    min_relevance: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Drop events whose grad_relevance is below this (after enrichment).",
    )
