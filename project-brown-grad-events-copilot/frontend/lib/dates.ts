/** Default newsletter window: 15th of this month → 15th of next month. */
export function defaultRange(): { start: string; end: string } {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), 15);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 15);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

export function formatRangeLabel(start: string, end: string): string {
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  try {
    const s = new Date(start + "T00:00:00").toLocaleDateString("en-US", opts);
    const e = new Date(end + "T00:00:00").toLocaleDateString("en-US", {
      ...opts,
      year: "numeric",
    });
    return `${s} – ${e}`;
  } catch {
    return `${start} – ${end}`;
  }
}
