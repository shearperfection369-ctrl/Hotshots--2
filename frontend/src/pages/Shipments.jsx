import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Truck, Plane, Ship, Package, Train, Search } from "lucide-react";

const MODE_ICON = { TL: Truck, LTL: Truck, Parcel: Package, Ocean: Ship, Air: Plane, Rail: Train };
const STATUS_BADGE = {
  in_transit: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  delayed: "bg-red-500/10 text-red-400 border-red-500/30",
  delivered: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  at_origin: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
};

export default function Shipments() {
  const [shipments, setShipments] = useState([]);
  const [carrier, setCarrier] = useState("ALL");
  const [mode, setMode] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      const { data } = await api.get("/shipments");
      setShipments(data);
    })();
  }, []);

  const carriers = useMemo(() => {
    const set = new Set(shipments.map((s) => s.carrier));
    return ["ALL", ...Array.from(set).sort()];
  }, [shipments]);

  const filtered = shipments.filter((s) => {
    if (carrier !== "ALL" && s.carrier !== carrier) return false;
    if (mode !== "ALL" && s.mode !== mode) return false;
    if (status !== "ALL" && s.status !== status) return false;
    if (q) {
      const ql = q.toLowerCase();
      if (!s.reference.toLowerCase().includes(ql) &&
          !s.shipment_id.toLowerCase().includes(ql) &&
          !s.commodity.toLowerCase().includes(ql) &&
          !s.destination.city.toLowerCase().includes(ql)) return false;
    }
    return true;
  });

  const carrierCount = (c) =>
    c === "ALL" ? shipments.length : shipments.filter((s) => s.carrier === c).length;

  return (
    <>
      <Topbar title="Shipments" subtitle={`${filtered.length} of ${shipments.length} shipments`} />
      <div className="p-4 md:p-6 space-y-4">

        {/* Carrier quick-toggle (horizontal scroll pills) */}
        <Card className="hud-surface p-3" data-testid="carrier-toggle">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 px-1">Carrier Toggle</div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {carriers.map((c) => (
              <button
                key={c}
                onClick={() => setCarrier(c)}
                data-testid={`carrier-pill-${c}`}
                className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all border ${
                  carrier === c
                    ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan"
                    : "bg-white/[0.02] text-slate-400 border-white/5 hover:border-cyan-500/40 hover:text-cyan-300"
                }`}
              >
                {c} <span className="opacity-70 ml-1">({carrierCount(c)})</span>
              </button>
            ))}
          </div>
        </Card>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-5 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="shipment-search"
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search reference, commodity, destination..."
              className="pl-9 bg-[#131821] border-white/10 text-white focus:border-cyan-500"
            />
          </div>
          <div className="md:col-span-3 flex gap-1 overflow-x-auto">
            {["ALL", "TL", "LTL", "Parcel", "Ocean", "Air", "Rail"].map((m) => (
              <button
                key={m}
                data-testid={`mode-filter-${m}`}
                onClick={() => setMode(m)}
                className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase border ${
                  mode === m ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/5 text-slate-400 hover:text-white"
                }`}
              >{m}</button>
            ))}
          </div>
          <div className="md:col-span-4 flex gap-1 overflow-x-auto">
            {["ALL", "in_transit", "delayed", "delivered", "pending"].map((st) => (
              <button
                key={st}
                data-testid={`status-filter-${st}`}
                onClick={() => setStatus(st)}
                className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase border ${
                  status === st ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/5 text-slate-400 hover:text-white"
                }`}
              >{st}</button>
            ))}
          </div>
        </div>

        {/* Table */}
        <Card className="hud-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Ref · ID</th>
                  <th className="text-left py-3 px-4">Mode</th>
                  <th className="text-left py-3 px-4">Carrier</th>
                  <th className="text-left py-3 px-4">Origin</th>
                  <th className="text-left py-3 px-4">Destination</th>
                  <th className="text-left py-3 px-4">Commodity</th>
                  <th className="text-right py-3 px-4">Weight (lbs)</th>
                  <th className="text-right py-3 px-4">Value</th>
                  <th className="text-left py-3 px-4">Status</th>
                  <th className="text-right py-3 px-4">ETA</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {filtered.map((s) => {
                  const Icon = MODE_ICON[s.mode] || Package;
                  return (
                    <tr key={s.shipment_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`shipment-row-${s.shipment_id}`}>
                      <td className="py-2.5 px-4">
                        <div className="text-cyan-300">{s.reference}</div>
                        <div className="text-[10px] text-slate-500">{s.shipment_id}</div>
                      </td>
                      <td className="py-2.5 px-4"><span className="inline-flex items-center gap-1.5 text-slate-300"><Icon size={13} />{s.mode}</span></td>
                      <td className="py-2.5 px-4 text-slate-300">{s.carrier}</td>
                      <td className="py-2.5 px-4 text-slate-400">{s.origin.city}</td>
                      <td className="py-2.5 px-4 text-slate-400">{s.destination.city}</td>
                      <td className="py-2.5 px-4 text-slate-400 truncate max-w-[180px]">{s.commodity}</td>
                      <td className="py-2.5 px-4 text-right text-slate-300">{Number(s.weight_lbs).toLocaleString()}</td>
                      <td className="py-2.5 px-4 text-right text-emerald-400">${Number(s.value_usd).toLocaleString()}</td>
                      <td className="py-2.5 px-4"><Badge className={`${STATUS_BADGE[s.status]} font-mono text-[10px] uppercase`}>{s.status}</Badge></td>
                      <td className="py-2.5 px-4 text-right text-slate-400 text-xs">{new Date(s.eta).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr><td colSpan={10} className="text-center py-12 text-slate-500">No shipments match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
