import React, { useCallback, useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Droplets, Sparkles, Users, ClipboardList, BookOpenText, FileDown, Bot, Plus, Trash2, Loader2, RefreshCw, Send, TrendingUp } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { toast } from "sonner";
import { api } from "../lib/api";

const TABS = [
  { id: "dashboard", label: "Command Deck", icon: Sparkles },
  { id: "clients", label: "Clients", icon: Users },
  { id: "jobs", label: "Jobs", icon: ClipboardList },
  { id: "playbook", label: "Playbook", icon: BookOpenText },
  { id: "docs", label: "Branded Docs", icon: FileDown },
  { id: "advisor", label: "AI Profit Advisor", icon: Bot },
];
const PLAN_LABEL = { one_time: "One-time", biweekly_sub: "Bi-weekly sub", fleet_sub: "Fleet sub" };
const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");

const Orbs = () => (
  <div className="pointer-events-none absolute inset-0 overflow-hidden">
    <div className="tc-orb" style={{ top: "-80px", left: "8%", background: "radial-gradient(circle, rgba(245,158,11,0.35), transparent 65%)", width: 420, height: 420, animationDelay: "0s" }} />
    <div className="tc-orb" style={{ top: "30%", right: "-120px", background: "radial-gradient(circle, rgba(34,211,238,0.28), transparent 65%)", width: 520, height: 520, animationDelay: "2s" }} />
    <div className="tc-orb" style={{ bottom: "-140px", left: "35%", background: "radial-gradient(circle, rgba(168,85,247,0.22), transparent 65%)", width: 460, height: 460, animationDelay: "4s" }} />
    <style>{`
      .tc-orb { position:absolute; border-radius:9999px; filter: blur(48px); animation: tcFloat 9s ease-in-out infinite; }
      @keyframes tcFloat { 0%,100%{ transform: translateY(0) scale(1); opacity:.8 } 50%{ transform: translateY(-34px) scale(1.08); opacity:1 } }
      .tc-glow { box-shadow: 0 0 32px -6px rgba(245,158,11,.35), inset 0 0 22px -14px rgba(245,158,11,.5); }
    `}</style>
  </div>
);

