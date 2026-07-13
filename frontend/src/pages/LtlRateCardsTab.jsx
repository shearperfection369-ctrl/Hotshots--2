import React, { useEffect, useState } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { FileSpreadsheet, Loader2, Calculator, Trophy, Percent } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 }));
const ACC_OPTIONS = [
  ["liftgate_delivery", "Liftgate Del."], ["liftgate_pickup", "Liftgate PU"],
  ["residential", "Residential"], ["inside_delivery", "Inside Del."],
  ["limited_access", "Ltd Access"], ["appointment", "Appt"],
  ["hazmat", "Hazmat"], ["protect_from_freeze", "PFZ"],
];

export default function LtlRateCardsTab() {
  const [cards, setCards] = useState([]);
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState({ origin_state: "MN", dest_state: "IL", weight_lbs: 2400, freight_class: "70", target_margin_pct: 22 });
  const [accs, setAccs] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadCards = () => api.get("/ltl/cards").then(({ data }) => {
    setCards(data.items || []); setClasses(data.classes || []);
  }).catch(() => {});
  useEffect(() => { loadCards(); }, []);

  const runQuote = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/ltl/quote", {
        ...form, weight_lbs: Number(form.weight_lbs),
        target_margin_pct: Number(form.target_margin_pct), accessorials: accs,
      });
      setResult(data);
      toast.success(`Rated ${data.carrier_count} carriers · zone ${data.zone} · ~${fmt(data.linehaul_miles_est)} mi`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Quote failed"); }
    finally { setBusy(false); }
  };

  const saveCard = async (c, patch) => {
    try {
      await api.post("/ltl/cards", { ...c, ...patch });
      toast.success(`${c.carrier_name} card updated`);
      loadCards();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="space-y-4" data-testid="ltl-rates-tab">
      {/* Instant rating tool */}
      <Card className="hud-surface p-5">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5">
          <Calculator size={11} /> Negotiated Rate Engine
        </div>
        <h3 className="font-display text-xl font-black flex items-center gap-2 mb-4">
          <FileSpreadsheet size={18} className="text-cyan-400" /> LTL Instant Rating
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          {[["origin_state", "Origin ST", "w-20"], ["dest_state", "Dest ST", "w-20"],
            ["weight_lbs", "Weight lbs", "w-28"], ["target_margin_pct", "Target %", "w-24"]].map(([k, label, w]) => (
            <div key={k}>
              <div className="text-[9px] font-mono uppercase text-slate-500 mb-1">{label}</div>
              <Input value={form[k]} onChange={set(k)} data-testid={`ltl-${k}`}
                className={`${w} h-8 bg-slate-950 border-white/10 font-mono text-xs uppercase`} />
            </div>
          ))}
          <div>
            <div className="text-[9px] font-mono uppercase text-slate-500 mb-1">Class</div>
            <select value={form.freight_class} onChange={set("freight_class")} data-testid="ltl-class"
              className="h-8 rounded bg-slate-950 border border-white/10 font-mono text-xs px-2 text-slate-200">
              {classes.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <Button onClick={runQuote} disabled={busy} data-testid="ltl-quote-btn"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase tracking-wider h-8">
            {busy ? <Loader2 size={13} className="mr-1.5 animate-spin" /> : <Calculator size={13} className="mr-1.5" />}
            Rate All Carriers
          </Button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {ACC_OPTIONS.map(([code, label]) => (
            <button key={code} data-testid={`ltl-acc-${code}`}
              onClick={() => setAccs((a) => a.includes(code) ? a.filter((x) => x !== code) : [...a, code])}
              className={`px-2 py-1 rounded font-mono text-[9px] uppercase tracking-wider border ${
                accs.includes(code) ? "bg-yellow-500/15 border-yellow-400/50 text-yellow-200"
                                    : "border-white/10 text-slate-500 hover:border-yellow-500/30"}`}>
              {label}
            </button>
          ))}
        </div>
      </Card>

      {/* Ranked results */}
      {result && (
        <Card className="hud-surface p-4" data-testid="ltl-results">
          <div className="text-[10px] font-mono text-slate-500 mb-3">
            {result.lane} · zone {result.zone} · ~{fmt(result.linehaul_miles_est)} mi · {fmt(result.weight_lbs)} lbs · class {result.freight_class} · target margin {result.target_margin_pct}%
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">
                <tr className="border-b border-white/5 text-right">
                  <th className="text-left py-2 px-2">Carrier</th>
                  <th className="px-2">Gross</th><th className="px-2">Disc %</th>
                  <th className="px-2">Linehaul</th><th className="px-2">FSC</th>
                  <th className="px-2">Access.</th><th className="px-2">Net Cost</th>
                  <th className="px-2">Sell</th><th className="px-2">Margin</th>
                </tr>
              </thead>
              <tbody>
                {result.quotes.map((q) => (
                  <tr key={q.scac} className={`border-b border-white/5 text-right font-mono ${q.cheapest ? "bg-emerald-500/[0.06]" : ""}`}
                      data-testid={`ltl-quote-row-${q.scac}`}>
                    <td className="text-left py-2 px-2 font-sans">
                      <span className="text-slate-200 flex items-center gap-1.5">
                        {q.cheapest && <Trophy size={11} className="text-emerald-400" />} {q.carrier_name}
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">{q.scac} · {q.weight_break}{q.min_charge_applied ? " · MIN applied" : ""}</span>
                    </td>
                    <td className="px-2 text-slate-500">${fmt(q.gross_usd)}</td>
                    <td className="px-2 text-cyan-300">{q.discount_pct}%</td>
                    <td className="px-2 text-slate-300">${fmt(q.net_linehaul_usd)}</td>
                    <td className="px-2 text-slate-400">${fmt(q.fsc_usd)}</td>
                    <td className="px-2 text-slate-400">${fmt(q.accessorials_usd)}</td>
                    <td className={`px-2 font-bold ${q.cheapest ? "text-emerald-300" : "text-slate-200"}`}>${fmt(q.net_total_usd)}</td>
                    <td className="px-2 text-yellow-300">${fmt(q.suggested_sell_usd)}</td>
                    <td className="px-2 text-emerald-300">${fmt(q.margin_usd)} <span className="text-slate-500">({q.margin_pct}%)</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Card management */}
      <Card className="hud-surface p-4" data-testid="ltl-cards-panel">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5 mb-3">
          <Percent size={11} /> Negotiated Rate Cards · edit discount / FSC / min inline
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-[9px] font-mono text-slate-500 uppercase tracking-wider">
              <tr className="border-b border-white/5">
                <th className="text-left py-2 px-2">Carrier</th><th className="text-left px-2">SCAC</th>
                <th className="px-2">Discount %</th><th className="px-2">FSC %</th>
                <th className="px-2">Min $</th><th className="text-left px-2">Coverage note</th>
              </tr>
            </thead>
            <tbody>
              {cards.map((c) => (
                <tr key={c.card_id} className="border-b border-white/5" data-testid={`ltl-card-${c.scac}`}>
                  <td className="py-2 px-2 text-slate-200">{c.carrier_name}</td>
                  <td className="px-2 font-mono text-cyan-300">{c.scac}</td>
                  {["discount_pct", "fsc_pct", "min_charge_usd"].map((k) => (
                    <td key={k} className="px-2 text-center">
                      <Input type="number" defaultValue={c[k]} key={`${c.card_id}-${k}-${c[k]}`}
                        onBlur={(e) => Number(e.target.value) !== c[k] && saveCard(c, { [k]: Number(e.target.value) })}
                        className="w-20 h-7 mx-auto bg-slate-950 border-white/10 font-mono text-xs text-center" />
                    </td>
                  ))}
                  <td className="px-2 text-[10px] text-slate-500">{c.transit_note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
