// Mirrors the fields the backend `Event` exposes that the UI needs.
// (The full backend model has more; this is the view contract sent by /api/curate.)

export type RelevanceTier = "high" | "mid" | "low";

export interface EventItem {
  id: string;
  title: string;
  section: SectionName;
  /** Human display date, e.g. "Mon 07/13 10:00" or a recurring span. */
  date: string;
  host: string;
  tier: RelevanceTier;
  /** One-line "why this score / who would value it" from enrichment. */
  reasoning: string;
  mastersFacing: boolean;
  /** Link to the real event page (or registration), opened in a new tab. */
  eventUrl: string;
  /** Feed image URL, when present (LiveWhale thumbnail). */
  imageUrl?: string;
}

// Section names match backend `report.SECTIONS` EXACTLY so grouping never drifts.
export const SECTION_ORDER = [
  "Career & Professional",
  "Academic & Research",
  "Wellness & Well-being",
  "Arts & Culture",
  "Social & Community",
  "Other / Administrative",
] as const;

export type SectionName = (typeof SECTION_ORDER)[number];

/** Filter for the min-relevance segmented control. */
export type MinTier = "all" | "mid" | "high";

const TIER_RANK: Record<RelevanceTier, number> = { low: 0, mid: 1, high: 2 };
const MIN_TIER_RANK: Record<MinTier, number> = { all: 0, mid: 1, high: 2 };

export function meetsMinTier(tier: RelevanceTier, min: MinTier): boolean {
  return TIER_RANK[tier] >= MIN_TIER_RANK[min];
}
