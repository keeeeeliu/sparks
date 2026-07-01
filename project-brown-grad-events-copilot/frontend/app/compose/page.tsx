"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { generateBlurbs, improveBlurb } from "@/lib/api";
import { formatRangeLabel } from "@/lib/dates";
import { useStore } from "@/lib/store";
import { CopyField } from "@/components/CopyField";
import { EventThumb } from "@/components/EventThumb";
import { RelevanceChip } from "@/components/RelevanceChip";
import { SECTION_ORDER, type EventItem, type SectionName } from "@/lib/types";

export default function ComposePage() {
  const { rangeStart, rangeEnd, blurbs, setBlurb, selectedEvents } = useStore();
  const selected = selectedEvents();

  const [generating, setGenerating] = useState(false);
  const [improvingId, setImprovingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bySection = useMemo(() => {
    const map = new Map<SectionName, EventItem[]>();
    for (const section of SECTION_ORDER) {
      const evs = selected.filter((e) => e.section === section);
      if (evs.length) map.set(section, evs);
    }
    return map;
  }, [selected]);

  const generateMissing = async () => {
    const missing = selected.filter((e) => !blurbs[e.id]?.trim()).map((e) => e.id);
    if (missing.length === 0) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await generateBlurbs(missing);
      for (const [id, text] of Object.entries(result)) setBlurb(id, text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Blurb generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const improve = async (ev: EventItem) => {
    const current = blurbs[ev.id];
    if (!current?.trim()) return;
    setImprovingId(ev.id);
    setError(null);
    try {
      setBlurb(ev.id, await improveBlurb(current, ev.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Improve failed");
    } finally {
      setImprovingId(null);
    }
  };

  const copyBlurb = async (ev: EventItem) => {
    const text = blurbs[ev.id]?.trim();
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopiedId(ev.id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  if (selected.length === 0) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12 sm:px-8">
        <Link href="/" className="text-[14px] text-faint hover:text-accent">
          ← Back to events
        </Link>
        <div className="mt-16 text-center">
          <p className="font-serif text-xl text-ink">No events selected yet</p>
          <p className="mt-2 text-[15px] text-muted">
            Go back, pick the events for this newsletter, then return here to draft blurbs.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12 sm:px-8">
      <Link href="/" className="text-[14px] text-faint hover:text-accent">
        ← Back to events
      </Link>

      <header className="mt-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-5xl font-semibold tracking-tight text-ink">
            Compose draft
          </h1>
          <p className="mt-2 text-[15px] text-muted">
            {selected.length} events · {formatRangeLabel(rangeStart, rangeEnd)}
          </p>
        </div>
        <button
          type="button"
          onClick={generateMissing}
          disabled={generating}
          className="flex-none rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {generating ? "Writing…" : "Generate blurbs"}
        </button>
      </header>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[14px] text-red-800">
          {error}
        </div>
      )}

      {/* Per-event blurb editors, grouped by section */}
      <div className="mt-10 space-y-10">
        {Array.from(bySection.entries()).map(([section, evs]) => (
          <section key={section}>
            <h2 className="mb-4 font-serif text-2xl font-semibold text-ink">{section}</h2>
            <div className="space-y-4">
              {evs.map((ev) => (
                <div key={ev.id} className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[15px] font-semibold leading-snug text-ink">
                        {ev.title}
                      </h3>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-faint">
                        <span>{ev.date}</span>
                        <span aria-hidden>·</span>
                        <span>{ev.host}</span>
                        <RelevanceChip tier={ev.tier} />
                      </div>
                    </div>
                    {ev.imageUrl && (
                      <div className="hidden flex-none sm:block">
                        <EventThumb src={ev.imageUrl} size="h-14 w-14" />
                      </div>
                    )}
                  </div>

                  <textarea
                    value={blurbs[ev.id] ?? ""}
                    onChange={(e) => setBlurb(ev.id, e.target.value)}
                    placeholder="Newsletter blurb — 2–3 warm sentences…"
                    rows={3}
                    className="mt-3 w-full resize-y rounded-lg border border-line bg-canvas px-3 py-2.5 text-[14px] leading-relaxed text-ink placeholder:text-faint focus:border-accent/60 focus:outline-none focus:ring-2 focus:ring-accent/15"
                  />

                  <div className="mt-2 flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => improve(ev)}
                      disabled={!blurbs[ev.id]?.trim() || improvingId === ev.id}
                      className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-[13px] font-medium text-muted transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-40"
                    >
                      ✨ {improvingId === ev.id ? "Improving…" : "Improve writing"}
                    </button>
                    <button
                      type="button"
                      onClick={() => copyBlurb(ev)}
                      disabled={!blurbs[ev.id]?.trim()}
                      className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-[13px] font-medium text-muted transition-colors hover:border-accent/50 hover:text-accent disabled:opacity-40"
                    >
                      {copiedId === ev.id ? "Copied ✓" : "Copy blurb"}
                    </button>
                    <a
                      href={ev.eventUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[13px] font-medium text-accent transition-colors hover:text-accent-hover hover:underline"
                    >
                      ↗ View event page
                    </a>
                  </div>

                  {/* Copy-paste-ready URLs for the Google Doc (Streamlit parity) */}
                  <div className="mt-3 grid gap-2 border-t border-line pt-3 sm:grid-cols-2">
                    <CopyField label="Event link" value={ev.eventUrl} />
                    {ev.imageUrl && <CopyField label="Image URL" value={ev.imageUrl} />}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
