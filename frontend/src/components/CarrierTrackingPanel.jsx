import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Search, ExternalLink, Truck } from "lucide-react";

/**
 * CarrierTrackingPanel · sits on the Live Tracking page and lets dispatchers
 * jump straight into any carrier's public tracking page from inside the TMS.
 *
 *   1. Pick or type a carrier (datalist autocomplete from /api/carriers/tracking-urls)
 *   2. Type a tracking / PRO / container / waybill number
 *   3. Click → opens the carrier's tracking page in a new tab
 */
export default function CarrierTrackingPanel() {
  const [carriers, setCarriers] = useState({});
  const [carrier, setCarrier] = useState("");
  const [tracking, setTracking] = useState("");
  const [recent, setRecent] = useState([]);

  useEffect(() => {
    api.get("/carriers/tracking-urls").then((r) => setCarriers(r.data.carriers || {})).catch(() => {});
    try {
      setRecent(JSON.parse(localStorage.getItem("tms-recent-tracking") || "[]"));
    } catch {}
  }, []);

  const carrierEntries = Object.entries(carriers); // [carrierKey, {url,label}]

  const go = (carrierKey, num) => {
    const tmpl = carriers[carrierKey];
    if (!tmpl) return;
    const url = tmpl.url.replace("{tracking}", encodeURIComponent(num));
    const entry = { carrier: carrierKey, label: tmpl.label, tracking: num, url, at: Date.now() };
    const next = [entry, ...recent.filter((r) => r.tracking !== num || r.carrier !== carrierKey)].slice(0, 8);
    setRecent(next);
    try { localStorage.setItem("tms-recent-tracking", JSON.stringify(next)); } catch {}
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const submit = (e) => {
    e?.preventDefault?.();
    if (!carrier || !tracking.trim()) return;
    // Match on case-insensitive carrier name
    const key = Object.keys(carriers).find((k) => k.toLowerCase() === carrier.trim().toLowerCase())
      || Object.keys(carriers).find((k) => k.toLowerCase().includes(carrier.trim().toLowerCase()));
    if (key) go(key, tracking.trim());
  };

  return (
    <Card className="hud-surface p-4" data-testid="carrier-tracking-panel">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3 flex items-center gap-2">
        <Truck size={11} /> Direct Carrier Tracking — {carrierEntries.length} carriers
      </div>
      <form onSubmit={submit} className="space-y-2">
        <div>
          <label className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Carrier</label>
          <input
            list="carrier-tracking-options"
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
            placeholder="UPS · FedEx · ODFL · Maersk…"
            data-testid="carrier-tracking-carrier"
            className="w-full mt-0.5 bg-[#11151F] border border-white/10 rounded px-2 py-1.5 text-xs font-mono text-white outline-none focus:border-cyan-500/50"
          />
          <datalist id="carrier-tracking-options">
            {carrierEntries.map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </datalist>
        </div>
        <div>
          <label className="text-[9px] font-mono uppercase tracking-wider text-slate-500">Tracking / PRO / Container / Waybill #</label>
          <div className="flex gap-1.5 mt-0.5">
            <Input
              value={tracking}
              onChange={(e) => setTracking(e.target.value)}
              placeholder="1Z999AA10123456784"
              data-testid="carrier-tracking-number"
              className="flex-1 bg-[#11151F] border-white/10 font-mono text-xs"
            />
            <Button
              type="submit"
              data-testid="carrier-tracking-submit"
              disabled={!carrier || !tracking}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
            >
              Track →
            </Button>
          </div>
        </div>
      </form>

      {recent.length > 0 && (
        <div className="mt-4 pt-3 border-t border-white/5" data-testid="recent-tracking">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5">Recent lookups</div>
          <div className="space-y-1">
            {recent.map((r, i) => (
              <a
                key={i}
                href={r.url}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-cyan-500/[0.06] text-[10px] font-mono"
              >
                <span className="px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">{r.carrier}</span>
                <span className="text-slate-200 truncate flex-1">{r.tracking}</span>
                <ExternalLink size={9} className="text-slate-500" />
              </a>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
