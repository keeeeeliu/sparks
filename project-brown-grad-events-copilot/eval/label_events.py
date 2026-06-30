"""Interactive labeling tool — build eval/labeled_events.json from the enriched cache.

Walk through a random sample of enriched events, show the current enrichment output, and
let you confirm or correct each label. Saves ground-truth labels that evaluate.py uses
for accuracy eval.

Usage:
    python eval/label_events.py                       # label 25 events (default)
    python eval/label_events.py --n 40 --seed 7       # 40 events, different sample
    python eval/label_events.py --append               # add more events to existing file

Press Enter to accept the shown default. Ctrl+C at any point — events labeled so far save.

Tip: run this after fetching a month with --save, so the cache is fresh.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.models import Event


def _rel_bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "mid"
    return "low"


def _ask(prompt: str, default: str) -> str:
    try:
        val = input(f"{prompt} [{default}]: ").strip()
        return val if val else default
    except EOFError:
        return default


def _ask_bool(prompt: str, default: bool) -> bool:
    d = "y" if default else "n"
    val = _ask(f"{prompt} (y/n)", d).lower()
    return val in {"y", "yes", "1", "true"}


def _load_existing_labels(output_path: Path) -> tuple[list[dict], set[str]]:
    if not output_path.exists():
        return [], set()
    data = json.loads(output_path.read_text())
    events = data.get("events", [])
    titles = {e["title"] for e in events}
    return events, titles


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive event labeling for eval")
    parser.add_argument("--n", type=int, default=25, help="Events to label this session")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--append", action="store_true", help="Add to existing labels (skip already-labeled)")
    parser.add_argument(
        "--cache",
        default=str(ROOT / "data" / "output" / "enriched_events.json"),
        help="Path to enriched_events.json",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "eval" / "labeled_events.json"),
        help="Output file for labels",
    )
    args = parser.parse_args()

    cache = Path(args.cache)
    if not cache.exists():
        print(f"Cache not found: {cache}")
        print("Run 'python run_curate.py --month 2026-07 --save' first.")
        sys.exit(1)

    output_path = Path(args.output)
    existing_labels, already_titled = _load_existing_labels(output_path)
    if args.append:
        print(f"Appending to {len(existing_labels)} existing label(s).")

    all_events = [Event.model_validate(item) for item in json.loads(cache.read_text())]

    # Exclude already-labeled events when appending
    pool = [ev for ev in all_events if ev.title not in already_titled] if args.append else all_events
    if not pool:
        print("All events in the cache are already labeled.")
        return

    rng = random.Random(args.seed)
    sample = rng.sample(pool, min(args.n, len(pool)))
    print(f"\nCache: {len(all_events)} events  |  Pool: {len(pool)}  |  Sample: {len(sample)}")
    print("Press Enter to accept defaults, Ctrl+C to stop early.\n")

    new_labels: list[dict] = []
    try:
        for i, ev in enumerate(sample, 1):
            print(f"\n{'─' * 70}")
            print(f"[{i}/{len(sample)}]  {ev.title}")
            print(f"  Host:  {ev.host_org or '—'}")
            print(f"  Date:  {ev.start.strftime('%Y-%m-%d %H:%M') if ev.start else 'n/a'}")
            desc = (ev.description or "").strip()
            print(f"  Desc:  {desc[:300]}{'…' if len(desc) > 300 else ''}")
            print(f"\n  Cached enrichment:")
            print(f"    audience  : {ev.audience}")
            rel = f"{ev.grad_relevance:.2f}" if ev.grad_relevance is not None else "n/a"
            print(f"    relevance : {rel}  ({_rel_bucket(ev.grad_relevance)})  — {ev.relevance_reasoning}")
            print(f"    category  : {ev.category}")
            print()

            grad = _ask_bool("  Grad-facing?", ev.is_grad_facing())
            masters = _ask_bool("  Masters-facing?", ev.is_masters_facing())
            cat = _ask("  Category", ev.category or "other")
            bucket = _ask("  Relevance bucket (high/mid/low)", _rel_bucket(ev.grad_relevance))
            notes = _ask("  Notes (optional)", "")

            new_labels.append({
                "title": ev.title,
                "ground_truth": {
                    "grad_facing": grad,
                    "masters_facing": masters,
                    "category": cat or None,
                    "relevance_bucket": bucket,
                },
                "notes": notes,
                "_cached_audience": ev.audience,
                "_cached_relevance": ev.grad_relevance,
                "_cached_category": ev.category,
            })

    except KeyboardInterrupt:
        print(f"\n\nStopped — {len(new_labels)} new event(s) labeled.")

    all_labels = existing_labels + new_labels
    output = {
        "version": 1,
        "description": "Hand-labeled ground truth for enrichment accuracy eval",
        "seed": args.seed,
        "source_cache": str(cache),
        "events": all_labels,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))
    print(f"\nSaved {len(all_labels)} label(s) ({len(new_labels)} new) → {output_path}")


if __name__ == "__main__":
    main()
