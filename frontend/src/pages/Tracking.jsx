import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import MapView from "../components/MapView";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Search, Container, RefreshCw } from "lucide-react";

export default function Tracking() {
  const [shipments, setShipments] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [selected, setSelected] = useState(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      const [s, f] = await Promise.all([api.get("/shipments"), api.get("/facilities")]);
      setShipments(s.data);
      setFacilities(f.data);
    })();
  }, []);

  const containerShipments = shipments.filter((s) => s.mode === "Ocean" && s.container_no);

  const filtered = shipments.filter((s) => {
    if (!q) return true;
    const ql = q.toLowerCase();
    return s.reference.toLowerCase().includes(ql) || (s.container_no || "").toLowerCase().includes(ql) || (s.bol_no || "").toLowerCase().includes(ql);
  });

  return (
    <>
      <Topbar title="Live Tracking" subtitle="Real-time positions · Ocean container search" />
      <div className="p-4 md:p-6 space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <Card className="hud-surface p-4 lg:col-span-8">
            <MapView shipments={filtered} facilities={facilities} height={560} showRoutes />
          </Card>

          <div className="lg:col-span-4 space-y-4">
            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3 flex items-center gap-2">
                <Container size={14} /> Container Search
              </div>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input
                  data-testid="container-search"
                  value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Container, BOL, or reference..."
                  className="pl-9 bg-[#0B0E14] border-white/10"
                />
              </div>
              <div className="mt-4 space-y-2 max-h-[480px] overflow-y-auto" data-testid="container-list">
                {containerShipments.map((s) => (
                  <button
                    key={s.shipment_id}
                    onClick={() => setSelected(s)}
                    className={`w-full text-left p-3 rounded-md border transition-all ${
                      selected?.shipment_id === s.shipment_id
                        ? "border-cyan-500/50 bg-cyan-500/10"
                        : "border-white/5 bg-white/[0.02] hover:border-cyan-500/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono text-xs text-cyan-300">{s.container_no}</div>
                      <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/30 text-[10px] font-mono">{s.status}</Badge>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">{s.origin.city} → {s.destination.city}</div>
                    <div className="mt-2 h-1 bg-white/5 rounded overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500" style={{ width: `${(s.progress || 0) * 100}%` }} />
                    </div>
                    <div className="flex justify-between mt-1 text-[10px] font-mono text-slate-500">
                      <span>{Math.round((s.progress || 0) * 100)}%</span>
                      <span>ETA {new Date(s.eta).toLocaleDateString()}</span>
                    </div>
                  </button>
                ))}
                {containerShipments.length === 0 && <div className="text-xs text-slate-500 text-center py-6">No ocean containers active</div>}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}
