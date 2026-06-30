"""Enrichment eval harness.

Two modes:

  CONSISTENCY (default) — re-enriches a random sample from the cached run and
    compares new output to the previous output. No hand-labeling required. Tells
    you whether the enricher is stable across re-runs (useful for detecting prompt
    drift or model changes). Run immediately after any curate + --save.

  ACCURACY — compares against hand-labeled ground truth. Run eval/label_events.py
    first to build eval/labeled_events.json, then use --labels here.

Usage:
    python eval/evaluate.py                                # consistency, 25 events
    python eval/evaluate.py --n 50 --seed 7               # consistency, bigger sample
    python eval/evaluate.py --labels eval/labeled_events.json  # accuracy eval
    python eval/evaluate.py --cache data/output/enriched_events.json --n 30

Metrics:
    grad_facing     — did we correctly classify as grad-student-facing (yes/no)?
    masters_facing  — did we correctly identify as masters-specific (yes/no)?
    category        — exact match on the category string
    relevance_bucket — high (≥0.8) / mid (0.4–0.79) / low (<0.4) bucket match
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import telemetry
from backend.curate import enrich_event
from backend.models import Event


def _rel_bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 0.8:
        return "high"
    if score >= 0.4:
        return "mid"
    return "low"


def _strip_enrichment(ev: Event) -> Event:
    """Return a copy with LLM-added fields cleared, keeping raw feed fields as hints."""
    return ev.model_copy(
        update={
            "audience": [],
            "audience_evidence": None,
            "grad_relevance": None,
            "relevance_reasoning": None,
            # Keep ev.category and ev.tags — they're feed hints, not enrichment output
        },
        deep=True,
    )


def _report_metrics(
    label: str,
    n: int,
    grad: int,
    masters: int,
    cat: int,
    rel: int,
) -> None:
    print(f"\n{'─' * 55}")
    print(f"Results ({n} events)  —  {label}")
    print(f"{'─' * 55}")
    print(f"  grad-facing accuracy    {grad:3d}/{n}  =  {grad/n:.0%}")
    print(f"  masters-facing accuracy {masters:3d}/{n}  =  {masters/n:.0%}")
    print(f"  category exact match    {cat:3d}/{n}  =  {cat/n:.0%}")
    print(f"  relevance bucket match  {rel:3d}/{n}  =  {rel/n:.0%}")
    telemetry.print_summary(prefix="\n  ")


def run_consistency_eval(cache_path: Path, n: int, seed: int) -> None:
    """Re-enrich a sample and compare to the previous run's output."""
    print(f"\n=== Consistency Eval — {n} events from cache ===")
    print(f"Cache: {cache_path}\n")

    all_events = [Event.model_validate(item) for item in json.loads(cache_path.read_text())]
    sample = random.Random(seed).sample(all_events, min(n, len(all_events)))
    print(f"Population: {len(all_events)}  |  Sample: {len(sample)}")

    grad_m = masters_m = cat_m = rel_m = 0
    mismatches = []

    for ev in sample:
        ref_grad = ev.is_grad_facing()
        ref_masters = ev.is_masters_facing()
        ref_cat = ev.category
        ref_rel = _rel_bucket(ev.grad_relevance)

        new = enrich_event(_strip_enrichment(ev))

        ok_grad = ref_grad == new.is_grad_facing()
        ok_masters = ref_masters == new.is_masters_facing()
        ok_cat = ref_cat == new.category
        ok_rel = ref_rel == _rel_bucket(new.grad_relevance)

        grad_m += ok_grad
        masters_m += ok_masters
        cat_m += ok_cat
        rel_m += ok_rel

        if not (ok_grad and ok_rel):
            mismatches.append(
                f"  ✗  {ev.title[:58]!r}\n"
                f"       grad:    ref={ref_grad}  got={new.is_grad_facing()}"
                + (f"\n       bucket:  ref={ref_rel}({ev.grad_relevance:.2f})"
                   f"  got={_rel_bucket(new.grad_relevance)}({new.grad_relevance:.2f})"
                   if not ok_rel else "")
            )

    if mismatches:
        print(f"\nDiffs (grad or relevance mismatch):")
        for m in mismatches[:10]:  # cap at 10 to keep output readable
            print(m)
        if len(mismatches) > 10:
            print(f"  … and {len(mismatches) - 10} more")

    _report_metrics("vs. previous enrichment run", len(sample), grad_m, masters_m, cat_m, rel_m)


