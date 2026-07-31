"use client";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  return (
    <html lang="en" className="dark">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#0e0f12",
          color: "#e8eaed",
          fontFamily:
            'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          padding: "3rem 1.5rem",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.625rem",
          }}
        >
          {/* biome-ignore lint/performance/noImgElement: global-error has no Next Image runtime */}
          <img
            src="/conve-logo.png"
            alt=""
            width={40}
            height={40}
            style={{
              width: 40,
              height: 40,
              borderRadius: "22%",
              imageRendering: "pixelated",
            }}
            aria-hidden
          />
          <span style={{ fontSize: "1.125rem", fontWeight: 600, letterSpacing: "-0.01em" }}>
            Conve
          </span>
        </span>
        <h1 style={{ marginTop: "1rem", fontSize: "1.75rem", fontWeight: 600 }}>
          Something went wrong
        </h1>
        <p style={{ marginTop: "0.75rem", color: "#8b919a", fontSize: "0.875rem" }}>
          {error.digest ? <span>Error ID: {error.digest}</span> : "Please try again."}
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: "2rem",
            height: "2.5rem",
            borderRadius: "10px",
            border: "none",
            background: "#e8eaed",
            color: "#0e0f12",
            padding: "0 1rem",
            fontSize: "0.875rem",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
