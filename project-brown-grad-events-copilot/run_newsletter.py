"""Generate a copy-paste newsletter draft from curated events.

Uses cached enrichment by default (no re-pay for LLM enrichment). Blurbs are one
LLM call per *selected* event (~30–40 for a typical month).

Usage:
    python run_newsletter.py --month 2026-07
    python run_newsletter.py --month 2026-07 --from-cache data/output/enriched_events.json
    python run_newsletter.py --month 2026-07 --no-llm          # fast draft, description-based blurbs
    python run_newsletter.py --month 2026-07 --refresh          # re-run full curation first

Output: data/output/newsletter_<start>_<end>.md
"""

from __future__ import annotations

import argparse
import calendar
from pathlib import Path

from backend.newsletter import (
    events_from_cache_for_month,
    prepare_draft,
    write_newsletter,
)
from backend.pipeline import curate_range, default_grad_target, resolve_month_range


def _month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a grad-events newsletter draft.")
    parser.add_argument("--month", required=True, help="YYYY-MM (e.g. 2026-07).")
    parser.add_argument(
        "--from-cache",
        default="data/output/enriched_events.json",
        help="Enriched events JSON (default: data/output/enriched_events.json).",
    )
    parser.add_argument("--refresh", action="store_true",
                        help="Re-run curate_range (ingest+dedupe+enrich) instead of cache.")
    parser.add_argument("--min-relevance", type=float, default=0.4,
                        help="Min grad_relevance to include (default 0.4).")
    parser.add_argument("--max-per-section", type=int, default=6,
                        help="Max events per section (default 6).")
    parser.add_argument("--max-highlights", type=int, default=8,
                        help="Max Don't Miss items (default 8).")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM blurbs; use first sentence of description.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent blurb calls.")
    parser.add_argument("--max-enrich", type=int, default=110,
                        help="When --refresh: cap events enriched.")
    args = parser.parse_args()

    start_date, end_date = resolve_month_range(args.month)
    span = f"{start_date} → {end_date}"
    label = _month_label(args.month)

    if args.refresh:
        print(f"Refreshing curation for {span}…")
        target = default_grad_target(start_date, end_date, min_relevance=0.0)
        result = curate_range(
            start_date, end_date, target=target, max_enrich=args.max_enrich
        )
        ranked = result.events
        print(f"  {result.unique_count} unique → {len(ranked)} ranked.")
    else:
        cache = Path(args.from_cache)
        if not cache.exists():
            raise SystemExit(
                f"Cache not found: {cache}\n"
                f"Run: python run_curate.py --month {args.month} --max 110 --save"
            )
        print(f"Loading enriched events from {cache}…")
        ranked = events_from_cache_for_month(cache, start_date, end_date)
        print(f"  {len(ranked)} events for {span}.")

    print("Generating newsletter draft…")
    draft = prepare_draft(
        ranked,
        span,
        label,
        min_relevance=args.min_relevance,
        max_per_section=args.max_per_section,
        max_highlights=args.max_highlights,
        use_llm=not args.no_llm,
        max_workers=args.workers,
    )

    out_dir = Path("data/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"newsletter_{start_date}_{end_date}.md"
    write_newsletter(out_path, draft)

    n_sections = sum(len(v) for v in draft.sections.values())
    print(f"\nSaved → {out_path}")
    print(f"  Don't Miss: {len(draft.highlights)} · Section events: {n_sections} · "
          f"Skipped (low/admin): {draft.skipped_count}")
    print("  Open the file, review blurbs, copy-paste into the shared Google Doc.")


if __name__ == "__main__":
    main()
