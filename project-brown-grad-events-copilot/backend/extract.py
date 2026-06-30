"""Grounded event extraction (the anti-hallucination core).

Pipeline: SourceItem -> LLM (grounded prompt) -> JSON -> Pydantic validation.
If validation fails, we do ONE repair retry feeding the error back to the model.

Anti-hallucination defenses implemented here:
  1. Grounded prompt    : only extract what's literally in the source; unknown -> null.
  2. Provenance         : each event must carry a verbatim `evidence` snippet + source_ref.
  3. Schema validation  : invented/garbage output fails Pydantic.
  4. Repair retry       : one self-correction pass on validation failure.
  5. Evidence check     : drop events whose `evidence` snippet isn't actually in the source.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from .llm import complete_json
from .models import Event, ExtractionResult, SourceItem

SYSTEM_PROMPT = """You are a precise event-extraction engine for a university grad-student newsletter.

You will be given the raw text of a single source (a pasted note, an email, a PDF, or a web page).
Extract every distinct real-world EVENT it describes.

STRICT GROUNDING RULES — follow exactly:
- Only extract information that is LITERALLY present in the source text.
- If a field's value is not stated in the source, set it to null. NEVER guess, infer, or invent.
- Do not invent dates, times, locations, URLs, costs, or organizers. Copy them as written.
- If the text contains no actual event, return an empty "events" list.
- For each event, include an "evidence" field: a SHORT VERBATIM quote copied exactly from the
  source that proves the event exists. If you cannot quote the source, do not emit the event.
- Set "extraction_confidence" (0-1): how sure you are this is a real, correctly-read event.
- Leave "grad_relevance" as null; relevance scoring happens in a later step, not here.

Return a single JSON object of this exact shape:
{
  "events": [
    {
      "title": str,
      "description": str,
      "start": str | null,            // ISO 8601 if a date/time is given, else null
      "end": str | null,
      "location": str | null,
      "on_campus": bool | null,
      "host_org": str | null,
      "category": str | null,         // "career" | "social" | "academic" | "wellness" | ...
      "grad_relevance": null,
      "registration_url": str | null,
      "cost": str | null,
      "tags": [str],
      "evidence": str,                // verbatim quote from the source
      "extraction_confidence": float
    }
  ]
}
Output ONLY the JSON object, no prose."""


def _build_user_prompt(item: SourceItem) -> str:
    return (
        f"SOURCE TYPE: {item.source_type.value}\n"
        f"SOURCE REF: {item.source_ref}\n"
        "----- BEGIN SOURCE TEXT -----\n"
        f"{item.content}\n"
        "----- END SOURCE TEXT -----"
    )


def _parse(raw: str) -> ExtractionResult:
    data = json.loads(raw)
    return ExtractionResult.model_validate(data)


def extract_events(item: SourceItem, *, verify_evidence: bool = True) -> list[Event]:
    """Extract events from one SourceItem with a single repair retry.

    If verify_evidence is True, any event whose `evidence` snippet is not actually
    found in the source text is dropped (defense #5 against fabricated quotes).
    """
    user = _build_user_prompt(item)

    raw = complete_json(SYSTEM_PROMPT, user, label="extract")
    try:
        result = _parse(raw)
    except (json.JSONDecodeError, ValidationError) as err:
        # --- Repair retry: feed the error back and ask for corrected JSON. ---
        repair_user = (
            f"{user}\n\n"
            "Your previous response was invalid and could not be parsed:\n"
            f"{type(err).__name__}: {err}\n\n"
            "Return ONLY a corrected JSON object matching the required schema. "
            "Remember the grounding rules: unknown fields must be null."
        )
        raw = complete_json(SYSTEM_PROMPT, repair_user, label="extract-repair")
        result = _parse(raw)  # if this still fails, let it raise — that's a real signal

    events: list[Event] = []
    for ev in result.events:
        ev.source_ref = item.source_ref  # stamp provenance from the source itself
        if verify_evidence and not _evidence_in_source(ev.evidence, item.content):
            print(f"[extract] dropped event (evidence not found in source): {ev.title!r}")
            continue
        events.append(ev)
    return events


def _evidence_in_source(evidence: str | None, source: str) -> bool:
    """Loose containment check: is the model's quoted evidence actually in the source?

    Normalizes whitespace/case to tolerate minor reformatting, but still catches
    fully fabricated quotes.
    """
    if not evidence:
        return False
    norm = lambda s: " ".join(s.lower().split())
    return norm(evidence) in norm(source)
