import React, { useCallback, useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  Handshake, Users, Sparkles, Gift, TrendingUp, Award, ShieldCheck, Truck,
  BadgeCheck, Fuel, Wallet, UserCheck, Clock, Star, Zap, Plug, Radio,
  Plus, RefreshCw, ChevronRight, MessageSquare, Calendar, Trash2,
  Loader2, CheckCircle2, AlertCircle, DollarSign, Package, Mail, FileText, Send,
} from "lucide-react";
import { api } from "../lib/api";
import { useBranding, useBrandRefresh } from "../lib/branding";
import { toast } from "sonner";

/**
 * ShipperRelations — full CRM + loyalty command deck for building quality
 * shipper relationships. Brand-aware (Orisei default). Six tabs:
 *   1. Command Deck (KPIs + pipeline)
 *   2. Accounts (CRM)
 *   3. Rate Cards & Volume Discounts
 *   4. Incentives (11-item catalog)
 *   5. QBRs & Performance Reviews
 *   6. TMS Integrations
 */
const LIFECYCLE_META = {
  lead:      { label: "LEAD",      color: "#94A3B8", ring: "border-slate-400/40 text-slate-300 bg-slate-500/10" },
  qualified: { label: "QUALIFIED", color: "#22D3EE", ring: "border-cyan-400/40 text-cyan-200 bg-cyan-500/10" },
  active:    { label: "ACTIVE",    color: "#10B981", ring: "border-emerald-400/40 text-emerald-200 bg-emerald-500/10" },
  at_risk:   { label: "AT RISK",   color: "#F59E0B", ring: "border-amber-400/40 text-amber-200 bg-amber-500/10" },
  churned:   { label: "CHURNED",   color: "#EF4444", ring: "border-red-400/40 text-red-200 bg-red-500/10" },
};

const INCENTIVE_ICON = {
  volume_rebate: Gift, damage_free_guarantee: ShieldCheck, otp_guarantee: BadgeCheck,
  dedicated_am: UserCheck, fuel_flex: Fuel, payment_terms: Wallet,
  flex_pickup: Clock, loyalty_tier: Star, tms_integration: Plug, performance_review: TrendingUp,
};

const TABS = [
  { id: "deck",       label: "Command Deck",  icon: Radio },
  { id: "accounts",   label: "Accounts",      icon: Users },
  { id: "standard",   label: "Service Standard", icon: BadgeCheck },
  { id: "rates",      label: "Rate Cards",    icon: DollarSign },
  { id: "incentives", label: "Incentives",    icon: Gift },
  { id: "qbrs",       label: "QBRs",          icon: TrendingUp },
  { id: "tms",        label: "TMS Integrations", icon: Plug },
];

