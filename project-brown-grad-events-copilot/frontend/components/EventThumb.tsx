"use client";

import { useState } from "react";

/**
 * Renders the event's feed image, falling back to a "Flyer" placeholder if the
 * URL is missing or fails to load (LiveWhale thumbnails occasionally 404).
 * Plain <img> (not next/image) to avoid remote-host config for arbitrary feeds.
 */
export function EventThumb({ src, size = "h-16 w-16" }: { src?: string; size?: string }) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        className={`${size} flex items-center justify-center rounded-lg border border-line bg-canvas text-[10px] uppercase tracking-wide text-faint`}
      >
        Flyer
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      onError={() => setFailed(true)}
      className={`${size} rounded-lg border border-line object-cover`}
    />
  );
}
