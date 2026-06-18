import React, { useEffect, useState, useCallback } from "react";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Wallet, TrendingUp, TrendingDown, Banknote, Building2, AlertTriangle,
  CheckCircle2, Sparkles, Zap, Target, Briefcase, Calculator, RefreshCw,
  ArrowRight, DollarSign, Copy, Shield, Activity,
} from "lucide-react";
import { toast } from "sonner";

/**
 * /cash-flow — Orisei Cash Flow Command Center.
 *
 * 8 modules from the user's spec, all on one high-tech HUD:
 *  1. Real-Time Cash Position (bank + AR + AP)
 *  2. Load Qualification (live decision tree)
 *  3. Auto-Route to Factor (best-rate engine)
 *  4. Shipper Payment Term Optimization
 *  5. Dynamic Carrier Discount Planner
 *  6. Factor comparison (re-used from /factoring)
 *  7. Shipper Credit Intelligence
 *  8. Scenario Planner
 */

const HEALTH_RING = {
  strong:   { color: "text-emerald-300", glow: "shadow-[0_0_28px_rgba(16,185,129,0.45)]", label: "STRONG" },
  healthy:  { color: "text-cyan-300",    glow: "shadow-[0_0_28px_rgba(6,182,212,0.4)]",   label: "HEALTHY" },
  tight:    { color: "text-amber-300",   glow: "shadow-[0_0_28px_rgba(245,158,11,0.45)]", label: "TIGHT" },
  critical: { color: "text-red-300",     glow: "shadow-[0_0_30px_rgba(239,68,68,0.55)]",  label: "CRITICAL" },
};

export default function CashFlow() {
  return (
    <>
      <Topbar
        title="Cash Flow · Command Center"
        subtitle="Live cash position · load qualification · auto-route · scenario planning"
      />
      <div className="p-4 md:p-6 grid grid-cols-12 gap-4">
        <Position />
        <LoadQualifier />
        <FactorProposals />
        <ShipperTermAnalysis />
        <DynamicDiscount />
        <ScenarioPlanner />
      </div>
    </>
  );
}

