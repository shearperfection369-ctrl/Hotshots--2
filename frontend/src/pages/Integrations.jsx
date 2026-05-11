import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { CheckCircle2, AlertTriangle, XCircle, ExternalLink } from "lucide-react";

const STATUS = {
  connected: { Icon: CheckCircle2, color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30", label: "CONNECTED" },
  warning: { Icon: AlertTriangle, color: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/30", label: "DEGRADED" },
  disconnected: { Icon: XCircle, color: "text-red-400", bg: "bg-red-500/10 border-red-500/30", label: "OFFLINE" },
};

export default function Integrations() {
  const [items, setItems] = useState([]);
  useEffect(() => { api.get("/integrations").then(({ data }) => setItems(data)); }, []);
  const grouped = items.reduce((acc, it) => { (acc[it.category] ||= []).push(it); return acc; }, {});

  return (
    <>
      <Topbar title="Integrations" subtitle="Enterprise systems · Carrier APIs · Productivity stack" />
      <div className="p-4 md:p-6 space-y-5">
        {Object.entries(grouped).map(([cat, list]) => (
          <Card key={cat} className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">{cat}</div>
            <h3 className="font-display text-lg font-bold mb-4">{cat} Integrations</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map((it) => {
                const s = STATUS[it.status] || STATUS.connected;
                return (
                  <div key={it.id} data-testid={`integration-${it.id}`} className="rounded-md border border-white/5 bg-white/[0.02] p-4 hover:border-cyan-500/30 transition-colors">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="font-display font-semibold text-white">{it.name}</div>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">{it.endpoint}</div>
                      </div>
                      <Badge className={`${s.bg} ${s.color} font-mono text-[10px] uppercase`}>{s.label}</Badge>
                    </div>
                    <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
                      <div className="flex items-center gap-1.5 text-xs">
                        <s.Icon size={13} className={s.color} />
                        <span className="font-mono text-slate-400">last sync {it.last_sync}</span>
                      </div>
                      <button className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
                        Configure <ExternalLink size={11} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
