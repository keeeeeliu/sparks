"use client";

import { useEffect, useState } from "react";

// Staged messages roughly track what the pipeline actually does in order:
// ingest (fast) → dedupe (fast) → per-event LLM enrichment (the long part).
const STAGES = [
  { at: 0, label: "Pulling events from the calendar…" },
  { at: 3, label: "Removing duplicate & recurring events…" },
  { at: 7, label: "Scoring each event's relevance with AI…" },
  { at: 30, label: "Almost there — finishing up…" },
];

function Spinner() {
  return (
    <svg className="h-8 w-8 animate-spin text-accent" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-20" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function FetchProgress() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const stage = [...STAGES].reverse().find((s) => elapsed >= s.at) ?? STAGES[0];
  const clock = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;

  return (
    <div className="mt-16 flex flex-col items-center text-center" aria-live="polite">
      <Spinner />
      <p className="mt-4 font-serif text-xl text-ink">Fetching events…</p>
      <p className="mt-2 text-[15px] text-muted">{stage.label}</p>

      {/* Indeterminate progress bar */}
      <div className="mt-5 h-1 w-64 overflow-hidden rounded-full bg-line">
        <div className="animate-indeterminate h-full w-1/3 rounded-full bg-accent" />
      </div>

      <p className="mt-3 text-[13px] text-faint">
        {clock} elapsed · usually 30–60s for a full month
      </p>
    </div>
  );
}
