import React, { useMemo, useState } from "react";
import { AlertTriangle, X, RefreshCw } from "lucide-react";
import { BACKEND_URL } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Detects the most common production deployment misconfig:
 * the deployed frontend bundle is still calling the PREVIEW backend host
 * because REACT_APP_BACKEND_URL wasn't overridden at build time.
 *
 * Shown only to admins, only when:
 *   - we're on a custom (non-preview) origin (e.g. livecleans.com), AND
 *   - the bundle's BACKEND_URL still points at *.preview.emergentagent.com
 */
const DISMISS_KEY = "deploy_health_dismissed_v1";

export default function DeployHealthBanner() {
  const { user } = useAuth();
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === "1");

  const mismatch = useMemo(() => {
    try {
      if (!BACKEND_URL || typeof window === "undefined") return null;
      const here = new URL(window.location.origin);
      const backend = new URL(BACKEND_URL);
      const sameHost = here.hostname === backend.hostname;
      // Compute the parent domain — if both hosts share a parent
      // (e.g. .emergentagent.com), the auth cookie now sets Domain=.parent
      // and sign-in works across hosts. Only show this banner when they
      // DON'T share a parent.
      const parentOf = (h) => {
        const parts = (h || "").split(".");
        if (parts.length < 2) return h;
        // Known shared parents take precedence
        for (const p of ["emergentagent.com", "emergent.host", "emergent.sh"]) {
          if (h === p || h.endsWith("." + p)) return p;
        }
        return parts.slice(-2).join(".");
      };
      const hereParent = parentOf(here.hostname);
      const backendParent = parentOf(backend.hostname);
      if (!sameHost && hereParent !== backendParent) {
        return { here: here.origin, backend: backend.origin };
      }
      return null;
    } catch (_) {
      return null;
    }
  }, []);

  if (!mismatch) return null;
  if (user && user.role !== "admin") return null;
  if (dismissed) return null;

  return (
    <div
      data-testid="deploy-health-banner"
      className="sticky top-0 z-50 bg-red-950/90 border-b border-red-500/40 backdrop-blur-md"
    >
      <div className="max-w-7xl mx-auto px-4 py-2 flex items-start gap-3">
        <AlertTriangle size={16} className="text-red-300 flex-shrink-0 mt-0.5" />
        <div className="flex-1 text-xs text-red-100 leading-snug">
          <div className="font-bold mb-0.5 text-red-200">Deployment misconfig — frontend and backend on different parent domains.</div>
          <div className="font-mono text-[11px] text-red-200/80 truncate">
            Frontend (<code>{mismatch.here}</code>) calls backend (<code>{mismatch.backend}</code>) — the auth cookie cannot be shared, so sign-in loops.
          </div>
          <div className="mt-1 text-red-200/90">
            Fix: Save to GitHub → Deploy with{" "}
            <code className="mx-1 px-1 py-0.5 bg-red-900/40 rounded">REACT_APP_BACKEND_URL={mismatch.here}/api</code>
            so the bundle calls the same origin as the frontend. Or contact Emergent Support to align both URLs under one parent domain.
          </div>
        </div>
        <button
          onClick={() => window.location.reload()}
          title="Reload (re-check after redeploy)"
          data-testid="deploy-health-reload"
          className="text-red-200 hover:text-white p-1 flex-shrink-0"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={() => { sessionStorage.setItem(DISMISS_KEY, "1"); setDismissed(true); }}
          title="Dismiss for this session"
          data-testid="deploy-health-dismiss"
          className="text-red-200 hover:text-white p-1 flex-shrink-0"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
