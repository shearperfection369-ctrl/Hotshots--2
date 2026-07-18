import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Target, Plus, Copy, Mail, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const STATUS_STYLE = {
  new: "text-slate-300 border-white/15", contacted: "text-cyan-300 border-cyan-500/40",
  replied: "text-amber-300 border-amber-500/40", demo_booked: "text-purple-300 border-purple-500/40",
  won: "text-emerald-300 border-emerald-500/40", lost: "text-red-400 border-red-500/40",
};
const EMPTY = { company: "", contact: "", email: "", phone: "", city: "", size: "", notes: "" };

export const ProspectList = () => {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/hotshot/prospects").then((r) => setData(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { await api.post("/hotshot/prospects", form); toast.success("Prospect added"); setOpen(false); setForm(EMPTY); load(); }
    catch (_) { toast.error("Failed to add prospect"); } finally { setBusy(false); }
  };
  const setStatus = async (id, status) => {
    try { await api.patch(`/hotshot/prospects/${id}`, { status }); load(); } catch (_) {}
  };
  const del = async (id) => { try { await api.delete(`/hotshot/prospects/${id}`); load(); } catch (_) {} };

  const copyEmail = (p) => {
    navigator.clipboard.writeText(`To: ${p.email}\nSubject: ${p.email_draft.subject}\n\n${p.email_draft.body}`);
    toast.success(`Personalized pitch for ${p.company} copied`);
  };
  const mailto = (p) =>
    `mailto:${p.email}?subject=${encodeURIComponent(p.email_draft.subject)}&body=${encodeURIComponent(p.email_draft.body)}`;

  if (!data) return null;
  return (
    <Card className="p-4 bg-slate-950/60 border-emerald-500/30" data-testid="hs-prospects-card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="text-xs font-mono uppercase tracking-widest text-emerald-300 flex items-center gap-2">
          <Target size={13} /> Small-broker hit list · {data.prospects.length} prospects
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-2 text-[10px] font-mono">
            {Object.entries(data.counts).map(([s, n]) => (
              <span key={s} className={`px-2 py-0.5 rounded-full border ${STATUS_STYLE[s]}`}>{s.replace("_", " ")} {n}</span>
            ))}
          </div>
          <button onClick={() => setOpen(!open)} data-testid="hs-add-prospect-btn"
                  className="px-3 py-1.5 rounded-full bg-emerald-500 text-black font-bold text-xs inline-flex items-center gap-1"><Plus size={12} /> Add</button>
        </div>
      </div>
      <div className="text-[10px] text-slate-500 mb-3">Seed rows are SAMPLE prospects for structure — swap in your real targets. Each row generates a personalized cold pitch: copy it or open your mail app.</div>
      {open && (
        <form onSubmit={add} className="mb-4 grid sm:grid-cols-4 gap-2" data-testid="hs-prospect-form">
          {[["company", "Company *"], ["contact", "Contact name"], ["email", "Email"], ["phone", "Phone"], ["city", "City, ST"], ["size", "Size / revenue"], ["notes", "Notes"]].map(([k, ph]) => (
            <input key={k} required={ph.includes("*")} value={form[k]} placeholder={ph} data-testid={`hs-prospect-${k}-input`}
                   onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                   className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs outline-none focus:border-emerald-400" />
          ))}
          <button type="submit" disabled={busy} data-testid="hs-prospect-submit"
                  className="h-9 rounded-full bg-emerald-500 text-black font-bold text-xs inline-flex items-center justify-center gap-1 disabled:opacity-60">
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />} Save
          </button>
        </form>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="py-2 pr-3">Prospect</th><th className="py-2 pr-3">Profile</th><th className="py-2 pr-3">Angle</th>
            <th className="py-2 pr-3">Status</th><th className="py-2">Solicit</th>
          </tr></thead>
          <tbody>
            {data.prospects.map((p) => (
              <tr key={p.prospect_id} className="border-b border-white/5" data-testid={`hs-prospect-row-${p.prospect_id}`}>
                <td className="py-2.5 pr-3">
                  <div className="text-white font-semibold">{p.company}{p.is_sample && <span className="ml-1.5 text-[8px] font-mono uppercase px-1 py-0.5 rounded bg-white/5 text-slate-500 border border-white/10">sample</span>}</div>
                  <div className="text-[10px] text-slate-500">{p.contact} · {p.city}</div>
                </td>
                <td className="py-2.5 pr-3 text-[11px] text-slate-400">{p.size}</td>
                <td className="py-2.5 pr-3 text-[11px] text-slate-500 max-w-[220px] truncate">{p.notes}</td>
                <td className="py-2.5 pr-3">
                  <select value={p.status} onChange={(e) => setStatus(p.prospect_id, e.target.value)} data-testid={`hs-prospect-status-${p.prospect_id}`}
                          className={`h-7 rounded bg-slate-950 border text-[10px] font-mono px-1 ${STATUS_STYLE[p.status]}`}>
                    {data.statuses.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                  </select>
                </td>
                <td className="py-2.5">
                  <div className="flex gap-2.5 items-center">
                    <button onClick={() => copyEmail(p)} title="Copy personalized pitch" data-testid={`hs-prospect-copy-${p.prospect_id}`}
                            className="text-cyan-300 hover:text-cyan-200"><Copy size={14} /></button>
                    <a href={mailto(p)} title="Open in mail app" onClick={() => setStatus(p.prospect_id, "contacted")}
                       data-testid={`hs-prospect-mail-${p.prospect_id}`} className="text-amber-300 hover:text-amber-200"><Mail size={14} /></a>
                    <button onClick={() => del(p.prospect_id)} title="Remove" className="text-slate-600 hover:text-red-400"><Trash2 size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
