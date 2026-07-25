import React, { useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Slider } from "./ui/slider";

const usd = (n) => `$${Math.round(n).toLocaleString()}`;

const PRESETS = {
  industry: { label: "Industry Avg '25", loads: 20, rate: 1900, margin: 15, dso: 35, dpo: 20 },
  plan: { label: "Plan Rev-2", loads: 20, rate: 2000, margin: 14.5, dso: 37, dpo: 19 },
  sandbox: { label: "Sandbox Actual", loads: 18, rate: 3150, margin: 13.5, dso: 37, dpo: 19 },
};

export const CashFlowSimulator = () => {
  const [loadsPerDay, setLoadsPerDay] = useState(20);
  const [avgRate, setAvgRate] = useState(2000);
  const [marginPct, setMarginPct] = useState(14.5);
  const [dso, setDso] = useState(37);
  const [dpo, setDpo] = useState(19);
  const [financing, setFinancing] = useState("factoring");
  const [preset, setPreset] = useState("plan");

  const applyPreset = (k) => {
    const p = PRESETS[k];
    setLoadsPerDay(p.loads); setAvgRate(p.rate); setMarginPct(p.margin);
    setDso(p.dso); setDpo(p.dpo); setPreset(k);
  };

  const loadsWk = loadsPerDay * 5;
  const revWk = loadsWk * avgRate;
  const annualRev = revWk * 52;
  const gmWk = revWk * (marginPct / 100);
  const provisionsWk = revWk * 0.035;
  const finRate = financing === "factoring" ? 0.0325 : 0.012;
  const financingWk = revWk * finRate;
  const overheadWk = 1060 + loadsPerDay * 88;
  const netWk = gmWk - provisionsWk - financingWk - overheadWk;
  const ar = (dso / 365) * annualRev;
  const wcSelf = (Math.max(0, dso - dpo) / 365) * annualRev;
  const wcFactored = ar * 0.08 + revWk * 0.855 * 0.2;

  const sliders = [
    ["Loads / day", loadsPerDay, setLoadsPerDay, 1, 40, 1, `${loadsPerDay}`, "cfs-loads", "IND 3–5/rep · 10+ top"],
    ["Avg rate / load", avgRate, setAvgRate, 800, 4000, 50, usd(avgRate), "cfs-rate", "IND avg $1,912 · $1.5–2.5K"],
    ["Gross margin %", marginPct, setMarginPct, 8, 25, 0.5, `${marginPct}%`, "cfs-margin", "IND 12–18% · avg ~15%"],
    ["DSO (shipper pays in)", dso, setDso, 15, 60, 1, `${dso} days`, "cfs-dso", "IND 30–45d · net-60 lg shippers"],
    ["Blended DPO (carriers paid in)", dpo, setDpo, 5, 30, 1, `${dpo} days`, "cfs-dpo", "quickpay 2d ↔ net-30"],
  ];

  return (
    <div className="mb-4 p-3 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.03]" data-testid="cashflow-simulator">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-1.5">
        <div className="text-[10px] font-mono uppercase text-emerald-300 flex items-center gap-1.5">
          <SlidersHorizontal size={11} /> Cash Flow Simulator — dial it in
        </div>
        <div className="flex gap-1" data-testid="cfs-presets">
          {Object.entries(PRESETS).map(([k, p]) => (
            <button key={k} onClick={() => applyPreset(k)} data-testid={`cfs-preset-${k}`}
                    className={`px-2 h-6 rounded-full border text-[9px] font-bold font-mono uppercase ${preset === k ? "border-emerald-400 text-emerald-300 bg-emerald-500/10" : "border-white/15 text-slate-500 hover:text-slate-300"}`}>
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <div className="grid md:grid-cols-2 gap-x-6 gap-y-3 mb-3">
        {sliders.map(([label, val, set, min, max, step, disp, tid, bench]) => (
          <div key={tid}>
            <div className="flex justify-between text-[10px] font-mono mb-1">
              <span className="text-slate-500 uppercase">{label}</span>
              <span className="text-white font-bold">{disp}</span>
            </div>
            <Slider value={[val]} onValueChange={(v) => { set(v[0]); setPreset(""); }} min={min} max={max} step={step} data-testid={tid} />
            <div className="text-[8px] font-mono text-slate-600 mt-0.5">{bench}</div>
          </div>
        ))}
        <div>
          <div className="text-[10px] font-mono text-slate-500 uppercase mb-1">Financing</div>
          <div className="flex gap-1.5">
            {[["factoring", "Factoring 3.25%"], ["bank", "Bank AR line 1.2%"]].map(([k, l]) => (
              <button key={k} onClick={() => setFinancing(k)} data-testid={`cfs-fin-${k}`}
                      className={`px-3 h-7 rounded-full border text-[10px] font-bold ${financing === k ? "border-emerald-400 text-emerald-300 bg-emerald-500/10" : "border-white/15 text-slate-500"}`}>{l}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="cfs-outputs">
        {[["Net desk profit / week", usd(netWk), netWk >= 0 ? "#10B981" : "#EF4444", "cfs-out-net"],
          ["Annualized profit", usd(netWk * 52), netWk >= 0 ? "#10B981" : "#EF4444", "cfs-out-annual"],
          ["AR outstanding", usd(ar), "#22D3EE", "cfs-out-ar"],
          [financing === "factoring" ? "Cash needed (factored, 92% adv)" : "Working capital (self-funded)",
           usd(financing === "factoring" ? wcFactored : wcSelf), "#A78BFA", "cfs-out-wc"]].map(([l, v, c, tid]) => (
          <div key={tid} className="p-2.5 rounded-xl border border-white/10 bg-slate-950/60 text-center" data-testid={tid}>
            <div className="text-sm font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[8px] font-mono uppercase text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>
      {marginPct < 10 && (
        <div className="mt-2 px-2 py-1 rounded-lg border border-red-500/40 bg-red-500/10 text-[9px] font-mono text-red-300" data-testid="cfs-margin-warning">
          ⚠ Below the 10% industry floor — sub-10% gross margin is widely cited as unsustainable for a brokerage.
        </div>
      )}
      <p className="text-[9px] font-mono text-slate-600 mt-2">
        Charges loss provisions 3.5% of revenue, financing on full book, staff/overhead scaled to volume ({usd(overheadWk)}/wk at these settings). Gross margin/wk: {usd(gmWk)} · Revenue/wk: {usd(revWk)}. Benchmarks: FreightWaves/DAT 2025.
      </p>
    </div>
  );
};
