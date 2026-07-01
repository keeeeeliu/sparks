"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { DateRangeBar } from "@/components/DateRangeBar";
import { EventCard } from "@/components/EventCard";
import { FetchProgress } from "@/components/FetchProgress";
import { SectionPanel } from "@/components/SectionPanel";
import { formatRangeLabel } from "@/lib/dates";
import { useStore } from "@/lib/store";
import {
  SECTION_ORDER,
  meetsMinTier,
  type EventItem,
  type MinTier,
  type SectionName,
} from "@/lib/types";

const MIN_TIER_OPTIONS: { value: MinTier; label: string }[] = [
  { value: "all", label: "All" },
  { value: "mid", label: "Mid+" },
  { value: "high", label: "High" },
];

export default function CuratePage() {
  const router = useRouter();
  const {
    events,
    loaded,
    loading,
    error,
    usage,
    rangeStart,
    rangeEnd,
    selected,
    toggleSelect,
  } = useStore();

  const [query, setQuery] = useState("");
  const [mastersOnly, setMastersOnly] = useState(false);
  const [minTier, setMinTier] = useState<MinTier>("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      if (mastersOnly && !e.mastersFacing) return false;
      if (!meetsMinTier(e.tier, minTier)) return false;
      if (q && !`${e.title} ${e.host}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [events, query, mastersOnly, minTier]);

  const bySection = useMemo(() => {
    const map = new Map<SectionName, EventItem[]>();
    for (const section of SECTION_ORDER) {
      const evs = filtered.filter((e) => e.section === section);
      if (evs.length) map.set(section, evs);
    }
    return map;
  }, [filtered]);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12 sm:px-8">
      {/* Header */}
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-5xl font-semibold tracking-tight text-ink">
            Grad Events
          </h1>
          <p className="mt-2 text-[15px] text-muted">
            {formatRangeLabel(rangeStart, rangeEnd)}
          </p>
        </div>
        <button
          type="button"
          disabled={selected.size === 0}
          onClick={() => router.push("/compose")}
          className="flex-none rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue to draft · {selected.size}
        </button>
      </header>

      {/* Date range setup */}
      <div className="mt-6">
        <DateRangeBar />
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-800">
          {error} — is the backend running on :8000?
        </div>
      )}

      {/* Empty / loading states before a fetch */}
      {loading ? (
        <FetchProgress />
      ) : !loaded ? (
        <div className="mt-16 text-center">
          <p className="font-serif text-xl text-ink">No events loaded yet</p>
          <p className="mt-2 text-[15px] text-muted">
            Pick a date range above and press Fetch events to begin.
          </p>
        </div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="mt-6 flex items-center gap-2 border-b border-line pb-5 text-[15px]">
            <span className="text-muted">{filtered.length} events</span>
            <span className="text-faint" aria-hidden>
              ·
            </span>
            <span className="font-medium text-accent">{selected.size} selected</span>
            {usage && usage.calls > 0 && (
              <>
                <span className="text-faint" aria-hidden>
                  ·
                </span>
                <span className="text-faint">
                  {(usage.tokens_in + usage.tokens_out).toLocaleString()} tokens used
                </span>
              </>
            )}
          </div>

          {/* Filters */}
          <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search events or hosts"
              className="h-11 min-w-50 flex-1 rounded-lg border border-line bg-surface px-4 text-[15px] text-ink placeholder:text-faint focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/15"
            />

            <div className="flex select-none items-center gap-2.5 text-[15px] text-muted">
              <button
                type="button"
                role="switch"
                aria-checked={mastersOnly}
                aria-label="Master's-facing only"
                onClick={() => setMastersOnly((v) => !v)}
                className={`relative inline-flex h-6 w-11 flex-none items-center rounded-full transition-colors ${
                  mastersOnly ? "bg-accent" : "bg-line"
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                    mastersOnly ? "translate-x-5.5" : "translate-x-0.5"
                  }`}
                />
              </button>
              Master&apos;s-facing only
            </div>

            <div className="flex items-center gap-2.5">
              <span className="text-[15px] text-faint">Min relevance</span>
              <div className="flex rounded-lg bg-line/50 p-0.5">
                {MIN_TIER_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setMinTier(opt.value)}
                    className={`rounded-md px-3 py-1.5 text-[14px] font-medium transition-colors ${
                      minTier === opt.value
                        ? "bg-surface text-ink shadow-sm"
                        : "text-faint hover:text-muted"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Foldable sections */}
          {bySection.size === 0 ? (
            <div className="mt-16 text-center">
              <p className="font-serif text-xl text-ink">No events match your filters</p>
              <p className="mt-2 text-[15px] text-muted">
                Try clearing the search or lowering the minimum relevance.
              </p>
            </div>
          ) : (
            <div className="mt-10 space-y-8">
              {Array.from(bySection.entries()).map(([section, evs]) => (
                <SectionPanel
                  key={section}
                  title={section}
                  count={evs.length}
                  selectedCount={evs.filter((e) => selected.has(e.id)).length}
                  defaultOpen={false}
                >
                  {evs.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      selected={selected.has(event.id)}
                      onToggle={toggleSelect}
                    />
                  ))}
                </SectionPanel>
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
