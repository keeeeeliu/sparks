"use client";

import { useState } from "react";

interface SectionPanelProps {
  title: string;
  count: number;
  selectedCount?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export function SectionPanel({
  title,
  count,
  selectedCount = 0,
  defaultOpen = true,
  children,
}: SectionPanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="group flex w-full items-baseline gap-2 border-b border-line pb-2 text-left"
      >
        <svg
          viewBox="0 0 16 16"
          fill="none"
          className={`h-3.5 w-3.5 flex-none self-center text-faint transition-transform ${
            open ? "rotate-90" : ""
          }`}
        >
          <path
            d="M6 4l4 4-4 4"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <h2 className="font-serif text-2xl font-semibold text-ink">{title}</h2>
        <span className="text-base font-normal text-faint">{count}</span>
        {selectedCount > 0 && (
          <span className="ml-auto self-center text-[13px] font-medium text-accent">
            {selectedCount} selected
          </span>
        )}
      </button>

      {open && <div className="mt-4 space-y-3">{children}</div>}
    </section>
  );
}
