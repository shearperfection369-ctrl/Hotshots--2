import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Search, Cpu, Battery, Gauge, Ruler, Weight, DollarSign, Sparkles } from "lucide-react";

export default function Machines() {
  const [machines, setMachines] = useState([]);
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("ALL");
  const [q, setQ] = useState("");
  const [active, setActive] = useState(null);

  useEffect(() => {
    api.get("/machines").then(({ data }) => {
      setMachines(data.machines);
      setCategories(data.categories);
    });
  }, []);

  const filtered = useMemo(() => machines.filter((m) => {
    if (category !== "ALL" && m.category !== category) return false;
    if (q) {
      const ql = q.toLowerCase();
      const hay = [m.model, m.category, m.type, m.power, m.use_case, (m.highlights || []).join(" ")].join(" ").toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  }), [machines, category, q]);

  return (
    <>
      <Topbar title="Tennant Machine Catalog" subtitle={`${machines.length} models · scrubbers · sweepers · burnishers · AMRs`} />
      <div className="p-4 md:p-6 space-y-4">
        <Card className="hud-surface p-3 flex flex-wrap items-center gap-2">
          <button onClick={() => setCategory("ALL")} data-testid="cat-ALL"
            className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${category === "ALL" ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>
            All ({machines.length})
          </button>
          {categories.map((c) => (
            <button key={c} onClick={() => setCategory(c)} data-testid={`cat-${c.replace(/\s+/g, '-')}`}
              className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${category === c ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>
              {c} ({machines.filter((m) => m.category === c).length})
            </button>
          ))}
          <div className="ml-auto relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search model, use case..." className="pl-9 w-72 bg-[#131821] border-white/10" data-testid="machine-search" />
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((m) => (
            <button key={m.model} onClick={() => setActive(m)} data-testid={`machine-card-${m.model}`}
              className="hud-surface text-left rounded-lg overflow-hidden border border-white/5 hover:border-cyan-500/40 hover:shadow-[0_0_20px_rgba(0,229,255,0.15)] transition-all bg-[#131821]">
              <div className="aspect-[4/3] bg-gradient-to-br from-cyan-500/5 to-slate-900 relative overflow-hidden">
                <img src={m.image_url} alt={m.model} className="w-full h-full object-cover" loading="lazy"
                  onError={(e) => { e.target.style.display = 'none'; e.target.parentElement.classList.add('bg-machine-fallback'); }} />
                <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm border border-cyan-500/30 text-[9px] font-mono uppercase tracking-wider text-cyan-300">{m.category}</div>
                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-emerald-500/15 backdrop-blur-sm border border-emerald-500/30 text-[10px] font-mono text-emerald-300">{m.size}</div>
              </div>
              <div className="p-3">
                <div className="font-display text-lg font-bold text-white">{m.model}</div>
                <div className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">{m.use_case}</div>
                <div className="grid grid-cols-2 gap-1 mt-2 text-[10px] font-mono">
                  <div className="text-cyan-300 flex items-center gap-1"><Battery size={9} /> {m.power}</div>
                  <div className="text-emerald-400 flex items-center gap-1"><Gauge size={9} /> {m.runtime}</div>
                </div>
              </div>
            </button>
          ))}
          {filtered.length === 0 && <Card className="hud-surface p-8 text-center text-slate-500 md:col-span-4">No machines match.</Card>}
        </div>
      </div>

      {/* Detail modal */}
      {active && <MachineDetail m={active} onClose={() => setActive(null)} />}
    </>
  );
}

function MachineDetail({ m, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose} data-testid="machine-detail">
      <div className="hud-surface bg-[#131821] border border-cyan-500/30 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="aspect-[16/9] bg-gradient-to-br from-cyan-500/10 to-slate-900 relative overflow-hidden">
          <img src={m.image_url} alt={m.model} className="w-full h-full object-cover" />
          <button onClick={onClose} className="absolute top-3 right-3 px-3 py-1 rounded bg-black/60 border border-white/10 text-xs font-mono text-white hover:border-cyan-400">CLOSE ✕</button>
          <div className="absolute top-3 left-3 px-2 py-1 rounded bg-black/60 backdrop-blur-sm border border-cyan-500/30 text-[10px] font-mono uppercase tracking-wider text-cyan-300">{m.category} · {m.type}</div>
        </div>
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-400">Tennant Companies · Model</div>
              <h2 className="font-display text-4xl font-bold text-white mt-1">{m.model}</h2>
              <p className="text-slate-400 text-base mt-2 max-w-2xl">{m.use_case}</p>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono uppercase text-emerald-400">List Price</div>
              <div className="font-mono text-3xl text-emerald-300 font-bold">${m.list_price_usd.toLocaleString()}</div>
              <div className="text-[10px] font-mono text-slate-500 mt-0.5">USD · MSRP</div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
            <Spec Icon={Battery} label="Power" value={m.power} />
            <Spec Icon={Gauge} label="Runtime" value={m.runtime} />
            <Spec Icon={Ruler} label="Deck Width" value={`${m.deck_width_in} in`} />
            <Spec Icon={Weight} label="Weight" value={`${m.weight_lbs.toLocaleString()} lbs`} />
            {m.tank_gal > 0 && <Spec Icon={Cpu} label="Tank" value={`${m.tank_gal} gal`} />}
          </div>

          <div className="mt-6">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5"><Sparkles size={11} /> Highlights</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
              {m.highlights.map((h) => (
                <div key={h} className="flex items-start gap-2 p-2 rounded border border-white/5 bg-white/[0.02]">
                  <span className="text-cyan-400 mt-0.5">▸</span>
                  <span className="text-sm text-slate-200">{h}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Spec({ Icon, label, value }) {
  return (
    <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 flex items-center gap-1.5"><Icon size={10} className="text-cyan-400" /> {label}</div>
      <div className="font-mono text-sm text-white mt-1">{value}</div>
    </div>
  );
}
