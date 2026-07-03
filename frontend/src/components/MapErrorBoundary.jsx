import React from "react";

/**
 * MapErrorBoundary — catches any runtime error thrown by a Leaflet/react-leaflet
 * subtree (bad LatLng, tile-layer failure, marker init crash) and renders a
 * friendly inline card instead of taking down the whole page.
 *
 * A crash inside a map should never break the surrounding dashboard.
 */
export default class MapErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    // Log but never re-throw — the whole point is graceful degradation.
    console.warn("[MapErrorBoundary] caught:", error?.message, info?.componentStack?.split("\n").slice(0, 4).join("\n"));
  }
  reset = () => this.setState({ hasError: false, error: null });

  render() {
    if (!this.state.hasError) return this.props.children;
    const message = String(this.state.error?.message || "Map failed to render");
    return (
      <div
        data-testid="map-error-boundary"
        style={{
          height: this.props.height || 480,
          border: "1px solid rgba(255,59,48,0.35)",
          background: "rgba(255,59,48,0.05)",
          borderRadius: 8,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 8,
          color: "#F87171",
          fontFamily: "monospace",
          fontSize: 12,
          textAlign: "center",
          padding: 24,
        }}
      >
        <div style={{ fontSize: 11, letterSpacing: 2, opacity: 0.75, textTransform: "uppercase" }}>
          Map temporarily unavailable
        </div>
        <div style={{ color: "#FCA5A5", fontSize: 11, maxWidth: 520 }}>{message}</div>
        <div style={{ color: "#94A3B8", fontSize: 10 }}>
          The rest of the console kept working — click retry once the underlying data reloads.
        </div>
        <button
          onClick={this.reset}
          data-testid="map-error-retry"
          style={{
            marginTop: 4,
            padding: "6px 14px",
            border: "1px solid rgba(34,211,238,0.4)",
            color: "#22D3EE",
            background: "transparent",
            borderRadius: 4,
            fontSize: 11,
            cursor: "pointer",
          }}
        >
          Retry map
        </button>
      </div>
    );
  }
}
