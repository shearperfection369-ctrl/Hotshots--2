import React from "react";

/**
 * AppErrorBoundary — global safety net wrapped around the app router.
 * Prevents ANY uncaught runtime error (bad prop, undefined access,
 * exploded 3rd-party lib) from rendering a red-screen and blocking the
 * dispatcher mid-shift. Renders a compact recovery card with a reload
 * button and the stack in a collapsible pane.
 */
export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, info: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("[AppErrorBoundary] caught:", error, info);
    this.setState({ info });
  }
  reset = () => {
    this.setState({ hasError: false, error: null, info: null });
  };
  reload = () => window.location.reload();

  render() {
    if (!this.state.hasError) return this.props.children;
    const message = String(this.state.error?.message || "Unhandled runtime error");
    const stackShort = String(this.state.error?.stack || "").split("\n").slice(0, 6).join("\n");
    return (
      <div
        data-testid="app-error-boundary"
        style={{
          minHeight: "100vh",
          background: "#0B0E14",
          color: "#E2E8F0",
          fontFamily: "monospace",
          padding: 24,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div style={{
          maxWidth: 720, width: "100%",
          border: "1px solid rgba(255,59,48,0.35)",
          background: "rgba(11,14,20,0.98)",
          borderRadius: 8, padding: 24,
        }}>
          <div style={{ fontSize: 11, letterSpacing: 3, color: "#F87171", textTransform: "uppercase", marginBottom: 12 }}>
            ⚠︎ Console recovery
          </div>
          <h1 style={{ fontSize: 20, color: "#F87171", margin: 0, marginBottom: 8 }}>
            The current view hit an unexpected error.
          </h1>
          <p style={{ color: "#94A3B8", fontSize: 13, marginBottom: 20 }}>
            Your data is safe — nothing you did was persisted incorrectly. Click <b>Try again</b> to re-render the last screen,
            or <b>Reload console</b> for a clean start.
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            <button
              onClick={this.reset}
              data-testid="app-error-retry"
              style={{
                padding: "8px 16px",
                border: "1px solid rgba(34,211,238,0.4)",
                color: "#22D3EE", background: "transparent",
                borderRadius: 4, fontSize: 12, cursor: "pointer",
              }}
            >
              Try again
            </button>
            <button
              onClick={this.reload}
              data-testid="app-error-reload"
              style={{
                padding: "8px 16px",
                border: "1px solid rgba(16,185,129,0.4)",
                color: "#10B981", background: "transparent",
                borderRadius: 4, fontSize: 12, cursor: "pointer",
              }}
            >
              Reload console
            </button>
          </div>
          <details style={{ fontSize: 11, color: "#64748B" }}>
            <summary style={{ cursor: "pointer", color: "#94A3B8" }}>Show diagnostic</summary>
            <div style={{
              marginTop: 8, padding: 12,
              background: "rgba(255,59,48,0.05)", border: "1px solid rgba(255,59,48,0.2)",
              borderRadius: 4, whiteSpace: "pre-wrap", color: "#FCA5A5",
            }}>
              <div><b>{message}</b></div>
              <pre style={{ margin: 0, fontSize: 10, marginTop: 8, whiteSpace: "pre-wrap" }}>{stackShort}</pre>
            </div>
          </details>
        </div>
      </div>
    );
  }
}
