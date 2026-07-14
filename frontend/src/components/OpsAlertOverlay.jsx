import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ShieldAlert, X, CheckCircle2, Radar, Loader2, Settings2, Siren, Mail, MessageSquare,
} from "lucide-react";

const SEV_STYLE = {
  critical: { ring: "#ef4444", text: "text-red-300", badge: "bg-red-500/15 border-red-500/50 text-red-300" },
  high: { ring: "#f97316", text: "text-orange-300", badge: "bg-orange-500/15 border-orange-500/50 text-orange-300" },
  medium: { ring: "#eab308", text: "text-yellow-300", badge: "bg-yellow-500/15 border-yellow-500/50 text-yellow-300" },
  low: { ring: "#38bdf8", text: "text-sky-300", badge: "bg-sky-500/15 border-sky-500/50 text-sky-300" },
};
const POPUP_SEV = ["critical", "high"];
const SEEN_KEY = "sentinel_seen_alerts";

const css = `
@keyframes sentinelPing { 0% { transform: scale(0.6); opacity: 0.9; } 100% { transform: scale(2.4); opacity: 0; } }
@keyframes sentinelScan { 0% { top: -8%; } 100% { top: 108%; } }
@keyframes sentinelGlow { 0%,100% { box-shadow: 0 0 30px -6px var(--sv), inset 0 0 24px -14px var(--sv); } 50% { box-shadow: 0 0 70px -6px var(--sv), inset 0 0 40px -14px var(--sv); } }
@keyframes sentinelIn { from { opacity: 0; transform: scale(0.92) translateY(14px); } to { opacity: 1; transform: scale(1) translateY(0); } }
@keyframes sentinelPulseDot { 0%,100% { opacity: 1; } 50% { opacity: 0.25; } }
`;

function getSeen() {
  try { return new Set(JSON.parse(sessionStorage.getItem(SEEN_KEY) || "[]")); } catch { return new Set(); }
}
function addSeen(ids) {
  const s = getSeen(); ids.forEach((i) => s.add(i));
  try { sessionStorage.setItem(SEEN_KEY, JSON.stringify([...s].slice(-300))); } catch {}
}

