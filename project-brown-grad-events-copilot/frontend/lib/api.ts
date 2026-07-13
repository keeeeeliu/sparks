import type { EventItem } from "./types";

// Base URL of the FastAPI backend. Override in .env.local via NEXT_PUBLIC_API_URL.
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Usage {
  calls: number;
  tokens_in: number;
  tokens_out: number;
  est_cost_usd: number;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Request to ${path} failed (${res.status}). ${detail}`);
  }
  return res.json() as Promise<T>;
}

/** POST /api/curate — ingest + dedupe + enrich for the date range. */
export function curate(
  start: string,
  end: string,
): Promise<{ events: EventItem[]; usage: Usage | null }> {
  return post("/api/curate", { start, end });
}

/** POST /api/blurbs — generate a draft blurb per selected event id. */
export async function generateBlurbs(ids: string[]): Promise<Record<string, string>> {
  const { blurbs } = await post<{ blurbs: Record<string, string> }>("/api/blurbs", {
    ids,
  });
  return blurbs;
}

/** POST /api/blurbs/improve — proofread + rewrite an edited blurb. */
export async function improveBlurb(text: string, id?: string): Promise<string> {
  const { blurb } = await post<{ blurb: string }>("/api/blurbs/improve", { text, id });
  return blurb;
}

/** POST /api/blurbs/proofread — fix grammar and typos only. */
export async function proofreadBlurb(text: string, id?: string): Promise<string> {
  const { blurb } = await post<{ blurb: string }>("/api/blurbs/proofread", { text, id });
  return blurb;
}
