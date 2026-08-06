import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { ShoppingCart, ExternalLink, FileDown, Send, Loader2 } from "lucide-react";

const STORE_STYLE = {
  Amazon: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  "Harbor Freight": "bg-red-500/15 text-red-300 border-red-500/30",
};

export const TcGear = () => {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { api.get("/truck-cleaning/gear").then(({ data: d }) => setData(d)).catch(() => {}); }, []);

  const downloadPdf = async () => {
    setBusy("pdf");
    try {
      const r = await api.get("/truck-cleaning/gear.pdf", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data);
      a.download = "Orisei-Crew-Gear-Kit.pdf";
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success("Gear kit PDF downloaded");
    } catch { toast.error("Download failed"); }
    finally { setBusy(""); }
  };
  const sendPdf = async () => {
    if (!email.includes("@")) { toast.error("Enter a valid email"); return; }
    setBusy("send");
    try {
      const { data: r } = await api.post("/truck-cleaning/gear/send", { email, note });
      toast.success(r.sent ? `Kit PDF emailed to ${r.to}` : `Queued for ${r.to} — connects & sends once Resend is configured`);
      setEmail(""); setNote("");
    } catch (e) { toast.error(e?.response?.data?.detail || "Send failed"); }
    finally { setBusy(""); }
  };

  if (!data) return <div className="text-slate-500 font-mono text-sm">Loading gear list…</div>;
  return (
    <div className="space-y-4" data-testid="tc-gear">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2"><ShoppingCart size={15} className="text-amber-400" /> Crew Gear & Supplies — sourced from Amazon + Harbor Freight</h3>
          <div className="text-[11px] text-slate-500">{data.note}</div>
        </div>
        <div className="px-4 py-2 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 text-right">
          <div className="text-lg font-black text-emerald-300">${data.kit_total_est.toLocaleString()}</div>
          <div className="text-[9px] font-mono uppercase text-slate-500">full kit est. / crew</div>
        </div>
      </div>
      <Card className="p-4 bg-slate-950/70 border-cyan-500/20" data-testid="tc-gear-share">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-2">Share the kit with business partners</div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={downloadPdf} disabled={!!busy} data-testid="tc-gear-pdf-btn"
            className="px-4 py-2 rounded-full border border-amber-500/50 text-amber-300 text-xs font-bold inline-flex items-center gap-1.5 hover:bg-amber-500/10 disabled:opacity-50">
            {busy === "pdf" ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />} Download Kit PDF
          </button>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="partner@email.com"
            className="h-9 px-3 rounded-full bg-[#11151F] border border-white/10 text-xs text-white w-56 outline-none focus:border-cyan-400" data-testid="tc-gear-email-input" />
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional) — e.g. buy 3 kits for the new crews"
            className="h-9 px-3 rounded-full bg-[#11151F] border border-white/10 text-xs text-white flex-1 min-w-[200px] outline-none focus:border-cyan-400" data-testid="tc-gear-note-input" />
          <button onClick={sendPdf} disabled={!!busy} data-testid="tc-gear-send-btn"
            className="px-4 py-2 rounded-full bg-cyan-500 text-black text-xs font-black inline-flex items-center gap-1.5 disabled:opacity-50">
            {busy === "send" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} EMAIL KIT PDF
          </button>
        </div>
        <div className="text-[10px] text-slate-500 mt-2">Branded PDF with every item, price and a clickable store link — partners can purchase straight from the list.</div>
      </Card>
      {data.gear.map((g) => (
        <Card key={g.cat} className="p-4 bg-slate-950/70 border-white/10" data-testid={`tc-gear-cat-${g.cat.replace(/[^a-z]/gi, "-").toLowerCase()}`}>
          <h4 className="text-xs font-mono uppercase tracking-widest text-cyan-300 mb-3">{g.cat}</h4>
          <div className="grid sm:grid-cols-2 gap-2">
            {g.items.map((i) => (
              <a key={i.name} href={i.url} target="_blank" rel="noreferrer" data-testid={`tc-gear-item-${i.name.slice(0, 18).replace(/[^a-z0-9]/gi, "-").toLowerCase()}`}
                className="p-3 rounded-xl border border-white/10 bg-white/[0.02] hover:border-amber-500/40 transition-colors group">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-xs text-white font-semibold group-hover:text-amber-300">{i.name}</div>
                  <ExternalLink size={11} className="text-slate-600 shrink-0 mt-0.5" />
                </div>
                <div className="text-[10px] text-slate-500 mt-1">{i.why}</div>
                <div className="flex items-center gap-2 mt-2">
                  <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono ${STORE_STYLE[i.store]}`}>{i.store}</span>
                  <span className="text-xs font-black text-emerald-300">~${i.est}</span>
                </div>
              </a>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
};
