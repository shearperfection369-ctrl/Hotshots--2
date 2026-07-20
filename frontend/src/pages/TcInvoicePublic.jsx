import React, { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Check, CreditCard, FileDown, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TcInvoicePublic() {
  const { invoiceId } = useParams();
  const [params] = useSearchParams();
  const sessionId = params.get("session_id") || "";
  const [inv, setInv] = useState(null);
  const [state, setState] = useState("loading"); // loading | ready | invalid
  const [paying, setPaying] = useState(false);
  const [polls, setPolls] = useState(0);

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/truck-cleaning/pay/${invoiceId}`); setInv(data); setState("ready"); }
    catch (_) { setState("invalid"); }
  }, [invoiceId]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!sessionId || !inv || inv.status === "paid" || polls > 6) return;
    const t = setTimeout(async () => {
      try {
        const { data } = await axios.get(`${API}/truck-cleaning/pay/${invoiceId}/status`, { params: { session_id: sessionId } });
        if (data.status === "paid") load();
        else setPolls((p) => p + 1);
      } catch (_) { setPolls((p) => p + 1); }
    }, polls === 0 ? 400 : 2500);
    return () => clearTimeout(t);
  }, [sessionId, inv, polls, invoiceId, load]);

  const pay = async () => {
    setPaying(true);
    try {
      const { data } = await axios.post(`${API}/truck-cleaning/pay/${invoiceId}/checkout`, { origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (_) { setPaying(false); }
  };

  const paid = inv?.status === "paid";
  return (
    <div className="min-h-screen bg-[#0D1117] text-white relative">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -100, right: "8%", width: 460, height: 460, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(245,158,11,0.28), transparent 65%)" }} />
        <div style={{ position: "absolute", bottom: -140, left: -80, width: 500, height: 500, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(34,211,238,0.22), transparent 65%)" }} />
      </div>
      <div className="relative max-w-lg mx-auto px-5 py-12">
        <div className="flex items-center gap-3 mb-8">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning" data-testid="tci-logo" className="h-16 w-auto drop-shadow-[0_0_18px_rgba(59,130,246,0.55)]" />
          <div>
            <div className="font-black text-lg leading-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[11px] text-slate-500 font-mono">Secure invoice payment</div>
          </div>
        </div>

        {state === "loading" && <div className="text-slate-500 font-mono text-sm flex gap-2 items-center"><Loader2 size={14} className="animate-spin" /> Loading invoice…</div>}
        {state === "invalid" && <div className="p-6 rounded-2xl border border-red-500/30 bg-red-500/5 text-sm" data-testid="tci-invalid">Invoice not found. Contact oliver@oriseifreight.com.</div>}

        {inv && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/85 backdrop-blur overflow-hidden" data-testid="tci-invoice-card">
            <div className="p-5 border-b border-white/10 flex justify-between items-start">
              <div>
                <div className="font-black text-xl">{inv.invoice_id}</div>
                <div className="text-xs text-slate-400 mt-0.5">Billed to <b className="text-slate-200">{inv.company}</b></div>
                <div className="text-[11px] text-slate-500 font-mono mt-0.5">Due {String(inv.due_date || "").slice(0, 10)}</div>
              </div>
              <span className={`px-3 py-1 rounded-full border text-[10px] font-mono uppercase font-bold ${paid ? "border-emerald-500/60 text-emerald-400" : "border-amber-500/60 text-amber-300"}`} data-testid="tci-status">
                {inv.status}
              </span>
            </div>
            <div className="p-5 space-y-2.5">
              {(inv.line_items || []).map((it, i) => (
                <div key={i} className="flex justify-between text-[13px]">
                  <span className="text-slate-300">{it.desc}</span>
                  <span className="tabular-nums text-slate-200">${Number(it.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              ))}
              <div className="border-t border-white/10 pt-3 flex justify-between items-center">
                <span className="text-xs font-mono text-slate-500 uppercase">Total due</span>
                <span className="text-2xl font-black text-amber-300 tabular-nums" data-testid="tci-total">${Number(inv.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
              </div>
            </div>
            <div className="p-5 pt-0 space-y-3">
              {paid ? (
                <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-center" data-testid="tci-paid-banner">
                  <Check className="mx-auto text-emerald-400 mb-1" size={22} />
                  <div className="font-black text-emerald-300">PAID — thank you!</div>
                  <div className="text-[11px] text-slate-400 mt-0.5">A receipt was issued by our payment processor.</div>
                </div>
              ) : sessionId && polls <= 6 ? (
                <div className="p-4 rounded-xl border border-cyan-500/40 bg-cyan-500/5 text-center text-sm text-cyan-200 flex items-center justify-center gap-2" data-testid="tci-confirming">
                  <Loader2 size={15} className="animate-spin" /> Confirming your payment…
                </div>
              ) : (
                <button onClick={pay} disabled={paying} data-testid="tci-pay-btn"
                        className="w-full h-12 rounded-full bg-amber-500 text-black font-black text-sm inline-flex items-center justify-center gap-2 hover:bg-amber-400 disabled:opacity-60">
                  {paying ? <Loader2 size={16} className="animate-spin" /> : <CreditCard size={16} />} PAY ${Number(inv.total).toLocaleString()} — CARD / ACH
                </button>
              )}
              <a href={`${API}/truck-cleaning/pay/${invoiceId}/pdf`} target="_blank" rel="noreferrer" data-testid="tci-pdf-link"
                 className="w-full h-10 rounded-full border border-white/15 text-slate-300 text-xs font-bold inline-flex items-center justify-center gap-1.5 hover:border-amber-400/50">
                <FileDown size={13} /> Download branded PDF
              </a>
            </div>
          </div>
        )}
        <div className="text-center text-[10px] text-slate-600 font-mono mt-8">Payments secured by Stripe · Orisei Truck Cleaning Solutions · Minneapolis–St. Paul, MN</div>
      </div>
    </div>
  );
}