export default function ShipperRelations() {
  const { brand } = useBranding();
  const [tab, setTab] = useState("deck");
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [incentives, setIncentives] = useState([]);
  const [rateCards, setRateCards] = useState([]);
  const [busy, setBusy] = useState(false);

  const loadAll = useCallback(async () => {
    setBusy(true);
    try {
      const [d, a, i, rc] = await Promise.all([
        api.get("/shipper-relations/dashboard"),
        api.get("/shipper-relations/accounts"),
        api.get("/shipper-relations/incentives"),
        api.get("/shipper-relations/rate-cards"),
      ]);
      setDashboard(d.data);
      setAccounts(a.data.items || []);
      setIncentives(i.data.items || []);
      setRateCards(rc.data.items || []);
    } catch (e) {
      toast.error("Failed to load shipper relations data");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useBrandRefresh(() => loadAll());

  const seedCatalog = async () => {
    try {
      const { data } = await api.post("/shipper-relations/seed-incentive-catalog");
      toast.success(`Seeded ${data.inserted} incentives (${data.existing} already present)`);
      loadAll();
    } catch (e) {
      toast.error("Seed failed");
    }
  };

  const brandShort = brand?.short_name || "Orisei";

  return (
    <>
      <Topbar
        title={`${brandShort} · Shipper Relations`}
        subtitle="Quality relationships · rate cards · loyalty · QBRs · integrations"
      />
      <div className="p-4 md:p-6 space-y-4">
        <div className="flex flex-wrap items-center gap-2" data-testid="shipper-relations-header">
          <Handshake size={22} style={{ color: brand?.primary_color || "#22D3EE" }} />
          <div className="text-slate-100 font-medium">Shipper Relationship Command Deck</div>
          <Badge className="bg-cyan-500/15 text-cyan-200 border border-cyan-400/30">FULL-STACK CRM · LOYALTY · TMS</Badge>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={loadAll} disabled={busy}
              data-testid="shipper-relations-refresh">
              {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <RefreshCw size={13} className="mr-1" />}
              Refresh
            </Button>
            <Button size="sm" onClick={seedCatalog} className="bg-cyan-500 hover:bg-cyan-400 text-black"
              data-testid="shipper-relations-seed">
              <Sparkles size={13} className="mr-1" /> Seed Incentive Catalog
            </Button>
          </div>
        </div>

        {/* Tab strip */}
        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="shipper-relations-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`shipper-tab-${id}`}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition border whitespace-nowrap ${
                tab === id
                  ? "bg-cyan-500 text-black border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.35)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "deck"       && <CommandDeckTab dashboard={dashboard} brand={brand} accounts={accounts} />}
        {tab === "accounts"   && <AccountsTab accounts={accounts} incentives={incentives} onChange={loadAll} />}
        {tab === "standard"   && <ServiceStandardTab />}
        {tab === "rates"      && <RateCardsTab cards={rateCards} onChange={loadAll} />}
        {tab === "incentives" && <IncentivesTab incentives={incentives} onChange={loadAll} />}
        {tab === "qbrs"       && <QbrsTab accounts={accounts} onChange={loadAll} />}
        {tab === "tms"        && <TmsTab accounts={accounts} onChange={loadAll} />}
      </div>
    </>
  );
}

// ============================================================
//                     COMMAND DECK TAB
// ============================================================
function CommandDeckTab({ dashboard, brand, accounts }) {
  if (!dashboard) return <Loader />;
  const { totals, pipeline, portfolio } = dashboard;
  const primary = brand?.primary_color || "#22D3EE";
  const accent = brand?.accent_color || "#F59E0B";

  return (
    <div className="space-y-4">
      {/* Headline KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="shipper-kpi-strip">
        <BigKpi label="Active Accounts" value={pipeline.active} accent="#10B981" icon={Users} sub={`${totals.accounts} total`} />
        <BigKpi label="Annual Volume" value={fmt(portfolio.annual_volume_loads)} accent={primary} icon={Package} sub="loads / year" />
        <BigKpi label="Annual Revenue" value={`$${fmtM(portfolio.annual_revenue_usd)}`} accent="#10B981" icon={DollarSign} sub="committed spend" />
        <BigKpi label="Rebate Accrued" value={`$${fmt(portfolio.loyalty_rebate_accrued_usd)}`} accent={accent} icon={Gift} sub="loyalty pool" />
      </div>

      {/* Pipeline funnel + Portfolio quality */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        <Card className="md:col-span-3 p-4 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">
            Pipeline funnel — {totals.accounts} accounts
          </div>
          <FunnelBars pipeline={pipeline} />
        </Card>
        <Card className="md:col-span-2 p-4 bg-slate-900/60 border-white/10 space-y-3">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            Portfolio quality (latest QBRs)
          </div>
          <MiniStat label="Avg OTD" value={portfolio.avg_otd_pct} suffix="%" target={95} />
          <MiniStat label="Avg OTP" value={portfolio.avg_otp_pct} suffix="%" target={98} />
          <MiniStat label="Damage-Free" value={portfolio.avg_damage_free_pct} suffix="%" target={99} />
          <MiniStat label="Avg NPS" value={portfolio.avg_nps} target={50} />
        </Card>
      </div>

      {/* Value propositions */}
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">
          <Sparkles size={12} className="inline mr-1" /> {(brand?.short_name || "Orisei")} incentive pillars
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { icon: Gift, label: "Volume rebates", desc: "2% back at 100 loads/qtr" },
            { icon: BadgeCheck, label: "OTP guarantee", desc: "98% or credit issued" },
            { icon: ShieldCheck, label: "Damage-free promise", desc: "$500 credit per claim" },
            { icon: Fuel, label: "EIA-indexed fuel", desc: "Weekly auto-adjust" },
            { icon: Wallet, label: "Net-60 for Platinum", desc: "Extended terms" },
            { icon: UserCheck, label: "Dedicated AM", desc: "4-hr response SLA" },
            { icon: Clock, label: "Flex pickup", desc: "0-4 hr windows" },
            { icon: Plug, label: "Free TMS integration", desc: "API/EDI 204/210/214" },
          ].map(({ icon: Icon, label, desc }, i) => (
            <div key={i} className="p-3 rounded border border-white/10 bg-black/30" data-testid={`shipper-pillar-${i}`}>
              <Icon size={14} style={{ color: accent }} />
              <div className="text-xs text-slate-100 mt-1 font-medium">{label}</div>
              <div className="text-[10px] text-slate-500 mt-0.5">{desc}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Top 5 recent accounts */}
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          Recent accounts
        </div>
        {accounts.length === 0 ? (
          <div className="p-6 text-center text-xs text-slate-500">
            No accounts yet — head to the <b>Accounts</b> tab to add your first shipper.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Account</th>
                <th className="px-3 py-2 text-left">Industry</th>
                <th className="px-3 py-2 text-right">Loads/yr</th>
                <th className="px-3 py-2 text-right">$ / yr</th>
                <th className="px-3 py-2 text-left">Terms</th>
                <th className="px-3 py-2 text-left">Lifecycle</th>
              </tr>
            </thead>
            <tbody>
              {accounts.slice(0, 5).map((a) => (
                <tr key={a.account_id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-slate-100">{a.company_name}</td>
                  <td className="px-3 py-2 text-slate-400">{a.industry || "—"}</td>
                  <td className="px-3 py-2 text-right text-slate-200 font-mono">{fmt(a.annual_volume_loads || 0)}</td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">${fmtM(a.annual_revenue_usd || 0)}</td>
                  <td className="px-3 py-2 text-cyan-300 font-mono">{(a.payment_terms || "").replace("_", "-").toUpperCase()}</td>
                  <td className="px-3 py-2"><LifecyclePill v={a.lifecycle} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

function FunnelBars({ pipeline }) {
  const total = Math.max(1, Object.values(pipeline).reduce((s, v) => s + v, 0));
  const order = ["lead", "qualified", "active", "at_risk", "churned"];
  return (
    <div className="space-y-2">
      {order.map((k) => {
        const v = pipeline[k] || 0;
        const pct = (v / total) * 100;
        const meta = LIFECYCLE_META[k];
        return (
          <div key={k} className="flex items-center gap-3" data-testid={`funnel-${k}`}>
            <div className="w-24 text-[10px] font-mono uppercase tracking-widest" style={{ color: meta.color }}>
              {meta.label}
            </div>
            <div className="flex-1 h-6 bg-black/40 rounded overflow-hidden border border-white/5">
              <div className="h-full flex items-center px-2 text-[10px] font-mono text-black"
                style={{ width: `${Math.max(pct, 4)}%`, background: meta.color }}>
                {v}
              </div>
            </div>
            <div className="w-12 text-right text-[10px] font-mono text-slate-500">{pct.toFixed(0)}%</div>
          </div>
        );
      })}
    </div>
  );
}

function MiniStat({ label, value, suffix = "", target }) {
  const num = value == null ? null : Number(value);
  const good = num != null && target != null && num >= target;
  const color = num == null ? "#64748B" : good ? "#10B981" : "#F59E0B";
  return (
    <div className="flex items-center justify-between border-b border-white/5 pb-2 last:border-0">
      <span className="text-[11px] text-slate-400">{label}</span>
      <div className="text-right">
        <div className="text-sm font-mono" style={{ color }}>
          {num == null ? "—" : `${num}${suffix}`}
        </div>
        <div className="text-[9px] text-slate-500">
          target {target}{suffix}
        </div>
      </div>
    </div>
  );
}

// ============================================================
//                     ACCOUNTS TAB
// ============================================================
function AccountsTab({ accounts, incentives, onChange }) {
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState(null);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <Users size={12} className="inline mr-1" /> {accounts.length} shipper accounts
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black"
          data-testid="shipper-add-account-btn">
          <Plus size={13} className="mr-1" /> New Account
        </Button>
      </div>

      {accounts.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <Users size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No accounts yet. Click <b>New Account</b> to add your first prospect.</div>
        </Card>
      ) : (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
          <table className="w-full text-xs" data-testid="shipper-accounts-table">
            <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Account</th>
                <th className="px-3 py-2 text-left">Contact</th>
                <th className="px-3 py-2 text-left">HQ</th>
                <th className="px-3 py-2 text-right">Loads/yr</th>
                <th className="px-3 py-2 text-right">Revenue</th>
                <th className="px-3 py-2 text-left">Terms</th>
                <th className="px-3 py-2 text-left">AM</th>
                <th className="px-3 py-2 text-left">Incentives</th>
                <th className="px-3 py-2 text-left">Lifecycle</th>
                <th className="px-3 py-2 text-right"></th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.account_id} className="border-t border-white/5 hover:bg-white/[0.02] cursor-pointer"
                  onClick={() => setSelected(a)}
                  data-testid={`shipper-row-${a.account_id}`}>
                  <td className="px-3 py-2 text-slate-100 font-medium">{a.company_name}</td>
                  <td className="px-3 py-2 text-slate-400">{a.contact_name || "—"}</td>
                  <td className="px-3 py-2 text-slate-400">{a.hq_city || "—"}{a.hq_state ? `, ${a.hq_state}` : ""}</td>
                  <td className="px-3 py-2 text-right text-slate-200 font-mono">{fmt(a.annual_volume_loads || 0)}</td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">${fmtM(a.annual_revenue_usd || 0)}</td>
                  <td className="px-3 py-2 text-cyan-300 font-mono">{(a.payment_terms || "").replace("_", "-").toUpperCase()}</td>
                  <td className="px-3 py-2 text-slate-300">{a.dedicated_am || "—"}</td>
                  <td className="px-3 py-2 text-slate-300 font-mono">{(a.assigned_incentives || []).length}</td>
                  <td className="px-3 py-2"><LifecyclePill v={a.lifecycle} /></td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button title="Service Scorecard PDF" data-testid={`shipper-scorecard-${a.account_id}`}
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          const res = await api.get(`/shipper-relations/accounts/${a.account_id}/scorecard.pdf`, { responseType: "blob" });
                          const url = URL.createObjectURL(res.data);
                          const el = document.createElement("a");
                          el.href = url; el.download = `Orisei_Scorecard_${a.company_name.replace(/ /g, "_")}.pdf`; el.click();
                          URL.revokeObjectURL(url);
                          toast.success("Scorecard PDF downloaded");
                        } catch (_) { toast.error("Scorecard failed"); }
                      }}
                      className="p-1 rounded text-amber-300 hover:bg-amber-500/10 mr-1"><FileText size={13} className="inline" /></button>
                    <ChevronRight size={14} className="text-slate-500 inline" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <AddAccountDialog open={addOpen} onClose={() => setAddOpen(false)} onSaved={onChange} />
      <AccountDetailDialog account={selected} incentives={incentives} onClose={() => setSelected(null)} onChange={onChange} />
    </div>
  );
}

function ServiceStandardTab() {
  const [std, setStd] = useState(null);
  useEffect(() => {
    api.get("/shipper-relations/service-standard").then(({ data }) => setStd(data)).catch(() => {});
  }, []);
  if (!std) return <div className="p-8 text-center text-slate-500 font-mono text-xs" data-testid="service-standard-loading">Loading service standard…</div>;
  const ACCENTS = ["#0E7C7B", "#E2725B", "#C9A24A", "#6D3B8E", "#2E7D46"];
  return (
    <div className="space-y-4" data-testid="service-standard-tab">
      <div className="flex items-center gap-2">
        <BadgeCheck size={16} className="text-emerald-300" />
        <h3 className="text-sm font-black text-white uppercase tracking-wider">The Orisei Service Standard — what shippers want, codified</h3>
      </div>
      <p className="text-[11px] text-slate-400 max-w-3xl">{std.note}</p>
      <div className="grid md:grid-cols-2 gap-3" data-testid="service-standard-grid">
        {std.standard.map((s, i) => (
          <Card key={s.metric} className="hud-surface p-4 border-white/10" data-testid={`sla-card-${s.metric}`}>
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <div className="text-[12px] font-black text-white uppercase tracking-wide">{s.want}</div>
              <span className="px-2 py-0.5 rounded-full border text-[9px] font-mono font-bold whitespace-nowrap"
                    style={{ color: ACCENTS[i % 5], borderColor: `${ACCENTS[i % 5]}66` }}>{s.target}</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">{s.commitment}</p>
          </Card>
        ))}
      </div>
      <p className="text-[10px] font-mono text-slate-500">
        Printed on page 4 of the shipper brochure · proven per account via the Service Scorecard PDF (Accounts tab → document icon).
      </p>
    </div>
  );
}

function AddAccountDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({
    company_name: "", dba: "", industry: "", hq_city: "", hq_state: "",
    contact_name: "", contact_email: "", contact_phone: "",
    annual_volume_loads: "", annual_revenue_usd: "",
    payment_terms: "net_30", lifecycle: "lead", dedicated_am: "",
    primary_lanes: "", equipment_needs: "", notes: "",
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.company_name.trim()) { toast.error("Company name required"); return; }
    setBusy(true);
    try {
      const payload = { ...form };
      ["annual_volume_loads", "annual_revenue_usd"].forEach((k) => {
        payload[k] = payload[k] === "" ? undefined : Number(payload[k]);
      });
      payload.primary_lanes = form.primary_lanes ? form.primary_lanes.split(",").map((s) => s.trim()).filter(Boolean) : undefined;
      payload.equipment_needs = form.equipment_needs ? form.equipment_needs.split(",").map((s) => s.trim()).filter(Boolean) : undefined;
      Object.keys(payload).forEach((k) => (payload[k] === "" || payload[k] === undefined) && delete payload[k]);
      await api.post("/shipper-relations/accounts", payload);
      toast.success(`Added ${form.company_name}`);
      onSaved?.(); onClose?.();
      setForm({ ...form, company_name: "", contact_email: "", contact_phone: "", notes: "" });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save");
    } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="shipper-add-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">New Shipper Account</DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Prospect enters as a LEAD by default. Move through the funnel via the account detail view.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FF label="Company Name *" tid="shipper-form-company">
            <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="shipper-form-company-input" />
          </FF>
          <FF label="DBA">
            <Input value={form.dba} onChange={(e) => setForm({ ...form, dba: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Industry">
            <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Retail, CPG, Manufacturing…" />
          </FF>
          <FF label="Contact Name">
            <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Contact Email">
            <Input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Contact Phone">
            <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="HQ City">
            <Input value={form.hq_city} onChange={(e) => setForm({ ...form, hq_city: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="HQ State">
            <Input value={form.hq_state} onChange={(e) => setForm({ ...form, hq_state: e.target.value.toUpperCase() })}
              className="bg-black/40 border-white/10 h-8 text-xs" maxLength={2} placeholder="MN" />
          </FF>
          <FF label="Annual Volume (loads)">
            <Input type="number" value={form.annual_volume_loads}
              onChange={(e) => setForm({ ...form, annual_volume_loads: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Annual Revenue (USD)">
            <Input type="number" value={form.annual_revenue_usd}
              onChange={(e) => setForm({ ...form, annual_revenue_usd: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Payment Terms">
            <select value={form.payment_terms}
              onChange={(e) => setForm({ ...form, payment_terms: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="shipper-form-terms">
              <option value="quick_pay">Quick Pay (2% discount)</option>
              <option value="net_15">Net-15</option>
              <option value="net_30">Net-30</option>
              <option value="net_45">Net-45</option>
              <option value="net_60">Net-60</option>
            </select>
          </FF>
          <FF label="Dedicated AM">
            <Input value={form.dedicated_am} onChange={(e) => setForm({ ...form, dedicated_am: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Oliver Cummins" />
          </FF>
          <FF label="Primary Lanes (comma-sep)" className="md:col-span-2">
            <Input value={form.primary_lanes} onChange={(e) => setForm({ ...form, primary_lanes: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Minneapolis→Dallas, Duluth→Chicago" />
          </FF>
          <FF label="Equipment Needs (comma-sep)" className="md:col-span-2">
            <Input value={form.equipment_needs} onChange={(e) => setForm({ ...form, equipment_needs: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Van, Reefer, Flatbed" />
          </FF>
          <FF label="Notes" className="md:col-span-2">
            <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="bg-black/40 border-white/10 text-xs" />
          </FF>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="shipper-form-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save Account
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AccountDetailDialog({ account, incentives, onClose, onChange }) {
  const [detail, setDetail] = useState(null);
  const [assignId, setAssignId] = useState("");
  const [activityForm, setActivityForm] = useState({ kind: "call", summary: "", outcome: "", next_step: "" });
  const [welcomeBusy, setWelcomeBusy] = useState(false);
  const [welcomeReceipt, setWelcomeReceipt] = useState(null);
  const [welcomeSender, setWelcomeSender] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!account) return;
    try {
      const { data } = await api.get(`/shipper-relations/accounts/${account.account_id}`);
      setDetail(data);
    } catch (e) { /* no-op */ }
  }, [account]);
  useEffect(() => { load(); }, [load]);

  if (!account) return null;

  const moveTier = async (lifecycle) => {
    try {
      await api.post(`/shipper-relations/accounts/${account.account_id}/tier`, { lifecycle });
      toast.success(`Moved to ${lifecycle.toUpperCase()}`);
      onChange?.(); load();
    } catch (e) { toast.error("Failed"); }
  };

  const assign = async () => {
    if (!assignId) return;
    try {
      await api.post(`/shipper-relations/accounts/${account.account_id}/assign-incentive`, { incentive_id: assignId });
      toast.success("Incentive assigned");
      setAssignId(""); onChange?.(); load();
    } catch (e) { toast.error("Failed"); }
  };

  const unassign = async (id) => {
    try {
      await api.delete(`/shipper-relations/accounts/${account.account_id}/incentives/${id}`);
      toast.success("Removed");
      onChange?.(); load();
    } catch (e) { toast.error("Failed"); }
  };

  const logActivity = async () => {
    if (!activityForm.summary.trim()) { toast.error("Summary required"); return; }
    setBusy(true);
    try {
      await api.post(`/shipper-relations/accounts/${account.account_id}/activity`, activityForm);
      toast.success("Logged");
      setActivityForm({ kind: "call", summary: "", outcome: "", next_step: "" });
      load();
    } catch (e) { toast.error("Failed"); } finally { setBusy(false); }
  };

  const sendWelcome = async () => {
    if (!account.contact_email) { toast.error("Add a contact_email to this account first."); return; }
    setWelcomeBusy(true);
    setWelcomeReceipt(null);
    try {
      const { data } = await api.post(`/shipper-relations/accounts/${account.account_id}/send-welcome`,
        { sender_name: welcomeSender || undefined });
      setWelcomeReceipt(data);
      toast.success(`Welcome kit sent to ${data.delivery.to} (mock)`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed");
    } finally { setWelcomeBusy(false); }
  };

  const downloadWelcomePdf = () => {
    const base = process.env.REACT_APP_BACKEND_URL || "";
    const token = localStorage.getItem("tms_session_token") || "";
    // Use fetch to include the auth header, then blob-download.
    fetch(`${base}/api/shipper-relations/accounts/${account.account_id}/welcome.pdf`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then((r) => r.blob()).then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `orisei_welcome_${account.account_id}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    }).catch(() => toast.error("Download failed"));
  };

  return (
    <Dialog open={!!account} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-4xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="shipper-detail-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100 flex items-center gap-2">
            {account.company_name} <LifecyclePill v={account.lifecycle} />
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            {account.industry || "—"} · {account.hq_city || "—"}{account.hq_state ? `, ${account.hq_state}` : ""} · {(account.payment_terms || "").replace("_", "-").toUpperCase()}
          </DialogDescription>
        </DialogHeader>

        {/* Lifecycle mover */}
        <div className="flex flex-wrap gap-2">
          {Object.keys(LIFECYCLE_META).map((k) => (
            <button key={k} onClick={() => moveTier(k)}
              data-testid={`shipper-move-${k}`}
              className={`px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider border transition ${
                account.lifecycle === k ? LIFECYCLE_META[k].ring : "border-white/10 text-slate-500 hover:border-white/30"
              }`}>
              {LIFECYCLE_META[k].label}
            </button>
          ))}
        </div>

        {/* Welcome Kit — Orisei-branded PDF + mocked email */}
        <Card className="p-3 bg-cyan-500/5 border-cyan-500/30" data-testid="shipper-welcome-card">
          <div className="flex items-center gap-2 mb-2">
            <Mail size={13} className="text-cyan-300" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
              Orisei welcome kit
            </span>
            <span className="text-[10px] text-slate-500">
              PDF + auto professional greeting → {account.contact_email || <span className="text-red-400">missing contact_email</span>}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Input
              value={welcomeSender}
              onChange={(e) => setWelcomeSender(e.target.value)}
              placeholder="Sender name (optional — defaults to The Orisei Freight Team)"
              className="flex-1 min-w-[240px] bg-black/40 border-white/10 h-8 text-xs"
              data-testid="shipper-welcome-sender"
            />
            <Button
              onClick={downloadWelcomePdf}
              variant="ghost"
              className="text-cyan-300 hover:text-cyan-100 h-8"
              data-testid="shipper-welcome-download">
              <FileText size={12} className="mr-1" /> Preview PDF
            </Button>
            <Button
              onClick={sendWelcome}
              disabled={welcomeBusy || !account.contact_email}
              className="bg-cyan-500 hover:bg-cyan-400 text-black h-8"
              data-testid="shipper-welcome-send">
              {welcomeBusy ? <Loader2 size={12} className="animate-spin mr-1" /> : <Send size={12} className="mr-1" />}
              Send welcome kit
            </Button>
          </div>
          {welcomeReceipt && (
            <div className="mt-3 text-[11px] text-emerald-100 border border-emerald-500/30 bg-emerald-500/5 rounded p-2 space-y-1"
              data-testid="shipper-welcome-receipt">
              <div className="font-mono text-[10px] uppercase tracking-widest text-emerald-300">
                Delivery receipt · {welcomeReceipt.delivery.provider}
              </div>
              <div className="text-slate-300">
                <b>To:</b> {welcomeReceipt.delivery.to} · <b>Subject:</b> {welcomeReceipt.delivery.subject}
              </div>
              <div className="text-slate-400">
                <b>Attached PDF:</b> {welcomeReceipt.delivery.attachment.filename} · {(welcomeReceipt.pdf_bytes/1024).toFixed(0)} KB
              </div>
              <div className="text-slate-300 whitespace-pre-wrap font-mono text-[10.5px] pt-1 border-t border-white/5">
                {welcomeReceipt.greeting_preview}
              </div>
            </div>
          )}
        </Card>

        {/* Assigned incentives */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">
            <Gift size={11} className="inline mr-1" /> Assigned incentives · {(detail?.incentives || []).length}
          </div>
          {(detail?.incentives || []).length === 0 ? (
            <div className="text-[11px] text-slate-500">No incentives assigned yet.</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
              {detail.incentives.map((inc) => {
                const Icon = INCENTIVE_ICON[inc.kind] || Gift;
                return (
                  <div key={inc.incentive_id} className="p-2 border border-white/10 rounded bg-black/30 flex items-start gap-2"
                    data-testid={`shipper-assigned-${inc.incentive_id}`}>
                    <Icon size={14} className="text-amber-300 mt-0.5 shrink-0" />
                    <div className="flex-1">
                      <div className="text-xs text-slate-100">{inc.name}</div>
                      <div className="text-[10px] text-slate-500">{inc.description}</div>
                    </div>
                    <button onClick={() => unassign(inc.incentive_id)}
                      data-testid={`shipper-unassign-${inc.incentive_id}`}
                      className="text-red-400 hover:text-red-200"><Trash2 size={12} /></button>
                  </div>
                );
              })}
            </div>
          )}
          <div className="flex gap-2">
            <select value={assignId} onChange={(e) => setAssignId(e.target.value)}
              className="flex-1 bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="shipper-assign-select">
              <option value="">Select an incentive to assign…</option>
              {incentives
                .filter((i) => !(detail?.incentives || []).some((x) => x.incentive_id === i.incentive_id))
                .map((i) => <option key={i.incentive_id} value={i.incentive_id}>{i.name}</option>)}
            </select>
            <Button size="sm" onClick={assign} disabled={!assignId}
              className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="shipper-assign-btn">
              <Plus size={13} className="mr-1" /> Attach
            </Button>
          </div>
        </Card>

        {/* Activity log */}
        <Card className="p-3 bg-slate-900/60 border-white/10">
          <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">
            <MessageSquare size={11} className="inline mr-1" /> Activity log
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-2 mb-2">
            <select value={activityForm.kind} onChange={(e) => setActivityForm({ ...activityForm, kind: e.target.value })}
              className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="shipper-activity-kind">
              <option value="call">Call</option>
              <option value="email">Email</option>
              <option value="meeting">Meeting</option>
              <option value="proposal">Proposal</option>
              <option value="contract">Contract</option>
              <option value="note">Note</option>
            </select>
            <Input value={activityForm.summary} onChange={(e) => setActivityForm({ ...activityForm, summary: e.target.value })}
              placeholder="Summary" className="bg-black/40 border-white/10 h-8 text-xs md:col-span-2"
              data-testid="shipper-activity-summary" />
            <Input value={activityForm.next_step} onChange={(e) => setActivityForm({ ...activityForm, next_step: e.target.value })}
              placeholder="Next step" className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
          <div className="flex justify-end mb-3">
            <Button size="sm" onClick={logActivity} disabled={busy}
              className="bg-cyan-500 hover:bg-cyan-400 text-black"
              data-testid="shipper-activity-save">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} Log
            </Button>
          </div>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {(detail?.activity || []).length === 0 && (
              <div className="text-[11px] text-slate-500 text-center py-4">No activity logged yet.</div>
            )}
            {(detail?.activity || []).map((act) => (
              <div key={act.activity_id} className="text-[11px] text-slate-300 border-l-2 border-cyan-500/30 pl-2 py-1">
                <span className="text-cyan-300 font-mono uppercase text-[9px] tracking-widest mr-2">{act.kind}</span>
                <span className="text-slate-400">{act.created_at?.slice(0, 10)}</span> · {act.summary}
                {act.next_step && <div className="text-[10px] text-amber-300/70 mt-0.5">→ Next: {act.next_step}</div>}
              </div>
            ))}
          </div>
        </Card>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     RATE CARDS TAB
// ============================================================
function RateCardsTab({ cards, onChange }) {
  const [addOpen, setAddOpen] = useState(false);
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <DollarSign size={12} className="inline mr-1" /> {cards.length} rate cards
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black"
          data-testid="rate-card-add-btn">
          <Plus size={13} className="mr-1" /> New Rate Card
        </Button>
      </div>
      {cards.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <DollarSign size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">
            No rate cards yet. Volume discounts drive shipper loyalty — create your first card.
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {cards.map((c) => (
            <RateCard key={c.rate_card_id} card={c} onChange={onChange} />
          ))}
        </div>
      )}
      <AddRateCardDialog open={addOpen} onClose={() => setAddOpen(false)} onSaved={onChange} />
    </div>
  );
}

function RateCard({ card, onChange }) {
  const del = async () => {
    if (!window.confirm(`Delete "${card.name}"?`)) return;
    try { await api.delete(`/shipper-relations/rate-cards/${card.rate_card_id}`);
      toast.success("Deleted"); onChange?.(); } catch (e) { toast.error("Failed"); }
  };
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10 space-y-2" data-testid={`rate-card-${card.rate_card_id}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-slate-100 font-medium">{card.name}</div>
          <div className="text-[10px] text-slate-500 font-mono">
            {card.equipment} · {card.origin_region || "any"} → {card.dest_region || "any"} · valid {card.valid_from?.slice(0, 10)}
          </div>
        </div>
        <button onClick={del} className="text-red-400 hover:text-red-200"
          data-testid={`rate-card-delete-${card.rate_card_id}`}><Trash2 size={12} /></button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="p-2 bg-black/30 border border-white/5 rounded">
          <div className="text-slate-500">Base RPM</div>
          <div className="text-slate-100 font-mono">${(card.base_rpm || 0).toFixed(2)}/mi</div>
        </div>
        <div className="p-2 bg-black/30 border border-white/5 rounded">
          <div className="text-slate-500">Fuel surcharge</div>
          <div className="text-slate-100 font-mono">{card.fuel_surcharge_pct || 0}%</div>
        </div>
      </div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mt-1">Volume Tiers</div>
      <div className="space-y-1">
        {(card.tiers || []).map((t, i) => (
          <div key={i} className="flex items-center justify-between text-[11px] p-1.5 bg-black/30 border border-white/5 rounded">
            <span className="text-slate-300 font-mono">≥ {t.min_loads_per_month} loads/mo</span>
            <span className="text-emerald-300 font-mono">−{t.discount_pct}%{t.rate_per_mile_floor ? ` · floor $${t.rate_per_mile_floor.toFixed(2)}/mi` : ""}</span>
          </div>
        ))}
      </div>
      {card.notes && <div className="text-[10px] text-slate-500 italic mt-1">&ldquo;{card.notes}&rdquo;</div>}
    </Card>
  );
}

function AddRateCardDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: "", equipment: "Van", origin_region: "", dest_region: "",
    base_rpm: "2.25", fuel_surcharge_pct: "0", valid_from: new Date().toISOString().slice(0, 10),
    valid_to: "", notes: "",
    tiers: [
      { min_loads_per_month: 0, discount_pct: 0, rate_per_mile_floor: "" },
      { min_loads_per_month: 25, discount_pct: 2, rate_per_mile_floor: "" },
      { min_loads_per_month: 100, discount_pct: 5, rate_per_mile_floor: "" },
    ],
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.name.trim()) { toast.error("Name required"); return; }
    setBusy(true);
    try {
      const payload = {
        ...form,
        base_rpm: Number(form.base_rpm),
        fuel_surcharge_pct: Number(form.fuel_surcharge_pct),
        tiers: form.tiers.map((t) => ({
          min_loads_per_month: Number(t.min_loads_per_month),
          discount_pct: Number(t.discount_pct),
          rate_per_mile_floor: t.rate_per_mile_floor === "" ? null : Number(t.rate_per_mile_floor),
        })),
      };
      if (!payload.valid_to) delete payload.valid_to;
      Object.keys(payload).forEach((k) => (payload[k] === "" || payload[k] == null) && !["tiers", "base_rpm", "fuel_surcharge_pct"].includes(k) && delete payload[k]);
      await api.post("/shipper-relations/rate-cards", payload);
      toast.success("Rate card saved");
      onSaved?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  const updateTier = (idx, field, val) => {
    const t = [...form.tiers];
    t[idx] = { ...t[idx], [field]: val };
    setForm({ ...form, tiers: t });
  };
  const addTier = () => setForm({ ...form, tiers: [...form.tiers, { min_loads_per_month: 0, discount_pct: 0, rate_per_mile_floor: "" }] });
  const removeTier = (idx) => setForm({ ...form, tiers: form.tiers.filter((_, i) => i !== idx) });
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="rate-card-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">New Rate Card</DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Set base RPM + fuel surcharge + volume-discount tiers.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FF label="Name *"><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" data-testid="rate-card-name" /></FF>
          <FF label="Equipment">
            <select value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              {["Van", "Reefer", "Flatbed", "Power Only", "Step Deck"].map((e) => <option key={e}>{e}</option>)}
            </select>
          </FF>
          <FF label="Origin region"><Input value={form.origin_region} onChange={(e) => setForm({ ...form, origin_region: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Midwest, TX Triangle…" /></FF>
          <FF label="Dest region"><Input value={form.dest_region} onChange={(e) => setForm({ ...form, dest_region: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Base RPM ($/mi) *"><Input type="number" step="0.05" value={form.base_rpm}
            onChange={(e) => setForm({ ...form, base_rpm: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Fuel surcharge %"><Input type="number" step="0.5" value={form.fuel_surcharge_pct}
            onChange={(e) => setForm({ ...form, fuel_surcharge_pct: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Valid From *"><Input type="date" value={form.valid_from}
            onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Valid To"><Input type="date" value={form.valid_to}
            onChange={(e) => setForm({ ...form, valid_to: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Notes" className="md:col-span-2"><Textarea rows={2} value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="bg-black/40 border-white/10 text-xs" /></FF>
        </div>
        <div className="mt-2">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">Volume Tiers</div>
            <Button size="sm" variant="secondary" onClick={addTier}><Plus size={11} className="mr-1" />Tier</Button>
          </div>
          <div className="space-y-2">
            {form.tiers.map((t, i) => (
              <div key={i} className="grid grid-cols-4 gap-2 items-center" data-testid={`rate-card-tier-${i}`}>
                <Input type="number" placeholder="Min loads/mo" value={t.min_loads_per_month}
                  onChange={(e) => updateTier(i, "min_loads_per_month", e.target.value)}
                  className="bg-black/40 border-white/10 h-8 text-xs" />
                <Input type="number" step="0.5" placeholder="Discount %" value={t.discount_pct}
                  onChange={(e) => updateTier(i, "discount_pct", e.target.value)}
                  className="bg-black/40 border-white/10 h-8 text-xs" />
                <Input type="number" step="0.05" placeholder="RPM floor (optional)" value={t.rate_per_mile_floor}
                  onChange={(e) => updateTier(i, "rate_per_mile_floor", e.target.value)}
                  className="bg-black/40 border-white/10 h-8 text-xs" />
                <button onClick={() => removeTier(i)} className="text-red-400 hover:text-red-200 justify-self-start"><Trash2 size={12} /></button>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="rate-card-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save Rate Card
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     INCENTIVES TAB
// ============================================================
function IncentivesTab({ incentives, onChange }) {
  return (
    <div className="space-y-4">
      <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
        <Gift size={12} className="inline mr-1" /> {incentives.length} incentive programs · click <b>Seed</b> above if empty
      </div>
      {incentives.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <Gift size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No incentives yet — click <b>Seed Incentive Catalog</b> above to load the 11 canonical Orisei programs.</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="incentives-grid">
          {incentives.map((inc) => {
            const Icon = INCENTIVE_ICON[inc.kind] || Gift;
            return (
              <Card key={inc.incentive_id} className="p-4 bg-slate-900/60 border-white/10 space-y-2"
                data-testid={`incentive-${inc.incentive_id}`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-9 h-9 rounded-lg bg-amber-500/15 border border-amber-400/40 flex items-center justify-center">
                      <Icon size={16} className="text-amber-300" />
                    </div>
                    <div>
                      <div className="text-sm text-slate-100 font-medium">{inc.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">
                        {inc.kind.replace(/_/g, " ")}
                      </div>
                    </div>
                  </div>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full border font-mono ${
                    inc.active ? "border-emerald-400/40 text-emerald-300 bg-emerald-500/10" : "border-slate-500/40 text-slate-400"
                  }`}>
                    {inc.active ? "ACTIVE" : "INACTIVE"}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 leading-relaxed">{inc.description}</div>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {inc.threshold_loads != null && (
                    <div className="text-[10px] text-cyan-300 font-mono">
                      Threshold: {inc.threshold_loads} loads
                    </div>
                  )}
                  {inc.threshold_revenue_usd != null && (
                    <div className="text-[10px] text-cyan-300 font-mono">
                      Threshold: ${fmt(inc.threshold_revenue_usd)}
                    </div>
                  )}
                  <div className="text-[10px] text-amber-300 font-mono">
                    Reward: {inc.reward_type === "rebate_pct" ? `${inc.reward_value}%` :
                             inc.reward_type === "credit_usd" ? `$${inc.reward_value}` :
                             inc.reward_type === "guarantee" ? (inc.kind === "payment_terms" ? `Net-${inc.reward_value}` : "Guaranteed") :
                             inc.reward_type.replace("_", " ")}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono">Cadence: {inc.frequency}</div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================
//                     QBR TAB
// ============================================================
function QbrsTab({ accounts, onChange }) {
  const [selected, setSelected] = useState(accounts[0]?.account_id || "");
  const [qbrs, setQbrs] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    if (accounts.length && !selected) setSelected(accounts[0].account_id);
  }, [accounts, selected]);

  const load = useCallback(async () => {
    if (!selected) return;
    try {
      const { data } = await api.get(`/shipper-relations/accounts/${selected}/qbrs`);
      setQbrs(data.items || []);
    } catch (e) { /* no-op */ }
  }, [selected]);
  useEffect(() => { load(); }, [load]);

  if (!accounts.length) {
    return (
      <Card className="p-8 text-center bg-slate-900/60 border-white/10">
        <div className="text-xs text-slate-500">Add a shipper account first to record a QBR.</div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <Label className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">Account</Label>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}
          className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
          data-testid="qbr-account-select">
          {accounts.map((a) => <option key={a.account_id} value={a.account_id}>{a.company_name}</option>)}
        </select>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black ml-auto"
          data-testid="qbr-add-btn">
          <Plus size={13} className="mr-1" /> New QBR
        </Button>
      </div>

      {qbrs.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <TrendingUp size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No QBRs recorded for this account yet.</div>
        </Card>
      ) : (
        <div className="space-y-3">
          {qbrs.map((q) => <QbrCard key={q.qbr_id} qbr={q} />)}
        </div>
      )}

      <AddQbrDialog open={addOpen} onClose={() => setAddOpen(false)} accountId={selected}
        onSaved={() => { load(); onChange?.(); }} />
    </div>
  );
}

function QbrCard({ qbr }) {
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10 space-y-2" data-testid={`qbr-${qbr.qbr_id}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm text-slate-100 font-medium">{qbr.period}</div>
          <div className="text-[10px] text-slate-500 font-mono">
            Recorded {qbr.created_at?.slice(0, 10)} by {qbr.created_by}
          </div>
        </div>
        <div className="flex gap-2">
          {qbr.otd_pct != null && <Metric label="OTD" value={`${qbr.otd_pct}%`} target={95} />}
          {qbr.otp_pct != null && <Metric label="OTP" value={`${qbr.otp_pct}%`} target={98} />}
          {qbr.damage_free_pct != null && <Metric label="DMG-FREE" value={`${qbr.damage_free_pct}%`} target={99} />}
          {qbr.nps_score != null && <Metric label="NPS" value={qbr.nps_score} target={50} />}
        </div>
      </div>
      {qbr.strengths && (
        <div className="text-[11px] text-emerald-300/80 border-l-2 border-emerald-500/40 pl-2">
          <b>Strengths:</b> {qbr.strengths}
        </div>
      )}
      {qbr.gaps && (
        <div className="text-[11px] text-amber-300/80 border-l-2 border-amber-500/40 pl-2">
          <b>Gaps:</b> {qbr.gaps}
        </div>
      )}
      {(qbr.action_items || []).length > 0 && (
        <div className="text-[11px] text-cyan-300/80">
          <b>Action items:</b>
          <ul className="list-disc pl-4 mt-1">
            {qbr.action_items.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Metric({ label, value, target }) {
  const num = Number(String(value).replace("%", ""));
  const good = !isNaN(num) && num >= target;
  return (
    <div className="text-right">
      <div className="text-[9px] font-mono text-slate-500 uppercase tracking-widest">{label}</div>
      <div className={`text-sm font-mono ${good ? "text-emerald-300" : "text-amber-300"}`}>{value}</div>
    </div>
  );
}

function AddQbrDialog({ open, onClose, accountId, onSaved }) {
  const [form, setForm] = useState({
    period: "", otd_pct: "", otp_pct: "", damage_free_pct: "", volume_loads: "",
    revenue_usd: "", nps_score: "", strengths: "", gaps: "", action_items: "", next_review_date: "",
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.period.trim()) { toast.error("Period required"); return; }
    setBusy(true);
    try {
      const payload = { ...form };
      ["otd_pct", "otp_pct", "damage_free_pct", "volume_loads", "revenue_usd", "nps_score"].forEach((k) => {
        payload[k] = payload[k] === "" ? undefined : Number(payload[k]);
      });
      payload.action_items = form.action_items
        ? form.action_items.split("\n").map((s) => s.trim()).filter(Boolean)
        : undefined;
      Object.keys(payload).forEach((k) => (payload[k] === "" || payload[k] === undefined) && delete payload[k]);
      await api.post(`/shipper-relations/accounts/${accountId}/qbr`, payload);
      toast.success("QBR recorded");
      setForm({ ...form, period: "", strengths: "", gaps: "", action_items: "" });
      onSaved?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-2xl bg-slate-950 border-white/10 max-h-[90vh] overflow-y-auto"
        data-testid="qbr-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">Record Quarterly Business Review</DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Capture the scorecards plus action items for the next quarter.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FF label="Period *"><Input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })}
            placeholder="Q1 2026" className="bg-black/40 border-white/10 h-8 text-xs"
            data-testid="qbr-period" /></FF>
          <FF label="Next review date"><Input type="date" value={form.next_review_date}
            onChange={(e) => setForm({ ...form, next_review_date: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="OTD %"><Input type="number" step="0.1" value={form.otd_pct}
            onChange={(e) => setForm({ ...form, otd_pct: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="OTP %"><Input type="number" step="0.1" value={form.otp_pct}
            onChange={(e) => setForm({ ...form, otp_pct: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Damage-Free %"><Input type="number" step="0.1" value={form.damage_free_pct}
            onChange={(e) => setForm({ ...form, damage_free_pct: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="NPS score (-100 to 100)"><Input type="number" value={form.nps_score}
            onChange={(e) => setForm({ ...form, nps_score: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Volume (loads)"><Input type="number" value={form.volume_loads}
            onChange={(e) => setForm({ ...form, volume_loads: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Revenue (USD)"><Input type="number" value={form.revenue_usd}
            onChange={(e) => setForm({ ...form, revenue_usd: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" /></FF>
          <FF label="Strengths" className="md:col-span-2"><Textarea rows={2} value={form.strengths}
            onChange={(e) => setForm({ ...form, strengths: e.target.value })}
            className="bg-black/40 border-white/10 text-xs"
            placeholder="What went well this quarter?" /></FF>
          <FF label="Gaps" className="md:col-span-2"><Textarea rows={2} value={form.gaps}
            onChange={(e) => setForm({ ...form, gaps: e.target.value })}
            className="bg-black/40 border-white/10 text-xs"
            placeholder="What needs improvement?" /></FF>
          <FF label="Action items (one per line)" className="md:col-span-2"><Textarea rows={3} value={form.action_items}
            onChange={(e) => setForm({ ...form, action_items: e.target.value })}
            className="bg-black/40 border-white/10 text-xs"
            placeholder="Deploy EDI 214 status pings by Mar 15\nSchedule tire drop pilot on TX lanes" /></FF>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="qbr-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Record QBR
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     TMS INTEGRATIONS TAB
// ============================================================
function TmsTab({ accounts, onChange }) {
  const [selected, setSelected] = useState(accounts[0]?.account_id || "");
  const [tms, setTms] = useState([]);
  const [addOpen, setAddOpen] = useState(false);

  useEffect(() => {
    if (accounts.length && !selected) setSelected(accounts[0].account_id);
  }, [accounts, selected]);

  const load = useCallback(async () => {
    if (!selected) return;
    try {
      const { data } = await api.get(`/shipper-relations/accounts/${selected}/tms`);
      setTms(data.items || []);
    } catch (e) { /* no-op */ }
  }, [selected]);
  useEffect(() => { load(); }, [load]);

  const del = async (tms_id) => {
    if (!window.confirm("Delete this TMS integration?")) return;
    try {
      await api.delete(`/shipper-relations/accounts/${selected}/tms/${tms_id}`);
      toast.success("Removed");
      load(); onChange?.();
    } catch (e) { toast.error("Failed"); }
  };

  if (!accounts.length) {
    return (
      <Card className="p-8 text-center bg-slate-900/60 border-white/10">
        <div className="text-xs text-slate-500">Add a shipper account first to register their TMS.</div>
      </Card>
    );
  }

  const statusColor = { planned: "text-slate-400", in_test: "text-amber-300", live: "text-emerald-300", paused: "text-red-300" };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center">
        <Label className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">Account</Label>
        <select value={selected} onChange={(e) => setSelected(e.target.value)}
          className="bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
          data-testid="tms-account-select">
          {accounts.map((a) => <option key={a.account_id} value={a.account_id}>{a.company_name}</option>)}
        </select>
        <Button size="sm" onClick={() => setAddOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black ml-auto"
          data-testid="tms-add-btn">
          <Plus size={13} className="mr-1" /> Register TMS
        </Button>
      </div>

      {tms.length === 0 ? (
        <Card className="p-8 text-center bg-slate-900/60 border-white/10">
          <Plug size={22} className="mx-auto text-slate-600 mb-2" />
          <div className="text-xs text-slate-500">No TMS integrations registered for this shipper yet.</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {tms.map((t) => (
            <Card key={t.tms_id} className="p-4 bg-slate-900/60 border-white/10 space-y-2"
              data-testid={`tms-${t.tms_id}`}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-sm text-slate-100 font-medium">{t.system}</div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    {t.method.toUpperCase()} · <span className={statusColor[t.status] || ""}>{t.status.toUpperCase()}</span>
                  </div>
                </div>
                <button onClick={() => del(t.tms_id)} className="text-red-400 hover:text-red-200"
                  data-testid={`tms-del-${t.tms_id}`}><Trash2 size={12} /></button>
              </div>
              {t.endpoint && <div className="text-[11px] text-cyan-300 font-mono break-all">{t.endpoint}</div>}
              {t.contact_it && <div className="text-[11px] text-slate-400">IT: {t.contact_it}</div>}
              {t.notes && <div className="text-[10px] text-slate-500 italic">&ldquo;{t.notes}&rdquo;</div>}
            </Card>
          ))}
        </div>
      )}

      <AddTmsDialog open={addOpen} onClose={() => setAddOpen(false)} accountId={selected}
        onSaved={() => { load(); onChange?.(); }} />
    </div>
  );
}

function AddTmsDialog({ open, onClose, accountId, onSaved }) {
  const [form, setForm] = useState({
    system: "", method: "api", endpoint: "", contact_it: "", status: "planned", notes: "",
  });
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!form.system.trim()) { toast.error("System required"); return; }
    setBusy(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => payload[k] === "" && delete payload[k]);
      await api.post(`/shipper-relations/accounts/${accountId}/tms`, payload);
      toast.success("TMS registered");
      setForm({ system: "", method: "api", endpoint: "", contact_it: "", status: "planned", notes: "" });
      onSaved?.(); onClose?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-lg bg-slate-950 border-white/10" data-testid="tms-modal">
        <DialogHeader>
          <DialogTitle className="text-cyan-100">Register TMS Integration</DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Track the shipper&apos;s TMS platform + how we exchange tenders and status.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <FF label="System *">
            <Input value={form.system} onChange={(e) => setForm({ ...form, system: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs"
              placeholder="MercuryGate, SAP TM, Oracle OTM, McLeod, Descartes…"
              data-testid="tms-system" />
          </FF>
          <FF label="Method">
            <select value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="tms-method">
              <option value="api">API</option>
              <option value="edi">EDI (204/210/214)</option>
              <option value="portal">Portal</option>
              <option value="email">Email</option>
              <option value="sftp">SFTP</option>
            </select>
          </FF>
          <FF label="Endpoint URL">
            <Input value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs"
              placeholder="https://tms.acme.com/api/v2/tender" />
          </FF>
          <FF label="IT Contact">
            <Input value={form.contact_it} onChange={(e) => setForm({ ...form, contact_it: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </FF>
          <FF label="Status">
            <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100">
              <option value="planned">Planned</option>
              <option value="in_test">In Test</option>
              <option value="live">Live</option>
              <option value="paused">Paused</option>
            </select>
          </FF>
          <FF label="Notes">
            <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="bg-black/40 border-white/10 text-xs" />
          </FF>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black"
            data-testid="tms-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     SHARED UI PRIMS
// ============================================================
function BigKpi({ label, value, accent, icon: Icon, sub }) {
  return (
    <Card className="p-4 bg-slate-900/60 border-white/10">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
        {Icon && <Icon size={14} style={{ color: accent }} />}
      </div>
      <div className="text-2xl md:text-3xl font-mono mt-1" style={{ color: accent }}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
    </Card>
  );
}
function LifecyclePill({ v }) {
  const meta = LIFECYCLE_META[v] || LIFECYCLE_META.lead;
  return (
    <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase tracking-widest border ${meta.ring}`}>
      {meta.label}
    </span>
  );
}
function FF({ label, children, className }) {
  return (
    <div className={className}>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  );
}
function Loader() {
  return (
    <div className="p-8 text-center text-xs text-slate-500">
      <Loader2 size={16} className="animate-spin inline mr-2" /> Loading…
    </div>
  );
}
function fmt(n) {
  const v = Number(n) || 0;
  return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}
function fmtM(n) {
  const v = Number(n) || 0;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
}
