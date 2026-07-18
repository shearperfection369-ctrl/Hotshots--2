import React, { useCallback, useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Zap, Copy, ExternalLink, FileText, Users, Video, Trash2, UploadCloud, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api, BACKEND_URL } from "../lib/api";

const STATUSES = ["new", "contacted", "demo_booked", "won", "lost"];
const SBADGE = {
  new: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  contacted: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  demo_booked: "bg-purple-500/15 text-purple-300 border-purple-500/40",
  won: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  lost: "bg-slate-500/15 text-slate-400 border-slate-500/40",
};

const LINKEDIN_MSG = `I built an AI-driven TMS from scratch after 13 years in logistics — it's running my own brokerage right now. Letting a handful of people use it at a founder rate before I open it up. Want a quick demo?`;

const COLD_EMAIL = `Subject: Built this for my own brokerage — thought of yours

Hi {first name},

I run a small freight brokerage in Minnesota and built our own AI-driven TMS because everything on the market was either ancient or enterprise-priced. It hunts load boards 24/7, triages exceptions, and chases invoices automatically — it runs our desk every day.

I'm licensing it to 5 small brokerages at a founder rate (35% off for life) before opening it up. 15-minute live demo — you'll watch the AI score real freight.

Worth a look? Grab a time or just reply: {landing link}

— Oliver Cummins, Orisei Freight Solutions / Hot Shot TMS`;

