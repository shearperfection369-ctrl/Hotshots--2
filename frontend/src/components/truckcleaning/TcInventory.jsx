import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Boxes, Plus, Minus, PackagePlus, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");

export const TcInventory = () => {
  const [items, setItems] = useState([]);
  const [meta, setMeta] = useState({ low_count: 0, retail_value: 0 });

  const load = useCallback(async () => {
    try { const { data } = await api.get("/truck-cleaning/inventory"); setItems(data.items); setMeta(data); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const adjust = async (id, delta) => {
    try { await api.post(`/truck-cleaning/inventory/${id}/adjust`, { delta }); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  const groups = [["bedding", "BEDDING & PILLOWS", "#FB7185"], ["freshener", "AIR FRESHENERS", "#22D3EE"]];

  return (
    <div className="space-y-4" data-testid="tc-inventory">
      <div className="grid grid-cols-3 gap-3">
        {[["Items tracked", items.length, "#F59E0B"], ["Low stock alerts", meta.low_count, meta.low_count ? "#F87171" : "#34D399"],
          ["Retail value on hand", `$${(meta.retail_value || 0).toLocaleString()}`, "#A78BFA"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-500 font-mono flex items-center gap-1.5"><Boxes size={12} className="text-amber-400" /> Stock auto-deducts when a job with these items is marked completed. "Committed" = reserved by scheduled jobs.</p>
      {groups.map(([cat, title, color]) => (
        <Card key={cat} className="p-4 bg-slate-950/70 border-white/10 backdrop-blur">
          <div className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color }}>{title}</div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.filter((i) => i.category === cat).map((i) => (
              <div key={i.item_id} data-testid={`tc-inv-${i.item_id}`}
                   className={`p-3.5 rounded-xl border bg-white/[0.02] ${i.low ? "border-red-500/50" : "border-white/10"}`}>
                <div className="flex justify-between items-start mb-1">
                  <div className="font-bold text-white text-sm leading-tight">{i.label}</div>
                  {i.low && <span className="shrink-0 inline-flex items-center gap-1 text-[8px] font-mono px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-300 border border-red-500/50"><AlertTriangle size={9} /> LOW</span>}
                </div>
                <div className="text-[10px] font-mono text-slate-500 mb-2">${i.unit_price} retail · {i.committed} committed · {i.available} available</div>
                <div className="flex items-center gap-2">
                  <button onClick={() => adjust(i.item_id, -1)} data-testid={`tc-inv-minus-${i.item_id}`}
                          className="h-8 w-8 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-red-400/60"><Minus size={13} /></button>
                  <span className="text-2xl font-black tabular-nums text-amber-300 min-w-[44px] text-center" data-testid={`tc-inv-stock-${i.item_id}`}>{i.stock}</span>
                  <button onClick={() => adjust(i.item_id, 1)} data-testid={`tc-inv-plus-${i.item_id}`}
                          className="h-8 w-8 grid place-items-center rounded-full border border-white/15 text-slate-300 hover:border-emerald-400/60"><Plus size={13} /></button>
                  <button onClick={() => adjust(i.item_id, 10)} data-testid={`tc-inv-restock-${i.item_id}`}
                          className="ml-auto px-3 h-8 rounded-full border border-emerald-500/50 text-emerald-400 text-[10px] font-bold inline-flex items-center gap-1"><PackagePlus size={12} /> +10</button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
};
