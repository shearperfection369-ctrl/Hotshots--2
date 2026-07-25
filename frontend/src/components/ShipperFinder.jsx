import React, { useCallback, useEffect, useState } from "react";
import { Radar, Plus, Loader2, Download, Sparkles, Phone, Mail, Linkedin, Trash2, BookOpen, ChevronDown, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { api } from "../lib/api";

const STAGE_META = {
  lead: ["Lead", "#94A3B8"], contacted: ["Contacted", "#38BDF8"], meeting: ["Meeting", "#A78BFA"],
  quoted: ["Quoted", "#FBBF24"], trial: ["Trial", "#FB923C"], contracted: ["Contracted", "#10B981"], lost: ["Lost", "#EF4444"],
};

const EMPTY = { company: "", contact_name: "", title: "", email: "", phone: "", city: "", state: "MN", industry: "", est_loads_per_week: 0, lanes: "", source: "cold", notes: "", next_action: "" };

export const ShipperFinder = () => {
  const [data, setData] = useState(null);
  const [playbook, setPlaybook] = useState(null);
  const [openBook, setOpenBook] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState("");
  const [outreach, setOutreach] = useState(null);

  const load = useCallback(async () => {
    try {
      const [{ data: d }, { data: pb }] = await Promise.all([
        api.get("/shipper-finder/prospects"), api.get("/shipper-finder/playbook")]);
      setData(d); setPlaybook(pb);
    } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const setStage = async (pid, stage) => {
    try { await api.patch(`/shipper-finder/prospects/${pid}`, { stage }); load(); }
    catch (e) { toast.error("Failed to update stage"); }
  };

  const addProspect = async () => {
    if (!form.company) { toast.error("Company name required"); return; }
    setBusy("add");
    try {
      await api.post("/shipper-finder/prospects", { ...form, est_loads_per_week: Number(form.est_loads_per_week) || 0 });
      toast.success(`${form.company} added to pipeline`);
      setForm(EMPTY); setShowAdd(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to add"); } finally { setBusy(""); }
  };

  const removeProspect = async (p) => {
    try { await api.delete(`/shipper-finder/prospects/${p.id}`); toast.success(`${p.company} removed`); load(); }
    catch (_) { toast.error("Failed to delete"); }
  };

  const genOutreach = async (p, channel) => {
    setBusy(`out-${p.id}`);
    setOutreach({ prospect: p, channel, script: "", loading: true });
    try {
      const { data: r } = await api.post(`/shipper-finder/prospects/${p.id}/outreach`, { channel });
      setOutreach({ prospect: p, channel, script: r.script, loading: false });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI generation failed");
      setOutreach(null);
    } finally { setBusy(""); }
  };

  const downloadBrochure = async () => {
    setBusy("brochure");
    try {
      const res = await api.get("/shipper-finder/brochure.pdf", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = "Ship_With_Orisei_Brochure.pdf"; a.click();
      URL.revokeObjectURL(url);
      toast.success("Shipper brochure downloaded");
    } catch (_) { toast.error("Download failed"); } finally { setBusy(""); }
  };

  if (!data) return <div className="p-8 text-center text-slate-500 font-mono text-xs" data-testid="shipper-finder-loading">Loading shipper pipeline…</div>;

  const BOOK_SECTIONS = playbook ? [
    ["advantages", "Competitive Advantages", playbook.competitive_advantages.map((a) => `${a.title} — ${a.detail}`)],
    ["offers", "The Offer Stack (what to pitch)", playbook.offer_stack.map((o) => `${o.offer} — ${o.detail}`)],
    ["channels", "Where to Find Shippers", playbook.sourcing_channels.map((s) => `${s.channel} — ${s.how}`)],
    ["tips", "Industry Outreach Tips", playbook.outreach_tips],
  ] : [];

  return (
    <div className="space-y-4" data-testid="shipper-finder">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Radar size={16} className="text-cyan-300" />
          <h3 className="text-sm font-black text-white uppercase tracking-wider">Shipper Finder — acquisition pipeline</h3>
        </div>
        <div className="flex gap-2">
          <Button onClick={downloadBrochure} disabled={busy === "brochure"} data-testid="shipper-brochure-btn"
                  className="bg-amber-500 hover:bg-amber-400 text-black font-bold font-mono text-[11px] uppercase h-9">
            {busy === "brochure" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Download size={12} className="mr-1" />} Shipper Brochure PDF
          </Button>
          <Button onClick={() => setShowAdd(true)} data-testid="shipper-add-btn"
                  className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase h-9">
            <Plus size={12} className="mr-1" /> Add Prospect
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="shipper-pipeline-stats">
        {Object.entries(STAGE_META).map(([k, [label, color]]) => (
          <div key={k} className="px-3 py-1.5 rounded-xl border border-white/10 bg-slate-950/60" data-testid={`shipper-stage-count-${k}`}>
            <span className="text-sm font-black tabular-nums" style={{ color }}>{data.counts[k] || 0}</span>
            <span className="text-[9px] font-mono uppercase text-slate-500 ml-1.5">{label}</span>
          </div>
        ))}
        <div className="px-3 py-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/5" data-testid="shipper-pipeline-loads">
          <span className="text-sm font-black text-emerald-300 tabular-nums">{data.pipeline_loads_per_week}</span>
          <span className="text-[9px] font-mono uppercase text-slate-500 ml-1.5">pipeline loads/wk · {data.contracted_loads_per_week} contracted</span>
        </div>
      </div>

      <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.03]" data-testid="shipper-playbook">
        <div className="px-3 py-2 text-[10px] font-mono uppercase text-amber-300 flex items-center gap-1.5">
          <BookOpen size={11} /> Shipper Acquisition Playbook
        </div>
        {BOOK_SECTIONS.map(([id, title, items]) => (
          <div key={id} className="border-t border-white/5">
            <button onClick={() => setOpenBook(openBook === id ? "" : id)} data-testid={`playbook-toggle-${id}`}
                    className="w-full flex items-center justify-between px-3 py-2 text-[11px] font-bold text-white hover:bg-white/[0.03]">
              {title} <ChevronDown size={13} className={`transition-transform ${openBook === id ? "rotate-180" : ""}`} />
            </button>
            {openBook === id && (
              <ul className="px-4 pb-3 space-y-1">
                {items.map((t) => (
                  <li key={t.slice(0, 40)} className="text-[10px] text-slate-400 flex gap-1.5"><span className="text-amber-400">▸</span>{t}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="w-full text-[11px]" data-testid="shipper-prospect-table">
          <thead>
            <tr className="text-slate-500 font-mono text-[9px] uppercase bg-slate-950/70">
              <th className="text-left px-3 py-2">Company</th><th className="text-left px-2">Contact</th>
              <th className="text-left px-2">Lanes</th><th className="text-right px-2">Loads/wk</th>
              <th className="text-left px-2">Source</th><th className="text-left px-2">Stage</th>
              <th className="text-left px-2">Next action</th><th className="text-right px-3">Outreach</th>
            </tr>
          </thead>
          <tbody>
            {data.prospects.map((p) => (
              <tr key={p.id} className="border-t border-white/5 text-slate-300" data-testid={`prospect-row-${p.id}`}>
                <td className="px-3 py-2">
                  <div className="font-bold text-white">{p.company}</div>
                  <div className="text-[9px] text-slate-500">{p.industry} · {p.city}, {p.state}</div>
                </td>
                <td className="px-2"><div>{p.contact_name}</div><div className="text-[9px] text-slate-500">{p.title}</div></td>
                <td className="px-2 text-[10px] text-slate-400 max-w-[160px]">{p.lanes}</td>
                <td className="px-2 text-right tabular-nums font-bold text-white">{p.est_loads_per_week}</td>
                <td className="px-2 text-[10px] text-slate-400">{p.source}</td>
                <td className="px-2">
                  <select value={p.stage} onChange={(e) => setStage(p.id, e.target.value)} data-testid={`prospect-stage-${p.id}`}
                          className="h-7 px-1.5 rounded bg-slate-950 border border-white/15 text-[10px] outline-none"
                          style={{ color: STAGE_META[p.stage]?.[1] }}>
                    {Object.entries(STAGE_META).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
                  </select>
                </td>
                <td className="px-2 text-[10px] text-slate-400 max-w-[150px]">{p.next_action}</td>
                <td className="px-3 text-right whitespace-nowrap">
                  {[["email", Mail], ["call", Phone], ["linkedin", Linkedin]].map(([ch, Icon]) => (
                    <button key={ch} onClick={() => genOutreach(p, ch)} disabled={busy === `out-${p.id}`} title={`AI ${ch} script`}
                            data-testid={`outreach-${ch}-${p.id}`}
                            className="p-1.5 rounded hover:bg-cyan-500/10 text-cyan-300 disabled:opacity-40">
                      <Icon size={12} />
                    </button>
                  ))}
                  <button onClick={() => removeProspect(p)} data-testid={`prospect-delete-${p.id}`}
                          className="p-1.5 rounded hover:bg-red-500/10 text-red-400"><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={showAdd} onOpenChange={setShowAdd}>
        <DialogContent className="bg-slate-950 border-white/15 max-w-lg">
          <DialogHeader><DialogTitle className="text-white text-sm font-black uppercase">Add Shipper Prospect</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-2">
            {[["company", "Company *"], ["contact_name", "Contact name"], ["title", "Title"], ["email", "Email"],
              ["phone", "Phone"], ["city", "City"], ["industry", "Industry"], ["est_loads_per_week", "Est loads/wk"],
              ["lanes", "Lanes"], ["source", "Source"], ["next_action", "Next action"]].map(([k, label]) => (
              <div key={k} className={k === "lanes" ? "col-span-2" : ""}>
                <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">{label}</div>
                <Input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                       data-testid={`prospect-form-${k}`} className="h-8 bg-slate-900 border-white/15 text-xs text-white" />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button onClick={addProspect} disabled={busy === "add"} data-testid="prospect-form-submit"
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase">
              {busy === "add" ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Plus size={12} className="mr-1" />} Add to Pipeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!outreach} onOpenChange={(o) => !o && setOutreach(null)}>
        <DialogContent className="bg-slate-950 border-white/15 max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-white text-sm font-black uppercase flex items-center gap-2">
              <Sparkles size={14} className="text-cyan-300" /> AI {outreach?.channel} script — {outreach?.prospect?.company}
            </DialogTitle>
          </DialogHeader>
          {outreach?.loading ? (
            <div className="py-8 text-center text-slate-500 font-mono text-xs" data-testid="outreach-loading">
              <Loader2 size={18} className="mx-auto mb-2 animate-spin text-cyan-300" /> Writing personalized outreach…
            </div>
          ) : (
            <>
              <pre className="whitespace-pre-wrap text-[11px] text-slate-300 bg-slate-900/70 rounded-lg p-3 max-h-[45vh] overflow-y-auto font-sans" data-testid="outreach-script">
                {outreach?.script}
              </pre>
              <DialogFooter>
                <Button onClick={() => { navigator.clipboard.writeText(outreach.script); toast.success("Copied to clipboard"); }}
                        data-testid="outreach-copy-btn"
                        className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase">
                  <Copy size={12} className="mr-1" /> Copy Script
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
