"""Generate a newsletter draft from HUMAN-SELECTED events.

Default: read picks from a YAML selection file (same format Streamlit will write later).
Blurbs are generated ONLY for selected events.

Usage:
    python run_newsletter.py --month 2026-07
    python run_newsletter.py --month 2026-07 --from-selection data/selections/july_2026_example.yaml
    python run_newsletter.py --month 2026-07 --no-llm
    python run_newsletter.py --month 2026-07 --auto   # legacy: model auto-picks events

Requires enriched cache: python run_curate.py --month 2026-07 --max 110 --save

Output: data/output/newsletter_<start>_<end>.md
"""

from __future__ import annotations

import argparse
import calendar
from pathlib import Path

from backend.newsletter import (
    events_from_cache_for_month,
    load_selection,
    prepare_draft_auto,
    prepare_draft_from_selection,
    write_newsletter,
)
from backend.pipeline import curate_range, default_grad_target, resolve_month_range


def _month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate newsletter draft from human-selected events."
    )
    parser.add_argument("--month", required=True, help="YYYY-MM (e.g. 2026-07).")
    parser.add_argument(
        "--from-selection",
        default="data/selections/july_2026_example.yaml",
        help="YAML file with selected event titles (aggregator picks).",
    )
    parser.add_argument(
        "--from-cache",
        default="data/output/enriched_events.json",
        help="Enriched events JSON cache.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Legacy: model auto-picks events by relevance (not the normal workflow).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-run curate_range before drafting (refreshes cache in memory only).",
    )
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM blurbs.")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent blurb calls.")
    parser.add_argument("--max-enrich", type=int, default=110, help="When --refresh.")
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
        pool = result.events
        print(f"  {result.unique_count} unique → {len(pool)} ranked.")
    else:
        cache = Path(args.from_cache)
        if not cache.exists():
            raise SystemExit(
                f"Cache not found: {cache}\n"
                f"Run: python run_curate.py --month {args.month} --max 110 --save"
            )
        print(f"Loading curated pool from {cache}…")
        pool = events_from_cache_for_month(cache, start_date, end_date)
        print(f"  {len(pool)} events in pool for {span}.")

    if args.auto:
        print("Auto-select mode (legacy — model picks events)…")
        draft = prepare_draft_auto(
            pool, span, label, use_llm=not args.no_llm, max_workers=args.workers
        )
    else:
        sel_path = Path(args.from_selection)
        if not sel_path.exists():
            raise SystemExit(
                f"Selection file not found: {sel_path}\n"
                "Copy data/selections/selection.example.yaml and add event titles "
                "from the curated report."
            )
        selection = load_selection(sel_path)
        print(f"Selection from {sel_path}: {len(selection.events)} event(s)")
        draft = prepare_draft_from_selection(
            pool,
            selection,
            span,
            label,
            use_llm=not args.no_llm,
            max_workers=args.workers,
        )

    out_dir = Path("data/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"newsletter_{start_date}_{end_date}.md"
    write_newsletter(out_path, draft)

    n_body = sum(len(v) for v in draft.sections.values())
    print(f"\nSaved → {out_path}")
    print(f"  Selected events in draft: {n_body}")
    if draft.unmatched_titles:
        print(f"  WARNING: {len(draft.unmatched_titles)} title(s) did not match the pool:")
        for t in draft.unmatched_titles:
            print(f"    - {t}")
    print("  Review blurbs → copy-paste into the shared Google Doc.")


if __name__ == "__main__":
    main()