function Dashboard({ metrics, qb, onSync }) {
  if (!metrics) return <div className="text-slate-500 font-mono text-sm">Loading…</div>;
  const k = metrics.kpis;
  const tiles = [
    ["Revenue (completed)", `$${k.revenue_total.toLocaleString()}`, "#F59E0B"],
    ["Gross profit", `$${k.gross_profit.toLocaleString()}`, "#34D399"],
    ["Gross margin", `${k.gross_margin_pct}%`, "#34D399"],
    ["MRR locked (subs)", `$${Math.round(k.mrr_locked).toLocaleString()}`, "#22D3EE"],
    ["Clients", k.clients, "#A78BFA"],
    ["Subscriptions", k.subscriptions, "#22D3EE"],
    ["Cabs cleaned", k.cabs_cleaned, "#F59E0B"],
    ["Upsell revenue", `$${k.upsell_revenue.toLocaleString()}`, "#FB923C"],
  ];
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {tiles.map(([label, val, color]) => (
          <div key={label} className="tc-glow relative p-4 rounded-2xl border border-white/10 bg-slate-950/70 backdrop-blur">
            <div className="text-2xl font-black tabular-nums" style={{ color }}>{val}</div>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-1">{label}</div>
          </div>
        ))}
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="md:col-span-2 p-4 bg-slate-950/70 border-white/10 backdrop-blur" data-testid="tc-revenue-chart">
          <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2 mb-2"><TrendingUp size={13} /> Revenue tracker</div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metrics.monthly}>
                <defs><linearGradient id="tcRev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.5} /><stop offset="100%" stopColor="#F59E0B" stopOpacity={0} />
                </linearGradient></defs>
                <XAxis dataKey="month" stroke="#475569" fontSize={10} />
                <YAxis stroke="#475569" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0D1117", border: "1px solid rgba(255,255,255,.1)", fontSize: 12 }} />
                <Area type="monotone" dataKey="revenue" stroke="#F59E0B" strokeWidth={2} fill="url(#tcRev)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <div className="space-y-4">
          <Card className="p-4 bg-slate-950/70 border-amber-500/30 backdrop-blur" data-testid="tc-goal-card">
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-2">Territory goal · $180K/yr run-rate</div>
            <div className="text-3xl font-black text-amber-400 tabular-nums">{k.goal_pct}%</div>
            <div className="mt-2 h-2.5 rounded-full bg-white/10 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${Math.min(100, k.goal_pct)}%`, background: "linear-gradient(90deg,#F59E0B,#22D3EE)" }} />
            </div>
            <div className="text-[10px] text-slate-500 mt-2">Sub MRR × 12 vs goal · avg ticket ${k.avg_ticket}</div>
          </Card>
          <Card className="p-4 bg-slate-950/70 border-emerald-500/30 backdrop-blur" data-testid="tc-qb-card">
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5">QuickBooks</div>
            <div className={`text-sm font-black ${qb?.connected ? "text-emerald-400" : "text-orange-300"}`}>
              {qb?.connected ? "CONNECTED" : "AWAITING OAUTH"}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">{qb?.pending_sync ?? 0} paid jobs pending sync</div>
            <button onClick={onSync} data-testid="tc-qb-sync-btn"
                    className="mt-2 px-3 py-1.5 rounded-full border border-emerald-500/40 text-emerald-300 text-xs font-bold inline-flex items-center gap-1.5 hover:bg-emerald-500/10">
              <RefreshCw size={12} /> Sync paid jobs
            </button>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Clients({ clients, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ company: "", contact: "", phone: "", email: "", cabs: 1, plan: "one_time", rate: 150, source: "", notes: "" });
  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/truck-cleaning/clients", { ...form, cabs: Number(form.cabs), rate: Number(form.rate) }); toast.success("Client added"); setOpen(false); reload(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  return (
    <div>
      <div className="flex justify-end mb-3">
        <button onClick={() => setOpen(!open)} data-testid="tc-add-client-btn" className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Plus size={13} /> Add Client</button>
      </div>
      {open && (
        <form onSubmit={add} className="mb-4 p-4 rounded-xl border border-white/10 bg-slate-950/70 grid sm:grid-cols-4 gap-2" data-testid="tc-client-form">
          {[["company", "Company *"], ["contact", "Contact"], ["phone", "Phone"], ["email", "Email"], ["cabs", "Cabs"], ["rate", "Rate $/cab"], ["source", "Lead source"]].map(([k, ph]) => (
            <input key={k} required={ph.includes("*")} value={form[k]} placeholder={ph} type={["cabs", "rate"].includes(k) ? "number" : "text"}
                   data-testid={`tc-client-${k}-input`} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                   className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs outline-none focus:border-amber-400" />
          ))}
          <select value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })} data-testid="tc-client-plan-select"
                  className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs">
            <option value="one_time">One-time · $150</option><option value="biweekly_sub">Bi-weekly sub · $120</option><option value="fleet_sub">Fleet sub · $125</option>
          </select>
          <button type="submit" data-testid="tc-client-submit" className="h-9 rounded-full bg-amber-500 text-black font-bold text-xs">Save</button>
        </form>
      )}
      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Client</th><th className="p-3">Plan</th><th className="p-3">Cabs</th><th className="p-3">Rate</th><th className="p-3">Source</th><th className="p-3" /></tr></thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.client_id} className="border-b border-white/5" data-testid={`tc-client-row-${c.client_id}`}>
                <td className="p-3"><div className="font-semibold text-white">{c.company}{c.is_sample && <span className="ml-1.5 text-[8px] font-mono px-1 rounded bg-white/5 text-slate-500 border border-white/10">SAMPLE</span>}</div><div className="text-[10px] text-slate-500">{c.contact}</div></td>
                <td className="p-3 text-xs text-cyan-300 font-mono">{PLAN_LABEL[c.plan]}</td>
                <td className="p-3 tabular-nums">{c.cabs}</td>
                <td className="p-3 tabular-nums text-amber-300">${c.rate}</td>
                <td className="p-3 text-xs text-slate-500">{c.source || "—"}</td>
                <td className="p-3"><button onClick={async () => { await api.delete(`/truck-cleaning/clients/${c.client_id}`); reload(); }} className="text-slate-600 hover:text-red-400"><Trash2 size={14} /></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Jobs({ jobs, clients, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ client_id: "", date: "", cabs: 1, upsells: [] });
  const toggleUp = (u) => setForm((f) => ({ ...f, upsells: f.upsells.includes(u) ? f.upsells.filter((x) => x !== u) : [...f.upsells, u] }));
  const add = async (e) => {
    e.preventDefault();
    try { await api.post("/truck-cleaning/jobs", { ...form, cabs: Number(form.cabs) }); toast.success("Job scheduled"); setOpen(false); reload(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };
  const setStatus = async (id, status) => { try { await api.post(`/truck-cleaning/jobs/${id}/status`, { status }); reload(); } catch (e2) { toast.error(errTxt(e2)); } };
  return (
    <div>
      <div className="flex justify-end mb-3">
        <button onClick={() => setOpen(!open)} data-testid="tc-add-job-btn" className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Plus size={13} /> Schedule Job</button>
      </div>
      {open && (
        <form onSubmit={add} className="mb-4 p-4 rounded-xl border border-white/10 bg-slate-950/70 flex flex-wrap gap-2 items-center" data-testid="tc-job-form">
          <select required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} data-testid="tc-job-client-select"
                  className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs min-w-[180px]">
            <option value="">Select client…</option>
            {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
          </select>
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="tc-job-date-input"
                 className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs" />
          <input type="number" min="1" value={form.cabs} onChange={(e) => setForm({ ...form, cabs: e.target.value })} data-testid="tc-job-cabs-input"
                 className="h-9 w-20 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs" />
          {[["engine_bay", "Engine bay +$25"], ["tire_dressing", "Tires +$20"], ["cabin_filter", "Filter +$15"]].map(([u, l]) => (
            <button type="button" key={u} onClick={() => toggleUp(u)}
                    className={`h-9 px-3 rounded-full border text-[11px] font-bold ${form.upsells.includes(u) ? "border-amber-400 text-amber-300 bg-amber-500/10" : "border-white/15 text-slate-400"}`}>{l}</button>
          ))}
          <button type="submit" data-testid="tc-job-submit" className="h-9 px-5 rounded-full bg-amber-500 text-black font-bold text-xs">Book</button>
        </form>
      )}
      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Job</th><th className="p-3">Client</th><th className="p-3">Cabs</th><th className="p-3">Price</th><th className="p-3">Margin</th><th className="p-3">QB</th><th className="p-3">Status</th></tr></thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id} className="border-b border-white/5" data-testid={`tc-job-row-${j.job_id}`}>
                <td className="p-3 font-mono text-[11px] text-amber-300">{j.job_id}<div className="text-slate-600">{j.date}</div></td>
                <td className="p-3 text-slate-200 text-xs">{j.company}</td>
                <td className="p-3 tabular-nums">{j.cabs}</td>
                <td className="p-3 tabular-nums font-bold">${j.price.toLocaleString()}</td>
                <td className="p-3 tabular-nums text-emerald-400">${(j.price - j.cogs).toLocaleString()}</td>
                <td className="p-3 text-[10px] font-mono">{j.qb_synced ? <span className="text-emerald-400">SYNCED</span> : <span className="text-slate-600">—</span>}</td>
                <td className="p-3">
                  <select value={j.status} onChange={(e) => setStatus(j.job_id, e.target.value)} data-testid={`tc-job-status-${j.job_id}`}
                          className="h-8 rounded bg-slate-950 border border-white/10 text-[11px] font-mono px-1">
                    <option value="scheduled">scheduled</option><option value="completed">completed</option><option value="paid">paid</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Playbook({ pb }) {
  if (!pb) return null;
  return (
    <div className="space-y-5" data-testid="tc-playbook">
      {[pb.business_plan, pb.marketing_plan, pb.branding_campaign, pb.deployment_plan].map((sec) => (
        <Card key={sec.title} className="p-5 bg-slate-950/70 border-white/10 backdrop-blur">
          <div className="font-black text-amber-300 mb-2">{sec.title}</div>
          {sec.summary && <p className="text-sm text-slate-300 mb-3">{sec.summary}</p>}
          {sec.sections?.map((s) => (
            <div key={s.h} className="mb-3"><div className="text-[11px] font-mono uppercase text-cyan-300 mb-1">{s.h}</div>
              <ul className="space-y-1">{s.items.map((i) => <li key={i} className="text-[13px] text-slate-300 flex gap-2"><span className="text-amber-400">▸</span>{i}</li>)}</ul></div>
          ))}
          {sec.channels && (
            <div className="grid sm:grid-cols-2 gap-3">
              {sec.channels.map((ch) => (
                <div key={ch.name} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]">
                  <div className="font-bold text-white text-sm">{ch.name} <span className="text-[10px] font-mono text-amber-300">{ch.budget}</span></div>
                  <div className="text-[11px] text-emerald-400 font-mono">{ch.expected}</div>
                  <p className="text-[12px] text-slate-400 mt-1">{ch.detail}</p>
                </div>
              ))}
            </div>
          )}
          {sec.identity && (
            <div className="mb-3 p-3 rounded-xl border border-amber-500/30 bg-amber-500/5 text-[13px] text-slate-300">
              <b className="text-amber-300">{sec.identity.name}</b> — “{sec.identity.tagline}” · {sec.identity.voice} · {sec.identity.colors}
            </div>
          )}
          {sec.platforms && (
            <div className="grid sm:grid-cols-2 gap-3">
              {sec.platforms.map((p) => (
                <div key={p.name} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]">
                  <div className="font-bold text-white text-sm">{p.name} <span className="text-[10px] font-mono text-cyan-300">{p.cadence}</span></div>
                  <p className="text-[12px] text-slate-400 mt-1">{p.play}</p>
                </div>
              ))}
            </div>
          )}
          {sec.milestones && (
            <div className="space-y-2">{sec.milestones.map((mi) => (
              <div key={mi.when} className="flex gap-3 text-[13px]"><span className="font-mono text-amber-300 w-24 shrink-0">{mi.when}</span><span className="text-slate-300">{mi.what}</span></div>
            ))}</div>
          )}
          {sec.kpis && <div className="mt-3 flex flex-wrap gap-2">{sec.kpis.map((kp) => <span key={kp} className="text-[10px] font-mono px-2 py-1 rounded-full border border-cyan-500/40 text-cyan-300">{kp}</span>)}</div>}
        </Card>
      ))}
    </div>
  );
}

