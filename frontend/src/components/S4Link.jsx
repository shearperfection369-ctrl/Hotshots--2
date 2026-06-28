import React, { useEffect, useState } from "react";
import { api } from "../lib/api";

/**
 * S4Link · auto-hyperlinks any S/4HANA reference number across the app.
 *
 *   <S4Link kind="purchase_order" value="4500012345" />
 *   <S4Link kind="invoke"        value="INV-987654" />
 *
 * On mount the component fetches /api/sap/link-config ONCE (cached at the
 * module level) so we don't roundtrip every render. The link opens the
 * Customer S/4 Fiori launchpad's fact-sheet for that reference type.
 *
 * Falls back to a plain <span> if the kind is unknown or value is empty.
 */

let _cached = null;
let _fetching = null;

function getConfig() {
  if (_cached) return Promise.resolve(_cached);
  if (_fetching) return _fetching;
  _fetching = api.get("/sap/link-config").then((r) => { _cached = r.data; return _cached; })
    .catch(() => (_cached = { base: "", patterns: {}, kinds: [] }));
  return _fetching;
}

function buildUrl(cfg, kind, value) {
  if (!cfg || !value) return null;
  const tmpl = cfg.patterns?.[kind];
  if (!tmpl) return null;
  return cfg.base + tmpl.replace("{value}", encodeURIComponent(String(value)));
}

export default function S4Link({ kind, value, className = "", children, testId, showIcon = true }) {
  const [cfg, setCfg] = useState(_cached);
  useEffect(() => { if (!cfg) getConfig().then(setCfg); }, [cfg]);

  if (!value || value === "—" || value === "null") {
    return <span className={className}>{children ?? value ?? "—"}</span>;
  }
  const url = buildUrl(cfg, kind, value);
  if (!url) {
    return <span className={className}>{children ?? value}</span>;
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      data-testid={testId || `s4-link-${kind}-${value}`}
      title={`Open ${kind.replace("_", " ")} ${value} in SAP S/4HANA`}
      className={`text-cyan-300 hover:text-cyan-200 underline decoration-cyan-500/30 hover:decoration-cyan-300 underline-offset-2 transition-colors inline-flex items-center gap-0.5 ${className}`}
    >
      {children ?? value}
      {showIcon && (
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="opacity-50 shrink-0">
          <path d="M15 3h6v6M10 14L21 3M19 11v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h8" />
        </svg>
      )}
    </a>
  );
}
