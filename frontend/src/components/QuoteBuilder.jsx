import React, { useCallback, useEffect, useState } from "react";
import { FileSignature, Plus, Loader2, Download, Trash2, Pencil, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/dialog";
import { api } from "../lib/api";

const STATUS_META = {
  draft: ["Draft", "#94A3B8"], sent: ["Sent", "#38BDF8"], accepted: ["Accepted", "#10B981"],
  declined: ["Declined", "#EF4444"], expired: ["Expired", "#F59E0B"],
};
const EQUIPMENT = ["van", "reefer", "flatbed", "stepdeck", "power-only"];
const EMPTY_LINE = { origin: "", destination: "", equipment: "van", miles: 0, rate_usd: 0, fuel_pct: 0, accessorials_usd: 0, notes: "" };
const EMPTY_Q = { shipper: "", contact_name: "", contact_email: "", contact_phone: "", valid_days: 14, notes: "", lines: [{ ...EMPTY_LINE }] };
const usd = (n) => (n == null ? "—" : `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })}`);

export const QuoteBuilder = ({ prefill, onPrefillConsumed }) => {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_Q);
  const [bench, setBench] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => api.get("/freight-quotes").then(({ data: d }) => setData(d)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (prefill) {
      setForm({ ...EMPTY_Q, shipper: prefill.company || "", contact_name: prefill.contact_name || "",
                contact_email: prefill.email || "", contact_phone: prefill.phone || "", lines: [{ ...EMPTY_LINE }] });
      setEditing("new"); setBench(null);
      onPrefillConsumed?.();
    }
  }, [prefill, onPrefillConsumed]);

  const openNew = () => { setForm(EMPTY_Q); setBench(null); setEditing("new"); };
  const openEdit = (q) => {
    setForm({ shipper: q.shipper, contact_name: q.contact_name, contact_email: q.contact_email,
              contact_phone: q.contact_phone, valid_days: q.valid_days, notes: q.notes,
              lines: q.lines.map(({ origin, destination, equipment, miles, rate_usd, fuel_pct, accessorials_usd, notes }) =>
                ({ origin, destination, equipment, miles, rate_usd, fuel_pct, accessorials_usd, notes })) });
    setBench(null); setEditing(q.id);
  };

  const setLine = (i, k, v) => {
    const lines = form.lines.map((l, j) => (j === i ? { ...l, [k]: v } : l));
    setForm({ ...form, lines });
  };

  const checkMarket = async () => {
    setBusy("bench");
    try {
      const { data: b } = await api.post("/freight-quotes/benchmark", { lines: normalizedLines() });
      setBench(b);
    } catch (_) { toast.error("Benchmark failed"); } finally { setBusy(""); }
  };

  const normalizedLines = () => form.lines.map((l) => ({
    ...l, miles: Number(l.miles) || 0, rate_usd: Number(l.rate_usd) || 0,
    fuel_pct: Number(l.fuel_pct) || 0, accessorials_usd: Number(l.accessorials_usd) || 0 }));

  const save = async () => {
    if (!form.shipper) { toast.error("Shipper required"); return; }
    if (!form.lines.length || !form.lines[0].origin) { toast.error("At least one lane required"); return; }
    setBusy("save");
    const payload = { ...form, valid_days: Number(form.valid_days) || 14, lines: normalizedLines() };
    try {
      if (editing === "new") { await api.post("/freight-quotes", payload); toast.success("Quote created"); }
      else { await api.patch(`/freight-quotes/${editing}`, payload); toast.success("Quote updated"); }
      setEditing(null); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); } finally { setBusy(""); }
  };

  const setStatus = async (q, status) => {
    try { await api.patch(`/freight-quotes/${q.id}`, { status }); load(); } catch (_) { toast.error("Status update failed"); }
  };

  const remove = async (q) => {
    try { await api.delete(`/freight-quotes/${q.id}`); toast.success(`${q.id} deleted`); load(); }
    catch (_) { toast.error("Delete failed"); }
  };

  const pdf = async (q) => {
    setBusy(`pdf-${q.id}`);
    try {
      const res = await api.get(`/freight-quotes/${q.id}/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Orisei_Quote_${q.id}.pdf`; a.click();
      URL.revokeObjectURL(url);
      toast.success("Branded quote PDF downloaded");
    } catch (_) { toast.error("PDF failed"); } finally { setBusy(""); }
  };

  if (!data) return <div className="p-8 text-center text-slate-500 font-mono text-xs" data-testid="quotes-loading">Loading quotes…</div>;

  return (
    <div className="space-y-4" data-testid="quote-builder">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileSignature size={16} className="text-cyan-300" />
          <h3 className="text-sm font-black text-white uppercase tracking-wider">Quote Builder — branded quotes in seconds</h3>
        </div>
        <Button onClick={openNew} data-testid="quote-new-btn"
                className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase h-9">
          <Plus size={12} className="mr-1" /> New Quote
        </Button>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="quote-status-stats">
        {Object.entries(STATUS_META).map(([k, [label, color]]) => (
          <div key={k} className="px-3 py-1.5 rounded-xl border border-white/10 bg-slate-950/60" data-testid={`quote-count-${k}`}>
            <span className="text-sm font-black tabular-nums" style={{ color }}>{data.counts[k] || 0}</span>
            <span className="text-[9px] font-mono uppercase text-slate-500 ml-1.5">{label}</span>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-[11px]" data-testid="quote-table">
          <thead>
            <tr className="text-slate-500 font-mono text-[9px] uppercase bg-slate-950/70">
              <th className="text-left px-3 py-2">Quote #</th><th className="text-left px-2">Shipper</th>
              <th className="text-right px-2">Lanes</th><th className="text-right px-2">Total</th>
              <th className="text-right px-2">vs Market</th><th className="text-left px-2">Valid until</th>
              <th className="text-left px-2">Status</th><th className="text-right px-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.quotes.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-slate-500 font-mono text-[10px]" data-testid="quotes-empty">
                No quotes yet — hit New Quote or quote a prospect from the Shipper Finder.</td></tr>
            )}
            {data.quotes.map((q) => (
              <tr key={q.id} className="border-t border-white/5 text-slate-300" data-testid={`quote-row-${q.id}`}>
                <td className="px-3 py-2 font-bold text-white font-mono">{q.id}</td>
                <td className="px-2"><div className="font-bold text-white">{q.shipper}</div>
                  <div className="text-[9px] text-slate-500">{q.contact_name}</div></td>
                <td className="px-2 text-right tabular-nums">{q.lines.length}</td>
                <td className="px-2 text-right tabular-nums font-bold text-emerald-300">{usd(q.total_usd)}</td>
                <td className={`px-2 text-right tabular-nums font-bold ${q.vs_market_usd >= 0 ? "text-emerald-300" : "text-amber-300"}`}>
                  {q.vs_market_usd == null ? "—" : `${usd(Math.abs(q.vs_market_usd))} ${q.vs_market_usd >= 0 ? "under" : "over"}`}
                </td>
                <td className="px-2 text-[10px] text-slate-400">{q.valid_until}</td>
                <td className="px-2">
                  <select value={q.status} onChange={(e) => setStatus(q, e.target.value)} data-testid={`quote-status-${q.id}`}
                          className="h-7 px-1.5 rounded bg-slate-950 border border-white/15 text-[10px] outline-none"
                          style={{ color: STATUS_META[q.status]?.[1] }}>
                    {Object.entries(STATUS_META).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
                  </select>
                </td>
                <td className="px-3 text-right whitespace-nowrap">
                  <button onClick={() => pdf(q)} disabled={busy === `pdf-${q.id}`} title="Branded PDF" data-testid={`quote-pdf-${q.id}`}
                          className="p-1.5 rounded hover:bg-amber-500/10 text-amber-300 disabled:opacity-40"><Download size={13} /></button>
                  <button onClick={() => openEdit(q)} title="Edit" data-testid={`quote-edit-${q.id}`}
                          className="p-1.5 rounded hover:bg-cyan-500/10 text-cyan-300"><Pencil size={13} /></button>
                  <button onClick={() => remove(q)} title="Delete" data-testid={`quote-delete-${q.id}`}
                          className="p-1.5 rounded hover:bg-red-500/10 text-red-400"><Trash2 size={13} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="bg-slate-950 border-white/15 max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white text-sm font-black uppercase">
              {editing === "new" ? "New Quote" : `Edit ${editing}`}
            </DialogTitle>
            <DialogDescription className="text-[10px] text-slate-500 font-mono">
              Add lanes, check market rates, save — then download the branded PDF
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[["shipper", "Shipper *"], ["contact_name", "Contact"], ["contact_email", "Email"], ["contact_phone", "Phone"]].map(([k, label]) => (
              <div key={k}>
                <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">{label}</div>
                <Input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                       data-testid={`quote-form-${k}`} className="h-8 bg-slate-900 border-white/15 text-xs text-white" />
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="text-[9px] font-mono uppercase text-slate-500">Lanes</div>
            {form.lines.map((l, i) => (
              <div key={i} className="p-2 rounded-lg border border-white/10 bg-slate-900/50" data-testid={`quote-line-${i}`}>
                <div className="grid grid-cols-2 md:grid-cols-7 gap-1.5 items-end">
                  {[["origin", "Origin", "text"], ["destination", "Destination", "text"]].map(([k, label]) => (
                    <div key={k}>
                      <div className="text-[8px] font-mono uppercase text-slate-600">{label}</div>
                      <Input value={l[k]} onChange={(e) => setLine(i, k, e.target.value)}
                             data-testid={`line-${i}-${k}`} className="h-7 bg-slate-950 border-white/15 text-[11px] text-white" />
                    </div>
                  ))}
                  <div>
                    <div className="text-[8px] font-mono uppercase text-slate-600">Equip</div>
                    <select value={l.equipment} onChange={(e) => setLine(i, "equipment", e.target.value)}
                            data-testid={`line-${i}-equipment`}
                            className="h-7 w-full px-1 rounded bg-slate-950 border border-white/15 text-[11px] text-white outline-none">
                      {EQUIPMENT.map((eq) => <option key={eq}>{eq}</option>)}
                    </select>
                  </div>
                  {[["miles", "Miles"], ["rate_usd", "Rate $"], ["fuel_pct", "FSC %"], ["accessorials_usd", "Access $"]].map(([k, label]) => (
                    <div key={k}>
                      <div className="text-[8px] font-mono uppercase text-slate-600">{label}</div>
                      <Input type="number" value={l[k]} onChange={(e) => setLine(i, k, e.target.value)}
                             data-testid={`line-${i}-${k}`} className="h-7 bg-slate-950 border-white/15 text-[11px] text-white" />
                    </div>
                  ))}
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[9px] font-mono text-slate-500" data-testid={`line-${i}-bench`}>
                    {bench?.lines?.[i]?.market_total
                      ? <>Market ref: <b className="text-sky-300">{usd(bench.lines[i].market_total)}</b> ({usd(bench.lines[i].market_per_mile)}/mi) · your line total: <b className="text-emerald-300">{usd(bench.lines[i].line_total)}</b></>
                      : "Run market check for benchmark"}
                  </span>
                  {form.lines.length > 1 && (
                    <button onClick={() => setForm({ ...form, lines: form.lines.filter((_, j) => j !== i) })}
                            data-testid={`line-${i}-remove`} className="p-1 rounded text-red-400 hover:bg-red-500/10"><X size={12} /></button>
                  )}
                </div>
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setForm({ ...form, lines: [...form.lines, { ...EMPTY_LINE }] })} data-testid="quote-add-line-btn"
                      className="bg-white/5 border border-white/15 text-slate-300 font-mono text-[10px] uppercase h-8 hover:bg-white/10">
                <Plus size={11} className="mr-1" /> Add Lane
              </Button>
              <Button onClick={checkMarket} disabled={busy === "bench"} data-testid="quote-benchmark-btn"
                      className="bg-white/5 border border-sky-500/40 text-sky-300 font-mono text-[10px] uppercase h-8 hover:bg-sky-500/10">
                {busy === "bench" ? <Loader2 size={11} className="mr-1 animate-spin" /> : null} Check Market Rates
              </Button>
              {bench && (
                <span className="self-center text-[10px] font-mono text-slate-400" data-testid="quote-bench-totals">
                  Total <b className="text-emerald-300">{usd(bench.total_usd)}</b> · market <b className="text-sky-300">{usd(bench.market_total_usd)}</b>
                  {bench.vs_market_usd != null && <> · {bench.vs_market_usd >= 0 ? "under" : "over"} by <b>{usd(Math.abs(bench.vs_market_usd))}</b></>}
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">Valid for (days)</div>
              <Input type="number" value={form.valid_days} onChange={(e) => setForm({ ...form, valid_days: e.target.value })}
                     data-testid="quote-form-valid_days" className="h-8 bg-slate-900 border-white/15 text-xs text-white" />
            </div>
            <div>
              <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">Notes (printed on PDF)</div>
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                     data-testid="quote-form-notes" className="h-8 bg-slate-900 border-white/15 text-xs text-white" />
            </div>
          </div>

          <DialogFooter>
            <Button onClick={save} disabled={busy === "save"} data-testid="quote-save-btn"
                    className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold font-mono text-[11px] uppercase">
              {busy === "save" ? <Loader2 size={12} className="mr-1 animate-spin" /> : null}
              {editing === "new" ? "Create Quote" : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
