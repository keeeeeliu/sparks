import { create } from "zustand";
import { curate, type Usage } from "./api";
import { defaultRange } from "./dates";
import type { EventItem } from "./types";

interface AppState {
  // Date range
  rangeStart: string;
  rangeEnd: string;
  setRange: (start: string, end: string) => void;

  // Event pool
  events: EventItem[];
  loaded: boolean;
  loading: boolean;
  error: string | null;
  usage: Usage | null;
  fetchEvents: () => Promise<void>;

  // Selection (curator's verdict)
  selected: Set<string>;
  toggleSelect: (id: string) => void;
  clearSelection: () => void;

  // Blurbs keyed by event id
  blurbs: Record<string, string>;
  setBlurb: (id: string, text: string) => void;

  selectedEvents: () => EventItem[];
}

const initial = defaultRange();

export const useStore = create<AppState>((set, get) => ({
  rangeStart: initial.start,
  rangeEnd: initial.end,
  setRange: (start, end) => set({ rangeStart: start, rangeEnd: end }),

  events: [],
  loaded: false,
  loading: false,
  error: null,
  usage: null,
  fetchEvents: async () => {
    set({ loading: true, error: null });
    try {
      const { events, usage } = await curate(get().rangeStart, get().rangeEnd);
      // New fetch = a fresh pool; clear stale picks/blurbs.
      set({
        events,
        usage,
        loaded: true,
        loading: false,
        selected: new Set(),
        blurbs: {},
      });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : "Fetch failed" });
    }
  },

  selected: new Set<string>(),
  toggleSelect: (id) =>
    set((s) => {
      const next = new Set(s.selected);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { selected: next };
    }),
  clearSelection: () => set({ selected: new Set(), blurbs: {} }),

  blurbs: {},
  setBlurb: (id, text) => set((s) => ({ blurbs: { ...s.blurbs, [id]: text } })),

  selectedEvents: () => {
    const { events, selected } = get();
    return events.filter((e) => selected.has(e.id));
  },
}));
