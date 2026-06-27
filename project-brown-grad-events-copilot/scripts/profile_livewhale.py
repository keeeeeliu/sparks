"""Reproducible profiling of the Brown LiveWhale feed.

Purpose: make the claims in docs/data-sources/livewhale.md VERIFIABLE. Anyone can run
this and reproduce the field-coverage numbers and the "audience tags are department
defaults" finding, rather than taking the data card's word for it.

Usage:
    python scripts/profile_livewhale.py            # default ~300-event sample
    python scripts/profile_livewhale.py 500        # larger sample

No API key needed (public feed). Network access required.
"""

from __future__ import annotations

import collections
import sys

import httpx

BASE = "https://events.brown.edu/live/json/v2/events"
HEADERS = {"User-Agent": "BrownGradEventsCopilot/0.1 (+profiling)"}
FIELDS = "event_types,tags,group_title,location,description"


def fetch(limit: int) -> list[dict]:
    url = f"{BASE}/response_fields/{FIELDS}/paginate/100/"
    items: list[dict] = []
    with httpx.Client(timeout=25.0, headers=HEADERS, follow_redirects=True) as client:
        while url and len(items) < limit:
            data = client.get(url).json()
            items += data["data"]
            url = (data.get("links") or {}).get("next")
    return items[:limit]


def coverage(items: list[dict], key: str) -> str:
    n = sum(1 for it in items if it.get(key))
    return f"{n}/{len(items)} ({round(100 * n / len(items))}%)"


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    items = fetch(limit)
    print(f"Sampled {len(items)} events from {BASE}\n")

    print("=== field coverage ===")
    for key in ["group_title", "tags", "event_types", "event_types_audience", "event_types_campus"]:
        print(f"  {key:24} {coverage(items, key)}")

    grad = sum(
        1
        for it in items
        if any("grad" in (a or "").lower() for a in (it.get("event_types_audience") or []))
    )
    print(f"\n  events with a 'graduate' audience value: {grad}/{len(items)}")

    print("\n=== finding: identical audience sets across different events in a group ===")
    by_group: dict[str, set[tuple]] = collections.defaultdict(set)
    titles_per_set: dict[tuple, set[str]] = collections.defaultdict(set)
    for it in items:
        aud = tuple(sorted(it.get("event_types_audience") or []))
        if aud:
            by_group[it.get("group_title") or "(none)"].add(aud)
            titles_per_set[aud].add((it.get("title") or "")[:40])
    shared = [(s, t) for s, t in titles_per_set.items() if len(t) > 1]
    if shared:
        aud_set, titles = max(shared, key=lambda x: len(x[1]))
        print(f"  {len(titles)} DIFFERENT events share this exact audience set:")
        print(f"    {list(aud_set)}")
        for t in list(titles)[:5]:
            print(f"      - {t}")
        print("  => identical sets across unrelated events = a department-wide default, not per-event curation.")
    else:
        print("  (no shared sets in this sample)")


if __name__ == "__main__":
    main()
