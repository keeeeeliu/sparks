"use client";

import type { EventItem } from "@/lib/types";
import { EventThumb } from "./EventThumb";
import { RelevanceChip } from "./RelevanceChip";

interface EventCardProps {
  event: EventItem;
  selected: boolean;
  onToggle: (id: string) => void;
}

export function EventCard({ event, selected, onToggle }: EventCardProps) {
  return (
    <div
      className={`group flex gap-4 rounded-xl border p-4 transition-colors ${
        selected
          ? "border-l-[3px] border-l-accent border-y-line border-r-line bg-selected"
          : "border-line bg-surface hover:border-faint/50"
      }`}
    >
      {/* Select toggle */}
      <button
        type="button"
        role="checkbox"
        aria-checked={selected}
        aria-label={selected ? `Deselect ${event.title}` : `Select ${event.title}`}
        onClick={() => onToggle(event.id)}
        className={`mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-md border transition-colors ${
          selected
            ? "border-accent bg-accent text-white"
            : "border-line bg-surface hover:border-accent/60"
        }`}
      >
        {selected && (
          <svg viewBox="0 0 16 16" fill="none" className="h-3.5 w-3.5">
            <path
              d="M3.5 8.5l3 3 6-6.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>

      {/* Body */}
      <div className="min-w-0 flex-1">
        <h3 className="text-[15px] font-semibold leading-snug text-ink">
          {event.title}
        </h3>

        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-faint">
          <span>{event.date}</span>
          <span aria-hidden>·</span>
          <span>{event.host}</span>
          <RelevanceChip tier={event.tier} />
          {event.mastersFacing && (
            <span className="text-[12px] text-muted">master&apos;s-facing</span>
          )}
        </div>

        <p className="mt-2 text-[13px] italic leading-relaxed text-muted">
          {event.reasoning}
        </p>

        {event.eventUrl && (
          <a
            href={event.eventUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-accent transition-colors hover:text-accent-hover hover:underline"
          >
            <span aria-hidden>↗</span> View event page
          </a>
        )}
      </div>

      {/* Event image (falls back to a placeholder if missing / fails to load) */}
      {event.imageUrl && (
        <div className="hidden flex-none sm:block">
          <EventThumb src={event.imageUrl} />
        </div>
      )}
    </div>
  );
}
