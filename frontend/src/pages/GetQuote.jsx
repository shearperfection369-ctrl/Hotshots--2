import React, { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Zap, Loader2, ShieldCheck, MapPin, Truck, Clock } from "lucide-react";

const inputCls = "h-11 rounded bg-slate-900/80 border border-white/15 font-mono text-sm px-3 text-slate-100 placeholder:text-slate-500 w-full focus:border-cyan-400 outline-none";

export default function GetQuote() {
  const [form, setForm] = useState({
    company: "", contact: "", email: "", phone: "",
    origin: "", destination: "", equipment: "Van", commodity: "", pickup_date: "",
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const { data } = await api.post("/public/revenue/quote", form);
      setResult(data);
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not price this lane — check City, ST format");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-[#070d17] text-slate-100" data-testid="get-quote-page">
      <div className="border-b border-white/10 bg-[#0E3A6B]/30">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="font-display text-xl font-black tracking-wide">
            <span className="text-[#C9A24A]">◆</span> ORISEI <span className="text-slate-400 font-normal">Freight Solutions</span>
          </div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 flex items-center gap-1.5">
            <Zap size={12} /> Instant Spot Quote
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-12">
        {!result ? (
          <>
            <h1 className="font-display text-4xl sm:text-5xl font-black leading-tight">
              A real truckload rate.<br /><span className="text-cyan-300">In seconds. Not hours.</span>
            </h1>
            <p className="text-slate-400 mt-3 max-w-xl text-sm">
              Live market pricing — lane balance, seasonality, and today's DOE fuel surcharge baked in.
              Your rate locks for 72 hours. No account required.
            </p>
            <form onSubmit={submit} className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="public-quote-form">
              <input required className={inputCls} placeholder="Origin — City, ST *" value={form.origin} onChange={set("origin")} data-testid="pq-origin" />
              <input required className={inputCls} placeholder="Destination — City, ST *" value={form.destination} onChange={set("destination")} data-testid="pq-destination" />
              <select className={inputCls} value={form.equipment} onChange={set("equipment")} data-testid="pq-equipment">
                <option>Van</option><option>Reefer</option><option>Flatbed</option>
              </select>
              <input className={inputCls} placeholder="Commodity (optional)" value={form.commodity} onChange={set("commodity")} />
              <input required className={inputCls} placeholder="Company *" value={form.company} onChange={set("company")} data-testid="pq-company" />
              <input required className={inputCls} placeholder="Your name *" value={form.contact} onChange={set("contact")} data-testid="pq-contact" />
              <input required type="email" className={inputCls} placeholder="Work email *" value={form.email} onChange={set("email")} data-testid="pq-email" />
              <input className={inputCls} placeholder="Pickup date (optional)" value={form.pickup_date} onChange={set("pickup_date")} />
              <div className="md:col-span-2">
                <Button type="submit" disabled={busy} data-testid="pq-submit-btn"
                  className="bg-cyan-400 hover:bg-cyan-300 text-black font-black font-mono uppercase tracking-widest px-10 py-6 text-sm">
                  {busy ? <Loader2 size={16} className="mr-2 animate-spin" /> : <Zap size={16} className="mr-2" />}
                  Get My Instant Rate
                </Button>
                {error && <div className="text-red-400 font-mono text-xs mt-3" data-testid="pq-error">{error}</div>}
              </div>
            </form>
            <div className="flex flex-wrap gap-6 mt-10 text-[11px] font-mono text-slate-500">
              <span className="flex items-center gap-1.5"><ShieldCheck size={13} className="text-emerald-400" /> Vetted, insured carriers</span>
              <span className="flex items-center gap-1.5"><MapPin size={13} className="text-cyan-400" /> Live GPS tracking on every load</span>
              <span className="flex items-center gap-1.5"><Truck size={13} className="text-yellow-400" /> Truck assigned within the hour</span>
            </div>
          </>
        ) : (
          <div className="max-w-xl mx-auto text-center" data-testid="pq-result">
            <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-emerald-400 mb-2">Rate Locked · {result.quote_id}</div>
            <div className="font-display text-2xl font-bold text-slate-300">{result.origin} → {result.destination}</div>
            <div className="text-[11px] font-mono text-slate-500 mt-1">{result.equipment} · {result.miles.toLocaleString()} practical miles</div>
            <div className="mt-6 rounded-xl border border-cyan-500/30 bg-cyan-500/[0.05] p-8">
              <div className="font-mono font-black text-5xl text-cyan-300" data-testid="pq-rate">
                ${Number(result.all_in_rate_usd).toLocaleString()}
              </div>
              <div className="text-[11px] font-mono text-slate-400 mt-2">
                all-in · ${result.rpm}/mi · fuel surcharge (${Number(result.fsc_included_usd).toLocaleString()}) included
              </div>
            </div>
            <div className="flex items-center justify-center gap-1.5 text-[11px] font-mono text-yellow-300 mt-4">
              <Clock size={12} /> Valid until {new Date(result.valid_until).toLocaleString()}
            </div>
            <p className="text-slate-400 text-sm mt-4">{result.message}</p>
            <Button onClick={() => { setResult(null); setForm({ ...form, origin: "", destination: "", commodity: "" }); }}
              data-testid="pq-another-btn"
              className="mt-6 bg-white/5 border border-white/15 text-slate-200 font-mono text-[11px] uppercase">
              Quote Another Lane
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