function DemoVideoCard() {
  const [status, setStatus] = useState({ exists: false });
  const [progress, setProgress] = useState(null);
  const fileRef = useRef(null);

  const refresh = useCallback(async () => {
    try { const { data } = await api.get("/hotshot/demo-video/status"); setStatus(data); } catch (_) {}
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const upload = async (file) => {
    if (!file) return;
    if (!file.type.startsWith("video/")) { toast.error("Pick a video file (mp4/webm/mov)"); return; }
    const chunkSize = 4 * 1024 * 1024;
    const total = Math.ceil(file.size / chunkSize);
    const uploadId = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
    setProgress(0);
    try {
      for (let i = 0; i < total; i++) {
        const fd = new FormData();
        fd.append("upload_id", uploadId);
        fd.append("chunk_index", i);
        fd.append("total_chunks", total);
        fd.append("file", file.slice(i * chunkSize, (i + 1) * chunkSize), file.name);
        await api.post("/hotshot/demo-video/chunk", fd);
        setProgress(Math.round(((i + 1) / total) * 100));
      }
      toast.success("Demo video is live on the landing page");
      refresh();
    } catch (e) {
      toast.error("Upload failed — try again");
    } finally {
      setProgress(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const remove = async () => {
    try { await api.delete("/hotshot/demo-video"); toast.success("Demo video removed"); refresh(); }
    catch (_) { toast.error("Failed to remove"); }
  };

  return (
    <Card className="p-4 bg-slate-950/60 border-purple-500/30" data-testid="hs-demo-video-card">
      <div className="text-xs font-mono uppercase tracking-widest text-purple-300 flex items-center gap-2 mb-2"><Video size={13} /> Landing page demo video</div>
      {status.exists ? (
        <div className="space-y-2">
          <video controls preload="metadata" className="w-full rounded-lg border border-white/10 bg-black max-h-40"
                 src={`${BACKEND_URL}/api/hotshot/demo-video`} data-testid="hs-demo-video-preview" />
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
            <span>{status.original_name} · {(status.size / 1024 / 1024).toFixed(1)} MB</span>
            <button onClick={remove} data-testid="hs-demo-video-delete" className="flex items-center gap-1 text-red-400 hover:text-red-300"><Trash2 size={12} /> Remove</button>
          </div>
          <div className="text-[10px] text-emerald-400 font-mono">✓ LIVE in the landing page demo box</div>
        </div>
      ) : progress !== null ? (
        <div className="py-4">
          <div className="flex items-center gap-2 text-sm text-slate-300 mb-2"><Loader2 size={14} className="animate-spin" /> Uploading… {progress}%</div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-purple-500 transition-all" style={{ width: `${progress}%` }} /></div>
        </div>
      ) : (
        <button onClick={() => fileRef.current?.click()} data-testid="hs-demo-video-upload-btn"
                className="w-full py-6 rounded-lg border-2 border-dashed border-purple-500/40 hover:border-purple-400 text-sm text-slate-300 flex flex-col items-center gap-1.5">
          <UploadCloud size={20} className="text-purple-300" />
          Upload your demo capture (mp4)
          <span className="text-[10px] text-slate-500">Chunked upload — large 10-min files are fine</span>
        </button>
      )}
      <input ref={fileRef} type="file" accept="video/*" className="hidden" data-testid="hs-demo-video-file-input"
             onChange={(e) => upload(e.target.files?.[0])} />
    </Card>
  );
}

export default function HotShotSales() {
  const [leads, setLeads] = useState([]);
  const landing = `${window.location.origin}/hotshot`;

  const load = useCallback(async () => {
    try { const r = await api.get("/hotshot/leads"); setLeads(r.data.leads || []); } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const setStatus = async (id, status) => {
    try { await api.post(`/hotshot/leads/${id}/status`, { status }); load(); }
    catch (_) { toast.error("Failed to update"); }
  };

  const copy = (txt, label) => { navigator.clipboard.writeText(txt); toast.success(`${label} copied`); };

  const counts = STATUSES.reduce((a, s) => ({ ...a, [s]: leads.filter((l) => l.status === s).length }), {});

  return (
    <>
      <Topbar title="Hot Shot TMS — Sales Command" subtitle="Phase 1 launch kit: landing page, collateral, outreach scripts, and your live lead pipeline" />
      <div className="p-4 md:p-6 space-y-5" data-testid="hotshot-sales-page">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-4 bg-slate-950/60 border-amber-500/30">
            <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2 mb-2"><Zap size={13} /> Launch assets</div>
            <div className="space-y-2 text-sm">
              <a href={landing} target="_blank" rel="noreferrer" data-testid="hs-open-landing"
                 className="flex items-center gap-2 text-cyan-300 hover:text-cyan-200"><ExternalLink size={13} /> Public landing page — /hotshot</a>
              <button onClick={() => copy(landing, "Landing link")} className="flex items-center gap-2 text-slate-300 hover:text-white"><Copy size={13} /> Copy landing link</button>
              <a href={`${BACKEND_URL}/api/hotshot/one-pager.pdf`} data-testid="hs-download-onepager"
                 className="flex items-center gap-2 text-amber-300 hover:text-amber-200"><FileText size={13} /> One-pager + pricing PDF</a>
            </div>
            <div className="text-[10px] text-slate-500 mt-3">Demo video: upload your screen capture in the purple card → it plays live in the landing page demo box.</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-2">LinkedIn opener (20–30/day)</div>
            <p className="text-[12px] text-slate-300 leading-relaxed">{LINKEDIN_MSG}</p>
            <button onClick={() => copy(LINKEDIN_MSG, "LinkedIn message")} data-testid="hs-copy-linkedin"
                    className="mt-2 text-xs text-cyan-300 hover:text-cyan-200 flex items-center gap-1"><Copy size={12} /> Copy</button>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-2">Cold email (FMCSA broker list)</div>
            <p className="text-[11px] text-slate-400 leading-relaxed whitespace-pre-line max-h-32 overflow-y-auto">{COLD_EMAIL}</p>
            <button onClick={() => copy(COLD_EMAIL.replace("{landing link}", landing), "Cold email")} data-testid="hs-copy-email"
                    className="mt-2 text-xs text-cyan-300 hover:text-cyan-200 flex items-center gap-1"><Copy size={12} /> Copy</button>
          </Card>
          <DemoVideoCard />
        </div>

        <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="hs-leads-card">
          <div className="flex items-center gap-3 mb-3">
            <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2"><Users size={13} /> Lead pipeline</div>
            {STATUSES.map((s) => counts[s] > 0 && (
              <Badge key={s} className={`${SBADGE[s]} text-[9px] font-mono uppercase`}>{s.replace("_", " ")} {counts[s]}</Badge>
            ))}
          </div>
          {leads.length === 0 ? (
            <div className="text-sm text-slate-500 py-6 text-center">No leads yet — share the landing page and start the LinkedIn cadence. They'll show up here live.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
                  <th className="py-2 pr-3">Lead</th><th className="py-2 pr-3">Company / size</th>
                  <th className="py-2 pr-3">Tier</th><th className="py-2 pr-3">Note</th><th className="py-2 pr-3">When</th><th className="py-2">Status</th>
                </tr></thead>
                <tbody>
                  {leads.map((l) => (
                    <tr key={l.lead_id} className="border-b border-white/5" data-testid={`hs-lead-${l.lead_id}`}>
                      <td className="py-2 pr-3"><div className="text-white">{l.name}</div><div className="text-[11px] text-slate-500 font-mono">{l.email}</div></td>
                      <td className="py-2 pr-3 text-slate-300 text-xs">{l.company || "—"}<div className="text-[10px] text-slate-500">{l.fleet_or_volume}</div></td>
                      <td className="py-2 pr-3 text-amber-300 text-xs font-mono">{l.tier_interest || "—"}</td>
                      <td className="py-2 pr-3 text-slate-400 text-[11px] max-w-[200px] truncate" title={l.message}>{l.message || "—"}</td>
                      <td className="py-2 pr-3 text-[10px] text-slate-500 font-mono">{new Date(l.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}</td>
                      <td className="py-2">
                        <select value={l.status} onChange={(e) => setStatus(l.lead_id, e.target.value)}
                                data-testid={`hs-lead-status-${l.lead_id}`}
                                className="h-7 rounded bg-slate-950 border border-white/10 text-[11px] font-mono px-1 text-slate-200">
                          {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
