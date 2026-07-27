import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Handshake, Truck, CalendarClock, BookOpen, Trash2, Plus, ChevronRight, Target, FileSpreadsheet, Zap } from "lucide-react";
import { CarrierCombobox } from "../components/CarrierCombobox";
import { toast } from "sonner";

const STAGE_LABEL = { target: "TARGET", contacted: "CONTACTED", meeting: "MEETING", pilot_load: "PILOT LOAD", locked_in: "LOCKED IN" };
const STAGE_ORDER = ["target", "contacted", "meeting", "pilot_load", "locked_in"];
const STAGE_CLS = {
  target: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  contacted: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  meeting: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  pilot_load: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  locked_in: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
};
const CAT_LABEL = {
  owner_op: "Owner-Ops & Small Fleets",
  regional_overflow: "Regional Overflow",
  specialty: "Specialty / Niche",
  backhauler: "Backhaulers",
};

const fmt = (n) => Number(n || 0).toLocaleString();

export default function CarrierNetwork() {
  const [tab, setTab] = useState("pipeline");
  const [score, setScore] = useState(null);
  const [playbook, setPlaybook] = useState(null);
  const loadScore = () => api.get("/carrier-network/scoreboard").then(({ data }) => setScore(data)).catch(() => {});
  useEffect(() => {
    loadScore();
    api.get("/carrier-network/playbook").then(({ data }) => setPlaybook(data)).catch(() => {});
  }, []);

  const TABS = [
    { key: "pipeline", label: "Relationship Pipeline", icon: Handshake },
    { key: "windows", label: "Capacity Windows", icon: CalendarClock },
    { key: "ratecards", label: "Rate Cards", icon: FileSpreadsheet },
    { key: "playbook", label: "Playbook", icon: BookOpen },
  ];
  return (
    <>
      <Topbar title="Carrier Network" subtitle="Own the overflow & backhaul lanes — owner-ops, regional overflow, specialty fleets, backhaulers" />
      <div className="p-4 md:p-6 space-y-4">
        <Scoreboard score={score} />
        <div className="flex gap-2">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)} data-testid={`cn-tab-${t.key}`}
                className={`px-4 py-2 rounded border text-xs font-mono uppercase tracking-wider flex items-center gap-2 transition-colors ${
                  tab === t.key ? "bg-cyan-500 text-black border-cyan-400" : "bg-white/[0.02] text-slate-400 border-white/10 hover:text-cyan-300"}`}>
                <Icon size={13} /> {t.label}
              </button>
            );
          })}
        </div>
        {tab === "pipeline" && <PipelineTab playbook={playbook} onChanged={loadScore} />}
        {tab === "windows" && <WindowsTab />}
        {tab === "ratecards" && <RateCardsTab />}
        {tab === "playbook" && <PlaybookTab playbook={playbook} />}
      </div>
    </>
  );
}

