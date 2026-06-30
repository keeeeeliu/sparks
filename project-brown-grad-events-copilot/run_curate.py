"""CLI wrapper for Stage 2 curation — calls `backend.pipeline.curate_range`.

All orchestration lives in the backend so a future API/UI reuses the same code.
See `backend/pipeline.py` and `backend/report.py`.

Usage:
    python run_curate.py --month 2026-07                 # rank July for grad students
    python run_curate.py --month 2026-07 --list-hosts    # NO LLM: list host orgs in July
    python run_curate.py --month 2026-07 --departments "Graduate School,Student"
    python run_curate.py --month 2026-07 --keywords "career,wellness"
    python run_curate.py --start-date 2026-07-01 --end-date 2026-07-15 --max 40 --save

Requires .env with LLM_PROVIDER + matching API key (enrichment uses the LLM).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from backend import telemetry
from backend.pipeline import (
    curate_range,
    default_grad_target,
    list_hosts_in_range,
    resolve_month_range,
)
from backend.report import format_when, write_markdown_report

_TERMINAL_LIMIT = 20  # when --save, terminal shows a preview; the report has the full list


def _csv(value: str | None) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()] if value else []


def _short(text: str | None, width: int = 80) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _resolve_range(args: argparse.Namespace) -> tuple[str | None, str | None]:
    if args.month:
        return resolve_month_range(args.month)
    return args.start_date, args.end_date


def _print_event(rank: int, ev) -> None:
    score = f"{ev.grad_relevance:.2f}" if ev.grad_relevance is not None else "n/a"
    flag = "MASTER'S" if ev.is_masters_facing() else ("grad" if ev.is_grad_facing() else "—")
    audience = ", ".join(ev.audience) or "unspecified"
    print(f"{rank:>2}. [{flag:>8} | rel {score}] {_short(ev.title, 78)}")
    print(f"    {format_when(ev)}  |  host: {ev.host_org or 'unknown'}  |  category: {ev.category or '—'}")
    print(f"    audience: {audience}")
    if ev.relevance_reasoning:
        print(f"    score: {_short(ev.relevance_reasoning, 88)}")
    if ev.audience_evidence:
        print(f"    why: \"{_short(ev.audience_evidence, 88)}\"")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich + prioritize a month of Brown events (Stage 2).")
    parser.add_argument("--month", help="YYYY-MM convenience (overrides --start-date/--end-date).")
    parser.add_argument("--start-date", help="YYYY-MM-DD inclusive lower bound.")
    parser.add_argument("--end-date", help="YYYY-MM-DD inclusive upper bound.")
    parser.add_argument("--max", type=int, default=60,
                        help="Cap unique events enriched (default 60; raise for a full month).")
    parser.add_argument("--workers", type=int, default=8,
                        help="Concurrent enrichment calls (default 8; use 1 for sequential baseline).")
    parser.add_argument("--min-relevance", type=float, default=0.0,
                        help="Drop events below this grad_relevance (default 0.0 = keep all, just rank).")
    parser.add_argument("--departments", help="Comma-separated host filter (substring).")
    parser.add_argument("--keywords", help="Comma-separated topic keywords.")
    parser.add_argument("--list-hosts", action="store_true",
                        help="No LLM: list host orgs (+counts) in the range.")
    parser.add_argument("--base-url", default="https://events.brown.edu", help="LiveWhale base URL.")
    parser.add_argument("--save", action="store_true",
                        help="Write curated report + enriched JSON to data/output/.")
    args = parser.parse_args()

    start_date, end_date = _resolve_range(args)
    span = f"{start_date or 'feed default'} → {end_date or 'feed default'}"

    if args.list_hosts:
        print(f"Listing host orgs for {span} (structured feed, no LLM)…")
        hosts = list_hosts_in_range(start_date, end_date, base_url=args.base_url)
        total = sum(n for _, n in hosts)
        print(f"  {total} event(s) across {len(hosts)} host(s):\n")
        for host, n in hosts:
            print(f"  {n:>4}  {host}")
        print("\nTip: pass Student Affairs hosts to --departments to focus the ranking.")
        return

    pull_cap = None if (start_date or end_date) else args.max
    print(f"Pulling events for {span} (structured feed, no LLM)…")

    target = default_grad_target(
        start_date, end_date,
        departments=_csv(args.departments),
        keywords=_csv(args.keywords),
        min_relevance=args.min_relevance,
    )

    mode = "sequential" if args.workers <= 1 else f"{args.workers}-way concurrent"
    print(f"Enriching (via backend.pipeline.curate_range, {mode})…")
    t0 = time.perf_counter()
    result = curate_range(
        start_date, end_date,
        target=target,
        base_url=args.base_url,
        pull_cap=pull_cap,
        max_enrich=args.max,
        max_workers=args.workers,
    )
    elapsed = time.perf_counter() - t0

    print(f"  got {result.raw_count} dated instance(s).")
    print(f"  deduped → {result.unique_count} unique "
          f"({result.raw_count - result.unique_count} duplicate instance(s) collapsed).")
    if result.unique_count > result.enriched_count:
        print(f"  NOTE: capping enrichment at --max {args.max} of {result.unique_count} unique "
              "(raise --max to cover the whole month).")
    print(f"  done in {elapsed:.1f}s ({elapsed / max(result.enriched_count, 1):.2f}s/event avg).")
    if result.usage and result.usage.calls > 0:
        telemetry.print_summary(prefix="  ")
    print()

    ranked = result.events
    n_masters = sum(e.is_masters_facing() for e in ranked)
    n_grad = sum(e.is_grad_facing() for e in ranked)
    print(f"=== {target.name} | {span} | min_relevance={args.min_relevance} ===")
    print(f"    {len(ranked)}/{result.enriched_count} kept  ·  {n_masters} explicitly master's  ·  "
          f"{n_grad} grad-facing  ·  rest are all/unspecified (kept for review)\n")

    preview = ranked[:_TERMINAL_LIMIT] if args.save else ranked
    for i, ev in enumerate(preview, 1):
        _print_event(i, ev)
    if args.save and len(ranked) > len(preview):
        print(f"… and {len(ranked) - len(preview)} more — see the full report below.\n")

    if args.save:
        out_dir = Path("data/output")
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "enriched_events.json"
        json_path.write_text(
            json.dumps([json.loads(e.model_dump_json()) for e in result.enriched], indent=2)
        )
        slug = f"{start_date}_{end_date}" if (start_date or end_date) else "latest"
        report_path = out_dir / f"curated_{slug}.md"
        write_markdown_report(report_path, ranked, span)
        print(f"Saved:\n  • {report_path}  ← readable, grouped by purpose, FULL reasoning\n"
              f"  • {json_path}  ← structured cache (reuse instead of re-enriching)")


if __name__ == "__main__":
    main()
