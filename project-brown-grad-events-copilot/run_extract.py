"""End-to-end smoke test for Wave A extraction (Milestone 1).

Usage:
    python run_extract.py                       # extract from data/raw/sample_event.txt
    python run_extract.py path/to/file.txt      # any pasted/email text file
    python run_extract.py path/to/flyer.pdf     # a text-based PDF
    python run_extract.py https://some.url/     # a single web page (LLM path)
    python run_extract.py https://events.brown.edu/   # Brown calendar (structured feed, no LLM)

The LLM paths require a .env with LLM_PROVIDER + the matching API key (see .env.example).
The LiveWhale feed path needs no API key.
"""

from __future__ import annotations

import sys
from pathlib import Path

from backend.extract import extract_events
from backend.ingest import ingest_livewhale_events, ingest_paste, ingest_pdf, ingest_web


def load_source(arg: str | None):
    if arg is None:
        text = Path("data/raw/sample_event.txt").read_text()
        return ingest_paste(text, source_ref="sample_event.txt")
    if arg.startswith("http://") or arg.startswith("https://"):
        return ingest_web(arg)
    path = Path(arg)
    if path.suffix.lower() == ".pdf":
        return ingest_pdf(path)
    return ingest_paste(path.read_text(), source_ref=path.name)


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if arg and "events.brown.edu" in arg:
        # Structured feed path: deterministic JSON -> Event, no LLM.
        print("Detected Brown LiveWhale calendar -> using structured JSON feed "
              "(deterministic, no LLM, no hallucination risk).\n")
        # Paginated; max_events caps the demo so output stays readable. Raise/None to pull more.
        events = ingest_livewhale_events(base_url="https://events.brown.edu", max_events=50)
    else:
        # Unstructured path: text -> SourceItem -> LLM extractor -> Event.
        item = load_source(arg)
        print(f"Ingested {item.source_type.value} from {item.source_ref!r} "
              f"({len(item.content)} chars)\n")
        events = extract_events(item)

    print(f"Got {len(events)} event(s):\n")
    for i, ev in enumerate(events, 1):
        print(f"--- Event {i} ---")
        print(ev.model_dump_json(indent=2))
        print()


if __name__ == "__main__":
    main()
