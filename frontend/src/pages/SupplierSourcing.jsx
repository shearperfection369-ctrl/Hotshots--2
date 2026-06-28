import React, { useEffect, useMemo, useState } from "react";
import { useBrandRefresh } from "../lib/branding";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Factory, ShieldAlert, Search, MapPin, Clock, TrendingUp, AlertTriangle, DollarSign, Plus, Trash2 } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const RISK_COLOR = (n) => n >= 25 ? "text-red-400" : n >= 15 ? "text-yellow-400" : "text-emerald-400";
const RISK_BG = (n) => n >= 25 ? "bg-red-500/10 border-red-500/30" : n >= 15 ? "bg-yellow-500/10 border-yellow-500/30" : "bg-emerald-500/10 border-emerald-500/30";

export default function SupplierSourcing() {
  const { user } = useAuth();
  const canEdit = user?.role === "admin" || user?.role === "dispatcher";
  const [data, setData] = useState({ suppliers: [], summary: {} });
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("ALL");
  const [country, setCountry] = useState("ALL");
  const [primaryOnly, setPrimaryOnly] = useState(false);
  const [singleSourceOnly, setSingleSourceOnly] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ primary: true, country: "USA", category: "Uncategorized" });

  const refresh = () => api.get("/suppliers").then(({ data }) => setData(data));
  useEffect(() => { refresh(); }, []);
  useBrandRefresh(() => refresh());

  const saveSupplier = async () => {
    if (!form.name) { toast.error("Supplier name is required"); return; }
    try {
      const payload = {
        ...form,
        components: typeof form.components === "string"
          ? form.components.split(",").map((s) => s.trim()).filter(Boolean)
          : form.components || [],
        alt_suppliers: typeof form.alt_suppliers === "string"
          ? form.alt_suppliers.split(",").map((s) => s.trim()).filter(Boolean)
          : form.alt_suppliers || [],
      };
      await api.post("/suppliers", payload);
      toast.success("Supplier added");
      setAddOpen(false);
      setForm({ primary: true, country: "USA", category: "Uncategorized" });
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to add supplier");
    }
  };

  const removeSupplier = async (id) => {
    if (!window.confirm("Delete this custom supplier?")) return;
    try {
      await api.delete(`/suppliers/${id}`);
      toast.success("Supplier removed");
      refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Cannot delete built-in supplier");
    }
  };

  const categories = useMemo(() => ["ALL", ...new Set(data.suppliers.map((s) => s.category))], [data.suppliers]);
  const countries = useMemo(() => ["ALL", ...new Set(data.suppliers.map((s) => s.country))], [data.suppliers]);

  const filtered = data.suppliers.filter((s) => {
    if (category !== "ALL" && s.category !== category) return false;
    if (country !== "ALL" && s.country !== country) return false;
    if (primaryOnly && !s.primary) return false;
    if (singleSourceOnly && (s.alt_suppliers && s.alt_suppliers.length > 0)) return false;
    if (q) {
      const ql = q.toLowerCase();
      const hay = [s.name, s.category, s.country, s.contact, (s.components || []).join(" ")].join(" ").toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  });

  const countryChart = (data.summary.by_country || []).slice(0, 8).map((x) => ({ name: x.country, spend: Math.round(x.spend / 1000) }));

  return (
    <>
      <Topbar title="Supplier Sourcing" subtitle="the platform's component supply base · risk · spend · contracts" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <Tile label="Total Suppliers" value={data.summary.total_suppliers || 0} Icon={Factory} accent="text-cyan-400" />
          <Tile label="Primary Sources" value={data.summary.primary_count || 0} Icon={ShieldAlert} accent="text-emerald-400" />
          <Tile label="Annual Spend" value={`$${((data.summary.total_annual_spend_usd || 0) / 1_000_000).toFixed(1)}M`} Icon={DollarSign} accent="text-emerald-400" />
          <Tile label="Single-Source" value={data.summary.single_source_components || 0} Icon={AlertTriangle} accent="text-yellow-400" />
          <Tile label="High Risk" value={data.summary.high_risk_count || 0} Icon={AlertTriangle} accent="text-red-400" />
          <Tile label="Expiring 12mo" value={data.summary.expiring_contracts_12mo || 0} Icon={Clock} accent="text-yellow-400" />
        </div>

        <Card className="hud-surface p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Annual Spend by Country</div>
              <h3 className="font-display text-base font-bold">Top 8 Countries · $K</h3>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={countryChart}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="name" stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
              <Bar dataKey="spend" fill="#00E5FF" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="hud-surface p-3 flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search supplier, part, contact..." className="pl-9 w-72 bg-[#131821] border-white/10" data-testid="supplier-search" />
          </div>
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="bg-[#131821] border border-white/10 rounded px-3 py-2 text-sm" data-testid="supplier-category">
            {categories.map((c) => <option key={c} value={c}>{c === "ALL" ? "All Categories" : c}</option>)}
          </select>
          <select value={country} onChange={(e) => setCountry(e.target.value)} className="bg-[#131821] border border-white/10 rounded px-3 py-2 text-sm" data-testid="supplier-country">
            {countries.map((c) => <option key={c} value={c}>{c === "ALL" ? "All Countries" : c}</option>)}
          </select>
          <button onClick={() => setPrimaryOnly(!primaryOnly)} className={`px-3 py-2 rounded text-xs font-mono uppercase border ${primaryOnly ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`} data-testid="primary-toggle">Primary Only</button>
          <button onClick={() => setSingleSourceOnly(!singleSourceOnly)} className={`px-3 py-2 rounded text-xs font-mono uppercase border ${singleSourceOnly ? "bg-red-500 text-black border-red-400" : "border-white/10 text-slate-300 hover:border-red-400/40"}`} data-testid="single-source-toggle">Single-Source</button>
          {canEdit && (
            <Button onClick={() => setAddOpen(true)} data-testid="add-supplier-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              <Plus size={13} className="mr-1" /> Add Supplier
            </Button>
          )}
          <div className="ml-auto text-xs text-slate-400 font-mono">{filtered.length} / {data.suppliers.length}</div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((s) => (
            <Card key={s.supplier_id} className={`hud-surface p-4 border-l-2 ${RISK_BG(s.risk_score).split(" ")[1].replace("bg-", "border-l-").replace("/30", "/50")}`} data-testid={`supplier-${s.supplier_id}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-display text-base font-bold text-white">{s.name}</span>
                    {s.primary && <span className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-[9px] font-mono uppercase">Primary</span>}
                  </div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{s.supplier_id} · {s.category}</div>
                </div>
                <div className={`px-2 py-0.5 rounded border text-[10px] font-mono ${RISK_BG(s.risk_score)} ${RISK_COLOR(s.risk_score)}`}>
                  RISK {s.risk_score}
                </div>
                {s.is_custom && canEdit && (
                  <button onClick={() => removeSupplier(s.supplier_id)} title="Delete custom supplier" data-testid={`delete-supplier-${s.supplier_id}`} className="text-red-400 hover:text-red-300 ml-1">
                    <Trash2 size={12} />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                <div className="flex items-center gap-1.5 text-slate-300"><MapPin size={11} className="text-cyan-400" />{s.country}</div>
                <div className="flex items-center gap-1.5 text-slate-300"><Clock size={11} className="text-cyan-400" />{s.lead_time_days}d · MOQ {s.moq}</div>
                <div className="flex items-center gap-1.5 text-emerald-400"><TrendingUp size={11} />OTD {s.on_time_pct}%</div>
                <div className="flex items-center gap-1.5 text-yellow-400"><AlertTriangle size={11} />PPM {s.quality_ppm}</div>
              </div>

              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-mono text-slate-500">Components:</span>
                {s.components.map((c) => (
                  <span key={c} className="px-1.5 py-0.5 rounded bg-white/[0.04] text-[10px] font-mono text-cyan-300 border border-white/5">{c}</span>
                ))}
              </div>

              <div className="mt-3 pt-2 border-t border-white/5 text-[10px] font-mono space-y-0.5">
                <div className="flex justify-between"><span className="text-slate-500">Annual Spend</span><span className="text-emerald-400">${s.annual_spend_usd.toLocaleString()}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">FTA</span><span className="text-cyan-300">{s.fta_eligible}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Contract Expires</span><span className="text-yellow-400">{s.contract_expiry}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Alt Sources</span><span className={`${s.alt_suppliers?.length ? "text-emerald-300" : "text-red-400"}`}>{s.alt_suppliers?.length ? s.alt_suppliers.join(", ") : "SINGLE-SOURCE"}</span></div>
              </div>

              <div className="mt-2 text-[10px] text-slate-400 truncate" title={s.contact}>{s.contact}</div>
              {s.notes && <div className="mt-1 text-[10px] text-slate-500 italic">{s.notes}</div>}
            </Card>
          ))}
          {filtered.length === 0 && <Card className="hud-surface p-8 text-center text-slate-500 md:col-span-2">No suppliers match the filters.</Card>}
        </div>
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-2xl" data-testid="add-supplier-dialog">
          <DialogHeader><DialogTitle className="text-white">Add Supplier · Manual Entry</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Sup label="Name *"            v={form.name}              k="name"              s={setForm} f={form} />
            <Sup label="Category"          v={form.category}          k="category"          s={setForm} f={form} placeholder="e.g., Battery · Li-ion" />
            <Sup label="Country"           v={form.country}           k="country"           s={setForm} f={form} />
            <Sup label="FTA Program"       v={form.fta_eligible}      k="fta_eligible"      s={setForm} f={form} placeholder="USMCA / KORUS / MFN" />
            <Sup label="Annual Spend (USD)" v={form.annual_spend_usd} k="annual_spend_usd"  s={setForm} f={form} type="number" />
            <Sup label="Lead Time (days)"  v={form.lead_time_days}    k="lead_time_days"    s={setForm} f={form} type="number" />
            <Sup label="MOQ"               v={form.moq}               k="moq"               s={setForm} f={form} type="number" />
            <Sup label="On-Time %"         v={form.on_time_pct}       k="on_time_pct"       s={setForm} f={form} type="number" />
            <Sup label="Quality PPM"       v={form.quality_ppm}       k="quality_ppm"       s={setForm} f={form} type="number" />
            <Sup label="Risk Score (0-30)" v={form.risk_score}        k="risk_score"        s={setForm} f={form} type="number" />
            <Sup label="Contract Expiry"   v={form.contract_expiry}   k="contract_expiry"   s={setForm} f={form} type="date" />
            <Sup label="Contact"           v={form.contact}           k="contact"           s={setForm} f={form} placeholder="Name · email · phone" />
            <div className="col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Components (comma-separated SKUs)</Label>
              <Input value={form.components || ""} onChange={(e) => setForm({ ...form, components: e.target.value })}
                     data-testid="sup-components" className="bg-[#11151F] border-white/10 mt-1" placeholder="TENN-BATT-AGM-36V, TENN-WH-T16" />
            </div>
            <div className="col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Alternate Suppliers (comma-separated)</Label>
              <Input value={form.alt_suppliers || ""} onChange={(e) => setForm({ ...form, alt_suppliers: e.target.value })}
                     data-testid="sup-alt" className="bg-[#11151F] border-white/10 mt-1" placeholder="East Penn Mfg, Trojan Battery" />
            </div>
            <div className="col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Notes</Label>
              <Input value={form.notes || ""} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                     data-testid="sup-notes" className="bg-[#11151F] border-white/10 mt-1" />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-300 col-span-2">
              <Switch checked={!!form.primary} onCheckedChange={(v) => setForm({ ...form, primary: v })} data-testid="sup-primary" />
              Primary supplier for these components
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={saveSupplier} data-testid="sup-save" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Save Supplier</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Tile({ label, value, Icon, accent }) {
  return (
    <Card className="hud-surface p-4 flex items-start gap-3">
      <div className="p-2 rounded bg-cyan-500/10 border border-cyan-500/20"><Icon size={14} className="text-cyan-400" /></div>
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
        <div className={`text-xl font-mono font-bold mt-0.5 tabular-nums ${accent}`}>{value}</div>
      </div>
    </Card>
  );
}

function Sup({ label, v, k, s, f, type = "text", placeholder }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input type={type} value={v ?? ""} onChange={(e) => s({ ...f, [k]: type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value })}
             data-testid={`sup-${k}`} placeholder={placeholder} className="bg-[#11151F] border-white/10 mt-1" />
    </div>
  );
}
