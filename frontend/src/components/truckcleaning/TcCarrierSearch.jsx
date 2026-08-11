import React, { useState } from "react";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { toast } from "sonner";
import { Search, Building2, Phone, MapPin, Truck, UserPlus, Loader2, Sparkles, Copy } from "lucide-react";

function AiContacts({ carrier }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/carrier-search/ai-contacts", carrier);
      setRes(data);
    } catch (e2) { toast.error(e2?.response?.data?.detail || "AI research failed — try again"); }
    finally { setBusy(false); }
  };
  const copy = async (t) => { try { await navigator.clipboard.writeText(t); toast.success(`Copied ${t}`); } catch { toast.error("Copy failed"); } };
  if (!res) return (
    <button onClick={run} disabled={busy} data-testid={`tc-cs-ai-${carrier.dot_number || "x"}`}
      className="mt-2 h-8 px-3 rounded-full border border-violet-500/50 text-violet-300 text-[10px] font-black flex items-center gap-1.5 hover:bg-violet-500/10 disabled:opacity-50">
      {busy ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />} {busy ? "RESEARCHING…" : "FIND CONTACTS (AI)"}
    </button>
  );
  return (
    <div className="mt-2 p-3 rounded-xl border border-violet-500/30 bg-violet-500/[0.05] space-y-2" data-testid={`tc-cs-ai-result-${carrier.dot_number || "x"}`}>
      <div className="flex flex-wrap gap-1.5">
        {(res.domains || []).map((d) => (
          <span key={d.domain} title={d.reason} className={`px-2 py-0.5 rounded-full text-[9px] font-mono border ${d.confidence === "high" ? "border-emerald-500/50 text-emerald-300" : d.confidence === "medium" ? "border-amber-500/40 text-amber-300" : "border-white/15 text-slate-400"}`}>
            {d.domain} · {d.confidence}
          </span>
        ))}
      </div>
      {(res.contacts || []).map((c) => (
        <div key={c.role} className="text-[11px]">
          <span className="font-bold text-white">{c.likely_title || c.role}</span>
          {c.note && <span className="text-slate-500"> — {c.note}</span>}
          <div className="flex flex-wrap gap-1 mt-1">
            {(c.email_guesses || []).map((em) => (
              <button key={em} onClick={() => copy(em)} className="px-2 py-0.5 rounded-full bg-[#11151F] border border-violet-500/30 text-violet-200 text-[10px] font-mono flex items-center gap-1 hover:border-violet-400">
                {em} <Copy size={9} />
              </button>
            ))}
          </div>
        </div>
      ))}
      {res.outreach_tip && <div className="text-[10px] text-cyan-200/80 italic">Tip: {res.outreach_tip}</div>}
      <div className="text-[9px] font-mono text-slate-500">{res.disclaimer}</div>
    </div>
  );
}