function Docs() {
  const download = async (id, name) => {
    try {
      const r = await api.get(`/truck-cleaning/docs/${id}.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `${name}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (_) { toast.error("Failed to generate document"); }
  };
  const docs = [
    ["proposal", "Fleet Cleaning Proposal", "Client-facing pitch: the 45-min spec, fleet pricing, why Orisei"],
    ["agreement", "Fleet Services Agreement", "Signable month-to-month contract with billing + quality terms"],
    ["report-card", "Post-Clean Report Card", "Crew checklist + driver sign-off delivered with photo proof"],
  ];
  return (
    <div className="grid sm:grid-cols-3 gap-4" data-testid="tc-docs">
      {docs.map(([id, name, d]) => (
        <Card key={id} className="p-5 bg-slate-950/70 border-white/10 backdrop-blur hover:border-amber-500/40 transition">
          <FileDown className="text-amber-400 mb-3" size={22} />
          <div className="font-black text-white">{name}</div>
          <p className="text-[12px] text-slate-400 mt-1 mb-4">{d}</p>
          <button onClick={() => download(id, name.replace(/ /g, "_"))} data-testid={`tc-doc-${id}-btn`}
                  className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs">Download PDF</button>
        </Card>
      ))}
    </div>
  );
}

function Advisor() {
  const [msgs, setMsgs] = useState([{ role: "ai", text: "I'm your profit advisor for Orisei Truck Cleaning. Ask me anything — pricing, upsells, crew utilization, which marketing channel to double down on. I can see your live numbers." }]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  const ask = async (e) => {
    e.preventDefault();
    if (!q.trim() || busy) return;
    const question = q; setQ("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const { data } = await api.post("/truck-cleaning/assistant", { question, session_id: "tc-advisor" }, { timeout: 90000 });
      setMsgs((m) => [...m, { role: "ai", text: data.answer }]);
    } catch (e2) { setMsgs((m) => [...m, { role: "ai", text: "Hit a snag — try again in a moment." }]); }
    finally { setBusy(false); }
  };
  return (
    <Card className="bg-slate-950/70 border-white/10 backdrop-blur flex flex-col h-[560px]" data-testid="tc-advisor">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {msgs.map((m, i) => (
          <div key={i} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${m.role === "user" ? "ml-auto bg-amber-500 text-black font-semibold" : "bg-white/5 border border-white/10 text-slate-200"}`}>
            {m.text}
          </div>
        ))}
        {busy && <div className="flex items-center gap-2 text-slate-500 text-xs font-mono"><Loader2 size={13} className="animate-spin" /> crunching your numbers…</div>}
        <div ref={endRef} />
      </div>
      <form onSubmit={ask} className="p-3 border-t border-white/5 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. How do I get to $3K MRR fastest?" data-testid="tc-advisor-input"
               className="flex-1 h-11 rounded-full bg-slate-950 border border-white/15 px-4 text-sm outline-none focus:border-amber-400" />
        <button type="submit" disabled={busy} data-testid="tc-advisor-send" className="h-11 w-11 rounded-full bg-amber-500 text-black grid place-items-center disabled:opacity-60"><Send size={16} /></button>
      </form>
    </Card>
  );
}

export default function TruckCleaning() {
  const [tab, setTab] = useState("dashboard");
  const [metrics, setMetrics] = useState(null);
  const [clients, setClients] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [pb, setPb] = useState(null);
  const [qb, setQb] = useState(null);

  const reload = useCallback(async () => {
    try {
      const [m, c, j, q] = await Promise.all([
        api.get("/truck-cleaning/metrics"), api.get("/truck-cleaning/clients"),
        api.get("/truck-cleaning/jobs"), api.get("/truck-cleaning/quickbooks/status"),
      ]);
      setMetrics(m.data); setClients(c.data.clients); setJobs(j.data.jobs); setQb(q.data);
    } catch (_) {}
  }, []);
  useEffect(() => { reload(); api.get("/truck-cleaning/playbook").then((r) => setPb(r.data)).catch(() => {}); }, [reload]);

  const sync = async () => {
    try { const { data } = await api.post("/truck-cleaning/quickbooks/sync"); data.ok ? toast.success(data.message) : toast.info(data.message); reload(); }
    catch (_) { toast.error("Sync failed"); }
  };

  return (
    <>
      <Topbar title="Orisei Truck Cleaning Solutions" subtitle="Your cab. Showroom clean. Every time. — Twin Cities division command deck" />
      <div className="relative p-4 md:p-6" data-testid="truck-cleaning-page">
        <Orbs />
        <div className="relative flex items-center gap-3 mb-5">
          <img src="/orisei-logo.svg" alt="Orisei" className="h-10 w-10 drop-shadow-[0_0_14px_rgba(245,158,11,0.6)]" />
          <div className="flex flex-wrap gap-2">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tc-tab-${t.id}`}
                      className={`px-4 py-2 rounded-full text-xs font-bold inline-flex items-center gap-1.5 border transition ${tab === t.id ? "bg-amber-500 text-black border-amber-500" : "border-white/15 text-slate-300 hover:border-amber-400/50"}`}>
                <t.icon size={13} /> {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="relative">
          {tab === "dashboard" && <Dashboard metrics={metrics} qb={qb} onSync={sync} />}
          {tab === "clients" && <Clients clients={clients} reload={reload} />}
          {tab === "jobs" && <Jobs jobs={jobs} clients={clients} reload={reload} />}
          {tab === "playbook" && <Playbook pb={pb} />}
          {tab === "docs" && <Docs />}
          {tab === "advisor" && <Advisor />}
        </div>
      </div>
    </>
  );
}
