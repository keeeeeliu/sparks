import type { RelevanceTier } from "@/lib/types";

const LABELS: Record<RelevanceTier, string> = {
  high: "High",
  mid: "Mid",
  low: "Low",
};

const STYLES: Record<RelevanceTier, string> = {
  high: "bg-accent-soft text-accent-ink",
  mid: "bg-line/60 text-muted",
  low: "bg-line/40 text-faint",
};

export function RelevanceChip({ tier }: { tier: RelevanceTier }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide ${STYLES[tier]}`}
    >
      {LABELS[tier]}
    </span>
  );
}
