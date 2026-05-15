import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Search, Cpu, Battery, Gauge, Ruler, Weight, DollarSign, Sparkles, Plus, Trash2 } from "lucide-react";
import { useBranding } from "../lib/branding";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";

export default function Machines() {
  const { brand } = useBranding();
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "dispatcher";
  const [machines, setMachines] = useState([]);
  const [categories, setCategories] = useState([]);
  const [catalogLabel, setCatalogLabel] = useState("Machine Catalog");
  const [category, setCategory] = useState("ALL");
  const [q, setQ] = useState("");
  const [active, setActive] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ category: "Custom" });

  const load = () => api.get("/machines").then(({ data }) => {
    setMachines(data.machines);
    setCategories(data.categories);
    setCatalogLabel(data.catalog_label || "Machine Catalog");
  });
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => machines.filter((m) => {
    if (category !== "ALL" && m.category !== category) return false;
    if (q) {
      const ql = q.toLowerCase();
      const hay = [m.model, m.category, m.type, m.power, m.use_case, m.description, (m.highlights || []).join(" ")].join(" ").toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  }), [machines, category, q]);

  const saveNew = async () => {
    if (!form.model?.trim()) { toast.error("Model is required"); return; }
    try {
      await api.post("/machines", form);
      toast.success("Machine added");
      setAdding(false);
      setForm({ category: "Custom" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const deleteMachine = async (m) => {
    if (!window.confirm(`${m.is_custom ? "Delete" : "Hide"} "${m.model}" from the catalog?`)) return;
    try {
      await api.delete(`/machines/${encodeURIComponent(m.model)}`);
      toast.success(m.is_custom ? "Machine deleted" : "Machine hidden");
      setActive(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <>
      <Topbar title={catalogLabel} subtitle={`${machines.length} models · ${brand?.short_name || "Tennant"} ${brand?.industry || "Industrial"}`} />
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
          <div className="ml-auto relative flex items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search model, use case..." className="pl-9 w-72 bg-[#131821] border-white/10" data-testid="machine-search" />
            </div>
            {canEdit && (
              <Button onClick={() => setAdding(true)} data-testid="machine-add-btn"
                      className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
                <Plus size={13} className="mr-1" /> Add
              </Button>
            )}
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((m) => (
            <div key={m.model} data-testid={`machine-card-${m.model}`} className="relative group">
              <button onClick={() => setActive(m)}
                className="w-full hud-surface text-left rounded-lg overflow-hidden border border-white/5 hover:border-cyan-500/40 hover:shadow-[0_0_20px_rgba(0,229,255,0.15)] transition-all bg-[#131821]">
                <div className="aspect-[4/3] bg-gradient-to-br from-cyan-500/5 to-slate-900 relative overflow-hidden">
                  <img src={m.image_url} alt={m.model} className="w-full h-full object-cover" loading="lazy"
                    onError={(e) => { e.target.style.display = 'none'; e.target.parentElement.classList.add('bg-machine-fallback'); }} />
                  <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm border border-cyan-500/30 text-[9px] font-mono uppercase tracking-wider text-cyan-300">{m.category}</div>
                  {m.size && <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-emerald-500/15 backdrop-blur-sm border border-emerald-500/30 text-[10px] font-mono text-emerald-300">{m.size}</div>}
                  {m.is_custom && <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-cyan-500/20 border border-cyan-500/40 text-[9px] font-mono text-cyan-300">Custom</div>}
                </div>
                <div className="p-3">
                  <div className="font-display text-lg font-bold text-white truncate">{m.model}</div>
                  <div className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">{m.use_case || m.description}</div>
                  <div className="grid grid-cols-2 gap-1 mt-2 text-[10px] font-mono">
                    {m.power && <div className="text-cyan-300 flex items-center gap-1"><Battery size={9} /> {m.power}</div>}
                    {m.runtime && <div className="text-emerald-400 flex items-center gap-1"><Gauge size={9} /> {m.runtime}</div>}
                  </div>
                </div>
              </button>
              {canEdit && (
                <button onClick={(e) => { e.stopPropagation(); deleteMachine(m); }} data-testid={`machine-delete-${m.model}`}
                        title={m.is_custom ? "Delete" : "Hide from catalog"}
                        className="absolute top-2 right-2 p-1.5 rounded bg-black/70 border border-red-500/30 text-red-400 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 transition-opacity">
                  <Trash2 size={11} />
                </button>
              )}
            </div>
          ))}
          {filtered.length === 0 && <Card className="hud-surface p-8 text-center text-slate-500 md:col-span-4">No machines match.</Card>}
        </div>
      </div>

      {active && <MachineDetail m={active} canEdit={canEdit} onClose={() => setActive(null)} onDelete={() => deleteMachine(active)} />}

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-xl" data-testid="machine-add-dialog">
          <DialogHeader><DialogTitle className="text-white">Add to {catalogLabel}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <MF label="Model *"           v={form.model}        k="model"        s={setForm} f={form} />
            <MF label="Display Name"      v={form.display_name} k="display_name" s={setForm} f={form} />
            <MF label="Category"          v={form.category}     k="category"     s={setForm} f={form} />
            <MF label="Power"             v={form.power}        k="power"        s={setForm} f={form} placeholder="Battery / LPG / Diesel" />
            <MF label="Image URL"         v={form.image_url}    k="image_url"    s={setForm} f={form} className="col-span-2" placeholder="https://" />
            <MF label="Description"       v={form.description}  k="description"  s={setForm} f={form} className="col-span-2" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAdding(false)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={saveNew} data-testid="machine-save-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function MF({ label, v, k, s, f, placeholder, className = "" }) {
  return (
    <div className={className}>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input value={v ?? ""} onChange={(e) => s({ ...f, [k]: e.target.value })}
             placeholder={placeholder} data-testid={`machine-field-${k}`}
             className="bg-[#11151F] border-white/10 mt-1" />
    </div>
  );
}

function MachineDetail({ m, onClose, canEdit, onDelete }) {
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
