import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Truck, Smartphone, QrCode, Copy } from "lucide-react";
import { toast } from "sonner";

export default function DriverConsole() {
  const [checkins, setCheckins] = useState([]);
  const [shipments, setShipments] = useState([]);

  useEffect(() => {
    Promise.all([api.get("/driver/checkins"), api.get("/shipments?status=in_transit")])
      .then(([c, s]) => { setCheckins(c.data); setShipments(s.data); });
    const t = setInterval(() => api.get("/driver/checkins").then(({ data }) => setCheckins(data)), 10000);
    return () => clearInterval(t);
  }, []);

  const copyLink = (sid) => {
    const url = `${window.location.origin}/driver/${sid}`;
    navigator.clipboard.writeText(url);
    toast.success("Driver link copied", { description: url });
  };

  return (
    <>
      <Topbar title="Driver Console" subtitle="Mobile check-ins · share driver links" />
      <div className="p-4 md:p-6 space-y-5">
        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Mobile Hand-off</div>
          <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2"><Smartphone size={18} className="text-cyan-400" /> Share Driver Links</h3>
          <p className="text-sm text-slate-400 mb-4">Send drivers a deep-link to a load. The mobile page captures GPS, fuel %, odometer, and status — no login required.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="driver-link-grid">
            {shipments.slice(0, 12).map((s) => (
              <div key={s.shipment_id} className="p-4 rounded-md border border-white/5 bg-white/[0.02]">
                <div className="flex items-center justify-between">
                  <Truck size={14} className="text-cyan-400" />
                  <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/30 text-[10px] font-mono">{s.mode}</Badge>
                </div>
                <div className="mt-2 text-sm text-white">{s.reference}</div>
                <div className="text-[10px] font-mono text-slate-500">{s.shipment_id}</div>
                <div className="text-xs text-slate-400 mt-1">{s.origin.city} → {s.destination.city}</div>
                <button
                  onClick={() => copyLink(s.shipment_id)}
                  data-testid={`copy-link-${s.shipment_id}`}
                  className="mt-3 w-full flex items-center justify-center gap-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 border border-cyan-500/30 hover:border-cyan-500/60 rounded py-2 transition-all"
                >
                  <Copy size={12} /> COPY MOBILE LINK
                </button>
              </div>
            ))}
          </div>
        </Card>

        <Card className="hud-surface overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Live Stream</div>
            <h3 className="font-display text-lg font-bold">Driver Check-Ins (auto-refresh)</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">Time</th>
                <th className="text-left py-3 px-4">Driver</th>
                <th className="text-left py-3 px-4">Shipment</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-left py-3 px-4">Location</th>
                <th className="text-right py-3 px-4">Fuel</th>
                <th className="text-right py-3 px-4">Odo</th>
                <th className="text-left py-3 px-4">Note</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {checkins.map((c) => (
                <tr key={c.checkin_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="py-2.5 px-4 text-slate-400 text-xs">{new Date(c.created_at).toLocaleString()}</td>
                  <td className="py-2.5 px-4 text-slate-300">{c.driver_name}<br/><span className="text-[10px] text-slate-500">{c.driver_phone}</span></td>
                  <td className="py-2.5 px-4 text-cyan-300">{c.shipment_id}</td>
                  <td className="py-2.5 px-4"><Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/30 font-mono text-[10px] uppercase">{c.status.replace("_", " ")}</Badge></td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">
                    {c.lat ? `${c.lat.toFixed(3)}, ${c.lng.toFixed(3)}` : "—"}
                    {c.location_text && <div className="text-slate-500">{c.location_text}</div>}
                  </td>
                  <td className="py-2.5 px-4 text-right text-yellow-400">{c.fuel_pct != null ? `${c.fuel_pct}%` : "—"}</td>
                  <td className="py-2.5 px-4 text-right text-slate-400">{c.odometer != null ? Math.round(c.odometer).toLocaleString() : "—"}</td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs italic max-w-xs truncate">{c.note || ""}</td>
                </tr>
              ))}
              {checkins.length === 0 && <tr><td colSpan={8} className="text-center py-10 text-slate-500">No check-ins yet. Share a driver link above to get started.</td></tr>}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
