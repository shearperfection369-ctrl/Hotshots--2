import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import {
  Rocket, Radio, Loader2, CheckCircle2, XCircle, Clock, Zap, Cpu,
  Truck, Award, DollarSign, TrendingUp, Users, Settings2, Play,
  ChevronDown, ChevronRight, MessageSquare, Mail, AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

/**
 * DispatchAutopilot — real-time rule-based load-matching engine console.
 *
 *   Live Feed     · streaming autopilot events + last N matches
 *   Carriers      · CRUD grid of the availability matrix
 *   Offer Pipeline· kanban-style (Pending → Accepted / Declined / Expired)
 *   Dashboard     · KPI HUD (accept rate, avg TTB, margin captured, offers/hr)
 */
export default function DispatchAutopilot() {
  const [tab, setTab] = useState("feed");
  return (
    <div className="p-4 space-y-4 min-h-screen bg-slate-950" data-testid="dispatch-autopilot-root">
      <header className="flex items-end justify-between border-b border-white/10 pb-3">
        <div>
          <h1 className="text-2xl font-mono tracking-widest text-cyan-100 uppercase flex items-center gap-2">
            <Rocket size={20} className="text-cyan-400" /> Dispatch Autopilot
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time load-matching · rule-based v1 · SMS/email mocked · offers logged for ML training.
          </p>
        </div>
        <div className="flex gap-2">
          {[
            { id: "feed",     label: "Live Feed",     icon: Radio },
            { id: "carriers", label: "Carriers",      icon: Users },
            { id: "offers",   label: "Offer Pipeline", icon: Zap },
            { id: "ml",       label: "ML Console",    icon: Cpu },
            { id: "dash",     label: "Dashboard",     icon: TrendingUp },
            { id: "cfg",      label: "Autopilot Cfg", icon: Settings2 },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`da-tab-${id}`}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded text-[11px] font-mono uppercase tracking-widest border transition ${
                tab === id
                  ? "bg-cyan-500/15 border-cyan-400 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.25)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-100"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
      </header>
      {tab === "feed"     && <FeedView />}
      {tab === "carriers" && <CarriersView />}
      {tab === "offers"   && <OffersView />}
      {tab === "ml"       && <MlConsoleView />}
      {tab === "dash"     && <DashView />}
      {tab === "cfg"      && <ConfigView />}
    </div>
  );
}

// ============================================================
//                    LIVE FEED (tick + latest offers)
// ============================================================
function FeedView() {
  const [offers, setOffers] = useState([]);
  const [lastCycle, setLastCycle] = useState(null);
  const [dash, setDash] = useState(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    const [o, d] = await Promise.all([
      api.get("/dispatch/offers?limit=20"),
      api.get("/dispatch/dashboard"),
    ]);
    setOffers(o.data.items || []);
    setDash(d.data);
  }, []);
  useEffect(() => { load(); }, [load]);

  const runTick = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/dispatch/tick");
      setLastCycle(data);
      toast.success(`Cycle · ${data.offers_sent} offers fired · ${data.loads_touched}/${data.loads_fresh} loads matched`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Tick failed");
    } finally { setBusy(false); }
  };
  const accept  = async (id) => { await api.post(`/dispatch/offers/${id}/accept`); toast.success("Accepted"); load(); };
  const decline = async (id) => { await api.post(`/dispatch/offers/${id}/decline`); toast.success("Declined"); load(); };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Carriers active" value={dash?.carriers_active ?? "—"} color="#22D3EE" icon={Users} />
        <KpiTile label="Offers · last hr"  value={dash?.offers_last_hour ?? 0} color="#10B981" icon={Zap} />
        <KpiTile label="Accept rate"       value={`${dash?.acceptance_rate_pct ?? 0}%`} color="#F59E0B" icon={Award} />
        <KpiTile label="Avg time-to-book"  value={`${dash?.avg_time_to_book_sec ?? 0}s`} color="#A78BFA" icon={Clock} />
        <KpiTile label="Margin captured"   value={`$${(dash?.margin_captured_usd || 0).toLocaleString()}`} color="#F472B6" icon={DollarSign} />
      </div>

      <Card className="p-3 bg-slate-900/60 border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`h-2 w-2 rounded-full ${dash?.config?.autopilot_enabled ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
          <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
            Autopilot {dash?.config?.autopilot_enabled ? "ARMED" : "IDLE"}
            &nbsp;·&nbsp;top-{dash?.config?.top_n_carriers_per_load} · ≥${dash?.config?.min_margin_usd} margin · ≥{dash?.config?.min_match_score} score
          </span>
        </div>
        <Button onClick={runTick} disabled={busy}
          className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="da-run-tick">
          {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <Play size={13} className="mr-1" />}
          Run Autopilot Cycle
        </Button>
      </Card>

      {lastCycle && (
        <Card className="p-3 bg-emerald-500/5 border-emerald-500/30 text-xs" data-testid="da-last-cycle">
          <div className="font-mono text-emerald-300 uppercase text-[10px] tracking-widest mb-1">Last cycle</div>
          <div className="text-slate-200 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>Loads scanned: <b>{lastCycle.loads_scanned}</b></div>
            <div>Loads fresh: <b>{lastCycle.loads_fresh}</b></div>
            <div>Loads matched: <b className="text-emerald-300">{lastCycle.loads_touched}</b></div>
            <div>Offers sent: <b className="text-cyan-300">{lastCycle.offers_sent}</b></div>
          </div>
        </Card>
      )}

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <Radio size={12} className="inline mr-1" /> latest offers stream ({offers.length})
        </div>
        <div className="divide-y divide-white/5" data-testid="da-feed-stream">
          {offers.map((o) => (
            <div key={o.offer_id} className="px-3 py-3 hover:bg-white/[0.02]"
              data-testid={`da-feed-row-${o.offer_id}`}>
              <div className="flex items-center gap-3">
                <button onClick={() => setExpanded(expanded === o.offer_id ? null : o.offer_id)}
                  className="text-slate-500">
                  {expanded === o.offer_id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
                <StatusPill status={o.status} />
                <ScoreChip score={o.match_score} />
                <div className="flex-1 min-w-0">
                  <div className="text-slate-100 font-mono text-xs truncate">
                    {o.origin} → {o.destination}
                    <span className="text-slate-500 mx-2">·</span>
                    <span className="text-cyan-300">{o.equipment}</span>
                    <span className="text-slate-500 mx-2">·</span>
                    <span className="text-slate-400">{o.miles} mi</span>
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                    → {o.carrier_name} · {o.carrier_contact_name}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-emerald-300 font-mono">${o.offer_amount_usd?.toFixed?.(0)}</div>
                  <div className="text-[10px] text-amber-300 font-mono">
                    +${o.margin_usd?.toFixed?.(0)} ({o.margin_pct?.toFixed?.(1)}%)
                  </div>
                </div>
                {o.status === "pending" && (
                  <div className="flex gap-1">
                    <Button size="sm" onClick={() => accept(o.offer_id)}
                      className="bg-emerald-500 hover:bg-emerald-400 text-black h-7"
                      data-testid={`da-accept-${o.offer_id}`}>
                      <CheckCircle2 size={11} />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => decline(o.offer_id)}
                      className="text-red-400 hover:text-red-200 h-7"
                      data-testid={`da-decline-${o.offer_id}`}>
                      <XCircle size={11} />
                    </Button>
                  </div>
                )}
              </div>
              {expanded === o.offer_id && (
                <div className="mt-3 pl-8 grid md:grid-cols-2 gap-3 text-[11px]">
                  <div>
                    <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Score breakdown</div>
                    <div className="space-y-0.5">
                      {Object.entries(o.score_breakdown || {}).map(([k, v]) => (
                        <div key={k} className="flex justify-between font-mono text-slate-300">
                          <span className="text-slate-500">{k.replace(/_/g, " ")}</span>
                          <span>{v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Delivery receipts</div>
                    {o.deliveries?.sms && (
                      <div className="flex items-center gap-2 text-slate-300"><MessageSquare size={11} className="text-cyan-400" /> SMS · {o.deliveries.sms.status} · {o.deliveries.sms.sid?.slice(0, 20)}…</div>
                    )}
                    {o.deliveries?.email && (
                      <div className="flex items-center gap-2 text-slate-300 mt-1"><Mail size={11} className="text-emerald-400" /> Email · {o.deliveries.email.status} · {o.deliveries.email.id?.slice(0, 20)}…</div>
                    )}
                    {!o.deliveries?.sms && !o.deliveries?.email && <div className="text-slate-500">No deliveries</div>}
                  </div>
                </div>
              )}
            </div>
          ))}
          {!offers.length && (
            <div className="p-8 text-center text-slate-500 text-xs">
              No offers yet. Click <b>Run Autopilot Cycle</b> to fire the engine.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//                    CARRIERS MATRIX
// ============================================================
function CarriersView() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [creating, setCreating] = useState(false);
  const empty = {
    legal_name: "", mc_number: "", contact_name: "", contact_phone: "", contact_email: "",
    equipment_types: ["Van"], max_weight_lbs: 45000, service_states: [], insurance_cargo_usd: 100000,
    insurance_covers_hazmat: false, insurance_covers_reefer: true, home_base_state: "",
    rate_expectation_per_mile: 2.15, on_time_pct: 90, damage_rate_pct: 1.0,
    historical_acceptance_pct: 65, days_idle: 0, is_active: true,
  };
  const [form, setForm] = useState(empty);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/dispatch/carriers");
      setRows(data.items || []);
    } catch { toast.error("Failed to load carriers"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const seed = async () => {
    try { await api.post("/dispatch/carriers/seed"); toast.success("Seeded"); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Seed failed"); }
  };
  const save = async () => {
    if (!form.legal_name || !form.contact_email) { toast.error("Legal name + email required"); return; }
    try {
      const payload = {
        ...form,
        service_states: Array.isArray(form.service_states) ? form.service_states
          : String(form.service_states || "").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean),
        equipment_types: Array.isArray(form.equipment_types) ? form.equipment_types
          : String(form.equipment_types || "").split(",").map((s) => s.trim()).filter(Boolean),
      };
      await api.post("/dispatch/carriers", payload);
      toast.success("Carrier saved"); setCreating(false); setEditing(null); setForm(empty); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };
  const retire = async (id) => {
    try { await api.delete(`/dispatch/carriers/${id}`); toast.success("Retired"); load(); }
    catch (e) { toast.error("Retire failed"); }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2 justify-end">
        {!rows.length && (
          <Button onClick={seed} className="bg-amber-500 hover:bg-amber-400 text-black" data-testid="da-seed-carriers">
            Seed demo fleet
          </Button>
        )}
        <Button onClick={() => { setCreating(true); setForm(empty); }}
          className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="da-add-carrier">
          + Add carrier
        </Button>
      </div>

      {(creating || editing) && (
        <Card className="p-4 bg-cyan-500/5 border-cyan-500/30 space-y-2" data-testid="da-carrier-form">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Field label="Legal name *"><Input value={form.legal_name} onChange={(e) => setForm({...form, legal_name: e.target.value})} className="bg-black/40 border-white/10 h-8 text-xs" data-testid="da-carrier-name" /></Field>
            <Field label="MC number"><Input value={form.mc_number} onChange={(e) => setForm({...form, mc_number: e.target.value})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Contact name"><Input value={form.contact_name} onChange={(e) => setForm({...form, contact_name: e.target.value})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Contact email *"><Input value={form.contact_email} onChange={(e) => setForm({...form, contact_email: e.target.value})} className="bg-black/40 border-white/10 h-8 text-xs" data-testid="da-carrier-email" /></Field>
            <Field label="Contact phone"><Input value={form.contact_phone} onChange={(e) => setForm({...form, contact_phone: e.target.value})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Equipment (CSV)"><Input value={form.equipment_types.join(",")} onChange={(e) => setForm({...form, equipment_types: e.target.value.split(",").map(s => s.trim())})} className="bg-black/40 border-white/10 h-8 text-xs" placeholder="Van,Reefer" /></Field>
            <Field label="Service states (CSV)"><Input value={form.service_states.join(",")} onChange={(e) => setForm({...form, service_states: e.target.value.split(",").map(s => s.trim().toUpperCase())})} className="bg-black/40 border-white/10 h-8 text-xs" placeholder="TX,OK,AR" /></Field>
            <Field label="Max weight (lbs)"><Input type="number" value={form.max_weight_lbs} onChange={(e) => setForm({...form, max_weight_lbs: Number(e.target.value)})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Rate/mile ask $"><Input type="number" step="0.01" value={form.rate_expectation_per_mile} onChange={(e) => setForm({...form, rate_expectation_per_mile: Number(e.target.value)})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="On-time %"><Input type="number" value={form.on_time_pct} onChange={(e) => setForm({...form, on_time_pct: Number(e.target.value)})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Damage %"><Input type="number" step="0.1" value={form.damage_rate_pct} onChange={(e) => setForm({...form, damage_rate_pct: Number(e.target.value)})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
            <Field label="Accept-hist %"><Input type="number" value={form.historical_acceptance_pct} onChange={(e) => setForm({...form, historical_acceptance_pct: Number(e.target.value)})} className="bg-black/40 border-white/10 h-8 text-xs" /></Field>
          </div>
          <div className="flex items-center gap-4 pt-1">
            <label className="text-xs text-slate-300 flex items-center gap-2">
              <input type="checkbox" checked={form.insurance_covers_hazmat} onChange={(e) => setForm({...form, insurance_covers_hazmat: e.target.checked})} /> hazmat insured
            </label>
            <label className="text-xs text-slate-300 flex items-center gap-2">
              <input type="checkbox" checked={form.insurance_covers_reefer} onChange={(e) => setForm({...form, insurance_covers_reefer: e.target.checked})} /> reefer insured
            </label>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={() => { setCreating(false); setEditing(null); setForm(empty); }}>Cancel</Button>
            <Button onClick={save} className="bg-emerald-500 hover:bg-emerald-400 text-black" data-testid="da-carrier-save">Save</Button>
          </div>
        </Card>
      )}

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300 flex justify-between">
          <span><Users size={12} className="inline mr-1" /> {rows.length} carriers in matrix</span>
          {busy && <Loader2 size={12} className="animate-spin" />}
        </div>
        <table className="w-full text-xs" data-testid="da-carriers-table">
          <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">Carrier</th>
              <th className="px-3 py-2 text-left">Equipment</th>
              <th className="px-3 py-2 text-left">Service Area</th>
              <th className="px-3 py-2 text-right">Rate/mi ask</th>
              <th className="px-3 py-2 text-right">On-time</th>
              <th className="px-3 py-2 text-right">Idle days</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.carrier_id} className="border-t border-white/5" data-testid={`da-carrier-row-${c.carrier_id}`}>
                <td className="px-3 py-2 text-slate-200">{c.legal_name}
                  <div className="text-[9px] text-slate-500 font-mono">{c.mc_number} · {c.contact_name}</div></td>
                <td className="px-3 py-2 text-cyan-300 font-mono text-[11px]">{(c.equipment_types || []).join(" · ")}</td>
                <td className="px-3 py-2 text-slate-400 font-mono text-[10px]">{(c.service_states || []).slice(0, 6).join(", ")}{(c.service_states || []).length > 6 ? "…" : ""}</td>
                <td className="px-3 py-2 text-right text-emerald-300 font-mono">${c.rate_expectation_per_mile?.toFixed?.(2)}</td>
                <td className="px-3 py-2 text-right font-mono">
                  <span className={c.on_time_pct >= 92 ? "text-emerald-400" : c.on_time_pct >= 85 ? "text-amber-400" : "text-red-400"}>
                    {c.on_time_pct?.toFixed?.(1)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  <Badge variant="outline" className={c.days_idle >= 3 ? "border-amber-500/40 text-amber-300" : "border-slate-500/40 text-slate-400"}>
                    {c.days_idle}d
                  </Badge>
                </td>
                <td className="px-3 py-2 text-right">
                  <Button size="sm" variant="ghost" onClick={() => retire(c.carrier_id)}
                    className="text-red-400 hover:text-red-200 h-7"
                    data-testid={`da-retire-${c.carrier_id}`}>Retire</Button>
                </td>
              </tr>
            ))}
            {!rows.length && !busy && (
              <tr><td colSpan={7} className="p-8 text-center text-slate-500">
                No carriers yet. Click <b>Seed demo fleet</b> to get started.
              </td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ============================================================
//                    OFFER PIPELINE (kanban)
// ============================================================
function OffersView() {
  const [offers, setOffers] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/dispatch/offers?limit=200");
      setOffers(data.items || []);
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const cols = useMemo(() => ({
    pending: offers.filter((o) => o.status === "pending"),
    accepted: offers.filter((o) => o.status === "accepted"),
    declined: offers.filter((o) => o.status === "declined"),
    expired: offers.filter((o) => o.status === "expired"),
  }), [offers]);

  const accept  = async (id) => { await api.post(`/dispatch/offers/${id}/accept`); toast.success("Accepted"); load(); };
  const decline = async (id) => { await api.post(`/dispatch/offers/${id}/decline`); toast.success("Declined"); load(); };

  const colorFor = {
    pending:  { bg: "bg-cyan-500/5",    border: "border-cyan-500/30",    text: "text-cyan-200" },
    accepted: { bg: "bg-emerald-500/5", border: "border-emerald-500/30", text: "text-emerald-200" },
    declined: { bg: "bg-red-500/5",     border: "border-red-500/30",     text: "text-red-200" },
    expired:  { bg: "bg-slate-500/5",   border: "border-slate-500/30",   text: "text-slate-300" },
  };

  return (
    <div className="grid md:grid-cols-4 gap-3" data-testid="da-kanban">
      {(["pending", "accepted", "declined", "expired"]).map((k) => {
        const c = colorFor[k];
        return (
          <Card key={k} className={`p-0 ${c.bg} border ${c.border} overflow-hidden`}
            data-testid={`da-column-${k}`}>
            <div className={`px-3 py-2 border-b ${c.border} font-mono uppercase text-[10px] tracking-widest flex justify-between ${c.text}`}>
              <span>{k}</span><span>{cols[k].length}</span>
            </div>
            <div className="max-h-[70vh] overflow-y-auto p-2 space-y-2">
              {cols[k].map((o) => (
                <div key={o.offer_id} className="p-2 rounded bg-black/40 border border-white/10 text-xs"
                  data-testid={`da-card-${o.offer_id}`}>
                  <div className="font-mono text-slate-300 truncate">{o.origin} → {o.destination}</div>
                  <div className="text-[10px] text-slate-500 truncate mt-0.5">{o.carrier_name}</div>
                  <div className="flex justify-between mt-1.5">
                    <ScoreChip score={o.match_score} small />
                    <div className="text-right">
                      <div className="text-emerald-300 font-mono text-[11px]">${o.offer_amount_usd?.toFixed?.(0)}</div>
                      <div className="text-[9px] text-amber-300 font-mono">+${o.margin_usd?.toFixed?.(0)} · {o.margin_pct?.toFixed?.(0)}%</div>
                    </div>
                  </div>
                  {k === "pending" && (
                    <div className="mt-1.5 flex gap-1">
                      <Button size="sm" onClick={() => accept(o.offer_id)}
                        className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-black h-6 text-[10px]"
                        data-testid={`da-kanban-accept-${o.offer_id}`}>Accept</Button>
                      <Button size="sm" variant="ghost" onClick={() => decline(o.offer_id)}
                        className="flex-1 text-red-400 h-6 text-[10px]"
                        data-testid={`da-kanban-decline-${o.offer_id}`}>Decline</Button>
                    </div>
                  )}
                </div>
              ))}
              {!cols[k].length && <div className="p-4 text-center text-[10px] text-slate-600">empty</div>}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

// ============================================================
//                    ML CONSOLE
// ============================================================
function MlConsoleView() {
  const [status, setStatus] = useState(null);
  const [busyTrain, setBusyTrain] = useState(false);
  const [busySeed, setBusySeed] = useState(false);
  const [loads, setLoads] = useState([]);
  const [selectedLoadId, setSelectedLoadId] = useState("");
  const [prediction, setPrediction] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [busyPredict, setBusyPredict] = useState(false);
  const [busyExplain, setBusyExplain] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const { data } = await api.get("/dispatch/ml/status");
      setStatus(data);
    } catch (e) { /* no-op */ }
  }, []);
  const loadCandidates = useCallback(async () => {
    try {
      const { data } = await api.get("/aggregator/feed?limit=10");
      setLoads(data.items || []);
      if (!selectedLoadId && data.items?.length) setSelectedLoadId(data.items[0].load_id);
    } catch (e) { /* no-op */ }
  }, [selectedLoadId]);
  useEffect(() => { refreshStatus(); loadCandidates(); }, [refreshStatus, loadCandidates]);

  const seed = async () => {
    setBusySeed(true);
    try {
      const { data } = await api.post("/dispatch/ml/seed-training-data");
      toast.success(`Seeded ${data.seeded} synthetic offers`);
      refreshStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Seed failed"); }
    finally { setBusySeed(false); }
  };
  const train = async () => {
    setBusyTrain(true);
    try {
      const { data } = await api.post("/dispatch/ml/train");
      if (data.trained) {
        toast.success(`Trained · AUC ${data.accept_auc ?? "n/a"} · R² ${data.rate_r2 ?? "n/a"}`);
      } else {
        toast.error(data.reason || "Training skipped");
      }
      refreshStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Train failed"); }
    finally { setBusyTrain(false); }
  };
  const predict = async () => {
    if (!selectedLoadId) { toast.error("Pick a load"); return; }
    setBusyPredict(true); setPrediction(null); setExplanation(null);
    try {
      const { data } = await api.post(`/dispatch/ml/predict/${selectedLoadId}`);
      setPrediction(data);
      toast.success(`ML ranked ${data.ranked.length} carriers`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Predict failed"); }
    finally { setBusyPredict(false); }
  };
  const explain = async (carrier_id) => {
    if (!selectedLoadId) return;
    setBusyExplain(true);
    try {
      const { data } = await api.post(
        `/dispatch/ml/explain/${selectedLoadId}${carrier_id ? `?carrier_id=${carrier_id}` : ""}`);
      setExplanation(data);
      toast.success(data.used_llm ? "Claude rationale generated" : "Heuristic rationale (Claude fallback)");
    } catch (e) { toast.error(e?.response?.data?.detail || "Explain failed"); }
    finally { setBusyExplain(false); }
  };

  const models_loaded = status?.models_loaded;
  return (
    <div className="space-y-3" data-testid="da-ml-console">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Models"          value={models_loaded ? "LIVE" : "COLD"} color={models_loaded ? "#10B981" : "#64748B"} icon={Cpu} />
        <KpiTile label="Training rows"   value={status?.training_rows_available ?? "—"} color="#22D3EE" icon={Users} />
        <KpiTile label="Accepted rows"   value={status?.training_rows_accepted ?? "—"} color="#10B981" icon={CheckCircle2} />
        <KpiTile label="Accept AUC"      value={status?.meta?.accept_auc ?? "—"} color="#F59E0B" icon={TrendingUp} />
        <KpiTile label="Rate R²"         value={status?.meta?.rate_r2 ?? "—"} color="#A78BFA" icon={DollarSign} />
      </div>

      <Card className="p-3 bg-slate-900/60 border-white/10 flex flex-wrap items-center gap-2" data-testid="da-ml-controls">
        <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mr-2">
          <Cpu size={12} className="inline mr-1" /> pipeline
        </span>
        <Button size="sm" onClick={seed} disabled={busySeed}
          className="bg-amber-500 hover:bg-amber-400 text-black h-8" data-testid="da-ml-seed-btn">
          {busySeed ? <Loader2 size={12} className="animate-spin mr-1" /> : "Seed 400 synthetic offers"}
        </Button>
        <Button size="sm" onClick={train} disabled={busyTrain}
          className="bg-emerald-500 hover:bg-emerald-400 text-black h-8" data-testid="da-ml-train-btn">
          {busyTrain ? <Loader2 size={12} className="animate-spin mr-1" /> : "Retrain models"}
        </Button>
        <span className="text-[10px] text-slate-500 font-mono ml-2">
          {status?.meta?.trained_at ? `last trained ${new Date(status.meta.trained_at).toLocaleString()}` : "never trained"}
        </span>
      </Card>

      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3" data-testid="da-ml-predict-card">
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-1">Load to score</div>
            <select value={selectedLoadId}
              onChange={(e) => setSelectedLoadId(e.target.value)}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-2 text-xs text-slate-100"
              data-testid="da-ml-load-select">
              {loads.map((l) => (
                <option key={l.load_id} value={l.load_id}>
                  {l.load_id} · {l.origin} → {l.destination} · {l.equipment} · ${l.rate_usd}
                </option>
              ))}
            </select>
          </div>
          <Button onClick={predict} disabled={busyPredict || !selectedLoadId}
            className="bg-cyan-500 hover:bg-cyan-400 text-black h-9" data-testid="da-ml-predict-btn">
            {busyPredict ? <Loader2 size={13} className="animate-spin mr-1" /> : <Cpu size={13} className="mr-1" />}
            ML Predict
          </Button>
        </div>

        {prediction && (
          <div className="space-y-3">
            <div className="text-[10px] font-mono text-slate-500">
              {prediction.ml_active ? (
                <span className="text-emerald-400"><Cpu size={11} className="inline mr-1" /> Trained models active</span>
              ) : (
                <span className="text-amber-400"><AlertTriangle size={11} className="inline mr-1" /> Heuristic fallback (models not trained)</span>
              )}
            </div>
            <div className="overflow-x-auto rounded border border-white/10">
              <table className="w-full text-xs" data-testid="da-ml-ranking-table">
                <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
                  <tr>
                    <th className="px-3 py-2 text-left">Carrier</th>
                    <th className="px-3 py-2 text-right">Rule Score</th>
                    <th className="px-3 py-2 text-right">Accept Prob</th>
                    <th className="px-3 py-2 text-right">Suggested $/mi</th>
                    <th className="px-3 py-2 text-right">Expected Margin</th>
                    <th className="px-3 py-2 text-right">Expected Value</th>
                    <th className="px-3 py-2 text-right"></th>
                  </tr>
                </thead>
                <tbody>
                  {prediction.ranked.slice(0, 8).map((r, i) => (
                    <tr key={r.carrier_id} className={`border-t border-white/5 ${i === 0 ? "bg-emerald-500/5" : ""}`}
                      data-testid={`da-ml-row-${r.carrier_id}`}>
                      <td className="px-3 py-2 text-slate-200">
                        {i === 0 && <Badge className="mr-2 bg-emerald-500/20 text-emerald-200 border-emerald-500/40">TOP PICK</Badge>}
                        {r.legal_name}
                        <div className="text-[10px] text-slate-500 font-mono">
                          on-time {r.on_time_pct}% · idle {r.days_idle}d
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-cyan-300">{r.match_score}</td>
                      <td className="px-3 py-2 text-right font-mono">
                        <span className={r.ml_accept_prob >= 0.65 ? "text-emerald-300"
                          : r.ml_accept_prob >= 0.45 ? "text-amber-300" : "text-red-300"}>
                          {(r.ml_accept_prob * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-amber-300">${r.ml_suggested_rpm}</td>
                      <td className="px-3 py-2 text-right font-mono text-emerald-300">${r.ml_expected_margin_usd?.toFixed(0)}</td>
                      <td className="px-3 py-2 text-right font-mono text-purple-300 font-semibold">${r.ml_expected_value_usd?.toFixed(0)}</td>
                      <td className="px-3 py-2 text-right">
                        <Button size="sm" variant="ghost" onClick={() => explain(r.carrier_id)}
                          disabled={busyExplain}
                          className="text-cyan-300 hover:text-cyan-100 h-7"
                          data-testid={`da-ml-explain-${r.carrier_id}`}>
                          Why?
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

      {explanation && (
        <Card className="p-4 bg-purple-500/5 border-purple-500/30" data-testid="da-ml-explanation">
          <div className="flex items-center gap-2 mb-2">
            <Cpu size={14} className="text-purple-400" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-purple-300">
              {explanation.used_llm ? "Claude Sonnet 4.5 · Rationale" : "Heuristic Rationale"}
            </span>
            <Badge className="bg-purple-500/20 text-purple-200 border-purple-500/40">
              {explanation.carrier_name}
            </Badge>
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">{explanation.rationale}</p>
        </Card>
      )}
    </div>
  );
}

// ============================================================
//                    DASHBOARD (KPIs)
// ============================================================
function DashView() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/dispatch/dashboard").then(({ data }) => setD(data)); }, []);
  if (!d) return <Card className="p-8 bg-slate-900/60 border-white/10 text-center text-slate-500"><Loader2 className="animate-spin inline mr-2" /> Loading…</Card>;
  const byStatus = d.offers_by_status || {};
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <KpiTile label="Carriers active"    value={d.carriers_active}       color="#22D3EE" icon={Users} />
        <KpiTile label="Offers total"        value={d.offers_total}         color="#A78BFA" icon={Zap} />
        <KpiTile label="Offers · last hr"   value={d.offers_last_hour}     color="#10B981" icon={Radio} />
        <KpiTile label="Acceptance rate"    value={`${d.acceptance_rate_pct}%`} color="#F59E0B" icon={Award} />
        <KpiTile label="Avg time-to-book"   value={`${d.avg_time_to_book_sec}s`} color="#F472B6" icon={Clock} />
        <KpiTile label="Margin captured"    value={`$${(d.margin_captured_usd || 0).toLocaleString()}`} color="#34D399" icon={DollarSign} />
      </div>
      <Card className="p-4 bg-slate-900/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">Offers by status</div>
        <div className="grid grid-cols-4 gap-3">
          {["pending", "accepted", "declined", "expired"].map((k) => (
            <div key={k} className="text-center p-3 rounded bg-black/40 border border-white/10">
              <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">{k}</div>
              <div className={`text-2xl font-mono mt-1 ${
                k === "accepted" ? "text-emerald-300"
                  : k === "pending" ? "text-cyan-300"
                  : k === "declined" ? "text-red-300"
                  : "text-slate-400"
              }`}>{byStatus[k] || 0}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//                    CONFIG
// ============================================================
function ConfigView() {
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/dispatch/config").then(({ data }) => setCfg(data)); }, []);
  if (!cfg) return null;
  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/dispatch/config", cfg);
      setCfg(data); toast.success("Autopilot config saved");
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="grid md:grid-cols-2 gap-3">
      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300"><Cpu size={12} className="inline mr-1" /> Matching thresholds</div>
        <CfgNumField cfg={cfg} setCfg={setCfg} label="Top N carriers per load" cfgKey="top_n_carriers_per_load" />
        <CfgNumField cfg={cfg} setCfg={setCfg} label="Min match score (0-100)" cfgKey="min_match_score" />
        <CfgNumField cfg={cfg} setCfg={setCfg} label="Min margin USD" cfgKey="min_margin_usd" step={10} />
        <CfgNumField cfg={cfg} setCfg={setCfg} label="Min margin %" cfgKey="min_margin_pct" step={0.5} />
        <CfgNumField cfg={cfg} setCfg={setCfg} label="Offer expiry (min)" cfgKey="offer_expiry_minutes" step={5} />
      </Card>
      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300"><Settings2 size={12} className="inline mr-1" /> Autopilot toggles</div>
        <CfgToggle cfg={cfg} setCfg={setCfg} label="Autopilot enabled (tick auto-fires offers)" cfgKey="autopilot_enabled" />
        <CfgToggle cfg={cfg} setCfg={setCfg} label="Send SMS offers (Twilio · MOCKED)" cfgKey="notify_sms" />
        <CfgToggle cfg={cfg} setCfg={setCfg} label="Send email offers (Resend · MOCKED)" cfgKey="notify_email" />
        <div className="pt-2">
          <Button onClick={save} disabled={busy} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="da-cfg-save">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
            Save config
          </Button>
        </div>
      </Card>
    </div>
  );
}

function CfgNumField({ cfg, setCfg, label, cfgKey, step = 1 }) {
  return (
    <Field label={label}>
      <Input type="number" step={step} value={cfg[cfgKey]}
        onChange={(e) => setCfg({ ...cfg, [cfgKey]: Number(e.target.value) })}
        className="bg-black/40 border-white/10 h-8 text-xs"
        data-testid={`da-cfg-${cfgKey}`} />
    </Field>
  );
}
function CfgToggle({ cfg, setCfg, label, cfgKey }) {
  return (
    <div className="flex items-center justify-between p-2 rounded bg-black/40 border border-white/10">
      <span className="text-xs text-slate-300">{label}</span>
      <Switch checked={cfg[cfgKey]} onCheckedChange={(v) => setCfg({ ...cfg, [cfgKey]: v })}
        data-testid={`da-cfg-toggle-${cfgKey}`} />
    </div>
  );
}

// ============================================================
//                     SHARED PRIMS
// ============================================================
function KpiTile({ label, value, color, icon: Icon }) {
  return (
    <Card className="p-3 bg-slate-900/60 border-white/10">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</span>
        {Icon && <Icon size={13} style={{ color }} />}
      </div>
      <div className="text-2xl font-mono mt-1" style={{ color }}>{value}</div>
    </Card>
  );
}

function StatusPill({ status }) {
  const map = {
    pending:  { c: "bg-cyan-500/20 text-cyan-200 border-cyan-500/40",     label: "PENDING" },
    accepted: { c: "bg-emerald-500/20 text-emerald-200 border-emerald-500/40", label: "ACCEPTED" },
    declined: { c: "bg-red-500/20 text-red-200 border-red-500/40",         label: "DECLINED" },
    expired:  { c: "bg-slate-500/20 text-slate-300 border-slate-500/40",   label: "EXPIRED" },
  };
  const m = map[status] || map.pending;
  return <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono uppercase border ${m.c}`}>{m.label}</span>;
}

function ScoreChip({ score, small }) {
  const color = score >= 80 ? "text-emerald-300" : score >= 65 ? "text-amber-300" : "text-red-300";
  return (
    <span className={`font-mono ${small ? "text-[10px]" : "text-xs"} ${color}`}>
      <Award size={small ? 10 : 12} className="inline mr-0.5" /> {score}
    </span>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  );
}
