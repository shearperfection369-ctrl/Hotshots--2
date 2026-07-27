import React, { useCallback, useEffect, useState } from "react";
import { Crosshair, Loader2, X, Sparkles, Send, Copy, Plus, Trash2, FlaskConical, Target as TargetIcon, TrendingUp, Landmark, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const money = (n) => `$${Math.round(n || 0).toLocaleString()}`;
const STAGE_META = {
  target: ["TARGET", "#94A3B8"], researched: ["RESEARCHED", "#22D3EE"], contacted: ["CONTACTED", "#A78BFA"],
  meeting: ["MEETING", "#F59E0B"], pilot: ["PILOT", "#FB923C"], contracted: ["CONTRACTED", "#10B981"],
};
const TIER_LABEL = { 1: "TIER 1 · MANUFACTURING & INDUSTRIAL", 2: "TIER 2 · SPECIALTY LOGISTICS", 3: "TIER 3 · NICHE VERTICALS" };

export default function NicheMarkets() {
  const [pb, setPb] = useState(null);
  const [dash, setDash] = useState(null);
  const [targets, setTargets] = useState([]);
  const [vertFilter, setVertFilter] = useState("");
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, d, t] = await Promise.all([
        api.get("/niche-markets/playbook"), api.get("/niche-markets/dashboard"), api.get("/niche-markets/targets"),
      ]);
      setPb(p.data); setDash(d.data); setTargets(t.data.targets);
    } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const setStage = async (t, stage) => {
    try { await api.patch(`/niche-markets/targets/${t.id}`, { stage }); toast.success(`${t.name} → ${stage}`); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  if (!pb || !dash) return <div className="p-8 text-slate-500 font-mono text-sm">Loading niche market network…</div>;
  const s = dash.stats;
  const shown = vertFilter ? targets.filter((t) => t.vertical === vertFilter) : targets;

  return (
    <div className="p-6 space-y-6 relative" data-testid="niche-markets-page">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -160, left: "18%", width: 520, height: 520, borderRadius: 9999, filter: "blur(60px)", background: "radial-gradient(circle, rgba(245,158,11,0.12), transparent 65%)" }} />
      </div>

      <div className="relative">
        <h1 className="text-2xl font-black text-white flex items-center gap-2"><Crosshair className="text-amber-300" size={24} /> MN Niche Market Network</h1>
        <p className="text-xs text-slate-500 font-mono mt-1">10 high-margin Minnesota verticals · {s.targets_total} named targets · AI battle cards + pitches · phase-tracked to 765 loads/mo & $4.5M Y1</p>
      </div>

      <div className="relative grid grid-cols-2 md:grid-cols-6 gap-3" data-testid="nm-stats">
        {[["Named targets", s.targets_total, "#22D3EE"], ["Pilots live", s.pilots_active, "#FB923C"],
          ["Contracted accts", s.contracted_accounts, "#10B981"],
          ["Loads/mo locked", `${s.contracted_loads_month}/765`, "#F59E0B"],
          ["Y1 locked", money(s.contracted_y1_revenue), "#34D399"],
          ["Weighted pipeline", money(s.weighted_pipeline_y1), "#A78BFA"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-lg font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="relative grid md:grid-cols-3 gap-3" data-testid="nm-phases">
        {dash.phases.map((ph) => (
          <div key={ph.phase} className="p-4 rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[11px] font-mono font-bold text-amber-300 uppercase">{ph.label}</div>
              <div className="text-[10px] font-mono text-slate-500">{ph.loads_committed}/{ph.loads_target} loads/mo</div>
            </div>
            <div className="h-1.5 rounded-full bg-white/10 mb-3">
              <div className="h-1.5 rounded-full bg-amber-400" style={{ width: `${Math.min(100, (ph.loads_committed / ph.loads_target) * 100)}%` }} />
            </div>
            <div className="space-y-1.5">
              {ph.targets.map((t) => {
                const [lab, col] = STAGE_META[t.stage];
                return (
                  <div key={t.id} className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-300 font-bold truncate">{t.name}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-slate-500">{t.est_loads_month}/mo</span>
                      <span className="px-1.5 py-0.5 rounded font-mono font-bold text-[8px]" style={{ color: col, border: `1px solid ${col}55` }}>{lab}</span>
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="text-[10px] font-mono text-slate-600 mt-2">Y1 plan {money(ph.y1_revenue_target)} · locked {money(ph.y1_committed)}</div>
          </div>
        ))}
      </div>

      <div className="relative space-y-3" data-testid="nm-verticals">
        {[1, 2, 3].map((tier) => (
          <div key={tier}>
            <div className="text-[10px] font-mono font-bold text-slate-500 uppercase tracking-widest mb-2">{TIER_LABEL[tier]}</div>
            <div className="grid md:grid-cols-3 lg:grid-cols-4 gap-2">
              {dash.verticals.filter((v) => v.tier === tier).map((v) => (
                <button key={v.vertical} onClick={() => setVertFilter(vertFilter === v.vertical ? "" : v.vertical)}
                        data-testid={`nm-vertical-${v.vertical}`}
                        className={`text-left p-3 rounded-2xl border transition ${vertFilter === v.vertical ? "border-amber-400 bg-amber-500/10" : "border-white/10 bg-white/[0.03] hover:border-amber-400/40"}`}>
                  <div className="text-[12px] font-bold text-white leading-tight">{v.label}</div>
                  <div className="text-[10px] font-mono text-emerald-300 mt-1">${v.margin_per_load[0]}–${v.margin_per_load[1]}/load</div>
                  <div className="text-[9px] font-mono text-slate-500">{v.targets} targets · {v.contracted} signed · wtd {money(v.weighted_y1)}</div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="relative rounded-2xl border border-white/10 bg-slate-950/60 backdrop-blur overflow-hidden" data-testid="nm-target-table">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
          <div className="text-sm font-black text-white">{vertFilter ? pb.verticals.find((v) => v.key === vertFilter)?.label : "All targets"} <span className="text-slate-500 font-mono text-xs">({shown.length})</span></div>
          <AddTarget verticals={pb.verticals} onAdded={load} />
        </div>
        <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
          <table className="w-full text-[12px]">
            <thead className="sticky top-0 bg-slate-950">
              <tr className="text-[9px] font-mono uppercase text-slate-500 text-left">
                <th className="px-4 py-2">Company</th><th className="px-2 py-2">Vertical</th><th className="px-2 py-2">Phase</th>
                <th className="px-2 py-2 text-right">Loads/mo</th><th className="px-2 py-2 text-right">Margin/load</th>
                <th className="px-2 py-2 text-right">Y1 potential</th><th className="px-2 py-2">Stage</th><th className="px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => {
                const [, col] = STAGE_META[t.stage];
                return (
                  <tr key={t.id} className="border-t border-white/5 hover:bg-white/[0.03]">
                    <td className="px-4 py-2">
                      <button onClick={() => setDetail(t)} data-testid={`nm-target-${t.id}`} className="text-left">
                        <div className="font-bold text-white">{t.name}</div>
                        <div className="text-[10px] font-mono text-slate-500">{t.city}</div>
                      </button>
                    </td>
                    <td className="px-2 py-2 text-[10px] font-mono text-slate-400">{pb.verticals.find((v) => v.key === t.vertical)?.label}</td>
                    <td className="px-2 py-2 font-mono text-amber-300">{t.phase ? `P${t.phase}` : "bench"}</td>
                    <td className="px-2 py-2 text-right font-mono text-slate-300">{t.est_loads_month}</td>
                    <td className="px-2 py-2 text-right font-mono text-slate-300">${t.margin_per_load_est}</td>
                    <td className="px-2 py-2 text-right font-mono text-emerald-300">{money(t.y1_potential)}</td>
                    <td className="px-2 py-2">
                      <select value={t.stage} onChange={(e) => setStage(t, e.target.value)} data-testid={`nm-stage-${t.id}`}
                              className="bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] font-mono font-bold" style={{ color: col }}>
                        {Object.keys(STAGE_META).map((st) => <option key={st} value={st}>{STAGE_META[st][0]}</option>)}
                      </select>
                    </td>
                    <td className="px-2 py-2">
                      <button onClick={() => setDetail(t)} data-testid={`nm-open-${t.id}`}
                              className="px-2.5 py-1 rounded-full border border-cyan-500/40 text-cyan-300 text-[10px] font-bold hover:bg-cyan-500/10">AI Desk</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {detail && <TargetDrawer target={detail} vertical={pb.verticals.find((v) => v.key === detail.vertical)} onClose={() => { setDetail(null); load(); }} />}
    </div>
  );
}

function AddTarget({ verticals, onAdded }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", vertical: verticals[0]?.key, city: "", est_loads_month: 10, margin_per_load_est: 400, phase: 0 });
  const save = async () => {
    try { await api.post("/niche-markets/targets", f); toast.success("Target added"); setOpen(false); onAdded(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  if (!open) return <button onClick={() => setOpen(true)} data-testid="nm-add-btn" className="px-3 py-1.5 rounded-full border border-amber-500/50 text-amber-300 text-[11px] font-bold inline-flex items-center gap-1 hover:bg-amber-500/10"><Plus size={12} /> Add target</button>;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <input placeholder="Company" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="nm-add-name" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-36" />
      <select value={f.vertical} onChange={(e) => setF({ ...f, vertical: e.target.value })} data-testid="nm-add-vertical" className="bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-slate-300">
        {verticals.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
      </select>
      <input placeholder="City" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-28" />
      <input type="number" title="loads/mo" value={f.est_loads_month} onChange={(e) => setF({ ...f, est_loads_month: +e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1 text-[11px] text-white w-16" />
      <button onClick={save} data-testid="nm-add-save" className="px-2.5 py-1 rounded-full bg-amber-500 text-black text-[10px] font-black">SAVE</button>
      <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-white"><X size={14} /></button>
    </div>
  );
}

function TargetDrawer({ target, vertical, onClose }) {
  const [t, setT] = useState(target);
  const [busy, setBusy] = useState("");
  const [contact, setContact] = useState({ contact_name: target.contact_name || "", contact_email: target.contact_email || "", contact_phone: target.contact_phone || "" });

  const saveContact = async () => {
    try { const { data } = await api.patch(`/niche-markets/targets/${t.id}`, contact); setT(data.target); toast.success("Contact saved"); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const genCard = async () => {
    setBusy("card");
    try { const { data } = await api.post(`/niche-markets/targets/${t.id}/battle-card`, {}, { timeout: 90000 }); setT({ ...t, battle_card: data.battle_card, stage: t.stage === "target" ? "researched" : t.stage }); toast.success("Battle card ready"); }
    catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(""); }
  };
  const genPitch = async (send) => {
    setBusy(send ? "send" : "pitch");
    try {
      const { data } = await api.post(`/niche-markets/targets/${t.id}/pitch`, { send, email: contact.contact_email || undefined }, { timeout: 90000 });
      setT({ ...t, last_pitch: data.pitch });
      toast.success(send ? (data.pitch.sent ? "Pitch sent via Resend" : "Pitch queued — add Resend key in Connections to deliver") : "Pitch drafted");
    } catch (e2) { toast.error(errTxt(e2)); } finally { setBusy(""); }
  };
  const del = async () => {
    try { await api.delete(`/niche-markets/targets/${t.id}`); toast.success("Target removed"); onClose(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const bc = t.battle_card;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-lg h-full bg-slate-950 border-l border-amber-500/30 p-5 overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="nm-drawer">
        <div className="flex justify-between items-start">
          <div>
            <div className="font-black text-white text-lg">{t.name}</div>
            <div className="text-[11px] font-mono text-slate-500">{t.city} · {vertical?.label} · Tier {vertical?.tier}</div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={del} data-testid="nm-delete" className="text-slate-600 hover:text-red-400"><Trash2 size={15} /></button>
            <button onClick={onClose} className="text-slate-500 hover:text-white"><X size={18} /></button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 my-4">
          {[["Loads/mo est", t.est_loads_month, TargetIcon], ["Margin/load", `$${t.margin_per_load_est}`, TrendingUp], ["Y1 potential", money(t.est_loads_month * t.margin_per_load_est * 12), Landmark]].map(([l, v, Icon]) => (
            <div key={l} className="p-2.5 rounded-xl border border-white/10 text-center">
              <Icon size={12} className="mx-auto text-amber-300 mb-1" />
              <div className="font-black text-white text-sm tabular-nums">{v}</div>
              <div className="text-[8px] font-mono uppercase text-slate-500">{l}</div>
            </div>
          ))}
        </div>

        {t.notes && <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] text-[11.5px] text-slate-300 mb-3"><ShieldCheck size={11} className="inline mr-1.5 text-emerald-300" />{t.notes}</div>}

        <div className="p-3 rounded-xl border border-white/10 bg-white/[0.03] mb-3">
          <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Contact — {vertical?.contact_role}</div>
          <div className="grid grid-cols-2 gap-1.5">
            <input placeholder="Name" value={contact.contact_name} onChange={(e) => setContact({ ...contact, contact_name: e.target.value })} data-testid="nm-contact-name" className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <input placeholder="Phone" value={contact.contact_phone} onChange={(e) => setContact({ ...contact, contact_phone: e.target.value })} className="bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
            <input placeholder="Email" value={contact.contact_email} onChange={(e) => setContact({ ...contact, contact_email: e.target.value })} data-testid="nm-contact-email" className="col-span-2 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
          </div>
          <button onClick={saveContact} data-testid="nm-contact-save" className="mt-2 px-3 py-1 rounded-full border border-white/20 text-slate-300 text-[10px] font-bold hover:border-amber-400">Save contact</button>
        </div>

        <div className="flex gap-2 mb-4">
          <button onClick={genCard} disabled={!!busy} data-testid="nm-battle-card-btn"
                  className="flex-1 px-3 py-2 rounded-full border border-cyan-500/50 text-cyan-300 text-[11px] font-bold inline-flex items-center justify-center gap-1.5 hover:bg-cyan-500/10 disabled:opacity-50">
            {busy === "card" ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />} AI Battle Card
          </button>
          <button onClick={() => genPitch(false)} disabled={!!busy} data-testid="nm-pitch-btn"
                  className="flex-1 px-3 py-2 rounded-full border border-amber-500/50 text-amber-300 text-[11px] font-bold inline-flex items-center justify-center gap-1.5 hover:bg-amber-500/10 disabled:opacity-50">
            {busy === "pitch" ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} AI Pitch
          </button>
        </div>

        {bc && (
          <div className="p-3.5 rounded-xl border border-cyan-500/25 bg-cyan-500/5 mb-4 space-y-2.5" data-testid="nm-battle-card">
            <div className="text-[10px] font-mono uppercase text-cyan-300 font-bold">Account Battle Card</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Ships:</b> {bc.what_they_ship}</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Likely lanes:</b> {(bc.likely_lanes || []).join(" · ")}</div>
            <div className="text-[11.5px] text-slate-200"><b className="text-white">Hunt on LinkedIn:</b> {(bc.decision_makers || []).join(" · ")}</div>
            {(bc.objections || []).map((o, i) => (
              <div key={i} className="text-[11px] p-2 rounded-lg bg-black/30 border border-white/10">
                <span className="text-red-300">"{o.objection}"</span>
                <div className="text-emerald-300 mt-0.5">↳ {o.counter}</div>
              </div>
            ))}
            <div className="text-[11.5px] text-amber-200 italic">Opening hook: "{bc.hook}"</div>
            <div className="text-[10.5px] text-slate-400"><b>Compliance:</b> {bc.compliance_notes}</div>
          </div>
        )}

        {t.last_pitch && (
          <div className="p-3.5 rounded-xl border border-amber-500/25 bg-amber-500/5 space-y-2" data-testid="nm-pitch-preview">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase text-amber-300 font-bold">Pitch email {t.last_pitch.sent && <span className="text-emerald-300">· SENT</span>}</div>
              <button onClick={() => { navigator.clipboard.writeText(`${t.last_pitch.subject}\n\n${t.last_pitch.body_text}`); toast.success("Copied"); }} data-testid="nm-pitch-copy" className="text-slate-400 hover:text-white"><Copy size={13} /></button>
            </div>
            <div className="text-[12px] font-bold text-white">{t.last_pitch.subject}</div>
            <pre className="text-[11px] text-slate-300 whitespace-pre-wrap font-sans">{t.last_pitch.body_text}</pre>
            <button onClick={() => genPitch(true)} disabled={!!busy || !contact.contact_email} data-testid="nm-pitch-send"
                    className="w-full px-3 py-2 rounded-full bg-amber-500 text-black text-[11px] font-black inline-flex items-center justify-center gap-1.5 disabled:opacity-40">
              {busy === "send" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} {contact.contact_email ? "SEND VIA RESEND" : "ADD CONTACT EMAIL TO SEND"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
