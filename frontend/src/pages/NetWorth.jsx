import React, { useCallback, useEffect, useState } from "react";
import { Landmark, Download, Plus, X, Loader2, FileText, CheckCircle2, Send as SendIcon } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const money = (n) => `$${Math.round(n || 0).toLocaleString()}`;

export default function NetWorth() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try { const { data: d } = await api.get("/net-worth"); setData(d); }
    catch (_) { toast.error("Failed to load net worth data"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const download = async (path, filename) => {
    setBusy(path);
    try {
      const { data: blob } = await api.get(`/net-worth/${path}`, { responseType: "blob", timeout: 60000 });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success(`${filename} downloaded`);
    } catch (_) { toast.error("Download failed"); } finally { setBusy(""); }
  };

  if (!data) return <div className="p-8 text-slate-500 font-mono text-sm">Loading net worth center…</div>;
  const cb = data.combined;

  return (
    <div className="p-6 space-y-6" data-testid="net-worth-page">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-2"><Landmark className="text-amber-300" size={24} /> Partnership Net Worth</h1>
          <p className="text-xs text-slate-500 font-mono mt-1">Branded member statements for insurance & surety underwriting · master document kept in-system</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => download("template.pdf", "Orisei-Member-Net-Worth-Template.pdf")} disabled={!!busy} data-testid="nw-template-btn"
                  className="px-4 py-2 rounded-full border border-cyan-500/50 text-cyan-300 text-[11px] font-bold inline-flex items-center gap-1.5 hover:bg-cyan-500/10 disabled:opacity-50">
            {busy === "template.pdf" ? <Loader2 size={13} className="animate-spin" /> : <FileText size={13} />} Blank Template (give to owners)
          </button>
          <button onClick={() => download("master.pdf", "Orisei-Partnership-Net-Worth-Master.pdf")} disabled={!!busy} data-testid="nw-master-btn"
                  className="px-4 py-2 rounded-full bg-amber-500 text-black text-[11px] font-black inline-flex items-center gap-1.5 disabled:opacity-50">
            {busy === "master.pdf" ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} MASTER STATEMENT PDF
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="nw-stats">
        {[["Combined assets", money(cb.total_assets), "#34D399"], ["Combined liabilities", money(cb.total_liabilities), "#F87171"],
          ["Combined net worth", money(cb.net_worth), "#F59E0B"], ["Statements submitted", `${cb.submitted}/${data.members.length}`, "#22D3EE"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70">
            <div className="text-lg font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        {data.members.map((m) => (
          <MemberCard key={m.id} member={m} assetCats={data.asset_categories} liabCats={data.liability_categories} onSaved={load} />
        ))}
      </div>
    </div>
  );
}

