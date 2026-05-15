import React, { useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Badge } from "./ui/badge";
import { Palette, Sparkles, RefreshCw, Trash2, Check, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useBranding } from "../lib/branding";
import { toast } from "sonner";

/**
 * CompanyTheme — single-input company switcher for Admin Settings.
 * Type a company name → backend uses Claude Sonnet to generate the full
 * brand identity (colors, products, suppliers, lanes, tagline) → activates
 * it immediately so the TMS re-skins everywhere.
 */
export default function CompanyTheme() {
  const { brand, refresh } = useBranding();
  const [allBrands, setAllBrands] = useState([]);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [activating, setActivating] = useState(null);

  const loadAll = async () => {
    try {
      const { data } = await api.get("/branding/all");
      setAllBrands(data.brands || []);
    } catch {
      setAllBrands([]);
    }
  };
  useEffect(() => { loadAll(); }, []);

  const generate = async () => {
    if (!name.trim()) { toast.error("Type a company name"); return; }
    setBusy(true);
    const t = toast.loading(`Generating brand profile for ${name.trim()}…`);
    try {
      const { data } = await api.post("/branding/generate", { company_name: name.trim(), activate: true });
      toast.success(`${data.brand.short_name} brand active`, { id: t });
      await refresh();
      await loadAll();
      setName("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Brand generation failed", { id: t });
    } finally {
      setBusy(false);
    }
  };

  const activate = async (brand_id) => {
    setActivating(brand_id);
    try {
      await api.post("/branding/activate", { brand_id });
      await refresh();
      await loadAll();
      toast.success("Brand activated");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Activate failed");
    } finally {
      setActivating(null);
    }
  };

  const remove = async (brand_id, label) => {
    if (!window.confirm(`Delete brand "${label}"? Cannot be undone.`)) return;
    try {
      await api.delete(`/branding/${brand_id}`);
      await loadAll();
      if (brand?.brand_id === brand_id) await activate("tennant");
      toast.success("Brand removed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <Card className="hud-surface p-5 lg:col-span-12" data-testid="admin-section-company-theme">
      <div className="flex items-center gap-2 mb-1">
        <Palette size={14} className="text-cyan-400" />
        <h3 className="font-display text-base font-bold text-white">Company Theme</h3>
        <Badge className="ml-2 text-[9px] font-mono uppercase bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">AI-generated</Badge>
      </div>
      <p className="text-[11px] text-slate-400 leading-relaxed">
        Type any company name to re-skin the entire TMS — brand colors, logo, tagline, sample products, suppliers, lanes.
        Powered by Claude Sonnet, generated once, then cached so every user sees the same theme.
      </p>

      {/* Active brand summary */}
      <div className="mt-4 flex items-center gap-3 p-3 rounded-md bg-white/[0.02] border border-cyan-500/20" data-testid="active-brand-row">
        <div className="w-9 h-9 rounded-full flex items-center justify-center text-black font-black text-base shadow-lg" style={{ background: brand?.primary_color || "#00E5FF" }}>
          {brand?.logo_letter || "T"}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-white truncate">{brand?.company_name || "Tennant Companies"}</div>
          <div className="text-[10px] font-mono text-slate-400 truncate">{brand?.tagline || ""}</div>
        </div>
        <Badge className="text-[9px] font-mono uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">Active</Badge>
      </div>

      {/* Type a new company */}
      <div className="mt-4 flex gap-2 items-stretch">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !busy) generate(); }}
          placeholder='Type a company name (e.g. "Walmart", "FedEx", "Caterpillar")'
          data-testid="brand-company-input"
          disabled={busy}
          className="bg-[#11151F] border-white/10"
        />
        <Button
          onClick={generate}
          disabled={busy || !name.trim()}
          data-testid="brand-generate-btn"
          className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shrink-0"
        >
          {busy ? <><Loader2 size={14} className="mr-1.5 animate-spin" /> Generating…</> : <><Sparkles size={14} className="mr-1.5" /> Generate & Activate</>}
        </Button>
      </div>

      {/* Built-in default + generated list */}
      <div className="mt-5 text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">Available Brands</div>
      <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="brands-list">
        {/* Tennant default - always shown */}
        <BrandRow
          b={{ brand_id: "tennant", company_name: "Tennant Companies", short_name: "Tennant", primary_color: "#00A4E4", logo_letter: "T", tagline: "Mission-control TMS · Built for the team's day (built-in default)", is_default: true }}
          active={brand?.brand_id === "tennant" || !brand?.brand_id}
          activating={activating}
          onActivate={activate}
          onRemove={null}
        />
        {allBrands.map((b) => (
          <BrandRow
            key={b.brand_id}
            b={b}
            active={brand?.brand_id === b.brand_id}
            activating={activating}
            onActivate={activate}
            onRemove={remove}
          />
        ))}
      </div>

      {allBrands.length === 0 && (
        <div className="mt-3 text-[10px] text-slate-500 italic">
          No custom brands yet. Type a company name above to generate your first one.
        </div>
      )}
    </Card>
  );
}

function BrandRow({ b, active, activating, onActivate, onRemove }) {
  const isActivating = activating === b.brand_id;
  return (
    <div
      data-testid={`brand-row-${b.brand_id}`}
      className={`flex items-center gap-3 p-2.5 rounded-md border transition-all ${
        active
          ? "border-emerald-500/50 bg-emerald-500/10"
          : "border-white/10 bg-white/[0.02] hover:border-cyan-500/30"
      }`}
    >
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-black font-black text-sm shrink-0"
        style={{ background: b.primary_color || "#00E5FF" }}
      >
        {b.logo_letter || (b.short_name || "?")[0]}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-bold text-white truncate">{b.company_name}</div>
        <div className="text-[10px] font-mono text-slate-500 truncate">{b.tagline || b.industry || ""}</div>
      </div>
      {active ? (
        <Badge className="text-[9px] font-mono uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
          <Check size={9} className="mr-1" /> Active
        </Badge>
      ) : (
        <Button
          size="sm"
          onClick={() => onActivate(b.brand_id)}
          disabled={isActivating}
          data-testid={`activate-${b.brand_id}`}
          className="h-7 text-[10px] font-mono uppercase tracking-wider bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
        >
          {isActivating ? <Loader2 size={10} className="animate-spin" /> : <><RefreshCw size={10} className="mr-1" /> Activate</>}
        </Button>
      )}
      {onRemove && !b.is_default && (
        <button
          onClick={() => onRemove(b.brand_id, b.short_name)}
          data-testid={`delete-brand-${b.brand_id}`}
          className="text-slate-500 hover:text-red-400 p-1"
          title="Delete brand"
        >
          <Trash2 size={12} />
        </button>
      )}
    </div>
  );
}