export const TcCarrierSearch = () => {
  const [q, setQ] = useState("");
  const [by, setBy] = useState("auto");
  const [state, setState] = useState("");
  const [minUnits, setMinUnits] = useState("");
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState({});

  const run = async (e) => {
    e?.preventDefault();
    if (q.trim().length < 2) { toast.error("Type a carrier name, USDOT or MC#"); return; }
    setBusy(true);
    try {
      const { data } = await api.get("/carrier-search", { params: { q, by, state, min_units: minUnits || 0, limit: 30 } });
      setRows(data.results);
      if (!data.results.length) toast.info("No carriers matched — try a broader name or a USDOT/MC number");
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Search failed"); }
    finally { setBusy(false); }
  };

  const addProspect = async (c) => {
    try {
      const { data } = await api.post("/carrier-search/add-prospect", c);
      setAdded({ ...added, [c.dot_number || c.legal_name]: true });
      toast[data.duplicate ? "info" : "success"](data.message);
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Could not add"); }
  };

  return (
    <div className="space-y-4" data-testid="tc-carrier-search">
      <Card className="p-4 bg-slate-950/70 border-cyan-500/25">
        <h3 className="text-sm font-black text-white flex items-center gap-2 mb-1">
          <Search size={16} className="text-cyan-300" /> FMCSA Carrier Search
          <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 text-[9px] font-black">LIVE GOV DATA · FREE</span>
        </h3>
        <p className="text-[11px] text-slate-500 mb-3">Look up any US trucking company by name, USDOT or MC number — pull their phone, address, fleet size & cargo, then add straight to your hit list.</p>
        <form onSubmit={run} className="flex flex-wrap gap-2 items-center">
          <select value={by} onChange={(e) => setBy(e.target.value)} data-testid="tc-cs-by"
            className="h-10 px-2 rounded-lg bg-[#11151F] border border-white/15 text-xs text-slate-300 outline-none">
            <option value="auto">Auto</option><option value="name">By name</option>
            <option value="dot">USDOT #</option><option value="mc">MC #</option>
          </select>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Swift, 44110, MC-1515…"
            className="h-10 px-4 rounded-lg bg-[#11151F] border border-white/15 text-sm text-white flex-1 min-w-[200px] outline-none focus:border-cyan-400" data-testid="tc-cs-query" />
          <input value={state} onChange={(e) => setState(e.target.value.toUpperCase().slice(0, 2))} placeholder="ST"
            className="h-10 w-16 px-3 rounded-lg bg-[#11151F] border border-white/15 text-sm text-white outline-none uppercase" data-testid="tc-cs-state" />
          <input type="number" value={minUnits} onChange={(e) => setMinUnits(e.target.value)} placeholder="min trucks"
            className="h-10 w-28 px-3 rounded-lg bg-[#11151F] border border-white/15 text-sm text-white outline-none" data-testid="tc-cs-minunits" />
          <button disabled={busy} data-testid="tc-cs-search-btn"
            className="h-10 px-5 rounded-lg bg-cyan-500 text-black text-xs font-black flex items-center gap-1.5 disabled:opacity-50">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />} SEARCH
          </button>
        </form>
      </Card>

      {rows && (
        <div className="grid md:grid-cols-2 gap-3" data-testid="tc-cs-results">
          {rows.map((c) => {
            const key = c.dot_number || c.legal_name;
            return (
              <Card key={key} className="p-4 bg-slate-950/70 border-white/10 hover:border-cyan-500/40 transition-colors" data-testid={`tc-cs-card-${c.dot_number || "x"}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-black text-white flex items-center gap-1.5"><Building2 size={13} className="text-cyan-300 shrink-0" />{c.legal_name}</div>
                    {c.dba_name && <div className="text-[10px] text-slate-500">dba {c.dba_name}</div>}
                  </div>
                  <button onClick={() => addProspect(c)} disabled={added[key]} data-testid={`tc-cs-add-${c.dot_number || "x"}`}
                    className={`h-8 px-3 rounded-full text-[10px] font-black flex items-center gap-1 shrink-0 ${added[key] ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "bg-amber-500 text-black"}`}>
                    <UserPlus size={11} /> {added[key] ? "ADDED" : "ADD PROSPECT"}
                  </button>
                </div>
                <div className="mt-2 space-y-1 text-[11px] text-slate-300">
                  {c.phone && <div className="flex items-center gap-1.5"><Phone size={11} className="text-slate-500" /><a href={`tel:${c.phone}`} className="hover:text-cyan-300">{c.phone}</a></div>}
                  {c.address && <div className="flex items-start gap-1.5"><MapPin size={11} className="text-slate-500 mt-0.5" />{c.address}</div>}
                  <div className="flex items-center gap-1.5"><Truck size={11} className="text-slate-500" />
                    {c.power_units ? `${c.power_units} power units` : "fleet size n/a"} · USDOT {c.dot_number}{c.docket ? ` · ${c.docket}` : ""}</div>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(c.cargo || []).slice(0, 4).map((cg) => (
                    <span key={cg} className="px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 text-[9px] text-slate-400">{cg}</span>
                  ))}
                  {c.status && <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${String(c.status).toUpperCase() === "A" ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-500/15 text-slate-400"}`}>{String(c.status).toUpperCase() === "A" ? "ACTIVE" : c.status}</span>}
                </div>
                <AiContacts carrier={c} />
              </Card>
            );
          })}
        </div>
      )}
      {rows && rows.length === 0 && <div className="text-center text-slate-500 text-sm py-8">No carriers matched.</div>}
    </div>
  );
};
