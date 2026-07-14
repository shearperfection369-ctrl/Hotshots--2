import React, { useCallback, useEffect, useState } from "react";
import { api, BACKEND_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Truck, Loader2, CheckCircle2, Zap, FileDown } from "lucide-react";

const inputCls = "h-10 rounded bg-slate-900/80 border border-white/15 font-mono text-xs px-3 text-slate-100 placeholder:text-slate-500 w-full focus:border-emerald-400 outline-none";

function BookForm({ load, onDone }) {
  const [f, setF] = useState({ mc_number: "", company: "", contact: "", email: "", phone: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const book = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const { data } = await api.post(`/public/revenue/loadboard/${load.mkt_id}/book`, f);
      onDone(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Booking failed");
    } finally { setBusy(false); }
  };
  return (
    <form onSubmit={book} className="mt-3 grid grid-cols-2 gap-2 border-t border-white/10 pt-3" data-testid={`book-form-${load.mkt_id}`}>
      <input required className={inputCls} placeholder="MC number *" value={f.mc_number} onChange={set("mc_number")} data-testid="book-mc-input" />
      <input required className={inputCls} placeholder="Carrier company *" value={f.company} onChange={set("company")} data-testid="book-company-input" />
      <input required className={inputCls} placeholder="Dispatcher name *" value={f.contact} onChange={set("contact")} data-testid="book-contact-input" />
      <input required type="email" className={inputCls} placeholder="Email *" value={f.email} onChange={set("email")} data-testid="book-email-input" />
      <input className={inputCls} placeholder="Phone" value={f.phone} onChange={set("phone")} />
      <Button type="submit" disabled={busy} data-testid="book-confirm-btn"
        className="bg-emerald-400 hover:bg-emerald-300 text-black font-black font-mono text-[10px] uppercase h-10">
        {busy ? <Loader2 size={13} className="animate-spin" /> : "Confirm Booking"}
      </Button>
      {error && <div className="col-span-2 text-red-400 font-mono text-[10px]">{error}</div>}
    </form>
  );
}

export default function CarrierLoadboard() {
  const [loads, setLoads] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [booked, setBooked] = useState(null);

  const refresh = useCallback(async () => {
    try { const { data } = await api.get("/public/revenue/loadboard"); setLoads(data.items); } catch { setLoads([]); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="min-h-screen bg-[#070d17] text-slate-100" data-testid="carrier-loadboard-page">
      <div className="border-b border-white/10 bg-[#0E3A6B]/30">
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="font-display text-xl font-black tracking-wide">
            <span className="text-[#C9A24A]">◆</span> ORISEI <span className="text-slate-400 font-normal">Carrier Board</span>
          </div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-300 flex items-center gap-1.5">
            <Zap size={12} /> Book It Now · No calls, no negotiating
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-10">
        {booked ? (
          <div className="max-w-xl mx-auto text-center" data-testid="book-success">
            <CheckCircle2 size={48} className="mx-auto text-emerald-400 mb-3" />
            <h2 className="font-display text-3xl font-black">Load Booked</h2>
            <div className="font-mono text-sm text-slate-400 mt-2">Confirmation code: <span className="text-emerald-300 font-bold" data-testid="book-confirm-code">{booked.confirm_code}</span></div>
            <p className="text-slate-400 text-sm mt-3">{booked.message}</p>
            <a href={`${BACKEND_URL}${booked.ratecon_url}`} target="_blank" rel="noreferrer" data-testid="book-ratecon-link"
              className="inline-flex items-center gap-2 mt-6 rounded bg-emerald-400 text-black font-black font-mono text-xs uppercase px-6 py-3 hover:bg-emerald-300">
              <FileDown size={14} /> Download Rate Confirmation
            </a>
            <div>
              <button onClick={() => { setBooked(null); setOpenId(null); refresh(); }}
                className="mt-4 text-[11px] font-mono text-slate-400 hover:text-slate-200 underline">Back to the board</button>
            </div>
          </div>
        ) : (
          <>
            <h1 className="font-display text-3xl sm:text-4xl font-black">
              Open loads. <span className="text-emerald-300">Fixed prices. Instant rate cons.</span>
            </h1>
            <p className="text-slate-400 mt-2 text-sm max-w-xl">
              See a load you want? Book it at the posted rate — your rate confirmation generates instantly.
              Net 30 on clean POD, or QuickPay same-day.
            </p>
            <div className="mt-8 space-y-3" data-testid="loadboard-list">
              {loads === null && <div className="text-slate-500 font-mono text-xs flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading board…</div>}
              {loads?.length === 0 && (
                <div className="rounded border border-white/10 bg-white/[0.02] p-8 text-center font-mono text-xs text-slate-500">
                  No open loads right now — check back soon. New freight posts throughout the day.
                </div>
              )}
              {(loads || []).map((l) => (
                <div key={l.mkt_id} className="rounded-lg border border-white/10 bg-white/[0.03] p-4" data-testid={`board-load-${l.mkt_id}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="font-mono font-bold text-sm text-slate-100 flex items-center gap-2">
                        <Truck size={14} className="text-emerald-400" /> {l.origin} → {l.destination}
                      </div>
                      <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                        {l.mkt_id} · {l.equipment} 53' · {l.miles.toLocaleString()} mi · {l.commodity}
                        {l.weight_lbs ? ` · ${l.weight_lbs.toLocaleString()} lbs` : ""}
                        {l.pickup_date ? ` · PU ${l.pickup_date}` : ""}
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className="font-mono font-black text-xl text-emerald-300">${l.book_now_usd.toLocaleString()}</div>
                        <div className="text-[9px] font-mono text-slate-500 uppercase">${l.rpm}/mi all-in</div>
                      </div>
                      <Button onClick={() => setOpenId(openId === l.mkt_id ? null : l.mkt_id)} data-testid={`board-book-${l.mkt_id}`}
                        className="bg-emerald-400 hover:bg-emerald-300 text-black font-black font-mono text-[10px] uppercase">
                        Book It Now
                      </Button>
                    </div>
                  </div>
                  {openId === l.mkt_id && <BookForm load={l} onDone={setBooked} />}
                </div>
              ))}
            </div>
            <div className="mt-8 text-[10px] font-mono text-slate-600">
              Requirements: active authority · $1M auto liability + $100K cargo · GPS tracking · POD within 24 hrs.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
