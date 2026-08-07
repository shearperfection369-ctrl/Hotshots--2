import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { Inbox, CheckCircle2, X, ExternalLink, Crosshair, Send, Link as LinkIcon, Copy, Download, PenLine, PhoneCall } from "lucide-react";

const STATUS_STYLE = {
  new: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  converted: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  dismissed: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

const TIER_STYLE = {
  A: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  B: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  C: "bg-violet-500/15 text-violet-300 border-violet-500/40",
};
const STAGE_COLOR = { prospect: "text-slate-400", pitched: "text-amber-300", meeting: "text-cyan-300", pilot: "text-violet-300", signed: "text-emerald-300", dead: "text-red-400" };

function ShareBookingLink() {
  const url = `${window.location.origin}/wash`;
  const qrBase = `${process.env.REACT_APP_BACKEND_URL}/api/truck-cleaning/public/booking-qr.png?url=${encodeURIComponent(url)}`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); toast.success("Booking link copied — paste it anywhere"); }
    catch { toast.error("Copy failed — long-press the link to copy"); }
  };
  return (
    <Card className="p-4 bg-slate-950/70 border-emerald-500/30" data-testid="tc-share-booking-link">
      <div className="flex flex-wrap items-center gap-4">
        <img src={qrBase} alt="Booking page QR code" className="w-24 h-24 rounded-lg bg-white p-1 shrink-0" data-testid="tc-booking-qr-img" />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <LinkIcon size={15} className="text-emerald-300" /> Your Client Booking Link
          </h3>
          <div className="text-[10px] text-slate-500 mt-0.5 mb-2">Text it, email it, put it on cards — or let clients scan the QR. Every booking emails Oliver instantly.</div>
          <div className="flex flex-wrap items-center gap-2">
            <code className="px-3 py-1.5 rounded-full bg-[#11151F] border border-white/10 text-[11px] text-emerald-300 font-mono truncate max-w-full" data-testid="tc-booking-url">{url}</code>
            <button onClick={copy} data-testid="tc-copy-booking-link-btn"
              className="px-4 py-1.5 rounded-full bg-emerald-500 text-black text-[10px] font-black flex items-center gap-1"><Copy size={11} /> COPY LINK</button>
            <a href={url} target="_blank" rel="noreferrer" data-testid="tc-open-booking-link"
              className="px-4 py-1.5 rounded-full border border-white/15 text-slate-300 text-[10px] font-bold flex items-center gap-1"><ExternalLink size={11} /> Open</a>
            <a href={`${qrBase}&download=1`} data-testid="tc-download-qr-btn"
              className="px-4 py-1.5 rounded-full border border-emerald-500/40 text-emerald-300 text-[10px] font-bold flex items-center gap-1"><Download size={11} /> Download QR</a>
          </div>
        </div>
      </div>
    </Card>
  );
}

function YardBlast({ prospects, reload }) {
  const top5 = prospects.filter((p) => !["signed", "dead"].includes(p.stage)).slice(0, 5);
  const [emails, setEmails] = useState({});
  const [busy, setBusy] = useState(false);
  const val = (p) => emails[p.prospect_id] ?? p.email ?? "";
  const ready = top5.filter((p) => val(p).includes("@")).length;
  const sendAll = async () => {
    const targets = top5.filter((p) => val(p).includes("@"));
    if (!targets.length) { toast.error("Enter at least one yard manager email first"); return; }
    setBusy(true);
    let ok = 0;
    for (const p of targets) {
      try {
        await api.post("/truck-cleaning/brochures/yard-promo/send", { email: val(p).trim(), company: p.name });
        await api.patch(`/truck-cleaning/yard-prospects/${p.prospect_id}`, { email: val(p).trim(), stage: p.stage === "prospect" ? "pitched" : p.stage });
        ok += 1;
      } catch { /* keep going */ }
    }
    setBusy(false);
    toast.success(`Yard blast complete — ${ok}/${targets.length} packages sent`);
    reload();
  };
  if (!top5.length) return null;
  return (
    <div className="p-3 rounded-xl border border-amber-500/40 bg-amber-500/[0.06] mb-3" data-testid="tc-yard-blast">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <div>
          <div className="text-xs font-black text-amber-300 flex items-center gap-1.5"><Send size={12} /> TOP 5 YARD BLAST</div>
          <div className="text-[10px] text-slate-500">Punch in each yard manager's email, fire all five Yard Manager Packages at once.</div>
        </div>
        <button onClick={sendAll} disabled={busy || !ready} data-testid="tc-yard-blast-send"
          className="px-5 py-2 rounded-full bg-amber-500 text-black text-[10px] font-black disabled:opacity-40">
          {busy ? "SENDING…" : `BLAST ${ready || ""} PACKAGE${ready === 1 ? "" : "S"}`}
        </button>
      </div>
      <div className="space-y-1.5">
        {top5.map((p) => (
          <div key={p.prospect_id} className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-slate-500 w-6 shrink-0">#{p.rank}</span>
            <span className="text-[11px] font-bold text-white truncate w-52 shrink-0">{p.name}</span>
            <input value={val(p)} onChange={(e) => setEmails({ ...emails, [p.prospect_id]: e.target.value })}
              placeholder="yard manager email…" data-testid={`tc-blast-email-${p.prospect_id}`}
              className={`h-8 px-3 rounded-full bg-[#11151F] border text-[11px] text-white flex-1 min-w-[160px] outline-none ${val(p).includes("@") ? "border-emerald-500/50" : "border-white/10 focus:border-amber-400"}`} />
          </div>
        ))}
      </div>
    </div>
  );
}