def run_accuracy_eval(labels_path: Path, cache_path: Path) -> None:
    """Compare enrichment output to hand-labeled ground truth."""
    print(f"\n=== Accuracy Eval — vs. hand-labeled ground truth ===")
    print(f"Labels: {labels_path}\n")

    labeled = json.loads(labels_path.read_text())
    items = labeled.get("events", [])
    if not items:
        print("No labeled events found. Run eval/label_events.py first.")
        sys.exit(1)
    print(f"Labeled events: {len(items)}")

    # Build a title → Event lookup from cache
    cache_by_title: dict[str, Event] = {}
    if cache_path.exists():
        for item in json.loads(cache_path.read_text()):
            ev = Event.model_validate(item)
            cache_by_title[ev.title.strip().lower()] = ev

    grad_m = masters_m = cat_m = rel_m = total = 0
    mismatches = []

    for item in items:
        title = item["title"]
        gt = item["ground_truth"]

        cached = cache_by_title.get(title.strip().lower())
        if cached is None:
            print(f"  [WARN] '{title[:60]}' not in cache — skipping")
            continue

        new = enrich_event(_strip_enrichment(cached))

        exp_grad = gt["grad_facing"]
        exp_masters = gt["masters_facing"]
        exp_cat = gt.get("category")
        exp_bucket = gt["relevance_bucket"]

        ok_grad = exp_grad == new.is_grad_facing()
        ok_masters = exp_masters == new.is_masters_facing()
        ok_cat = (exp_cat is None) or (exp_cat == new.category)
        ok_rel = exp_bucket == _rel_bucket(new.grad_relevance)

        grad_m += ok_grad
        masters_m += ok_masters
        cat_m += ok_cat
        rel_m += ok_rel
        total += 1

        if not (ok_grad and ok_masters and ok_rel):
            parts = []
            if not ok_grad:
                parts.append(f"grad: exp={exp_grad} got={new.is_grad_facing()}")
            if not ok_masters:
                parts.append(f"masters: exp={exp_masters} got={new.is_masters_facing()}")
            if not ok_rel:
                parts.append(
                    f"bucket: exp={exp_bucket} got={_rel_bucket(new.grad_relevance)}"
                    f"({new.grad_relevance:.2f})"
                )
            mismatches.append(f"  ✗  {title[:58]!r}\n       " + "  |  ".join(parts))

    if mismatches:
        print(f"\nMismatches:")
        for m in mismatches[:10]:
            print(m)
        if len(mismatches) > 10:
            print(f"  … and {len(mismatches) - 10} more")

    if total == 0:
        print("No events could be evaluated (none found in cache).")
        return

    _report_metrics("vs. hand-labeled ground truth", total, grad_m, masters_m, cat_m, rel_m)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichment eval harness")
    parser.add_argument(
        "--labels",
        help="Path to labeled_events.json for accuracy eval. "
        "Omit to run consistency eval against the cache.",
    )
    parser.add_argument("--n", type=int, default=25, help="Sample size for consistency eval")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--cache",
        default=str(ROOT / "data" / "output" / "enriched_events.json"),
        help="Path to enriched_events.json",
    )
    args = parser.parse_args()

    cache = Path(args.cache)
    if not cache.exists():
        print(f"Cache not found: {cache}")
        print("Run 'python run_curate.py --month 2026-07 --save' first, then re-run.")
        sys.exit(1)

    telemetry.reset()

    if args.labels:
        run_accuracy_eval(Path(args.labels), cache)
    else:
        run_consistency_eval(cache, args.n, args.seed)


if __name__ == "__main__":
    main()
