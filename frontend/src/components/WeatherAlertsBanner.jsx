import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { AlertTriangle, X, ExternalLink } from "lucide-react";

/**
 * WeatherAlertsBanner · polls /api/weather/alerts every 60 seconds and
 * surfaces NWS-style warnings/watches at the very top of the page.
 *
 * Banner is sticky-top, severity-colored, dismissible per alert_id (sessionStorage
 * so the dismissal survives page navigation but resets on a new session).
 */

const DISMISS_KEY = "tms-weather-alerts-dismissed";
const POLL_MS = 60 * 1000;

const SEVERITY = {
  high: { bg: "from-red-500/30 to-red-900/10", border: "border-red-500/40", icon: "text-red-300", label: "bg-red-500/20 text-red-200 border-red-500/40" },
  moderate: { bg: "from-yellow-500/25 to-yellow-900/5", border: "border-yellow-500/40", icon: "text-yellow-300", label: "bg-yellow-500/20 text-yellow-200 border-yellow-500/40" },
  low: { bg: "from-cyan-500/15 to-cyan-900/0", border: "border-cyan-500/30", icon: "text-cyan-300", label: "bg-cyan-500/15 text-cyan-200 border-cyan-500/30" },
};

const getDismissed = () => {
  try { return new Set(JSON.parse(sessionStorage.getItem(DISMISS_KEY) || "[]")); }
  catch { return new Set(); }
};
const setDismissed = (set) => {
  try { sessionStorage.setItem(DISMISS_KEY, JSON.stringify([...set])); }
  catch {}
};

export default function WeatherAlertsBanner() {
  const [alerts, setAlerts] = useState([]);
  const [dismissedTick, setDismissedTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await api.get("/weather/alerts");
        if (!cancelled) setAlerts(data || []);
      } catch {}
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const dismissed = getDismissed();
  const visible = alerts.filter((a) => !dismissed.has(a.alert_id));
  if (visible.length === 0) return null;

  // Show highest-severity first, max 2 stacked
  const sevRank = { high: 0, moderate: 1, low: 2 };
  const sorted = [...visible].sort((a, b) =>
    (sevRank[a.severity] || 9) - (sevRank[b.severity] || 9)
  ).slice(0, 2);

  const dismiss = (id) => {
    const d = getDismissed();
    d.add(id);
    setDismissed(d);
    setDismissedTick((t) => t + 1);
  };

  return (
    <div className="px-4 md:px-6 pt-3 space-y-2" data-testid="weather-alerts-banner">
      {sorted.map((a) => {
        const sev = SEVERITY[a.severity] || SEVERITY.low;
        return (
          <Card
            key={a.alert_id}
            data-testid={`weather-alert-${a.alert_id}`}
            className={`p-3 bg-gradient-to-r ${sev.bg} ${sev.border} border relative`}
          >
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className={`${sev.icon} mt-0.5 shrink-0`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border ${sev.label}`}>
                    {a.type}
                  </span>
                  <span className="text-[10px] font-mono text-slate-300 uppercase tracking-wider">
                    {a.area}
                  </span>
                  {a.affected_facility && (
                    <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-wider">
                      Affects · {a.affected_facility}
                    </span>
                  )}
                </div>
                <div className="text-sm font-bold text-white mt-1">{a.headline}</div>
                <div className="text-xs text-slate-300 mt-1 leading-relaxed">{a.body}</div>
                <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-slate-400">
                  <span>Issued {new Date(a.issued_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
                  <span>· Expires {new Date(a.expires_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
                  {a.source_url && (
                    <a href={a.source_url} target="_blank" rel="noreferrer"
                       className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200">
                      {a.source} <ExternalLink size={9} />
                    </a>
                  )}
                </div>
              </div>
              <button
                onClick={() => dismiss(a.alert_id)}
                data-testid={`weather-alert-dismiss-${a.alert_id}`}
                aria-label="Dismiss alert"
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 shrink-0"
              >
                <X size={14} />
              </button>
            </div>
          </Card>
        );
      })}
      <span className="hidden" data-testid="weather-alerts-count">{sorted.length}</span>
      <span className="hidden" data-tick={dismissedTick} />
    </div>
  );
}
