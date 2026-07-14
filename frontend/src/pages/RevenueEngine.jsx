import React, { useCallback, useEffect, useState } from "react";
import Topbar from "@/components/Topbar";
import { api, BACKEND_URL } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Zap, Mail, Users, Store, Wallet, Loader2, FileDown, Send, Trophy, XCircle,
  Sparkles, Upload, RefreshCw, ExternalLink, DollarSign,
} from "lucide-react";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const inputCls = "h-9 rounded bg-slate-950 border border-white/10 font-mono text-[11px] px-3 text-slate-200 placeholder:text-slate-600 w-full";
const QUOTE_STATUS = { draft: "text-slate-400", sent: "text-cyan-300", won: "text-emerald-300", lost: "text-red-300", expired: "text-slate-600" };
const STAGES = ["new", "sequenced", "replied", "discovery", "won", "lost"];

function Stat({ label, value, accent = "text-emerald-300", tid }) {
  return (
    <div className="rounded border border-white/10 bg-white/[0.03] px-3 py-2 min-w-[118px]" data-testid={tid}>
      <div className={`font-mono font-bold text-base ${accent}`}>{value}</div>
      <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-500">{label}</div>
    </div>
  );
}

function QuotesTab({ refreshDash }) {
  const [quotes, setQuotes] = useState([]);
  const [emailText, setEmailText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [form, setForm] = useState({ origin: "", destination: "", equipment: "Van", company: "", contact: "", email: "" });
  const [creating, setCreating] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/revenue/quotes"); setQuotes(data.items); } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const parse = async () => {
    setParsing(true);
    try {
      const { data } = await api.post("/revenue/quotes/parse", { email_text: emailText });
      toast.success(`⚡ Parsed & priced — ${data.quote.quote_id} at $${fmt(data.quote.pricing.sell_usd)} all-in`);
      setEmailText(""); load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Parse failed"); }
    finally { setParsing(false); }
  };
  const create = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/revenue/quotes", form);
      toast.success(`${data.quote_id} priced: $${fmt(data.pricing.sell_usd)} all-in ($${data.pricing.rpm_all_in}/mi)`);
      setForm({ origin: "", destination: "", equipment: "Van", company: "", contact: "", email: "" });
      load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Quote failed"); }
    finally { setCreating(false); }
  };
  const send = async (q) => {
    let to = q.shipper?.email;
    if (!to) { to = window.prompt("Recipient email:"); if (!to) return; }
    setBusyId(q.quote_id);
    try {
      const { data } = await api.post(`/revenue/quotes/${q.quote_id}/send`, { to_email: to });
      toast.success(data.status === "sent" ? "📤 Quote emailed" : "📥 Queued — sends the moment your Resend key is connected");
      load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Send failed"); }
    finally { setBusyId(null); }
  };
  const setStatus = async (q, status) => {
    setBusyId(q.quote_id);
    try {
      const { data } = await api.post(`/revenue/quotes/${q.quote_id}/status`, { status });
      toast.success(status === "won" && data.marketplace_load
        ? `🏆 WON — auto-posted to marketplace as ${data.marketplace_load.mkt_id}`
        : `Marked ${status}`);
      load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Update failed"); }
    finally { setBusyId(null); }
  };
  const pdf = async (q) => {
    try {
      const res = await api.get(`/revenue/quotes/${q.quote_id}/pdf`, { responseType: "blob" });
      window.open(window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" })), "_blank");
    } catch { toast.error("PDF failed"); }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="hud-surface p-4" data-testid="quote-email-parser">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 mb-2 flex items-center gap-1.5">
            <Mail size={12} /> Email → Quote (AI)
          </div>
          <textarea value={emailText} onChange={(e) => setEmailText(e.target.value)} rows={6}
            data-testid="quote-email-input"
            placeholder={"Paste the shipper's email…\n\ne.g. \"Hi, we need a reefer from Miami FL to Chicago IL next Tuesday, 38k lbs of frozen produce. Can you quote? — Dana, Fresh Farms\""}
            className="w-full rounded bg-slate-950 border border-white/10 font-mono text-[11px] p-3 text-slate-200 placeholder:text-slate-600" />
          <Button onClick={parse} disabled={parsing || emailText.trim().length < 15} data-testid="quote-parse-btn"
            className="mt-2 bg-cyan-500 hover:bg-cyan-400 text-black font-black font-mono text-[10px] uppercase">
            {parsing ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Zap size={12} className="mr-1" />}
            Parse & Price Instantly
          </Button>
        </Card>
        <Card className="hud-surface p-4" data-testid="quote-manual-form">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 mb-2">Manual Quote</div>
          <div className="grid grid-cols-2 gap-2">
            <input className={inputCls} placeholder="Origin (City, ST)" value={form.origin} data-testid="quote-origin-input"
              onChange={(e) => setForm({ ...form, origin: e.target.value })} />
            <input className={inputCls} placeholder="Destination (City, ST)" value={form.destination} data-testid="quote-dest-input"
              onChange={(e) => setForm({ ...form, destination: e.target.value })} />
            <select className={inputCls} value={form.equipment} data-testid="quote-equipment-select"
              onChange={(e) => setForm({ ...form, equipment: e.target.value })}>
              {["Van", "Reefer", "Flatbed"].map((x) => <option key={x}>{x}</option>)}
            </select>
            <input className={inputCls} placeholder="Shipper company" value={form.company}
              onChange={(e) => setForm({ ...form, company: e.target.value })} />
            <input className={inputCls} placeholder="Contact name" value={form.contact}
              onChange={(e) => setForm({ ...form, contact: e.target.value })} />
            <input className={inputCls} placeholder="Contact email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <Button onClick={create} disabled={creating || !form.origin || !form.destination} data-testid="quote-create-btn"
            className="mt-2 bg-emerald-500 hover:bg-emerald-400 text-black font-black font-mono text-[10px] uppercase">
            {creating ? <Loader2 size={12} className="mr-1 animate-spin" /> : <DollarSign size={12} className="mr-1" />}
            Price This Lane
          </Button>
          <div className="text-[9px] font-mono text-slate-500 mt-2">
            Pricing: market RPM × lane imbalance × seasonality + FSC · shipper self-serve portal at <span className="text-cyan-400">/get-quote</span>
          </div>
        </Card>
      </div>
      <Card className="hud-surface p-4" data-testid="quotes-table">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Quote Pipeline ({quotes.length})</div>
        <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
          {quotes.length === 0 && <div className="text-[10px] font-mono text-slate-500">No quotes yet — paste a shipper email above or price a lane manually.</div>}
          {quotes.map((q) => (
            <div key={q.quote_id} className="text-[10px] font-mono p-2 rounded bg-white/[0.02] flex flex-wrap items-center gap-2 justify-between">
              <div className="min-w-0">
                <span className="text-slate-200">{q.quote_id}</span>
                <span className={`ml-2 uppercase ${QUOTE_STATUS[q.status]}`}>{q.status}</span>
                <span className="ml-2 text-[8px] border border-white/10 rounded px-1 text-slate-500 uppercase">{q.source}</span>
                <div className="text-slate-500">{q.pricing.origin} → {q.pricing.destination} · {q.pricing.equipment} · {q.pricing.miles} mi · {q.shipper?.company || "—"}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-emerald-300">${fmt(q.pricing.sell_usd)}</span>
                <span className="text-yellow-300">+${fmt(q.pricing.margin_usd)}</span>
                <button onClick={() => pdf(q)} title="Quote PDF" className="text-slate-400 hover:text-cyan-300" data-testid={`quote-pdf-${q.quote_id}`}><FileDown size={13} /></button>
                <button onClick={() => send(q)} disabled={busyId === q.quote_id} title="Email quote" className="text-slate-400 hover:text-cyan-300" data-testid={`quote-send-${q.quote_id}`}><Send size={13} /></button>
                {q.status !== "won" && <button onClick={() => setStatus(q, "won")} disabled={busyId === q.quote_id} title="Mark won → auto-post to marketplace" className="text-slate-400 hover:text-emerald-300" data-testid={`quote-won-${q.quote_id}`}><Trophy size={13} /></button>}
                {q.status !== "lost" && <button onClick={() => setStatus(q, "lost")} disabled={busyId === q.quote_id} title="Mark lost" className="text-slate-400 hover:text-red-300"><XCircle size={13} /></button>}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function ProspectsTab({ refreshDash }) {
  const [prospects, setProspects] = useState([]);
  const [queue, setQueue] = useState({ items: [], awaiting_key: 0, resend_connected: false });
  const [form, setForm] = useState({ company: "", contact_name: "", email: "", city_state: "", industry: "", est_loads_week: 3 });
  const [csvText, setCsvText] = useState("");
  const [gen, setGen] = useState({ region: "Midwest", industry: "food & beverage", count: 8 });
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, q] = await Promise.all([api.get("/revenue/prospects"), api.get("/revenue/outreach/queue")]);
      setProspects(p.data.items); setQueue(q.data);
    } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const run = async (key, fn, okMsg) => {
    setBusy(key);
    try { await fn(); if (okMsg) toast.success(okMsg); load(); refreshDash(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="hud-surface p-4" data-testid="prospect-add-form">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 mb-2">Add Prospect</div>
          <div className="space-y-2">
            <input className={inputCls} placeholder="Company *" value={form.company} data-testid="prospect-company-input"
              onChange={(e) => setForm({ ...form, company: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <input className={inputCls} placeholder="Contact" value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
              <input className={inputCls} placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              <input className={inputCls} placeholder="City, ST" value={form.city_state} onChange={(e) => setForm({ ...form, city_state: e.target.value })} />
              <input className={inputCls} placeholder="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
            </div>
            <Button onClick={() => run("add", () => api.post("/revenue/prospects", form).then(() => setForm({ company: "", contact_name: "", email: "", city_state: "", industry: "", est_loads_week: 3 })), "Prospect added")}
              disabled={!form.company || busy === "add"} data-testid="prospect-add-btn"
              className="bg-emerald-500 hover:bg-emerald-400 text-black font-black font-mono text-[10px] uppercase w-full">
              {busy === "add" ? <Loader2 size={12} className="animate-spin" /> : "Add To Pipeline"}
            </Button>
          </div>
        </Card>
        <Card className="hud-surface p-4" data-testid="prospect-ai-gen">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-purple-300 mb-2 flex items-center gap-1.5">
            <Sparkles size={12} /> AI Target Research
          </div>
          <div className="space-y-2">
            <input className={inputCls} placeholder="Region (e.g. Midwest)" value={gen.region} onChange={(e) => setGen({ ...gen, region: e.target.value })} />
            <input className={inputCls} placeholder="Industry" value={gen.industry} onChange={(e) => setGen({ ...gen, industry: e.target.value })} />
            <Button onClick={() => run("gen", () => api.post("/revenue/prospects/generate", gen), "🎯 AI target list generated — verify emails before sequencing")}
              disabled={busy === "gen"} data-testid="prospect-generate-btn"
              className="bg-purple-500/20 border border-purple-500/40 text-purple-200 font-mono text-[10px] uppercase w-full hover:bg-purple-500/30">
              {busy === "gen" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Sparkles size={12} className="mr-1" />}
              Research {gen.count} Targets
            </Button>
            <div className="text-[9px] font-mono text-slate-500">AI lists real shippers by region/industry. Verify contacts, then sequence.</div>
          </div>
        </Card>
        <Card className="hud-surface p-4" data-testid="prospect-csv-import">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 mb-2 flex items-center gap-1.5">
            <Upload size={12} /> CSV Import
          </div>
          <textarea rows={4} value={csvText} onChange={(e) => setCsvText(e.target.value)}
            placeholder="company,contact_name,email,phone,city_state,industry,est_loads_week,lanes"
            className="w-full rounded bg-slate-950 border border-white/10 font-mono text-[10px] p-2 text-slate-200 placeholder:text-slate-600" />
          <Button onClick={() => run("csv", () => api.post("/revenue/prospects/import", { csv_text: csvText }).then(() => setCsvText("")), "CSV imported")}
            disabled={!csvText.trim() || busy === "csv"} data-testid="prospect-import-btn"
            className="mt-2 bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 font-mono text-[10px] uppercase w-full hover:bg-cyan-500/30">
            Import
          </Button>
        </Card>
      </div>

      <Card className="hud-surface p-4" data-testid="prospects-table">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-400 mb-2 flex items-center gap-1.5">
          <Users size={12} /> Prospect Pipeline ({prospects.length})
        </div>
        <div className="space-y-1.5 max-h-[360px] overflow-y-auto">
          {prospects.length === 0 && <div className="text-[10px] font-mono text-slate-500">Empty pipeline — add, research, or import prospects above.</div>}
          {prospects.map((p) => (
            <div key={p.prospect_id} className="text-[10px] font-mono p-2 rounded bg-white/[0.02] flex flex-wrap items-center gap-2 justify-between">
              <div className="min-w-0">
                <span className="text-slate-200">{p.company}</span>
                <span className="ml-2 text-[8px] border border-white/10 rounded px-1 text-slate-500 uppercase">{p.source}</span>
                <div className="text-slate-500">{p.city_state || "—"} · {p.industry || "—"} · ~{p.est_loads_week} loads/wk · {p.email || "no email"}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <select value={p.stage} data-testid={`prospect-stage-${p.prospect_id}`}
                  onChange={(e) => run(p.prospect_id, () => api.post(`/revenue/prospects/${p.prospect_id}/stage`, { stage: e.target.value }), `Stage → ${e.target.value}`)}
                  className="h-7 rounded bg-slate-950 border border-white/10 font-mono text-[9px] px-1 text-slate-300 uppercase">
                  {STAGES.map((s) => <option key={s}>{s}</option>)}
                </select>
                <Button size="sm" onClick={() => run(`seq-${p.prospect_id}`, () => api.post(`/revenue/prospects/${p.prospect_id}/sequence`), "✉️ 3-touch AI sequence built")}
                  disabled={busy === `seq-${p.prospect_id}`} data-testid={`prospect-sequence-${p.prospect_id}`}
                  className="h-7 bg-white/5 border border-emerald-500/30 text-emerald-300 font-mono text-[9px] uppercase">
                  {busy === `seq-${p.prospect_id}` ? <Loader2 size={10} className="animate-spin" /> : <><Send size={10} className="mr-1" />AI Sequence</>}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="hud-surface p-4" data-testid="outreach-queue">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-300">
            Outreach Queue · {queue.resend_connected ? <span className="text-emerald-300">RESEND LIVE</span> : <span className="text-orange-300">{queue.awaiting_key} AWAITING RESEND KEY</span>}
          </div>
          {queue.resend_connected && queue.awaiting_key > 0 && (
            <Button size="sm" onClick={() => run("dispatch", () => api.post("/revenue/outreach/dispatch"), "Queue flushed")}
              data-testid="outreach-dispatch-btn"
              className="h-7 bg-yellow-500 text-black font-bold font-mono text-[9px] uppercase">Flush Queue</Button>
          )}
        </div>
        <div className="space-y-1 max-h-40 overflow-y-auto">
          {queue.items.slice(0, 25).map((i) => (
            <div key={i.queue_id} className="text-[10px] font-mono p-1.5 rounded bg-white/[0.02] flex justify-between gap-2">
              <span className="text-slate-300 truncate">{i.to_email} · {i.subject}</span>
              <span className={`uppercase shrink-0 ${i.status === "sent" ? "text-emerald-300" : i.status === "failed" ? "text-red-300" : "text-orange-300"}`}>{i.status.replaceAll("_", " ")}</span>
            </div>
          ))}
          {queue.items.length === 0 && <div className="text-[10px] font-mono text-slate-500">No outreach yet.</div>}
        </div>
      </Card>
    </div>
  );
}

function MarketplaceTab({ refreshDash }) {
  const [loads, setLoads] = useState([]);
  const [form, setForm] = useState({ origin: "", destination: "", equipment: "Van", commodity: "FAK", pickup_date: "" });
  const [busy, setBusy] = useState(false);
  const publicUrl = `${window.location.origin}/carriers/loadboard`;

  const load = useCallback(async () => {
    try { const { data } = await api.get("/revenue/marketplace/loads"); setLoads(data.items); } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const post = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/revenue/marketplace/loads", form);
      toast.success(`📣 ${data.mkt_id} live on the board — Book-It-Now $${fmt(data.book_now_usd)} (margin $${fmt(data.margin_usd)})`);
      setForm({ origin: "", destination: "", equipment: "Van", commodity: "FAK", pickup_date: "" });
      load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Post failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Card className="hud-surface p-4" data-testid="marketplace-post-form">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 flex items-center gap-1.5">
            <Store size={12} /> Post A Book-It-Now Load
          </div>
          <a href={publicUrl} target="_blank" rel="noreferrer" data-testid="marketplace-public-link"
            className="text-[10px] font-mono text-cyan-400 hover:underline flex items-center gap-1">
            Public carrier board: {publicUrl} <ExternalLink size={11} />
          </a>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <input className={inputCls} placeholder="Origin (City, ST)" value={form.origin} data-testid="mkt-origin-input"
            onChange={(e) => setForm({ ...form, origin: e.target.value })} />
          <input className={inputCls} placeholder="Destination (City, ST)" value={form.destination} data-testid="mkt-dest-input"
            onChange={(e) => setForm({ ...form, destination: e.target.value })} />
          <select className={inputCls} value={form.equipment} onChange={(e) => setForm({ ...form, equipment: e.target.value })}>
            {["Van", "Reefer", "Flatbed"].map((x) => <option key={x}>{x}</option>)}
          </select>
          <input className={inputCls} placeholder="Commodity" value={form.commodity} onChange={(e) => setForm({ ...form, commodity: e.target.value })} />
          <input className={inputCls} placeholder="Pickup date" value={form.pickup_date} onChange={(e) => setForm({ ...form, pickup_date: e.target.value })} />
        </div>
        <Button onClick={post} disabled={busy || !form.origin || !form.destination} data-testid="mkt-post-btn"
          className="mt-2 bg-cyan-500 hover:bg-cyan-400 text-black font-black font-mono text-[10px] uppercase">
          {busy ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Store size={12} className="mr-1" />}
          Price & Post To Board
        </Button>
        <div className="text-[9px] font-mono text-slate-500 mt-2">Book-Now price = market carrier rate; your sell rate & margin stay hidden from carriers. Won quotes auto-post here.</div>
      </Card>
      <Card className="hud-surface p-4" data-testid="marketplace-table">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Marketplace Loads ({loads.length})</div>
        <div className="space-y-1.5 max-h-[420px] overflow-y-auto">
          {loads.length === 0 && <div className="text-[10px] font-mono text-slate-500">No loads posted yet.</div>}
          {loads.map((l) => (
            <div key={l.mkt_id} className="text-[10px] font-mono p-2 rounded bg-white/[0.02] flex flex-wrap items-center gap-2 justify-between">
              <div className="min-w-0">
                <span className="text-slate-200">{l.mkt_id}</span>
                <span className={`ml-2 uppercase ${l.status === "open" ? "text-emerald-300" : l.status === "booked" ? "text-cyan-300" : "text-slate-500"}`}>{l.status}</span>
                <div className="text-slate-500">{l.origin} → {l.destination} · {l.equipment} · {l.miles} mi · {l.commodity}</div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-cyan-300">Book-Now ${fmt(l.book_now_usd)}</span>
                <span className="text-yellow-300">margin ${fmt(l.margin_usd)}</span>
                {l.status === "open" && (
                  <button onClick={async () => { try { await api.post(`/revenue/marketplace/loads/${l.mkt_id}/close`); toast.success("Closed"); load(); } catch { toast.error("Failed"); } }}
                    className="text-slate-400 hover:text-red-300" title="Close load" data-testid={`mkt-close-${l.mkt_id}`}><XCircle size={13} /></button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function QuickPayTab({ refreshDash }) {
  const [prog, setProg] = useState(null);
  const [busy, setBusy] = useState(null);
  const load = useCallback(async () => {
    try { const { data } = await api.get("/revenue/quickpay/program"); setProg(data); } catch {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const request = async (b, tier) => {
    setBusy(b.booked_id);
    try {
      const { data } = await api.post("/revenue/quickpay/request", { booked_id: b.booked_id, tier });
      toast.success(`💸 QuickPay approved — fee $${fmt(data.fee_usd)} (${data.fee_pct}%) is pure spread revenue`);
      load(); refreshDash();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(null); }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Stat label="Spread Earned" value={`$${fmt(prog?.spread_earned)}`} accent="text-yellow-300" tid="qp-spread-earned" />
        <Stat label="Pending Payout" value={`$${fmt(prog?.pending_payout)}`} accent="text-orange-300" />
        <Stat label="Requests" value={prog?.requests?.length ?? "—"} accent="text-cyan-300" />
        <Stat label="Tiers" value="3.5 / 2.5 / 1.5%" accent="text-slate-300" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="hud-surface p-4" data-testid="qp-eligible">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 mb-2">Eligible Bookings</div>
          <div className="space-y-1.5 max-h-[380px] overflow-y-auto">
            {(prog?.eligible_bookings || []).length === 0 && <div className="text-[10px] font-mono text-slate-500">No eligible real bookings yet — QuickPay activates as loads book & deliver.</div>}
            {(prog?.eligible_bookings || []).map((b) => (
              <div key={b.booked_id} className="text-[10px] font-mono p-2 rounded bg-white/[0.02]">
                <div className="flex justify-between">
                  <span className="text-slate-200">{b.booked_id} · {b.carrier_name}</span>
                  <span className="text-slate-300">${fmt(b.carrier_rate_usd)}</span>
                </div>
                <div className="text-slate-500">{b.origin} → {b.destination} · {b.status}</div>
                <div className="flex gap-1.5 mt-1">
                  {[["same_day", "Same-Day 3.5%"], ["two_day", "48-Hr 2.5%"], ["five_day", "5-Day 1.5%"]].map(([t, label]) => (
                    <button key={t} onClick={() => request(b, t)} disabled={busy === b.booked_id}
                      data-testid={`qp-request-${b.booked_id}-${t}`}
                      className="text-[9px] font-mono uppercase text-yellow-300 border border-yellow-500/30 rounded px-2 py-0.5 hover:bg-yellow-500/10">
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card className="hud-surface p-4" data-testid="qp-requests">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-300 mb-2 flex items-center gap-1.5">
            <Wallet size={12} /> QuickPay Ledger
          </div>
          <div className="space-y-1.5 max-h-[380px] overflow-y-auto">
            {(prog?.requests || []).length === 0 && <div className="text-[10px] font-mono text-slate-500">No QuickPay requests yet.</div>}
            {(prog?.requests || []).map((r) => (
              <div key={r.qp_id} className="text-[10px] font-mono p-2 rounded bg-white/[0.02] flex justify-between items-center gap-2">
                <div>
                  <span className="text-slate-200">{r.qp_id} · {r.carrier_name}</span>
                  <div className="text-slate-500">{r.booked_id} · pay ${fmt(r.carrier_pay_usd)} − fee ${fmt(r.fee_usd)} ({r.fee_pct}%) = net ${fmt(r.net_pay_usd)}</div>
                </div>
                {r.status === "approved" ? (
                  <button onClick={async () => { try { await api.post(`/revenue/quickpay/${r.qp_id}/mark-paid`); toast.success("Paid"); load(); } catch { toast.error("Failed"); } }}
                    className="text-[9px] font-mono uppercase text-emerald-300 border border-emerald-500/30 rounded px-2 py-0.5 hover:bg-emerald-500/10 shrink-0"
                    data-testid={`qp-paid-${r.qp_id}`}>Mark Paid</button>
                ) : <span className="text-emerald-300 uppercase shrink-0">paid</span>}
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

const TABS = [
  { id: "quotes", label: "Instant Quotes", icon: Zap },
  { id: "prospects", label: "Shipper Acquisition", icon: Users },
  { id: "marketplace", label: "Book-It-Now Board", icon: Store },
  { id: "quickpay", label: "QuickPay Spread", icon: Wallet },
];

export default function RevenueEngine() {
  const [tab, setTab] = useState("quotes");
  const [dash, setDash] = useState(null);
  const refreshDash = useCallback(async () => {
    try { const { data } = await api.get("/revenue/dashboard"); setDash(data); } catch {}
  }, []);
  useEffect(() => { refreshDash(); }, [refreshDash]);

  return (
    <>
      <Topbar title="Revenue Engine" />
      <div className="p-6 max-w-[1500px] mx-auto space-y-4" data-testid="revenue-page">
        <Card className="hud-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-yellow-400 flex items-center gap-1.5">
                <DollarSign size={11} /> Orisei Revenue Stack · 4 automated engines
              </div>
              <div className="font-display text-2xl font-black">Revenue Command</div>
            </div>
            <Button size="sm" variant="ghost" onClick={refreshDash} data-testid="revenue-refresh-btn"
              className="border border-white/10 text-slate-300 font-mono text-[10px] uppercase">
              <RefreshCw size={12} className="mr-1" /> Refresh
            </Button>
          </div>
          <div className="flex flex-wrap gap-2 mt-4" data-testid="revenue-kpis">
            <Stat label="Quotes" value={dash?.quotes?.total ?? "—"} accent="text-cyan-300" tid="rev-kpi-quotes" />
            <Stat label="Win Rate" value={`${dash?.quotes?.win_rate ?? "—"}%`} tid="rev-kpi-winrate" />
            <Stat label="Won Revenue" value={`$${fmt(dash?.quotes?.won_revenue)}`} tid="rev-kpi-won-rev" />
            <Stat label="Won Margin" value={`$${fmt(dash?.quotes?.won_margin)}`} accent="text-yellow-300" />
            <Stat label="Prospects" value={dash?.prospects?.total ?? "—"} accent="text-cyan-300" tid="rev-kpi-prospects" />
            <Stat label="Monthly Pipeline" value={`$${fmt(dash?.prospects?.monthly_pipeline_usd)}`} accent="text-purple-300" tid="rev-kpi-pipeline" />
            <Stat label="Board Open/Booked" value={`${dash?.marketplace?.open ?? 0}/${dash?.marketplace?.booked ?? 0}`} accent="text-cyan-300" />
            <Stat label="QuickPay Spread" value={`$${fmt(dash?.quickpay?.spread_earned)}`} accent="text-yellow-300" tid="rev-kpi-qp-spread" />
            <Stat label="Emails Queued" value={dash?.outreach_queued_awaiting_key ?? 0}
              accent={dash?.resend_connected ? "text-emerald-300" : "text-orange-300"} tid="rev-kpi-queued" />
          </div>
        </Card>

        <div className="flex flex-wrap gap-2">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setTab(id)} data-testid={`revenue-tab-${id}`}
              className={`flex items-center gap-1.5 px-4 py-2 rounded font-mono text-[10px] uppercase tracking-widest border transition-colors ${
                tab === id ? "bg-cyan-500/15 border-cyan-500/50 text-cyan-200" : "bg-white/[0.02] border-white/10 text-slate-400 hover:text-slate-200"}`}>
              <Icon size={12} /> {label}
            </button>
          ))}
        </div>

        {tab === "quotes" && <QuotesTab refreshDash={refreshDash} />}
        {tab === "prospects" && <ProspectsTab refreshDash={refreshDash} />}
        {tab === "marketplace" && <MarketplaceTab refreshDash={refreshDash} />}
        {tab === "quickpay" && <QuickPayTab refreshDash={refreshDash} />}
      </div>
    </>
  );
}
