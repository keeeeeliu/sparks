"use client";

import { useEffect, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import "react-day-picker/style.css";

// Parse/format "yyyy-mm-dd" as a LOCAL date (avoids the UTC-shift bug of new Date(iso)).
function parseISO(iso: string): Date | undefined {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return undefined;
  return new Date(y, m - 1, d);
}

function toISO(date: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}`;
}

function label(date?: Date): string {
  return date
    ? date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
    : "Select date";
}

interface DatePickerProps {
  value: string; // "yyyy-mm-dd"
  onChange: (iso: string) => void;
  ariaLabel?: string;
}

export function DatePicker({ value, onChange, ariaLabel }: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = parseISO(value);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label={ariaLabel}
        onClick={() => setOpen((v) => !v)}
        className="flex h-10 items-center gap-2 rounded-lg border border-line bg-surface px-3 text-[15px] text-ink transition-colors hover:border-accent/50 focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/15"
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 text-faint" aria-hidden>
          <rect x="3" y="4" width="14" height="13" rx="2.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M3 8h14M7 2.5v3M13 2.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        {label(selected)}
      </button>

      {open && (
        <div className="cal-elegant absolute left-0 z-30 mt-2 rounded-xl border border-line bg-surface p-3 shadow-lg shadow-black/5">
          <DayPicker
            mode="single"
            selected={selected}
            defaultMonth={selected}
            onSelect={(d) => {
              if (d) {
                onChange(toISO(d));
                setOpen(false);
              }
            }}
          />
        </div>
      )}
    </div>
  );
}
