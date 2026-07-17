import React, { useEffect, useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { Siren, X, ChevronRight } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

/**
 * Red alert banner — lights up the moment Agent Sentinel detects a
 * degradation (deployment down, LLM budget, error rates). Polls every 60 s.
 */
export default function SentinelBanner() {
  const { user } = useAuth();
  const location = useLocation();
  const [banner, setBanner] = useState(null);
  const [dismissedKey, setDismissedKey] = useState(
    () => sessionStorage.getItem("sentinel_banner_dismissed") || ""
  );

  useEffect(() => {
    if (!user) return;
    let alive = true;
    const poll = async () => {
      try {
        const r = await api.get("/sentinel/status");
        if (alive) setBanner(r.data?.banner || null);
      } catch (_) { /* silent */ }
    };
    poll();
    const t = setInterval(poll, 60000);
    return () => { alive = false; clearInterval(t); };
  }, [user]);

  if (!user || !banner) return null;
  const key = (banner.alert_ids || []).join(",");
  if (key && key === dismissedKey) return null;
  if (location.pathname === "/sentinel") return null;

  const critical = banner.severity === "critical";
  return (
    <div
      data-testid="sentinel-red-banner"
      className={`sticky top-0 z-50 border-b backdrop-blur-md ${
        critical ? "bg-red-950/95 border-red-500/50" : "bg-amber-950/95 border-amber-500/40"
      }`}
    >
      <div className="px-4 py-2 flex items-center gap-3">
        <Siren size={16} className={`${critical ? "text-red-400" : "text-amber-400"} animate-pulse shrink-0`} />
        <div className="flex-1 min-w-0 text-sm">
          <span className={`font-mono text-[10px] uppercase tracking-[0.2em] mr-2 ${critical ? "text-red-300" : "text-amber-300"}`}>
            {critical ? "RED ALERT" : "DEGRADED"}
          </span>
          <span className="text-slate-100 truncate" data-testid="sentinel-banner-message">{banner.message}</span>
        </div>
        <Link
          to="/sentinel"
          data-testid="sentinel-banner-link"
          className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded ${
            critical ? "bg-red-500/20 text-red-200 hover:bg-red-500/30" : "bg-amber-500/20 text-amber-200 hover:bg-amber-500/30"
          }`}
        >
          Open Sentinel <ChevronRight size={12} />
        </Link>
        <button
          data-testid="sentinel-banner-dismiss"
          onClick={() => { sessionStorage.setItem("sentinel_banner_dismissed", key); setDismissedKey(key); }}
          className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