function Scoreboard({ score }) {
  if (!score) return null;
  const proj = score.projection || {};
  const [lo, hi] = proj.loads_per_month || [0, 0];
  const [glo, ghi] = proj.gross_margin_usd || [0, 0];
  return (
    <Card className="hud-surface p-4" data-testid="cn-scoreboard">
      <div className="flex items-center gap-2 mb-3">
        <Target size={14} className="text-amber-400" />
        <h3 className="font-display text-base font-bold text-white">The Realistic Play — live scoreboard</h3>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3">
        {Object.entries(score.by_category || {}).map(([k, c]) => (
          <div key={k} className="p-2.5 rounded border border-white/10 bg-white/[0.02]" data-testid={`cn-score-${k}`}>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 truncate">{CAT_LABEL[k]}</div>
            <div className={`text-lg font-bold ${c.locked_in >= c.target_min ? "text-emerald-300" : "text-slate-100"}`}>
              {c.locked_in}<span className="text-slate-500 text-xs">/{c.target} locked</span>
            </div>
            <div className="text-[9px] font-mono text-slate-500">{c.in_pipeline} in pipeline · {c.trucks_secured} trucks</div>
          </div>
        ))}
        <div className="p-2.5 rounded border border-cyan-500/30 bg-cyan-500/5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-cyan-400">Trucks Secured</div>
          <div className="text-lg font-bold text-cyan-300" data-testid="cn-trucks-secured">{score.trucks_secured}</div>
          <div className="text-[9px] font-mono text-slate-500">{score.trucks_in_play_window}</div>
        </div>
        <div className="p-2.5 rounded border border-emerald-500/30 bg-emerald-500/5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-emerald-400">Projected Loads/Mo</div>
          <div className="text-lg font-bold text-emerald-300" data-testid="cn-projected-loads">{lo}–{hi}</div>
          <div className="text-[9px] font-mono text-slate-500">2–3 loads/truck/week</div>
        </div>
        <div className="p-2.5 rounded border border-amber-500/30 bg-amber-500/5">
          <div className="text-[9px] font-mono uppercase tracking-widest text-amber-400">Projected Gross/Mo</div>
          <div className="text-lg font-bold text-amber-300" data-testid="cn-projected-gross">${fmt(glo)}–${fmt(ghi)}</div>
          <div className="text-[9px] font-mono text-slate-500">at ~$1.2K margin/load</div>
        </div>
        <div className="p-2.5 rounded border border-white/10 bg-white/[0.02]">
          <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">Capacity Windows</div>
          <div className="text-lg font-bold text-slate-100">{score.capacity_windows_open}</div>
          <div className="text-[9px] font-mono text-slate-500">open right now</div>
        </div>
      </div>
      <div className={`mt-3 text-[11px] font-mono ${proj.referral_overflow_unlocked ? "text-emerald-300" : "text-slate-500"}`} data-testid="cn-referral-note">
        {proj.referral_note}
      </div>
    </Card>
  );
}

