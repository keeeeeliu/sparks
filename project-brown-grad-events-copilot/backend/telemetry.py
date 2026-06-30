"""In-process LLM call telemetry: tokens, latency, and estimated cost.

Records are accumulated in a thread-safe list so concurrent enrichment calls
(enrich_events uses a ThreadPoolExecutor) can all write safely.

Typical usage:
    from backend import telemetry
    telemetry.reset()             # clear before a run
    ...                           # pipeline runs, complete_json records each call
    telemetry.print_summary()     # or use telemetry.summarize() for structured data
"""
from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass

_lock = threading.Lock()
_records: list[_CallRecord] = []

# Cost per 1 M tokens: (input_usd, output_usd). Approximate mid-2026 pricing.
# Update if you switch models or pricing changes.
_COST_PER_M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (15.00, 75.00),
}


@dataclass
class _CallRecord:
    label: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float


@dataclass
class LabelStats:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    total_ms: float = 0.0
    est_cost_usd: float = 0.0


@dataclass
class UsageSummary:
    calls: int
    tokens_in: int
    tokens_out: int
    total_ms: float
    est_cost_usd: float
    by_label: dict[str, LabelStats]

    def __str__(self) -> str:
        if self.calls == 0:
            return "0 LLM calls"
        return (
            f"{self.calls} LLM calls · "
            f"{self.tokens_in:,} in / {self.tokens_out:,} out tokens · "
            f"{self.total_ms / 1000:.1f}s wall · "
            f"est. ${self.est_cost_usd:.4f}"
        )


def record_call(
    *, label: str, model: str, tokens_in: int, tokens_out: int, latency_ms: float
) -> None:
    with _lock:
        _records.append(
            _CallRecord(
                label=label,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
            )
        )


def reset() -> None:
    """Clear all records. Call at the start of each pipeline run to get per-run stats."""
    with _lock:
        _records.clear()


def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    in_r, out_r = _COST_PER_M.get(model, (0.0, 0.0))
    return (tokens_in * in_r + tokens_out * out_r) / 1_000_000


def summarize() -> UsageSummary:
    """Return a snapshot of all accumulated records."""
    with _lock:
        records = list(_records)

    by_label: dict[str, LabelStats] = defaultdict(LabelStats)
    for r in records:
        s = by_label[r.label]
        s.calls += 1
        s.tokens_in += r.tokens_in
        s.tokens_out += r.tokens_out
        s.total_ms += r.latency_ms
        s.est_cost_usd += _cost(r.model, r.tokens_in, r.tokens_out)

    total_in = sum(r.tokens_in for r in records)
    total_out = sum(r.tokens_out for r in records)
    return UsageSummary(
        calls=len(records),
        tokens_in=total_in,
        tokens_out=total_out,
        total_ms=sum(r.latency_ms for r in records),
        est_cost_usd=sum(_cost(r.model, r.tokens_in, r.tokens_out) for r in records),
        by_label=dict(by_label),
    )


def print_summary(*, prefix: str = "") -> None:
    """Print a human-readable cost/latency breakdown to stdout."""
    s = summarize()
    if s.calls == 0:
        print(f"{prefix}[telemetry] No LLM calls recorded.")
        return
    print(f"{prefix}[telemetry] {s}")
    for label, ls in sorted(s.by_label.items()):
        avg_ms = ls.total_ms / ls.calls if ls.calls else 0
        avg_out = ls.tokens_out / ls.calls if ls.calls else 0
        print(
            f"{prefix}  {label:<20s} {ls.calls:4d} calls · "
            f"{avg_ms:6.0f}ms avg · "
            f"{avg_out:5.0f} out-tok avg · "
            f"${ls.est_cost_usd:.4f}"
        )
