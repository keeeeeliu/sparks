"use client";

import { DatePicker } from "@/components/DatePicker";
import { useStore } from "@/lib/store";

export function DateRangeBar() {
  const { rangeStart, rangeEnd, setRange, fetchEvents, loading, loaded } = useStore();

  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] text-faint">From</span>
          <DatePicker
            value={rangeStart}
            onChange={(iso) => setRange(iso, rangeEnd)}
            ariaLabel="From date"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] text-faint">To</span>
          <DatePicker
            value={rangeEnd}
            onChange={(iso) => setRange(rangeStart, iso)}
            ariaLabel="To date"
          />
        </div>

        <button
          type="button"
          onClick={() => fetchEvents()}
          disabled={loading}
          className="ml-auto h-10 rounded-lg bg-accent px-5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? "Fetching…" : loaded ? "Refresh events" : "Fetch events"}
        </button>
      </div>
    </div>
  );
}