function PipelineTab({ playbook, onChanged }) {
  const [prospects, setProspects] = useState([]);
  const [detail, setDetail] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", category: "owner_op", city: "", trucks: 5, equipment: "Van", contact_name: "", contact_phone: "", lanes: "", notes: "" });
  const load = () => api.get("/carrier-network/prospects").then(({ data }) => setProspects(data.prospects || []));
  useEffect(() => { load(); }, []);

  const advance = async (p) => {
    const next = STAGE_ORDER[Math.min(STAGE_ORDER.indexOf(p.stage) + 1, STAGE_ORDER.length - 1)];
    if (next === p.stage) return;
    try {
      await api.patch(`/carrier-network/prospects/${p.id}`, { stage: next });
      toast.success(`${p.name} → ${STAGE_LABEL[next]}`);
      load(); onChanged?.();
    } catch (e) { toast.error("Update failed"); }
  };
  const remove = async (p) => {
    try { await api.delete(`/carrier-network/prospects/${p.id}`); toast.success("Removed"); load(); onChanged?.(); }
    catch (e) { toast.error("Delete failed"); }
  };
  const create = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    try {
      await api.post("/carrier-network/prospects", {
        ...form,
        trucks: Number(form.trucks) || 1,
        equipment: form.equipment.split(",").map((s) => s.trim()).filter(Boolean),
        lanes: form.lanes.split(",").map((s) => s.trim()).filter(Boolean),
      });
      toast.success("Prospect added");
      setAdding(false);
      setForm({ name: "", category: "owner_op", city: "", trucks: 5, equipment: "Van", contact_name: "", contact_phone: "", lanes: "", notes: "" });
      load(); onChanged?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Create failed"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setAdding(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="cn-add-prospect-btn">
          <Plus size={14} className="mr-1.5" /> Add Carrier Prospect
        </Button>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {Object.keys(CAT_LABEL).map((cat) => (
          <Card key={cat} className="hud-surface p-4" data-testid={`cn-cat-${cat}`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-display text-sm font-bold text-white">{CAT_LABEL[cat]}</h3>
              <span className="text-[10px] font-mono text-slate-500">{prospects.filter((p) => p.category === cat).length} carriers</span>
            </div>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {prospects.filter((p) => p.category === cat).map((p) => (
                <div key={p.id} className="p-2.5 rounded border border-white/10 bg-white/[0.02]" data-testid={`cn-prospect-${p.id}`}>
                  <div className="flex items-start justify-between gap-2">
                    <button onClick={() => setDetail(p)} className="text-left min-w-0" data-testid={`cn-open-${p.id}`}>
                      <div className="text-xs text-slate-100 font-semibold truncate hover:text-cyan-300">{p.name}</div>
                      <div className="text-[9px] font-mono text-slate-500">{p.city} · {p.trucks} trucks · {(p.equipment || []).join("/")}</div>
                    </button>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <Badge className={`${STAGE_CLS[p.stage]} text-[8px] font-mono`}>{STAGE_LABEL[p.stage]}</Badge>
                      {p.stage !== "locked_in" && (
                        <Button size="sm" variant="ghost" onClick={() => advance(p)} className="h-6 px-1.5 text-cyan-300" title="Advance stage" data-testid={`cn-advance-${p.id}`}>
                          <ChevronRight size={13} />
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => remove(p)} className="h-6 px-1.5 text-red-400" data-testid={`cn-delete-${p.id}`}>
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  </div>
                  {(p.lanes || []).length > 0 && <div className="text-[9px] font-mono text-cyan-300/70 mt-1 truncate">{p.lanes.join(" · ")}</div>}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>

      {/* Add dialog */}
      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="bg-slate-900 border-cyan-500/20" data-testid="cn-add-dialog">
          <DialogHeader><DialogTitle>Add Carrier Prospect</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Carrier name *" className="col-span-2 bg-[#11151F] border-white/10" data-testid="cn-form-name" />
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="bg-[#11151F] border border-white/10 rounded px-2 py-2 text-xs text-white" data-testid="cn-form-category">
              {Object.entries(CAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} placeholder="City, ST" className="bg-[#11151F] border-white/10" data-testid="cn-form-city" />
            <Input type="number" value={form.trucks} onChange={(e) => setForm({ ...form, trucks: e.target.value })} placeholder="Trucks" className="bg-[#11151F] border-white/10" data-testid="cn-form-trucks" />
            <Input value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} placeholder="Equipment CSV (Van,Reefer)" className="bg-[#11151F] border-white/10" />
            <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="Contact name" className="bg-[#11151F] border-white/10" />
            <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} placeholder="Contact phone" className="bg-[#11151F] border-white/10" />
            <Input value={form.lanes} onChange={(e) => setForm({ ...form, lanes: e.target.value })} placeholder="Lanes CSV (MSP → Chicago)" className="col-span-2 bg-[#11151F] border-white/10" />
            <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes" className="col-span-2 bg-[#11151F] border-white/10" />
          </div>
          <Button onClick={create} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="cn-form-save">Save Prospect</Button>
        </DialogContent>
      </Dialog>

      {detail && <ProspectDetail p={detail} playbook={playbook} onClose={() => { setDetail(null); load(); onChanged?.(); }} />}
    </div>
  );
}

function ProspectDetail({ p, playbook, onClose }) {
  const [answers, setAnswers] = useState(p.discovery || {});
  const [notes, setNotes] = useState(p.notes || "");
  const [email, setEmail] = useState(p.contact_email || "");
  const [sending, setSending] = useState(false);
  const questions = playbook?.discovery_questions || [];
  const save = async () => {
    try {
      await api.patch(`/carrier-network/prospects/${p.id}`, { discovery: answers, notes });
      toast.success("Discovery saved");
      onClose();
    } catch (e) { toast.error("Save failed"); }
  };
  const sendPitch = async () => {
    if (!email || !email.includes("@")) { toast.error("Enter the contact's email first"); return; }
    setSending(true);
    try {
      const { data } = await api.post(`/carrier-network/outreach/${p.id}`, { email });
      if (data.sent) toast.success(`Pitch emailed to ${email}${data.packet_attached ? " with carrier packet attached" : ""}`);
      else toast.warning("Email recorded but NOT sent — add your Resend API key in Connections to send for real");
      if (data.stage === "contacted" && p.stage === "target") toast.info(`${p.name} moved to CONTACTED`);
    } catch (e) { toast.error(e.response?.data?.detail || "Send failed"); }
    finally { setSending(false); }
  };
  const pitch = (playbook?.categories || []).find((c) => c.key === p.category)?.pitch;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-slate-900 border-cyan-500/20 max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="cn-detail-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Truck size={15} className="text-cyan-400" /> {p.name}</DialogTitle>
        </DialogHeader>
        <div className="text-[10px] font-mono text-slate-500">{p.city} · {p.trucks} trucks · {(p.equipment || []).join("/")} · stage {STAGE_LABEL[p.stage]}</div>
        {pitch && (
          <div className="p-3 rounded border border-amber-500/30 bg-amber-500/5 text-xs text-amber-200/90" data-testid="cn-pitch-script">
            <div className="text-[9px] font-mono uppercase tracking-widest text-amber-400 mb-1">Your pitch script</div>
            “{pitch}”
          </div>
        )}
        <div className="p-3 rounded border border-cyan-500/30 bg-cyan-500/5 space-y-2" data-testid="cn-outreach-block">
          <div className="text-[9px] font-mono uppercase tracking-widest text-cyan-400">One-click outreach — branded pitch email + carrier packet PDF</div>
          <div className="flex gap-2">
            <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="contact@carrier.com" className="bg-[#11151F] border-white/10" data-testid="cn-outreach-email" />
            <Button onClick={sendPitch} disabled={sending} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shrink-0" data-testid="cn-outreach-send-btn">
              {sending ? "Sending…" : "Send Pitch"}
            </Button>
          </div>
        </div>
        <div className="space-y-3">
          <div className="text-[9px] font-mono uppercase tracking-widest text-cyan-400">What to ask them (log the answers)</div>
          {questions.map((q) => (
            <div key={q.key}>
              <div className="text-xs text-slate-200">{q.q}</div>
              <div className="text-[9px] text-slate-500 mb-1">{q.why}</div>
              <Input value={answers[q.key] || ""} onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
                placeholder="Their answer…" className="bg-[#11151F] border-white/10" data-testid={`cn-discovery-${q.key}`} />
            </div>
          ))}
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Relationship notes" className="bg-[#11151F] border-white/10" data-testid="cn-detail-notes" />
          <Button onClick={save} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="cn-discovery-save">Save Discovery Notes</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function WindowsTab() {
  const [windows, setWindows] = useState([]);
  const [form, setForm] = useState({ carrier_name: "", lane: "", days: "", trucks_available: 1, equipment: "Van", rate_note: "" });
  const load = () => api.get("/carrier-network/capacity-windows").then(({ data }) => setWindows(data.windows || []));
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!form.carrier_name || !form.lane) { toast.error("Carrier and lane required"); return; }
    try {
      await api.post("/carrier-network/capacity-windows", { ...form, trucks_available: Number(form.trucks_available) || 1 });
      toast.success("Capacity window logged — that lane is yours now");
      setForm({ carrier_name: "", lane: "", days: "", trucks_available: 1, equipment: "Van", rate_note: "" });
      load();
    } catch (e) { toast.error("Save failed"); }
  };
  const remove = async (id) => {
    try { await api.delete(`/carrier-network/capacity-windows/${id}`); load(); } catch (e) { toast.error("Delete failed"); }
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card className="hud-surface p-5" data-testid="cn-window-form">
        <h3 className="font-display text-base font-bold text-white mb-1">Log a Capacity Window</h3>
        <div className="text-[10px] text-slate-500 mb-3">“We've got 12 trucks available Tue–Thu on the Chicago–KC corridor.” — That's your load. Own the window.</div>
        <div className="space-y-2.5">
          <Input value={form.carrier_name} onChange={(e) => setForm({ ...form, carrier_name: e.target.value })} placeholder="Carrier *" className="bg-[#11151F] border-white/10" data-testid="cn-window-carrier" />
          <Input value={form.lane} onChange={(e) => setForm({ ...form, lane: e.target.value })} placeholder="Lane * (Chicago → Kansas City)" className="bg-[#11151F] border-white/10" data-testid="cn-window-lane" />
          <div className="grid grid-cols-3 gap-2">
            <Input value={form.days} onChange={(e) => setForm({ ...form, days: e.target.value })} placeholder="Days (Tue–Thu)" className="bg-[#11151F] border-white/10" data-testid="cn-window-days" />
            <Input type="number" value={form.trucks_available} onChange={(e) => setForm({ ...form, trucks_available: e.target.value })} placeholder="# trucks" className="bg-[#11151F] border-white/10" data-testid="cn-window-trucks" />
            <Input value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} placeholder="Equipment" className="bg-[#11151F] border-white/10" />
          </div>
          <Input value={form.rate_note} onChange={(e) => setForm({ ...form, rate_note: e.target.value })} placeholder="Rate note (below-board OK, quick-pay…)" className="bg-[#11151F] border-white/10" />
          <Button onClick={create} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="cn-window-save">Log Window</Button>
        </div>
      </Card>
      <Card className="hud-surface p-5 lg:col-span-2" data-testid="cn-windows-list">
        <h3 className="font-display text-base font-bold text-white mb-3">Open Capacity Windows ({windows.length})</h3>
        <div className="space-y-2 max-h-[480px] overflow-y-auto">
          {windows.map((w) => (
            <div key={w.id} className="p-3 rounded border border-white/10 bg-white/[0.02] flex items-start justify-between gap-2" data-testid={`cn-window-${w.id}`}>
              <div>
                <div className="text-sm text-slate-100 font-semibold">{w.lane} <span className="text-[10px] font-mono text-cyan-300">· {w.trucks_available} trucks · {w.equipment}</span></div>
                <div className="text-[10px] font-mono text-slate-500">{w.carrier_name}{w.days ? ` · ${w.days}` : ""}{w.rate_note ? ` · ${w.rate_note}` : ""}</div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => remove(w.id)} className="text-red-400 h-7 px-2" data-testid={`cn-window-delete-${w.id}`}><Trash2 size={13} /></Button>
            </div>
          ))}
          {!windows.length && <div className="py-10 text-center text-slate-500 text-sm">No windows logged yet. Every call with a carrier contact should end with at least one lane + day window captured here.</div>}
        </div>
      </Card>
    </div>
  );
}

function RateCardsTab() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ carrier_name: "", carrier_mc: "", origin: "", destination: "", equipment: "Van", rate_type: "flat", rate_usd: "", rpm_usd: "", valid_until: "", loads_per_week: "", notes: "" });
  const load = () => api.get("/carrier-rate-cards").then(({ data }) => setData(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.carrier_name || !form.origin || !form.destination) { toast.error("Carrier, origin and destination required"); return; }
    try {
      await api.post("/carrier-rate-cards", {
        ...form,
        rate_usd: Number(form.rate_usd) || 0,
        rpm_usd: Number(form.rpm_usd) || 0,
        loads_per_week: Number(form.loads_per_week) || 0,
      });
      toast.success("Rate card locked in — First Strike now bids off this cost");
      setForm({ carrier_name: "", carrier_mc: "", origin: "", destination: "", equipment: "Van", rate_type: "flat", rate_usd: "", rpm_usd: "", valid_until: "", loads_per_week: "", notes: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const toggle = async (c) => {
    try { await api.patch(`/carrier-rate-cards/${c.id}`, { active: !c.active }); load(); } catch (e) { toast.error("Update failed"); }
  };
  const remove = async (id) => {
    try { await api.delete(`/carrier-rate-cards/${id}`); toast.success("Deleted"); load(); } catch (e) { toast.error("Delete failed"); }
  };
  const selCls = "bg-[#11151F] border border-white/10 rounded px-2 py-2 text-xs text-white w-full";

  return (
    <div className="space-y-4">
      <Card className="hud-surface p-4 border-cyan-500/20" data-testid="rc-firststrike-banner">
        <div className="flex items-center gap-2 text-xs text-cyan-300">
          <Zap size={14} className="text-amber-400" />
          <span><b>Wired into First Strike:</b> on lanes with a live card, bids are priced off your contracted carrier cost with a hard margin floor — loads that can't clear min margin at YOUR cost are auto-skipped, and won loads book straight to the contracted carrier.</span>
        </div>
        {data && (
          <div className="flex gap-5 mt-3 text-[10px] font-mono text-slate-400">
            <span><b className="text-cyan-300">{data.live_count}</b> live cards</span>
            <span><b className="text-cyan-300">{data.lanes_covered}</b> lanes covered</span>
            <span><b className="text-cyan-300">{data.weekly_capacity_committed}</b> loads/wk committed capacity</span>
            <span><b className="text-emerald-300">{data.moved_this_week_total}</b> moved this week</span>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="hud-surface p-5" data-testid="rc-form">
          <h3 className="font-display text-base font-bold text-white mb-3">Lock In a Pre-Negotiated Rate</h3>
          <div className="space-y-2.5">
            <CarrierCombobox value={form.carrier_name} onChange={(v) => setForm({ ...form, carrier_name: v })}
              onSelect={(rec) => setForm((f) => ({ ...f, carrier_name: rec.name, carrier_mc: rec.mc || f.carrier_mc }))}
              placeholder="Carrier *" className="bg-[#11151F] border-white/10" testid="rc-carrier" />
            <div className="grid grid-cols-2 gap-2">
              <Input value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })} placeholder="Origin * (Minneapolis, MN)" className="bg-[#11151F] border-white/10" data-testid="rc-origin" />
              <Input value={form.destination} onChange={(e) => setForm({ ...form, destination: e.target.value })} placeholder="Destination * (Chicago, IL)" className="bg-[#11151F] border-white/10" data-testid="rc-destination" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })} className={selCls} data-testid="rc-equipment">
                {["Van", "Reefer", "Flatbed", "Any"].map((x) => <option key={x}>{x}</option>)}
              </select>
              <select value={form.rate_type} onChange={(e) => setForm({ ...form, rate_type: e.target.value })} className={selCls} data-testid="rc-rate-type">
                <option value="flat">Flat rate ($/load)</option>
                <option value="per_mile">Per mile ($/mi)</option>
              </select>
            </div>
            {form.rate_type === "flat" ? (
              <Input type="number" value={form.rate_usd} onChange={(e) => setForm({ ...form, rate_usd: e.target.value })} placeholder="Contracted rate $ *" className="bg-[#11151F] border-white/10" data-testid="rc-rate-usd" />
            ) : (
              <Input type="number" step="0.01" value={form.rpm_usd} onChange={(e) => setForm({ ...form, rpm_usd: e.target.value })} placeholder="Rate per mile $ *" className="bg-[#11151F] border-white/10" data-testid="rc-rpm-usd" />
            )}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">Valid until (blank = evergreen)</div>
                <Input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} className="bg-[#11151F] border-white/10" data-testid="rc-valid-until" />
              </div>
              <div>
                <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">Committed loads/wk</div>
                <Input type="number" value={form.loads_per_week} onChange={(e) => setForm({ ...form, loads_per_week: e.target.value })} className="bg-[#11151F] border-white/10" data-testid="rc-loads-week" />
              </div>
            </div>
            <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes (quick-pay, tarps incl…)" className="bg-[#11151F] border-white/10" />
            <Button onClick={create} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="rc-save-btn">Lock In Rate</Button>
          </div>
        </Card>

        <Card className="hud-surface p-5 lg:col-span-2" data-testid="rc-list">
          <h3 className="font-display text-base font-bold text-white mb-3">Contracted Lane Rates ({data?.count || 0})</h3>
          <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-[#0B0E14]">
                <tr className="text-left text-[9px] font-mono uppercase tracking-widest text-slate-500 border-b border-white/10">
                  <th className="py-2 pr-3">Lane</th><th className="py-2 pr-3">Carrier</th><th className="py-2 pr-3">Equip</th>
                  <th className="py-2 pr-3">Rate</th><th className="py-2 pr-3">Wk Util</th><th className="py-2 pr-3">Status</th><th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {(data?.cards || []).map((c) => (
                  <tr key={c.id} className="border-b border-white/5 hover:bg-white/[0.02]" data-testid={`rc-row-${c.id}`}>
                    <td className="py-2 pr-3 text-slate-200 whitespace-nowrap">{c.origin} → {c.destination}<div className="text-[8px] font-mono text-slate-600">{c.lane_key}</div></td>
                    <td className="py-2 pr-3 text-slate-300">{c.carrier_name}{c.carrier_mc && <div className="text-[8px] font-mono text-slate-600">MC {c.carrier_mc}</div>}</td>
                    <td className="py-2 pr-3 font-mono text-slate-400">{c.equipment}</td>
                    <td className="py-2 pr-3 font-mono text-cyan-300">{c.rate_type === "per_mile" ? `$${c.rpm_usd}/mi` : `$${Number(c.rate_usd).toLocaleString()}`}</td>
                    <td className="py-2 pr-3" data-testid={`rc-util-${c.id}`}>
                      <div className="font-mono text-slate-300">{c.moved_this_week || 0}<span className="text-slate-600">/{c.loads_per_week || "—"}</span></div>
                      {c.utilization_pct != null && (
                        <div className="h-1 w-16 rounded bg-white/5 overflow-hidden mt-0.5">
                          <div className={`h-full rounded ${c.utilization_pct >= 100 ? "bg-emerald-400" : c.utilization_pct >= 50 ? "bg-cyan-400" : "bg-amber-400"}`}
                            style={{ width: `${Math.min(c.utilization_pct, 100)}%` }} />
                        </div>
                      )}
                    </td>
                    <td className="py-2 pr-3">
                      <button onClick={() => toggle(c)} data-testid={`rc-toggle-${c.id}`}>
                        <Badge className={c.live ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[8px] font-mono" : "bg-slate-500/15 text-slate-400 border-slate-500/30 text-[8px] font-mono"}>
                          {c.live ? "LIVE — FEEDING FIRST STRIKE" : (c.active ? "EXPIRED" : "PAUSED")}
                        </Badge>
                      </button>
                    </td>
                    <td className="py-2 text-right">
                      <Button size="sm" variant="ghost" onClick={() => remove(c.id)} className="text-red-400 h-6 px-1.5" data-testid={`rc-delete-${c.id}`}><Trash2 size={12} /></Button>
                    </td>
                  </tr>
                ))}
                {!(data?.cards || []).length && <tr><td colSpan={7} className="py-10 text-center text-slate-500">No rate cards yet — every locked rate turns First Strike from market-guesser into cost-certain sniper.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}

function PlaybookTab({ playbook }) {
  if (!playbook) return null;
  const rp = playbook.realistic_play || {};
  return (
    <div className="space-y-4" data-testid="cn-playbook-panel">
      <Card className="hud-surface p-5">
        <h3 className="font-display text-base font-bold text-white mb-2">The Strategy</h3>
        <p className="text-sm text-slate-300">{playbook.strategy}</p>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(playbook.categories || []).map((c) => (
          <Card key={c.key} className="hud-surface p-5" data-testid={`cn-playbook-${c.key}`}>
            <h4 className="text-sm font-bold text-cyan-300 mb-1">{c.label}</h4>
            <div className="text-xs text-slate-400 mb-2">{c.why}</div>
            <div className="p-2.5 rounded border border-amber-500/20 bg-amber-500/5 text-xs text-amber-200/90">“{c.pitch}”</div>
            <div className="text-[9px] font-mono text-slate-500 mt-2 uppercase">Target: {c.target_locked_min}–{c.target_locked} locked in</div>
          </Card>
        ))}
      </div>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-base font-bold text-white mb-3">The Realistic Play</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-300">
          {Object.entries(rp).map(([k, v]) => (
            <div key={k} className="p-2.5 rounded border border-white/10 bg-white/[0.02]">
              <div className="text-[9px] font-mono uppercase text-slate-500 mb-1">{k.replace(/_/g, " ")}</div>{v}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