// =====================================================================
// 1. REAL-TIME CASH POSITION
// =====================================================================
function Position() {
  const [pos, setPos] = useState(null);
  const [editing, setEditing] = useState(false);
  const [bal, setBal] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/cash-flow/position");
      setPos(data);
      setBal(String(data.bank_balance_usd || ""));
    } catch (e) { toast.error("Could not load cash position"); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  const saveBalance = async () => {
    try {
      const { data } = await api.post("/cash-flow/bank-balance", {
        balance_usd: parseFloat(bal) || 0, source: "manual",
      });
      setPos(data); setEditing(false);
      toast.success("Bank balance updated");
    } catch (e) { toast.error("Could not save"); }
  };

  if (!pos) return <Card className="col-span-12 p-6 bg-slate-950/60 border-white/10 text-slate-500">Loading cash position…</Card>;

  const ring = HEALTH_RING[pos.health] || HEALTH_RING.healthy;

  return (
    <Card className={`col-span-12 p-5 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 border-2 ${pos.health === "critical" ? "border-red-400/40" : "border-amber-400/30"} relative overflow-hidden ${ring.glow}`}
          data-testid="cash-position">
      <div className="pointer-events-none absolute inset-0 opacity-[0.05]"
           style={{ backgroundImage: "linear-gradient(rgba(245,158,11,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(245,158,11,0.5) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />

      <div className="relative z-10 grid grid-cols-12 gap-4 items-center">
        {/* LEFT: bank balance (editable) */}
        <div className="col-span-12 lg:col-span-4">
          <div className="text-[10px] uppercase tracking-[0.3em] text-amber-300 font-mono mb-1">Live Bank Position</div>
          {!editing ? (
            <>
              <div className="flex items-baseline gap-3">
                <div className="text-5xl font-mono text-white tabular-nums" data-testid="bank-balance">
                  ${(pos.bank_balance_usd || 0).toLocaleString()}
                </div>
                <Button size="sm" variant="outline" onClick={() => setEditing(true)}
                        data-testid="edit-bank-btn"
                        className="bg-slate-900 border-white/10 h-7 text-[10px]">
                  Edit
                </Button>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                {pos.as_of_at ? `As of ${new Date(pos.as_of_at).toLocaleString()}` : "No balance set · click Edit"}
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 mt-2">
              <Input value={bal} type="number" min="0" step="0.01"
                     data-testid="bank-balance-input"
                     onChange={(e) => setBal(e.target.value)}
                     className="bg-slate-900 border-white/10 text-2xl font-mono w-48" />
              <Button onClick={saveBalance} data-testid="save-bank-btn"
                      className="bg-amber-500 text-slate-950 hover:bg-amber-400 h-9">
                Save
              </Button>
              <Button variant="outline" onClick={() => setEditing(false)}
                      className="bg-slate-900 border-white/10 h-9">Cancel</Button>
            </div>
          )}
          <div className={`mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${ring.color} bg-slate-950/70 border-current`}>
            <Activity size={12} />
            <span className="text-xs font-mono uppercase">{ring.label}</span>
          </div>
        </div>

        {/* CENTER: AR/AP cards */}
        <div className="col-span-12 lg:col-span-5 grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-400/30">
            <div className="flex items-center gap-1 text-[10px] uppercase tracking-widest text-emerald-300 font-mono">
              <TrendingUp size={11} /> Receivables
            </div>
            <div className="text-2xl font-mono text-white mt-1 tabular-nums" data-testid="ar-total">
              ${pos.accounts_receivable_usd.toLocaleString()}
            </div>
            <div className="text-[10px] text-emerald-400/70 mt-0.5">
              {pos.ar_invoice_count} open invoices · factorable ${pos.factorable_ar_usd.toLocaleString()}
            </div>
          </div>
          <div className="p-3 rounded-lg bg-red-950/30 border border-red-400/30">
            <div className="flex items-center gap-1 text-[10px] uppercase tracking-widest text-red-300 font-mono">
              <TrendingDown size={11} /> Payables
            </div>
            <div className="text-2xl font-mono text-white mt-1 tabular-nums" data-testid="ap-total">
              ${pos.accounts_payable_usd.toLocaleString()}
            </div>
            <div className="text-[10px] text-red-400/70 mt-0.5">
              {pos.ap_booking_count} bookings awaiting carrier pay
            </div>
          </div>
        </div>

        {/* RIGHT: Available */}
        <div className="col-span-12 lg:col-span-3 text-right">
          <div className="text-[10px] uppercase tracking-[0.3em] text-amber-300 font-mono mb-1">Deploy</div>
          <div className={`text-4xl font-mono tabular-nums ${pos.available_to_deploy_usd >= 0 ? "text-emerald-300" : "text-red-300"}`}
               data-testid="deploy-amount">
            ${pos.available_to_deploy_usd.toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            ≈ <b className="text-amber-300">{pos.loads_can_take}</b> load{pos.loads_can_take === 1 ? "" : "s"} at ${pos.carrier_cost_assumption_usd.toFixed(0)} carrier cost
          </div>
        </div>
      </div>
    </Card>
  );
}

// =====================================================================
// 2. LOAD QUALIFIER (auto-route to factor)
// =====================================================================
function LoadQualifier() {
  const [form, setForm] = useState({
    customer_rate_usd: 1500, carrier_cost_usd: 1050,
    payment_terms_days: 14, shipper_name: "Target",
  });
  const [verdict, setVerdict] = useState(null);
  const [routing, setRouting] = useState(false);
  const [route, setRoute] = useState(null);

  const qualify = async () => {
    try {
      const { data } = await api.post("/cash-flow/qualify-load", form);
      setVerdict(data); setRoute(null);
    } catch (e) { toast.error("Could not qualify"); }
  };
  const autoRoute = async () => {
    setRouting(true);
    try {
      const { data } = await api.post("/cash-flow/auto-route-factor", {
        invoice_usd: form.customer_rate_usd,
        carrier_cost_usd: form.carrier_cost_usd,
        payment_terms_days: form.payment_terms_days,
        shipper_credit_score: verdict?.shipper_credit?.score,
      });
      setRoute(data);
    } catch (e) { toast.error("Could not auto-route"); }
    finally { setRouting(false); }
  };

  const verdictColor = {
    emerald: "border-emerald-400/40 bg-emerald-950/30",
    cyan:    "border-cyan-400/40 bg-cyan-950/30",
    amber:   "border-amber-400/40 bg-amber-950/30",
    red:     "border-red-400/40 bg-red-950/30",
  };

  return (
    <Card className="col-span-12 lg:col-span-6 p-5 bg-slate-950/60 border-white/10" data-testid="load-qualifier">
      <div className="flex items-center gap-2 mb-4">
        <Target className="text-cyan-300" size={18} />
        <div className="text-sm font-semibold text-white">Load Qualifier</div>
        <Badge className="bg-cyan-500/15 text-cyan-200 border-cyan-400/30 text-[9px]">DAT INTERCEPT</Badge>
      </div>
      <p className="text-xs text-slate-400 mb-3">
        Paste a candidate load — instant verdict + auto-route to best factor.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Customer rate $" type="number" testid="ql-customer"
               value={form.customer_rate_usd}
               onChange={(v) => setForm({ ...form, customer_rate_usd: parseFloat(v) || 0 })} />
        <Field label="Carrier cost $" type="number" testid="ql-carrier"
               value={form.carrier_cost_usd}
               onChange={(v) => setForm({ ...form, carrier_cost_usd: parseFloat(v) || 0 })} />
        <Field label="Terms (days)" type="number" testid="ql-terms"
               value={form.payment_terms_days}
               onChange={(v) => setForm({ ...form, payment_terms_days: parseInt(v) || 14 })} />
        <Field label="Shipper name" testid="ql-shipper"
               value={form.shipper_name}
               onChange={(v) => setForm({ ...form, shipper_name: v })} />
      </div>
      <Button onClick={qualify} data-testid="ql-qualify-btn"
              className="w-full mt-3 bg-cyan-500 text-black hover:bg-cyan-400 font-semibold">
        <Zap size={14} className="mr-1.5" /> Qualify
      </Button>

      {verdict && (
        <div className={`mt-4 p-4 rounded-lg border ${verdictColor[verdict.verdict_color]}`} data-testid="ql-verdict">
          <div className="flex justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-400">Margin</div>
              <div className="text-2xl font-mono text-white">${verdict.forecast_margin_usd}</div>
              <div className="text-xs text-amber-300">{verdict.forecast_margin_pct}%</div>
            </div>
            {verdict.shipper_credit && (
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-widest text-slate-400">Shipper Credit</div>
                <div className="text-2xl font-mono text-white">{verdict.shipper_credit.tier}</div>
                <div className="text-xs text-slate-400">score {verdict.shipper_credit.score} · {verdict.shipper_credit.risk}</div>
              </div>
            )}
          </div>
          <ul className="space-y-1 mt-3">
            {verdict.actions.map((a, i) => (
              <li key={i} className="flex gap-2 text-xs text-slate-200">
                <ArrowRight size={12} className="flex-none text-cyan-300 mt-0.5" />
                <span>{a}</span>
              </li>
            ))}
          </ul>
          {verdict.shipper_credit?.recommendation && (
            <div className="text-[11px] text-slate-300 italic mt-2 border-t border-white/10 pt-2">
              {verdict.shipper_credit.recommendation}
            </div>
          )}
          {verdict.needs_factoring && (
            <Button onClick={autoRoute} disabled={routing}
                    data-testid="ql-auto-route-btn"
                    className="mt-3 w-full bg-amber-500 text-slate-950 hover:bg-amber-400 font-semibold">
              {routing ? <RefreshCw size={14} className="mr-1.5 animate-spin" /> : <Banknote size={14} className="mr-1.5" />}
              Auto-route to best factor
            </Button>
          )}
        </div>
      )}

      {route?.best && (
        <div className="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-400/40">
          <div className="text-[10px] uppercase tracking-widest text-amber-300 font-mono">
            Best factor for this invoice
          </div>
          <div className="flex justify-between items-baseline mt-1">
            <div className="text-base font-semibold text-white">{route.best.name}</div>
            <div className="text-xl font-mono text-amber-300">{route.best.fee_pct}%</div>
          </div>
          <div className="text-xs text-slate-300 mt-1">
            Advance ${route.best.advance_usd.toLocaleString()} ·
            Fee ${route.best.fee_usd.toLocaleString()} ·
            <span className={route.broker_take_home_usd >= 0 ? "text-emerald-300" : "text-red-300"}>
              {" "}take-home ${route.broker_take_home_usd}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}

// =====================================================================
// 3. FACTOR PROPOSALS (from auto-route hook)
// =====================================================================
function FactorProposals() {
  const [items, setItems] = useState([]);
  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/cash-flow/factor-proposals");
      setItems(data.items || []);
    } catch { /* ignore */ }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <Card className="col-span-12 lg:col-span-6 p-5 bg-slate-950/60 border-white/10" data-testid="proposal-feed">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="text-amber-300" size={18} />
          <div className="text-sm font-semibold text-white">Auto-Routed Proposals</div>
        </div>
        <Button size="sm" variant="outline" onClick={load} className="bg-slate-900 border-white/10 h-7 text-xs">
          <RefreshCw size={11} className="mr-1" /> Refresh
        </Button>
      </div>
      <p className="text-xs text-slate-400 mb-3">
        The moment you mark a load <b className="text-cyan-300">Carrier Assigned</b> in the Workflow HUD,
        we score every factor and queue the cheapest one here for one-tap submission.
      </p>
      {!items.length && (
        <div className="text-center text-slate-500 py-8 text-xs">
          No proposals yet. Mark a booking <b>Carrier Assigned</b> on <a href="/workflow" className="text-cyan-300 hover:underline">/workflow</a> to populate.
        </div>
      )}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {items.map(p => (
          <div key={p.booked_id} data-testid={`proposal-${p.booked_id}`}
               className="p-3 rounded-lg bg-slate-900/60 border border-white/5">
            <div className="flex justify-between items-start">
              <div className="min-w-0">
                <div className="font-mono text-cyan-200 text-xs">{p.booked_id}</div>
                <div className="text-sm text-white truncate">{p.shipper_name || "—"}</div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  ${p.invoice_usd?.toLocaleString()} · {p.payment_terms_days}d terms
                </div>
              </div>
              {p.shipper_credit && (
                <Badge variant="outline" className="border-amber-400/30 text-amber-300 text-[9px]">
                  {p.shipper_credit.tier} · {p.shipper_credit.score}
                </Badge>
              )}
            </div>
            {p.best_factor && (
              <div className="mt-2 p-2 rounded bg-amber-500/10 border border-amber-400/30">
                <div className="flex justify-between items-baseline">
                  <span className="text-amber-200 text-sm font-semibold">{p.best_factor.name}</span>
                  <span className="font-mono text-amber-300 text-sm">{p.best_factor.fee_pct}%</span>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Advance ${p.best_factor.advance_usd?.toLocaleString()} ·
                  Setup {p.best_factor.setup_time_days}d
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// =====================================================================
// 4. SHIPPER PAYMENT TERM ANALYSIS
// =====================================================================
function ShipperTermAnalysis() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);
  const [pitch, setPitch] = useState(null);

  useEffect(() => {
    api.get("/cash-flow/shipper-term-analysis").then(({ data }) => setData(data)).catch(() => {});
  }, []);

  const draftPitch = async (cust) => {
    setOpen(cust); setPitch(null);
    try {
      // Look up customer_id from name via /orisei/customers
      const { data: custs } = await api.get("/orisei/customers");
      const match = (custs.items || []).find(c => c.name === cust.customer_name);
      if (!match) {
        toast.info("Customer not in CRM yet — open Brokerage settings to add them first");
        setPitch({ subject: "Customer not in CRM",
                   body: `Add "${cust.customer_name}" to your CRM first via /broker-settings → Invoices section.`,
                   monthly_invoice_usd: 0 });
        return;
      }
      const { data } = await api.post("/cash-flow/shipper-pitch", {
        customer_id: match.customer_id,
        current_terms: cust.current_terms || "Net 30",
        proposed_terms: "Net 7",
        discount_offer_pct: 2.0,
        loads_per_month: cust.loads,
        avg_invoice_usd: cust.revenue_usd / cust.loads,
      });
      setPitch(data);
    } catch (e) { toast.error("Could not draft pitch"); }
  };

  return (
    <Card className="col-span-12 lg:col-span-6 p-5 bg-slate-950/60 border-white/10" data-testid="term-analysis">
      <div className="flex items-center gap-2 mb-3">
        <Briefcase className="text-cyan-300" size={18} />
        <div className="text-sm font-semibold text-white">Shipper Payment-Term Optimization</div>
      </div>
      {data && (
        <div className="mb-3 p-3 rounded-lg bg-emerald-950/30 border border-emerald-400/30">
          <div className="flex justify-between items-baseline">
            <div className="text-[10px] uppercase tracking-widest text-emerald-300 font-mono">Annualized savings if all move to Net 7</div>
            <div className="text-2xl font-mono text-white" data-testid="term-savings">
              ${(data.total_potential_savings_usd * 12).toLocaleString()}
            </div>
          </div>
          <div className="text-[11px] text-emerald-400/70 mt-0.5">
            {data.candidate_count} candidate shippers · ${data.total_potential_savings_usd.toLocaleString()}/mo
          </div>
        </div>
      )}
      <div className="space-y-1.5 max-h-72 overflow-y-auto">
        {data?.candidates?.slice(0, 10).map((c, i) => (
          <div key={i} className="flex items-center gap-2 p-2 rounded bg-slate-900/60 border border-white/5">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-white truncate">{c.customer_name}</div>
              <div className="text-[10px] text-slate-400">
                {c.loads} loads · {c.current_terms || "Net 30"}
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs font-mono text-amber-300">${c.potential_savings_usd.toLocaleString()}/mo</div>
              {c.candidate && (
                <Button size="sm" variant="outline" onClick={() => draftPitch(c)}
                        data-testid={`pitch-${i}`}
                        className="bg-slate-900 border-white/10 h-6 text-[10px] mt-1">
                  Draft pitch
                </Button>
              )}
            </div>
          </div>
        ))}
        {!data?.candidates?.length && (
          <div className="text-center text-slate-500 py-6 text-xs">
            No shippers tracked yet. Book some loads to populate.
          </div>
        )}
      </div>

      <Dialog open={!!open} onOpenChange={() => { setOpen(null); setPitch(null); }}>
        <DialogContent className="bg-slate-950 border-amber-400/30 text-white max-w-2xl">
          <DialogHeader>
            <DialogTitle>Pitch · {open?.customer_name}</DialogTitle>
          </DialogHeader>
          {pitch && (
            <div className="space-y-3">
              {pitch.win_win !== undefined && (
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded bg-slate-900 border border-white/10">
                    <div className="text-[9px] uppercase text-slate-400">Shipper saves</div>
                    <div className="text-base font-mono text-emerald-300">${pitch.shipper_savings_usd?.toLocaleString()}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-white/10">
                    <div className="text-[9px] uppercase text-slate-400">You save (factor)</div>
                    <div className="text-base font-mono text-cyan-300">${pitch.broker_factor_savings_usd?.toLocaleString()}</div>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-white/10">
                    <div className="text-[9px] uppercase text-slate-400">Net to broker</div>
                    <div className={`text-base font-mono ${pitch.net_broker_gain_usd >= 0 ? "text-amber-300" : "text-red-300"}`}>
                      ${pitch.net_broker_gain_usd?.toLocaleString()}
                    </div>
                  </div>
                </div>
              )}
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Subject</Label>
                <Input value={pitch.subject} readOnly className="bg-slate-900 border-white/10 text-amber-200" />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Body</Label>
                <textarea value={pitch.body} readOnly
                          className="w-full bg-slate-900 border border-white/10 rounded p-2 font-mono text-xs min-h-[240px]" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setOpen(null); setPitch(null); }} className="bg-slate-900 border-white/10">Close</Button>
            <Button onClick={() => { navigator.clipboard.writeText(pitch?.body || ""); toast.success("Copied"); }}
                    className="bg-amber-500 text-slate-950 hover:bg-amber-400">
              <Copy size={14} className="mr-1.5" /> Copy
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// =====================================================================
// 5. DYNAMIC CARRIER DISCOUNT
// =====================================================================
function DynamicDiscount() {
  const [form, setForm] = useState({
    waiting_carriers_usd: 15000, available_cash_usd: 10000, proposed_discount_pct: 5,
  });
  const [result, setResult] = useState(null);
  const calc = useCallback(async () => {
    try {
      const { data } = await api.post("/cash-flow/dynamic-discount", form);
      setResult(data);
    } catch { /* ignore */ }
  }, [form]);
  useEffect(() => { calc(); }, [calc]);

  return (
    <Card className="col-span-12 lg:col-span-6 p-5 bg-slate-950/60 border-white/10" data-testid="dynamic-discount">
      <div className="flex items-center gap-2 mb-3">
        <Zap className="text-emerald-300" size={18} />
        <div className="text-sm font-semibold text-white">Dynamic Carrier Discount</div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Waiting carriers $" type="number" testid="dd-waiting"
               value={form.waiting_carriers_usd}
               onChange={(v) => setForm({ ...form, waiting_carriers_usd: parseFloat(v) || 0 })} />
        <Field label="Available cash $" type="number" testid="dd-cash"
               value={form.available_cash_usd}
               onChange={(v) => setForm({ ...form, available_cash_usd: parseFloat(v) || 0 })} />
        <Field label="Discount %" type="number" testid="dd-pct"
               value={form.proposed_discount_pct}
               onChange={(v) => setForm({ ...form, proposed_discount_pct: parseFloat(v) || 0 })} />
      </div>
      {result && (
        <>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <Mini label="Total potential save" v={`$${result.total_discount_savings_usd.toLocaleString()}`} c="text-emerald-300" />
            <Mini label="Expected outlay (70% accept)" v={`$${result.expected_cash_outlay_usd.toLocaleString()}`} c="text-cyan-300" />
            <Mini label="Coverage ratio" v={`${result.coverage_ratio}×`} c={result.can_cover_expected ? "text-emerald-300" : "text-red-300"} />
            <Mini label="Working capital cut" v={`${result.broker_save_pct_of_total}%`} c="text-amber-300" />
          </div>
          <div className={`mt-3 p-3 rounded-lg border ${result.can_cover_expected ? "bg-emerald-950/30 border-emerald-400/30" : "bg-red-950/30 border-red-400/30"}`}>
            <div className="text-xs text-white font-semibold">
              {result.can_cover_expected
                ? "✓ You can fund this · run the discount."
                : "Even with discounts you're short — open recourse factoring on a few invoices first."}
            </div>
            <div className="text-[11px] text-slate-300 italic mt-1">
              Carrier pitch: &ldquo;{result.carrier_pitch}&rdquo;
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

// =====================================================================
// 6. SCENARIO PLANNER
// =====================================================================
function ScenarioPlanner() {
  const [form, setForm] = useState({
    target_loads_per_week: 200, avg_invoice_usd: 1280,
    avg_margin_usd_per_load: 230, payment_terms_days: 14,
    hire_dispatcher: false, dispatcher_monthly_cost_usd: 5500,
  });
  const [result, setResult] = useState(null);
  const calc = useCallback(async () => {
    try {
      const { data } = await api.post("/cash-flow/scenario", form);
      setResult(data);
    } catch { /* ignore */ }
  }, [form]);
  useEffect(() => { calc(); }, [calc]);

  return (
    <Card className="col-span-12 p-5 bg-slate-950/60 border-amber-400/20" data-testid="scenario-planner">
      <div className="flex items-center gap-2 mb-3">
        <Calculator className="text-amber-300" size={18} />
        <div className="text-sm font-semibold text-white">Growth Scenario Planner</div>
        <Badge className="bg-amber-500/15 text-amber-200 border-amber-400/30 text-[9px]">REAL NUMBERS · NO GUESSES</Badge>
      </div>
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 md:col-span-5 grid grid-cols-2 gap-2">
          <Field label="Target loads/wk" type="number" testid="sc-loads"
                 value={form.target_loads_per_week}
                 onChange={(v) => setForm({ ...form, target_loads_per_week: parseInt(v) || 0 })} />
          <Field label="Avg invoice $" type="number"
                 value={form.avg_invoice_usd}
                 onChange={(v) => setForm({ ...form, avg_invoice_usd: parseFloat(v) || 0 })} />
          <Field label="Avg margin $/load" type="number"
                 value={form.avg_margin_usd_per_load}
                 onChange={(v) => setForm({ ...form, avg_margin_usd_per_load: parseFloat(v) || 0 })} />
          <Field label="Terms (days)" type="number"
                 value={form.payment_terms_days}
                 onChange={(v) => setForm({ ...form, payment_terms_days: parseInt(v) || 14 })} />
          <label className="col-span-2 flex items-center gap-2 text-xs text-slate-300 mt-1">
            <input type="checkbox" checked={form.hire_dispatcher}
                   data-testid="sc-hire-dispatch"
                   onChange={(e) => setForm({ ...form, hire_dispatcher: e.target.checked })} />
            Add a dispatcher
          </label>
          {form.hire_dispatcher && (
            <Field label="Dispatcher $/mo" type="number"
                   value={form.dispatcher_monthly_cost_usd}
                   onChange={(v) => setForm({ ...form, dispatcher_monthly_cost_usd: parseFloat(v) || 0 })} />
          )}
        </div>
        {result && (
          <div className="col-span-12 md:col-span-7">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <Mini label="Monthly loads" v={result.monthly_loads.toLocaleString()} c="text-white" />
              <Mini label="Gross margin / mo" v={`$${result.gross_margin_usd_monthly.toLocaleString()}`} c="text-emerald-300" />
              <Mini label="Working capital req" v={`$${result.working_capital_required_usd.toLocaleString()}`} c="text-amber-300" />
              <Mini label="Net after funding" v={`$${result.net_margin_after_funding_usd.toLocaleString()}`} c="text-cyan-300" />
            </div>
            <Card className="p-3 bg-amber-500/10 border-amber-400/30">
              <div className="text-[10px] uppercase tracking-widest text-amber-300 font-mono">Recommended Funding</div>
              <div className="text-lg text-white font-semibold mt-1" data-testid="sc-best-method">
                {result.best_funding_method}
              </div>
              <div className="text-xs text-slate-300 mt-1">
                Cost ${result.funding_cost_usd.toLocaleString()}/mo (vs ${(result.gross_margin_usd_monthly / 100 * 21).toLocaleString()}/mo on Spot)
                {form.hire_dispatcher && ` · dispatcher $${result.dispatcher_monthly_cost_usd.toLocaleString()}/mo deducted`}
              </div>
            </Card>
          </div>
        )}
      </div>
    </Card>
  );
}

// ----- Helpers -----
function Field({ label, value, onChange, type = "text", testid }) {
  return (
    <div>
      <Label className="text-[10px] uppercase tracking-widest text-slate-400">{label}</Label>
      <Input
        data-testid={testid} type={type} value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="bg-slate-900 border-white/10 text-white"
      />
    </div>
  );
}

function Mini({ label, v, c = "text-white" }) {
  return (
    <div className="p-2 rounded bg-slate-900/60 border border-white/5">
      <div className="text-[9px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`text-base font-mono mt-0.5 tabular-nums ${c}`}>{v}</div>
    </div>
  );
}
