import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AlertTriangle, X, Trash2, ShieldCheck, Sparkles } from "lucide-react";
import { toast } from "sonner";

/**
 * DataStatusBanner — slim sticky banner that surfaces whether the TMS is
 * currently full of sample data, mixed, or fully live, so the operator
 * always knows what they're looking at. Admin can wipe sample rows from
 * here in one click.
 *
 * Pulls /api/data-status (counts per collection). Hides itself in `live`
 * mode (no sample rows present) or when the operator dismisses it.
 */
const STORAGE_KEY = "tms_sample_banner_dismissed_at";

export default function DataStatusBanner() {
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);

  const fetchStatus = async () => {
    try {
      const { data } = await api.get("/data-status");
      setStatus(data);
    } catch {
      // silent — user might not be authed yet
    }
  };

  useEffect(() => {
    // dismissal is per-session
    if (sessionStorage.getItem(STORAGE_KEY)) setDismissed(true);
    fetchStatus();
    const t = setInterval(fetchStatus, 30000);
    return () => clearInterval(t);
  }, []);

  if (!status || dismissed) return null;
  if (status.mode === "live" || status.mode === "empty") return null;

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, String(Date.now()));
    setDismissed(true);
  };

  const wipeSample = async () => {
    if (!window.confirm(
      `This will permanently delete ${status.total_sample.toLocaleString()} sample rows across ${status.collections.length} collections. ` +
      `Your real loads (booked via Book Load) will be kept. Continue?`
    )) return;
    setBusy(true);
    try {
      const r = await api.post("/admin/clear-sample-data?confirm=true");
      const deleted = (r.data?.collections || []).reduce((s, c) => s + (c.deleted || 0), 0);
      toast.success(`Wiped ${deleted.toLocaleString()} sample rows. App is now live.`);
      await fetchStatus();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to wipe sample data");
    } finally { setBusy(false); }
  };

  const MODE_COPY = {
    sample_only:   { color: "amber",  label: "SAMPLE MODE",   note: "100% of records are sample / demo data." },
    sample_heavy:  { color: "amber",  label: "MOSTLY SAMPLE", note: "Most records are sample / demo data." },
    mostly_live:   { color: "emerald", label: "MOSTLY LIVE",  note: "Real records exceed sample records." },
  };
  const m = MODE_COPY[status.mode] || MODE_COPY.sample_heavy;

  return (
    <div data-testid="data-status-banner"
         className={`sticky top-0 z-40 border-b backdrop-blur-xl ${
           m.color === "amber"
             ? "bg-amber-950/40 border-amber-400/40"
             : "bg-emerald-950/40 border-emerald-400/40"
         }`}>
      <div className="px-4 md:px-6 py-2 flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          {m.color === "amber"
            ? <AlertTriangle className="text-amber-300 shrink-0" size={14} />
            : <ShieldCheck className="text-emerald-300 shrink-0" size={14} />}
          <span className={`font-mono uppercase tracking-widest shrink-0 ${
            m.color === "amber" ? "text-amber-200" : "text-emerald-200"
          }`}>{m.label}</span>
          <span className="text-slate-300 truncate">
            {m.note} <span className="text-slate-400">
              · {status.total_sample.toLocaleString()} sample / {status.total_real.toLocaleString()} real
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            data-testid="banner-wipe-sample"
            onClick={wipeSample}
            disabled={busy}
            title="Permanently delete every is_sample=true row. Real records (Book Load) are kept."
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-mono uppercase tracking-widest border border-red-400/40 text-red-200 hover:bg-red-500/20 transition disabled:opacity-50"
          >
            <Trash2 size={11} /> Wipe Sample
          </button>
          <a href="/launch-plan"
             className={`hidden md:inline-flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-mono uppercase tracking-widest border ${
               m.color === "amber"
                 ? "border-amber-400/40 text-amber-200 hover:bg-amber-500/20"
                 : "border-emerald-400/40 text-emerald-200 hover:bg-emerald-500/20"
             } transition`}>
            <Sparkles size={11} /> Go Live · Launch Runway
          </a>
          <button
            type="button"
            data-testid="banner-dismiss"
            onClick={dismiss}
            className="text-slate-400 hover:text-white"
          >
            <X size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