function CallbackReminders({ prospects, onJump }) {
  const today = new Date().toISOString().slice(0, 10);
  const due = (prospects || []).filter((p) => p.callback_date && p.callback_date <= today && !["signed", "dead"].includes(p.stage));
  if (!due.length) return null;
  return (
    <Card className="p-4 bg-slate-950/70 border-rose-500/40" data-testid="tc-callback-reminders">
      <h3 className="text-sm font-black text-rose-300 flex items-center gap-2 mb-2">
        <PhoneCall size={15} /> CALLBACKS DUE — DON'T LET A YARD SLIP
        <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-black">{due.length}</span>
      </h3>
      <div className="space-y-1.5">
        {due.map((p) => (
          <div key={p.prospect_id} className="flex items-center justify-between gap-2 p-2.5 rounded-xl border border-white/10 bg-white/[0.02] flex-wrap" data-testid={`tc-callback-${p.prospect_id}`}>
            <div className="min-w-0">
              <span className="text-xs font-bold text-white">{p.name}</span>
              <span className={`ml-2 text-[9px] font-mono uppercase px-1.5 py-0.5 rounded ${p.callback_date < today ? "bg-rose-500/20 text-rose-300" : "bg-amber-500/20 text-amber-300"}`}>
                {p.callback_date < today ? `OVERDUE · ${p.callback_date}` : "DUE TODAY"}
              </span>
              <div className="text-[10px] font-mono text-slate-500">
                {p.phone || "no phone on file"}{p.last_call_outcome ? ` · last call: ${p.last_call_outcome.replace("_", " ")}` : ""} · stage: {p.stage}
              </div>
            </div>
            <button onClick={() => onJump(p.prospect_id)} data-testid={`tc-callback-log-${p.prospect_id}`}
              className="px-4 py-1.5 rounded-full bg-rose-500 text-white text-[10px] font-black shrink-0">LOG THE CALL</button>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ProspectList() {
  const [data, setData] = useState(null);
  const [emailFor, setEmailFor] = useState(null);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [contractFor, setContractFor] = useState(null);
  const [cCabs, setCCabs] = useState(4);
  const [cFreq, setCFreq] = useState("biweekly");
  const [callFor, setCallFor] = useState(null);
  const [callOutcome, setCallOutcome] = useState("spoke");
  const [callNotes, setCallNotes] = useState("");
  const [callbackDate, setCallbackDate] = useState("");
  const load = () => api.get("/truck-cleaning/yard-prospects").then(({ data: d }) => setData(d)).catch(() => {});
  useEffect(() => { load(); }, []);
  const setStage = async (p, stage) => {
    try { await api.patch(`/truck-cleaning/yard-prospects/${p.prospect_id}`, { stage }); load(); }
    catch { toast.error("Update failed"); }
  };
  const sendPromo = async (p) => {
    if (!email.includes("@")) { toast.error("Enter the yard manager's email"); return; }
    setSending(true);
    try {
      const { data: r } = await api.post("/truck-cleaning/brochures/yard-promo/send", { email, company: p.name });
      await api.patch(`/truck-cleaning/yard-prospects/${p.prospect_id}`, { email, stage: p.stage === "prospect" ? "pitched" : p.stage });
      toast.success(r.sent ? `Package sent to ${r.to}` : `Package queued for ${r.to}`);
      setEmailFor(null); setEmail(""); load();
    } catch { toast.error("Send failed"); }
    finally { setSending(false); }
  };
  const createContract = async (p) => {
    setSending(true);
    try {
      const { data: r } = await api.post("/truck-cleaning/agreements", {
        company: p.name, contact: p.contact || "", email: (p.email || email || "").trim(),
        prospect_id: p.prospect_id, cabs: Number(cCabs) || 4, frequency: cFreq,
        base: window.location.origin });
      try { await navigator.clipboard.writeText(r.sign_url); } catch { /* noop */ }
      toast.success(r.emailed ? "Contract emailed to the yard + sign link copied" : "Sign link copied — text it to the yard manager", { description: r.sign_url });
      setContractFor(null);
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Could not create contract"); }
    finally { setSending(false); }
  };
  const submitCall = async (p) => {
    setSending(true);
    try {
      const { data: r } = await api.post(`/truck-cleaning/yard-prospects/${p.prospect_id}/call`,
        { outcome: callOutcome, notes: callNotes, callback_date: callbackDate });
      toast.success(`Call logged — ${r.call.outcome.replace("_", " ")}${callbackDate ? ` · callback ${callbackDate}` : ""}`);
      setCallFor(null); setCallNotes(""); setCallbackDate("");
      load();
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Could not log call"); }
    finally { setSending(false); }
  };
  if (!data) return null;
  return (
    <>
    <CallbackReminders prospects={data.prospects} onJump={(id) => { setCallFor(id); setContractFor(null); setEmailFor(null); }} />
    <Card className="p-4 bg-slate-950/70 border-amber-500/25" data-testid="tc-prospects">
      <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Crosshair size={15} className="text-amber-400" /> Twin Cities Yard Hit List — 20 ranked prospects
        </h3>
        <div className="flex gap-1.5 text-[9px] font-mono">
          {Object.entries(data.counts).filter(([, v]) => v > 0).map(([s, v]) => (
            <span key={s} className={`px-2 py-0.5 rounded-full border border-white/10 ${STAGE_COLOR[s]}`}>{s}: {v}</span>
          ))}
        </div>
      </div>
      <div className="text-[10px] text-slate-500 mb-3">Tier A = 10–30 cab agile fleets & drayage yards (start here) · Tier B = LTL service centers (nightly day cabs) · Tier C = anchors & owner-op networks. Cab counts are field estimates — verify on the call.</div>
      <YardBlast prospects={data.prospects} reload={load} />
      <div className="space-y-1.5 max-h-[520px] overflow-y-auto pr-1">
        {data.prospects.map((p) => (
          <div key={p.prospect_id} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]" data-testid={`tc-prospect-${p.prospect_id}`}>
            <div className="flex items-start justify-between gap-2 flex-wrap">
              <div className="min-w-0">
                <div className="text-xs font-bold text-white flex items-center gap-2 flex-wrap">
                  <span className="text-slate-600 font-mono">#{p.rank}</span> {p.name}
                  <span className={`px-1.5 py-0.5 rounded border text-[9px] font-mono ${TIER_STYLE[p.tier]}`}>TIER {p.tier}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500">{p.city} · {p.ptype} · {p.est_cabs}{p.address ? ` · ${p.address}` : ""}</div>
                <div className="text-[10px] text-cyan-200/70 mt-1">{p.angle}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <select value={p.stage} onChange={(e) => setStage(p, e.target.value)}
                  className={`h-8 px-2 rounded-lg bg-[#11151F] border border-white/10 text-[10px] font-mono uppercase ${STAGE_COLOR[p.stage]}`}
                  data-testid={`tc-prospect-stage-${p.prospect_id}`}>
                  {data.stages.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <button onClick={() => { setEmailFor(emailFor === p.prospect_id ? null : p.prospect_id); setEmail(p.email || ""); setContractFor(null); }}
                  className="h-8 px-3 rounded-full bg-amber-500 text-black text-[10px] font-black flex items-center gap-1"
                  data-testid={`tc-prospect-send-${p.prospect_id}`}>
                  <Send size={11} /> PACKAGE
                </button>
                <button onClick={() => { setContractFor(contractFor === p.prospect_id ? null : p.prospect_id); setEmailFor(null); }}
                  className="h-8 px-3 rounded-full bg-violet-500 text-white text-[10px] font-black flex items-center gap-1"
                  data-testid={`tc-prospect-contract-${p.prospect_id}`}>
                  <PenLine size={11} /> CONTRACT
                </button>
                <button onClick={() => { setCallFor(callFor === p.prospect_id ? null : p.prospect_id); setEmailFor(null); setContractFor(null); }}
                  className="h-8 px-3 rounded-full bg-cyan-500 text-black text-[10px] font-black flex items-center gap-1"
                  data-testid={`tc-prospect-call-${p.prospect_id}`}>
                  <PhoneCall size={11} /> LOG CALL{p.call_count ? ` (${p.call_count})` : ""}
                </button>
              </div>
            </div>
            {emailFor === p.prospect_id && (
              <div className="flex gap-2 mt-2">
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder={`yard manager @ ${p.name.split(" ")[0].toLowerCase()}…`}
                  className="h-8 px-3 rounded-full bg-[#11151F] border border-amber-500/30 text-xs text-white flex-1 outline-none focus:border-amber-400"
                  data-testid={`tc-prospect-email-${p.prospect_id}`} />
                <button onClick={() => sendPromo(p)} disabled={sending}
                  className="h-8 px-4 rounded-full bg-emerald-500 text-black text-[10px] font-black disabled:opacity-50"
                  data-testid={`tc-prospect-email-send-${p.prospect_id}`}>
                  {sending ? "SENDING…" : "EMAIL IT"}
                </button>
              </div>
            )}
            {contractFor === p.prospect_id && (
              <div className="flex flex-wrap items-center gap-2 mt-2" data-testid={`tc-contract-panel-${p.prospect_id}`}>
                <select value={cFreq} onChange={(e) => setCFreq(e.target.value)}
                  className="h-8 px-2 rounded-lg bg-[#11151F] border border-violet-500/40 text-[10px] font-mono text-violet-300"
                  data-testid={`tc-contract-freq-${p.prospect_id}`}>
                  <option value="biweekly">BI-WEEKLY · $130/cab</option>
                  <option value="weekly">WEEKLY · $110/cab</option>
                </select>
                <input type="number" min="1" max="200" value={cCabs} onChange={(e) => setCCabs(e.target.value)}
                  className="h-8 w-20 px-3 rounded-full bg-[#11151F] border border-violet-500/40 text-[11px] text-white outline-none"
                  data-testid={`tc-contract-cabs-${p.prospect_id}`} />
                <span className="text-[10px] font-mono text-slate-500">cabs</span>
                <button onClick={() => createContract(p)} disabled={sending}
                  className="h-8 px-4 rounded-full bg-violet-500 text-white text-[10px] font-black disabled:opacity-50"
                  data-testid={`tc-contract-create-${p.prospect_id}`}>
                  {sending ? "CREATING…" : "CREATE + COPY SIGN LINK"}
                </button>
                {p.email && <span className="text-[9px] font-mono text-emerald-400">will also email {p.email}</span>}
              </div>
            )}
            {callFor === p.prospect_id && (
              <div className="flex flex-wrap items-center gap-2 mt-2" data-testid={`tc-call-panel-${p.prospect_id}`}>
                <select value={callOutcome} onChange={(e) => setCallOutcome(e.target.value)}
                  className="h-8 px-2 rounded-lg bg-[#11151F] border border-cyan-500/40 text-[10px] font-mono text-cyan-300"
                  data-testid={`tc-call-outcome-${p.prospect_id}`}>
                  <option value="spoke">SPOKE TO SOMEONE</option>
                  <option value="meeting_set">MEETING SET</option>
                  <option value="voicemail">LEFT VOICEMAIL</option>
                  <option value="no_answer">NO ANSWER</option>
                  <option value="not_interested">NOT INTERESTED</option>
                </select>
                <input value={callNotes} onChange={(e) => setCallNotes(e.target.value)} placeholder="notes — who, what, objections…"
                  className="h-8 px-3 rounded-full bg-[#11151F] border border-cyan-500/40 text-[11px] text-white flex-1 min-w-[180px] outline-none focus:border-cyan-300"
                  data-testid={`tc-call-notes-${p.prospect_id}`} />
                <input type="date" value={callbackDate} onChange={(e) => setCallbackDate(e.target.value)}
                  className="h-8 px-2 rounded-lg bg-[#11151F] border border-cyan-500/40 text-[10px] text-slate-300 outline-none"
                  data-testid={`tc-call-callback-${p.prospect_id}`} />
                <button onClick={() => submitCall(p)} disabled={sending}
                  className="h-8 px-4 rounded-full bg-cyan-500 text-black text-[10px] font-black disabled:opacity-50"
                  data-testid={`tc-call-save-${p.prospect_id}`}>
                  {sending ? "SAVING…" : "SAVE CALL"}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
    </>
  );
}

export const TcBookings = ({ reloadAll }) => {
  const [rows, setRows] = useState([]);
  const load = useCallback(() => {
    api.get("/truck-cleaning/bookings").then(({ data }) => setRows(data.bookings || [])).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const convert = async (id) => {
    try {
      const { data } = await api.post(`/truck-cleaning/bookings/${id}/convert`);
      toast.success(`Converted — client + job ${data.job_id} created`);
      load();
      reloadAll && reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Convert failed"); }
  };
  const dismiss = async (id) => {
    try { await api.post(`/truck-cleaning/bookings/${id}/dismiss`); load(); } catch { toast.error("Dismiss failed"); }
  };

  return (
    <div className="space-y-4">
    <ShareBookingLink />
    <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-bookings">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Inbox size={15} className="text-cyan-300" /> Booking Requests from the public page
          {rows.filter((r) => r.status === "new").length > 0 &&
            <span className="px-2 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-black">{rows.filter((r) => r.status === "new").length} NEW</span>}
        </h3>
        <a href="/wash" target="_blank" rel="noreferrer" className="text-[10px] font-mono text-cyan-300 flex items-center gap-1" data-testid="tc-bookings-page-link">
          view booking page <ExternalLink size={10} />
        </a>
      </div>
      <div className="space-y-2 max-h-[480px] overflow-y-auto">
        {rows.map((b) => (
          <div key={b.booking_id} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]" data-testid={`tc-booking-${b.booking_id}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm text-white font-semibold">{b.company} <span className="text-slate-500 font-normal">· {b.cabs} cab{b.cabs > 1 ? "s" : ""}</span></div>
                <div className="text-[10px] font-mono text-slate-500">
                  {b.contact && `${b.contact} · `}{b.phone}{b.email ? ` · ${b.email}` : ""}{b.preferred_date ? ` · wants ${b.preferred_date}` : ""}
                </div>
                {b.services?.length > 0 && <div className="text-[10px] text-cyan-300 mt-0.5">add-ons: {b.services.join(", ")}</div>}
                {b.notes && <div className="text-[10px] text-slate-500 mt-0.5">{b.notes}</div>}
              </div>
              <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono uppercase shrink-0 ${STATUS_STYLE[b.status]}`}>{b.status}</span>
            </div>
            {b.status === "new" && (
              <div className="flex gap-2 mt-2">
                <button onClick={() => convert(b.booking_id)} data-testid={`tc-booking-convert-${b.booking_id}`}
                  className="px-3 py-1.5 rounded-full bg-emerald-500 text-black text-[10px] font-black flex items-center gap-1">
                  <CheckCircle2 size={11} /> CONVERT TO CLIENT + JOB
                </button>
                <button onClick={() => dismiss(b.booking_id)} data-testid={`tc-booking-dismiss-${b.booking_id}`}
                  className="px-3 py-1.5 rounded-full border border-white/15 text-slate-400 text-[10px] font-bold flex items-center gap-1">
                  <X size={11} /> Dismiss
                </button>
              </div>
            )}
          </div>
        ))}
        {!rows.length && <div className="py-8 text-center text-slate-500 text-sm">No booking requests yet — share <b>/wash</b> with clients and watch this inbox fill up.</div>}
      </div>
    </Card>
    <ProspectList />
    </div>
  );
};