function AlertPopup({ alerts, onAck, onResolve, onDismiss, busy }) {
  const a = alerts[0];
  const sev = SEV_STYLE[a.severity] || SEV_STYLE.high;
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4" data-testid="sentinel-popup"
      style={{ background: "radial-gradient(ellipse at center, rgba(239,68,68,0.10), rgba(3,7,15,0.88) 65%)", backdropFilter: "blur(10px)" }}>
      <div className="relative w-full max-w-2xl rounded-2xl border overflow-hidden"
        style={{ "--sv": sev.ring, borderColor: `${sev.ring}66`, background: "linear-gradient(160deg, #0a1220 0%, #060b14 100%)", animation: "sentinelIn 0.35s cubic-bezier(0.2,0.9,0.3,1.2), sentinelGlow 2.4s ease-in-out infinite" }}>
        <div className="absolute left-0 right-0 h-px pointer-events-none" style={{ background: `linear-gradient(90deg, transparent, ${sev.ring}, transparent)`, animation: "sentinelScan 3s linear infinite" }} />
        <div className="p-7">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="relative w-14 h-14 flex items-center justify-center shrink-0">
                {[0, 0.6, 1.2].map((d) => (
                  <span key={d} className="absolute inset-0 rounded-full border-2" style={{ borderColor: sev.ring, animation: `sentinelPing 1.8s ${d}s ease-out infinite` }} />
                ))}
                <Siren size={26} style={{ color: sev.ring }} />
              </div>
              <div>
                <div className="text-[9px] font-mono uppercase tracking-[0.35em] text-slate-500 flex items-center gap-2">
                  <Radar size={10} className="text-cyan-400" /> Orisei AI Load Sentinel
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" style={{ animation: "sentinelPulseDot 1s infinite" }} />
                  LIVE
                </div>
                <div className={`text-[10px] font-mono uppercase tracking-widest mt-1 inline-block border rounded px-2 py-0.5 ${sev.badge}`} data-testid="sentinel-severity">
                  {a.severity} · {String(a.type).replaceAll("_", " ")}
                </div>
              </div>
            </div>
            <button onClick={onDismiss} className="text-slate-500 hover:text-slate-200" data-testid="sentinel-dismiss-btn"><X size={18} /></button>
          </div>

          <h2 className="font-display text-2xl font-black mt-5 text-slate-100" data-testid="sentinel-title">{a.title}</h2>
          <div className="text-[11px] font-mono text-slate-400 mt-1">{a.detail}</div>

          <div className="mt-4 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.05] p-4">
            <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-cyan-300 mb-1.5">AI Action Brief</div>
            <div className="text-[13px] text-slate-200 leading-relaxed" data-testid="sentinel-ai-brief">{a.ai_brief || a.detail}</div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 mt-5">
            <div className="text-[9px] font-mono text-slate-500 flex items-center gap-3">
              <span className="flex items-center gap-1"><Mail size={10} /> {a.notified_email ? a.notified_email.replaceAll("_", " ") : "email off"}</span>
              <span className="flex items-center gap-1"><MessageSquare size={10} /> {a.notified_sms ? a.notified_sms.replaceAll("_", " ") : "sms off"}</span>
              <span>{new Date(a.detected_at).toLocaleTimeString()}</span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => onAck(a)} disabled={busy} data-testid="sentinel-ack-btn"
                className="bg-white/5 border border-white/15 text-slate-200 font-mono text-[10px] uppercase">
                {busy ? <Loader2 size={12} className="animate-spin" /> : "Acknowledge"}
              </Button>
              <Button size="sm" onClick={() => onResolve(a)} disabled={busy} data-testid="sentinel-resolve-btn"
                className="bg-emerald-500 text-black font-bold font-mono text-[10px] uppercase">
                <CheckCircle2 size={12} className="mr-1" /> Resolved
              </Button>
            </div>
          </div>
          {alerts.length > 1 && (
            <div className="text-[10px] font-mono text-orange-300 mt-3" data-testid="sentinel-more-count">
              +{alerts.length - 1} more alert{alerts.length > 2 ? "s" : ""} behind this one
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SentinelPanel({ open, onClose, alerts, onAck, onResolve, refresh }) {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  useEffect(() => {
    if (open) api.get("/alerts/settings").then(({ data }) => setSettings(data)).catch(() => {});
  }, [open]);
  if (!open) return null;
  const save = async () => {
    setSaving(true);
    try { await api.post("/alerts/settings", settings); toast.success("Sentinel settings saved"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setSaving(false); }
  };
  const fireTest = async () => {
    setTesting(true);
    try { await api.post("/alerts/test"); toast.success("🚨 Test alert fired"); refresh(); }
    catch { toast.error("Test failed"); }
    finally { setTesting(false); }
  };
  return (
    <div className="fixed bottom-20 right-5 z-[9998] w-[380px] rounded-xl border border-white/15 bg-[#080e1a]/95 backdrop-blur-xl p-4 shadow-2xl" data-testid="sentinel-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-300 flex items-center gap-1.5">
          <Radar size={12} /> Load Sentinel
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fireTest} disabled={testing} className="text-[9px] font-mono uppercase text-orange-300 border border-orange-500/30 rounded px-2 py-0.5 hover:bg-orange-500/10" data-testid="sentinel-test-btn">
            {testing ? "firing…" : "Test Alert"}
          </button>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200"><X size={15} /></button>
        </div>
      </div>
      <div className="space-y-1.5 max-h-52 overflow-y-auto mb-3" data-testid="sentinel-alert-list">
        {alerts.length === 0 && (
          <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1.5 py-3">
            <CheckCircle2 size={11} className="text-emerald-400" /> All clear — Sentinel is watching your loads.
          </div>
        )}
        {alerts.map((a) => {
          const sev = SEV_STYLE[a.severity] || SEV_STYLE.low;
          return (
            <div key={a.alert_id} className="p-2 rounded border border-white/10 bg-white/[0.02]">
              <div className="flex justify-between gap-2">
                <span className={`text-[10px] font-mono ${sev.text}`}>{a.title}</span>
                <div className="flex gap-1 shrink-0">
                  {a.status === "open" && <button onClick={() => onAck(a)} title="Acknowledge" className="text-slate-500 hover:text-slate-200 text-[9px] font-mono uppercase border border-white/10 rounded px-1">ack</button>}
                  <button onClick={() => onResolve(a)} title="Resolve" className="text-emerald-400 hover:text-emerald-300"><CheckCircle2 size={12} /></button>
                </div>
              </div>
              <div className="text-[9px] font-mono text-slate-500 mt-0.5 line-clamp-2">{a.ai_brief || a.detail}</div>
            </div>
          );
        })}
      </div>
      {settings && (
        <div className="border-t border-white/10 pt-3 space-y-2" data-testid="sentinel-settings">
          <div className="text-[9px] font-mono uppercase tracking-[0.2em] text-slate-500 flex items-center gap-1"><Settings2 size={10} /> Notify Me</div>
          <input value={settings.email} onChange={(e) => setSettings({ ...settings, email: e.target.value })}
            placeholder="Alert email" data-testid="sentinel-email-input"
            className="w-full h-8 rounded bg-slate-950 border border-white/10 font-mono text-[10px] px-2 text-slate-200 placeholder:text-slate-600" />
          <input value={settings.phone} onChange={(e) => setSettings({ ...settings, phone: e.target.value })}
            placeholder="SMS phone (+1…)" data-testid="sentinel-phone-input"
            className="w-full h-8 rounded bg-slate-950 border border-white/10 font-mono text-[10px] px-2 text-slate-200 placeholder:text-slate-600" />
          <div className="flex items-center justify-between">
            <div className="flex gap-3 text-[9px] font-mono text-slate-400">
              <label className="flex items-center gap-1"><input type="checkbox" checked={settings.email_enabled} onChange={(e) => setSettings({ ...settings, email_enabled: e.target.checked })} /> Email</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={settings.sms_enabled} onChange={(e) => setSettings({ ...settings, sms_enabled: e.target.checked })} /> SMS</label>
              <select value={settings.min_severity} onChange={(e) => setSettings({ ...settings, min_severity: e.target.value })}
                className="bg-slate-950 border border-white/10 rounded text-[9px] px-1">
                {["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <Button size="sm" onClick={save} disabled={saving} data-testid="sentinel-save-settings-btn"
              className="h-7 bg-cyan-500 text-black font-bold font-mono text-[9px] uppercase">
              {saving ? <Loader2 size={10} className="animate-spin" /> : "Save"}
            </Button>
          </div>
          <div className="text-[8px] font-mono text-slate-600">Email sends via Resend · SMS via Twilio — both queue automatically until keys are connected.</div>
        </div>
      )}
    </div>
  );
}

export default function OpsAlertOverlay() {
  const [openAlerts, setOpenAlerts] = useState([]);
  const [popupAlerts, setPopupAlerts] = useState([]);
  const [panelOpen, setPanelOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const timerRef = useRef(null);

  const scan = useCallback(async () => {
    try {
      const { data } = await api.post("/alerts/scan");
      const open = data.open_alerts || [];
      setOpenAlerts(open);
      const seen = getSeen();
      const fresh = open.filter((a) => POPUP_SEV.includes(a.severity) && a.status === "open" && !seen.has(a.alert_id));
      if (fresh.length) setPopupAlerts(fresh);
    } catch {}
  }, []);

  useEffect(() => {
    scan();
    timerRef.current = setInterval(scan, 60000);
    return () => clearInterval(timerRef.current);
  }, [scan]);

  const dismissPopup = () => { addSeen(popupAlerts.map((a) => a.alert_id)); setPopupAlerts([]); };
  const act = async (a, action) => {
    setBusy(true);
    try {
      await api.post(`/alerts/${a.alert_id}/${action}`);
      addSeen([a.alert_id]);
      setPopupAlerts((prev) => prev.filter((x) => x.alert_id !== a.alert_id));
      toast.success(action === "ack" ? "Acknowledged" : "Resolved");
      scan();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const activeCount = openAlerts.filter((a) => a.status === "open").length;
  return (
    <>
      <style>{css}</style>
      {popupAlerts.length > 0 && (
        <AlertPopup alerts={popupAlerts} busy={busy} onDismiss={dismissPopup}
          onAck={(a) => act(a, "ack")} onResolve={(a) => act(a, "resolve")} />
      )}
      <button onClick={() => setPanelOpen((v) => !v)} data-testid="sentinel-fab"
        className={`fixed bottom-5 right-5 z-[9998] flex items-center gap-2 rounded-full border px-4 py-2.5 font-mono text-[10px] uppercase tracking-widest backdrop-blur-md transition-colors ${
          activeCount ? "border-red-500/50 bg-red-500/10 text-red-300" : "border-white/15 bg-white/[0.04] text-slate-400 hover:text-slate-200"}`}>
        <ShieldAlert size={14} className={activeCount ? "animate-pulse" : ""} />
        Sentinel {activeCount > 0 && <span className="font-black" data-testid="sentinel-count">{activeCount}</span>}
      </button>
      <SentinelPanel open={panelOpen} onClose={() => setPanelOpen(false)} alerts={openAlerts}
        onAck={(a) => act(a, "ack")} onResolve={(a) => act(a, "resolve")} refresh={scan} />
    </>
  );
}