function MemberCard({ member, assetCats, liabCats, onSaved }) {
  const [m, setM] = useState(member);
  const [saving, setSaving] = useState(false);
  const [email, setEmail] = useState(member.form_sent_to || "");
  const [sending, setSending] = useState(false);
  useEffect(() => setM(member), [member]);

  const sendForm = async () => {
    if (!email.includes("@")) { toast.error("Enter the partner's email first"); return; }
    setSending(true);
    try {
      const { data } = await api.post(`/net-worth/members/${m.id}/send-form`, { email });
      toast.success(data.sent ? `Form emailed to ${email}` : `Form queued for ${email} — add Resend key in Connections to deliver`);
      onSaved();
    } catch (_) { toast.error("Send failed"); } finally { setSending(false); }
  };

  const save = async (status) => {
    setSaving(true);
    try {
      const body = { member_name: m.member_name, as_of_date: m.as_of_date || "", assets: m.assets, liabilities: m.liabilities, status: status || m.status };
      const { data } = await api.put(`/net-worth/members/${m.id}`, body);
      setM(data.member);
      toast.success(status === "submitted" ? `${m.member_name} statement submitted` : "Saved");
      onSaved();
    } catch (_) { toast.error("Save failed"); } finally { setSaving(false); }
  };
  const setRow = (kind, i, patch) => {
    const rows = [...m[kind]];
    rows[i] = { ...rows[i], ...patch };
    setM({ ...m, [kind]: rows });
  };
  const addRow = (kind, cats) => setM({ ...m, [kind]: [...m[kind], { category: cats[0], description: "", value: 0 }] });
  const rmRow = (kind, i) => setM({ ...m, [kind]: m[kind].filter((_, x) => x !== i) });
  const ta = m.assets.reduce((a, x) => a + (+x.value || 0), 0);
  const tl = m.liabilities.reduce((a, x) => a + (+x.value || 0), 0);

  const section = (kind, cats, color, label) => (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <div className="text-[9px] font-mono uppercase font-bold" style={{ color }}>{label}</div>
        <button onClick={() => addRow(kind, cats)} data-testid={`nw-add-${kind}-${m.id}`} className="text-slate-500 hover:text-white"><Plus size={12} /></button>
      </div>
      {m[kind].map((r, i) => (
        <div key={i} className="flex gap-1 mb-1 items-center">
          <select value={r.category} onChange={(e) => setRow(kind, i, { category: e.target.value })}
                  className="flex-1 min-w-0 bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-slate-300">
            {cats.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input placeholder="detail" value={r.description} onChange={(e) => setRow(kind, i, { description: e.target.value })}
                 className="w-20 bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-white" />
          <input type="number" value={r.value} onChange={(e) => setRow(kind, i, { value: +e.target.value || 0 })} data-testid={`nw-${kind}-value-${m.id}-${i}`}
                 className="w-24 bg-slate-900 border border-white/15 rounded-lg px-1.5 py-1 text-[10px] text-right" style={{ color }} />
          <button onClick={() => rmRow(kind, i)} className="text-slate-700 hover:text-red-400"><X size={11} /></button>
        </div>
      ))}
      {!m[kind].length && <div className="text-[10px] font-mono text-slate-600">none yet — click +</div>}
    </div>
  );

  return (
    <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/60" data-testid={`nw-member-${m.id}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="font-black text-white text-sm">{m.member_name}</div>
        {m.status === "submitted"
          ? <span className="text-[9px] font-mono font-black text-emerald-300 flex items-center gap-1"><CheckCircle2 size={11} /> SUBMITTED</span>
          : <span className="text-[9px] font-mono font-black text-slate-500">DRAFT</span>}
      </div>
      <label className="text-[9px] font-mono text-slate-500 uppercase">As of date
        <input type="date" value={m.as_of_date || ""} onChange={(e) => setM({ ...m, as_of_date: e.target.value })} data-testid={`nw-date-${m.id}`}
               className="w-full bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white mt-0.5 mb-3" />
      </label>
      <div className="mb-3 p-2 rounded-xl border border-cyan-500/20 bg-cyan-500/5">
        <div className="text-[9px] font-mono uppercase text-cyan-300 font-bold mb-1">Email the form to this partner</div>
        <div className="flex gap-1.5">
          <input placeholder="partner@email.com" value={email} onChange={(e) => setEmail(e.target.value)} data-testid={`nw-email-${m.id}`}
                 className="flex-1 min-w-0 bg-slate-900 border border-white/15 rounded-lg px-2 py-1.5 text-[11px] text-white" />
          <button onClick={sendForm} disabled={sending} data-testid={`nw-send-form-${m.id}`}
                  className="px-3 py-1.5 rounded-full border border-cyan-500/50 text-cyan-300 text-[10px] font-black inline-flex items-center gap-1 hover:bg-cyan-500/10 disabled:opacity-50">
            {sending ? <Loader2 size={11} className="animate-spin" /> : <SendIcon size={11} />} SEND
          </button>
        </div>
        {m.form_sent_at && <div className="text-[9px] font-mono text-slate-500 mt-1">Form {m.form_send_status === "sent" ? "sent" : "queued"} to {m.form_sent_to} · {m.form_sent_at.slice(0, 10)}</div>}
      </div>
      {section("assets", assetCats, "#34D399", "Assets")}
      {section("liabilities", liabCats, "#F87171", "Liabilities")}
      <div className="flex justify-between text-[11px] font-mono border-t border-white/10 pt-2 mb-3">
        <span className="text-slate-400">Net worth</span>
        <span className="font-black" style={{ color: ta - tl >= 0 ? "#F59E0B" : "#F87171" }} data-testid={`nw-networth-${m.id}`}>{money(ta - tl)}</span>
      </div>
      <div className="flex gap-2">
        <button onClick={() => save()} disabled={saving} data-testid={`nw-save-${m.id}`}
                className="flex-1 px-3 py-1.5 rounded-full border border-white/20 text-slate-300 text-[10px] font-bold hover:border-amber-400 disabled:opacity-50">Save draft</button>
        <button onClick={() => save("submitted")} disabled={saving} data-testid={`nw-submit-${m.id}`}
                className="flex-1 px-3 py-1.5 rounded-full bg-emerald-500 text-black text-[10px] font-black disabled:opacity-50">SUBMIT</button>
      </div>
    </div>
  );
}
