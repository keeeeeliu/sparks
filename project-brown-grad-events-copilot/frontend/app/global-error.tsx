"use client";

// Top-level error boundary. Also works around an intermittent Next 16 / Turbopack
// RSC-manifest bug that expects an explicit global-error module.
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#f7f6f2" }}>
        <div
          style={{
            maxWidth: 480,
            margin: "20vh auto",
            padding: "0 24px",
            textAlign: "center",
            color: "#232020",
          }}
        >
          <h1 style={{ fontSize: 24, marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ color: "#6f675f", marginBottom: 20 }}>
            An unexpected error occurred while loading this page.
          </p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              background: "#4f6f54",
              color: "white",
              border: "none",
              borderRadius: 8,
              padding: "10px 18px",
              fontSize: 14,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
