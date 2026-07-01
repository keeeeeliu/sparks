"use client";

import { useState } from "react";

/**
 * A copy-paste-ready URL field (Streamlit parity): the value sits in a readonly
 * input so it's always visible and selectable — click to select-all, or hit Copy.
 */
export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-faint">
        {label}
      </label>
      <div className="flex items-center gap-1.5">
        <input
          readOnly
          value={value}
          onFocus={(e) => e.currentTarget.select()}
          className="h-8 min-w-0 flex-1 rounded-md border border-line bg-canvas px-2 font-mono text-[12px] text-muted focus:border-accent/60 focus:outline-none"
        />
        <button
          type="button"
          onClick={copy}
          className="flex-none rounded-md border border-line px-2 py-1 text-[12px] text-faint transition-colors hover:border-accent/50 hover:text-accent"
        >
          {copied ? "✓" : "Copy"}
        </button>
      </div>
    </div>
  );
}
