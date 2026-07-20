import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { Bot, Send, Trash2, Loader2, Eye, Sparkles, Mail } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const TYPE_LABEL = { win_back: "WIN-BACK", sub_upgrade: "SUB UPGRADE", upsell_bundle: "UPSELL BUNDLE", referral: "REFERRAL", fleet_rate: "FLEET RATE", custom: "CUSTOM" };
const STATUS_CLS = { draft: "border-slate-500/50 text-slate-400", sent: "border-emerald-500/50 text-emerald-400", failed: "border-red-500/50 text-red-400", skipped: "border-amber-500/50 text-amber-300" };

export const TcOffers = () => {
  const [offers, setOffers] = useState([]);
  const [resendOk, setResendOk] = useState(false);
  const [scrubbing, setScrubbing] = useState(false);
  const [sending, setSending] = useState("");
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try { const { data } = await api.get("/truck-cleaning/offers"); setOffers(data.offers); setResendOk(data.resend_configured); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const scrub = async () => {
    setScrubbing(true);
    try {
      const { data } = await api.post("/truck-cleaning/offers/scrub", {}, { timeout: 120000 });
      toast.success(`AI scrubbed the registry — ${data.created} targeted offers drafted`);
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setScrubbing(false); }
  };

  const send = async (id) => {
    setSending(id);
    try {
      const { data } = await api.post(`/truck-cleaning/offers/${id}/send`);
      data.status === "sent" ? toast.success("Offer emailed") : toast.info(`Offer ${data.status}`);
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setSending(""); }
  };

  const sendAll = async () => {
    setSending("all");
    try { const { data } = await api.post("/truck-cleaning/offers/send-all"); toast.success(`${data.sent} offers emailed`); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
    finally { setSending(""); }
  };

  const del = async (id) => {
    try { await api.delete(`/truck-cleaning/offers/${id}`); load(); } catch (e2) { toast.error(errTxt(e2)); }
  };

  const drafts = offers.filter((o) => o.status === "draft").length;

  return (
    <div className="space-y-4" data-testid="tc-offers">
      <Card className="p-5 bg-slate-950/70 border-cyan-500/30 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-black text-white flex items-center gap-2"><Bot size={16} className="text-cyan-300" /> AI Offer Engine</div>
            <p className="text-[12px] text-slate-400 mt-1 max-w-lg">Scrubs the client registry — inactivity, plan, upsell gaps, fleet size — and drafts one targeted offer per client (win-backs, subscription upgrades, upsell bundles, referral asks, fleet-rate pitches).</p>
            {!resendOk && <p className="text-[11px] text-amber-300/90 mt-1.5 font-mono">Sending needs your Resend key in Connections · Keys — drafting works now.</p>}
          </div>
          <div className="flex gap-2">
            <button onClick={scrub} disabled={scrubbing} data-testid="tc-offers-scrub-btn"
                    className="px-5 py-2.5 rounded-full bg-cyan-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
              {scrubbing ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />} {scrubbing ? "Scrubbing registry…" : "AI Scrub Client List"}
            </button>
            {drafts > 0 && (
              <button onClick={sendAll} disabled={sending === "all"} data-testid="tc-offers-send-all"
                      className="px-5 py-2.5 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
                {sending === "all" ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Send All ({drafts})
              </button>
            )}
          </div>
        </div>
      </Card>

      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Client</th><th className="p-3">Angle</th><th className="p-3">Subject</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead>
          <tbody>
            {offers.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-slate-600 text-xs font-mono">No offers yet — hit "AI Scrub Client List" once your registry is populated.</td></tr>}
            {offers.map((o) => (
              <tr key={o.offer_id} className="border-b border-white/5" data-testid={`tc-offer-row-${o.offer_id}`}>
                <td className="p-3"><div className="font-semibold text-white text-xs">{o.company}</div><div className="text-[10px] text-slate-500">{o.email || "no email on file"}</div></td>
                <td className="p-3"><span className="px-2 py-0.5 rounded-full border border-cyan-500/40 text-cyan-300 text-[9px] font-mono">{TYPE_LABEL[o.offer_type] || o.offer_type}</span></td>
                <td className="p-3 text-xs text-slate-300 max-w-[280px] truncate">{o.subject}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono uppercase ${STATUS_CLS[o.status] || ""}`}>{o.status}</span></td>
                <td className="p-3">
                  <div className="flex gap-2 items-center">
                    <button onClick={() => setPreview(o)} title="Preview" data-testid={`tc-offer-preview-${o.offer_id}`} className="text-slate-400 hover:text-white"><Eye size={14} /></button>
                    {o.status === "draft" && (
                      <button onClick={() => send(o.offer_id)} disabled={sending === o.offer_id} title="Send now"
                              data-testid={`tc-offer-send-${o.offer_id}`} className="text-amber-400 hover:text-amber-300 disabled:opacity-50">
                        {sending === o.offer_id ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                      </button>
                    )}
                    <button onClick={() => del(o.offer_id)} data-testid={`tc-offer-delete-${o.offer_id}`} className="text-slate-600 hover:text-red-400"><Trash2 size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {preview && (
        <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={() => setPreview(null)}>
          <Card className="w-full max-w-lg p-5 bg-slate-950 border-cyan-500/30 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="tc-offer-preview-dialog">
            <div className="text-[10px] font-mono text-cyan-300 mb-1">{TYPE_LABEL[preview.offer_type] || preview.offer_type} → {preview.company}</div>
            <div className="font-black text-white mb-3">{preview.subject}</div>
            <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] text-[13px] text-slate-300 whitespace-pre-wrap leading-relaxed">{preview.body}</div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setPreview(null)} className="px-4 py-2 rounded-full border border-white/15 text-slate-300 text-xs font-bold">Close</button>
              {preview.status === "draft" && (
                <button onClick={() => { send(preview.offer_id); setPreview(null); }} data-testid="tc-offer-preview-send"
                        className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Mail size={12} /> Send</button>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};
