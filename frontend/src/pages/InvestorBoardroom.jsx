import React, { useEffect, useState, useMemo } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { useBranding } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, Legend, PieChart, Pie, Cell,
} from "recharts";
import {
  Download, FileSpreadsheet, FileText, Archive, Briefcase, TrendingUp,
  Target, Sparkles, AlertTriangle,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const DEFAULT_INPUTS = {
  starting_capital_usd: 75000,
  operator_experience_years: 13,
  monthly_marketing_budget_usd: 1500,
  carrier_pool_size: 0,
  has_tms: true,
  has_factoring_partner: true,
  has_authority: true,
  target_lanes_count: 6,
};

const BAND_COLORS = {
  STRONG: "#10B981",
  FAVORABLE: "#22D3EE",
  WORKABLE: "#FBBF24",
  FRAGILE: "#EF4444",
};

export default function InvestorBoardroom() {
  const { brand } = useBranding();
  const primary = brand?.primary_color || "#0E3A6B";
  const accent = brand?.accent_color || "#C9A24A";
  const company = brand?.company_name || "Orisei Freight Solutions LLC";
  const short = brand?.short_name || "Orisei";

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [inputs, setInputs] = useState(DEFAULT_INPUTS);
  const [scoreResult, setScoreResult] = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data: d } = await api.get("/investor/boardroom");
        setData(d);
        setScoreResult(d.default_probability);
      } catch (e) {
        toast.error(e?.response?.data?.detail || "Failed to load boardroom data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Re-compute probability live whenever the sliders change
  useEffect(() => {
    if (!data) return;
    const handler = setTimeout(async () => {
      try {
        const { data: res } = await api.post("/investor/probability", inputs);
        setScoreResult(res);
      } catch (e) { /* noop */ }
    }, 250);
    return () => clearTimeout(handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputs, data]);

  const triggerDownload = async (path, label, filename) => {
    setDownloading(label);
    try {
      const token = localStorage.getItem("session_token") || "test_session_admin_1";
      const r = await fetch(`${REACT_APP_BACKEND_URL}/api${path}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: "include",
      });
      if (!r.ok) throw new Error((await r.text()) || "Download failed");
      const blob = await r.blob();
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${label} downloaded`);
    } catch (e) {
      toast.error(`${label} failed: ${e.message || e}`);
    } finally {
      setDownloading(null);
    }
  };

  const annualChartData = useMemo(() => (data?.annual_summary || []).map((r) => ({
    year: `Year ${r.year}`,
    revenue: r.revenue_usd,
    ebitda: r.ebitda_usd,
    loads: r.loads,
  })), [data]);

  const monthlyChartData = useMemo(() => (data?.monthly_model || []).map((m) => ({
    month: m.month_label,
    Revenue: m.revenue_usd,
    EBITDA: m.ebitda_usd,
    "Gross Profit": m.gross_profit_usd,
  })), [data]);

  const tamSamSomPie = useMemo(() => data ? [
    { name: "TAM (US Brokerage)",  value: data.market_sizing.tam.value_usd_billion * 1000 },
    { name: "SAM (Midwest TL/LTL)", value: data.market_sizing.sam.value_usd_billion * 1000 },
    { name: "SOM (Year 3)",        value: data.market_sizing.som_year3.value_usd_million },
  ] : [], [data]);
  void tamSamSomPie;  // reserved for future TAM/SAM/SOM pie viz

  if (loading) {
    return <><Topbar title="Investor Boardroom" /><div className="p-6 text-slate-400">Loading…</div></>;
  }
  if (!data) return null;

  const band = scoreResult?.band || "WORKABLE";
  const bandColor = BAND_COLORS[band];

  return (
    <>
      <Topbar
        title={`${short} · Investor Boardroom`}
        subtitle="VC-grade analytics · TAM/SAM/SOM · Financial Projections · Success Probability"
      />
      <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">

        {/* DATA-ROOM DOWNLOAD ACTIONS */}
        <Card className="hud-surface p-5" style={{ borderColor: `${accent}33` }} data-testid="dataroom-card">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                VC Data Room · One-Click Downloads
              </div>
              <h2 className="font-display text-2xl font-bold mt-1" style={{ color: accent }}>
                Everything a VC needs in {company}
              </h2>
              <p className="text-sm text-slate-400 mt-1">Pitch deck · One-pager · Financial model · Cap table · Industry probability report · Business plan — all brand-stamped, all ready to share.</p>
            </div>
            <Button
              onClick={() => triggerDownload("/investor/data-room.zip", "Full data-room ZIP", `${company.replace(/ /g, "_")}_VC_Data_Room.zip`)}
              disabled={!!downloading}
              className="font-bold text-black"
              style={{ background: accent }}
              data-testid="dataroom-download-zip"
            >
              <Archive size={14} className="mr-2" />
              {downloading === "Full data-room ZIP" ? "Bundling…" : "Download Full Data Room (ZIP)"}
            </Button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4">
            <DownloadPill icon={FileText} label="Pitch Deck" sublabel="15 slides · PDF" accent={accent}
              onClick={() => triggerDownload("/investor/deck.pdf", "Pitch Deck", `${company.replace(/ /g, "_")}_Pitch_Deck.pdf`)}
              loading={downloading === "Pitch Deck"} testId="download-deck" />
            <DownloadPill icon={FileText} label="One-Pager" sublabel="At-a-glance · PDF" accent={accent}
              onClick={() => triggerDownload("/investor/one-pager.pdf", "One-Pager", `${company.replace(/ /g, "_")}_One_Pager.pdf`)}
              loading={downloading === "One-Pager"} testId="download-one-pager" />
            <DownloadPill icon={FileSpreadsheet} label="Financial Model" sublabel="36 mo · XLSX" accent={accent}
              onClick={() => triggerDownload("/investor/financial-model.xlsx", "Financial Model", `${company.replace(/ /g, "_")}_Financial_Model.xlsx`)}
              loading={downloading === "Financial Model"} testId="download-xlsx" />
            <DownloadPill icon={FileText} label="Business Plan" sublabel="Founder plan · PDF" accent={accent}
              onClick={() => triggerDownload("/brokerage/business-plan/pdf", "Business Plan", `${company.replace(/ /g, "_")}_Business_Plan.pdf`)}
              loading={downloading === "Business Plan"} testId="download-business-plan" />
          </div>
        </Card>

        {/* HEADLINE METRICS */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric label="TAM" value={`$${data.market_sizing.tam.value_usd_billion}B`} sub="US Brokerage · TIA 2024" accent={accent} />
          <Metric label="SAM" value={`$${data.market_sizing.sam.value_usd_billion}B`} sub="Midwest TL/LTL" accent={accent} />
          <Metric label="Year 3 SOM" value={`$${data.market_sizing.som_year3.value_usd_million}M`} sub="Twin Cities + Upper MW" accent={accent} />
          <Metric label="Year 3 EBITDA" value={`$${Math.round(data.annual_summary[2].ebitda_usd / 1000)}K`} sub={`${data.annual_summary[2].ebitda_margin_pct}% margin`} accent={accent} />
        </div>

        {/* PROBABILITY OF SUCCESS — INTERACTIVE */}
        <Card className="hud-surface p-6" style={{ borderColor: `${accent}33` }} data-testid="probability-card">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Sliders */}
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                Industry Probability of Success · Year 1
              </div>
              <h3 className="font-display text-xl font-bold mt-1 mb-4 text-white">Interactive scorecard</h3>

              <SliderRow label="Starting Capital (USD)" testId="slider-capital"
                value={inputs.starting_capital_usd} onChange={(v) => setInputs({ ...inputs, starting_capital_usd: parseFloat(v) })}
                min={0} max={500000} step={5000} format={(v) => `$${Number(v).toLocaleString()}`} accent={accent} />
              <SliderRow label="Operator Experience (Years)" testId="slider-experience"
                value={inputs.operator_experience_years} onChange={(v) => setInputs({ ...inputs, operator_experience_years: parseFloat(v) })}
                min={0} max={25} step={1} format={(v) => `${v} yrs`} accent={accent} />
              <SliderRow label="Monthly Marketing Budget (USD)" testId="slider-marketing"
                value={inputs.monthly_marketing_budget_usd} onChange={(v) => setInputs({ ...inputs, monthly_marketing_budget_usd: parseFloat(v) })}
                min={0} max={10000} step={250} format={(v) => `$${Number(v).toLocaleString()}/mo`} accent={accent} />
              <SliderRow label="Carrier Pool Size" testId="slider-pool"
                value={inputs.carrier_pool_size} onChange={(v) => setInputs({ ...inputs, carrier_pool_size: parseInt(v) })}
                min={0} max={1000} step={10} format={(v) => `${v} carriers`} accent={accent} />
              <SliderRow label="Target Lanes Count" testId="slider-lanes"
                value={inputs.target_lanes_count} onChange={(v) => setInputs({ ...inputs, target_lanes_count: parseInt(v) })}
                min={1} max={30} step={1} format={(v) => `${v} lanes`} accent={accent} />

              <div className="grid grid-cols-3 gap-2 mt-4">
                <ToggleChip label="Operator-grade TMS" enabled={inputs.has_tms} onToggle={() => setInputs({ ...inputs, has_tms: !inputs.has_tms })} accent={accent} testId="toggle-tms" />
                <ToggleChip label="Authority + BMC-84" enabled={inputs.has_authority} onToggle={() => setInputs({ ...inputs, has_authority: !inputs.has_authority })} accent={accent} testId="toggle-authority" />
                <ToggleChip label="Factoring partner" enabled={inputs.has_factoring_partner} onToggle={() => setInputs({ ...inputs, has_factoring_partner: !inputs.has_factoring_partner })} accent={accent} testId="toggle-factoring" />
              </div>
            </div>

            {/* Score Output */}
            <div>
              <div className="rounded-xl p-6 border-2 text-center"
                   style={{ borderColor: bandColor, background: `${bandColor}11` }}
                   data-testid="probability-score">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: bandColor }}>
                  Year-1 Success Probability
                </div>
                <div className="font-display text-7xl font-black tabular-nums" style={{ color: bandColor }}>
                  {scoreResult?.score_pct?.toFixed(1) || "—"}<span className="text-3xl">%</span>
                </div>
                <div className="mt-2 font-mono text-sm uppercase tracking-wider font-bold" style={{ color: bandColor }} data-testid="probability-band">
                  {band}
                </div>
                <div className="text-xs text-slate-300 mt-2 max-w-md mx-auto leading-relaxed">
                  {scoreResult?.band_note || "Adjust the inputs to model your scenario."}
                </div>
              </div>

              {/* Drivers */}
              <div className="mt-4 space-y-1.5">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>Score drivers</div>
                {(scoreResult?.drivers || []).map((d, i) => (
                  <div key={i} className="flex items-start justify-between gap-3 py-1 border-b border-white/5 text-sm" data-testid={`driver-${i}`}>
                    <div className="flex-1">
                      <div className="text-slate-200">{d.label}</div>
                      <div className="text-[10px] text-slate-500">{d.note}</div>
                    </div>
                    <div className={`font-mono font-bold tabular-nums ${d.delta >= 0 ? "" : "text-red-400"}`}
                         style={d.delta >= 0 ? { color: bandColor } : {}}>
                      {d.delta >= 0 ? "+" : ""}{d.delta.toFixed(1)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* FINANCIAL CHART */}
        <Card className="hud-surface p-6" style={{ borderColor: `${accent}33` }} data-testid="financial-chart">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
            36-Month Financial Projection · Bootstrap baseline
          </div>
          <h3 className="font-display text-xl font-bold mt-1 mb-4 text-white">Revenue + EBITDA waterfall</h3>
          <div className="h-72 w-full">
            <ResponsiveContainer>
              <AreaChart data={monthlyChartData} margin={{ left: 0, right: 10, top: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accent} stopOpacity={0.6} />
                    <stop offset="100%" stopColor={accent} stopOpacity={0.05} />
                  </linearGradient>
                  <linearGradient id="ebitda" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={primary} stopOpacity={0.6} />
                    <stop offset="100%" stopColor={primary} stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1F2937" strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fill: "#94A3B8", fontSize: 10 }} interval={2} />
                <YAxis tick={{ fill: "#94A3B8", fontSize: 10 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: `1px solid ${accent}55`, color: "#fff" }}
                  formatter={(v) => `$${Number(v).toLocaleString()}`} />
                <Legend />
                <Area type="monotone" dataKey="Revenue" stroke={accent} strokeWidth={2} fill="url(#rev)" />
                <Area type="monotone" dataKey="Gross Profit" stroke="#10B981" strokeWidth={1.5} fillOpacity={0.15} />
                <Area type="monotone" dataKey="EBITDA" stroke={primary} strokeWidth={2} fill="url(#ebitda)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* TAM / SAM / SOM + UNIT ECONOMICS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="hud-surface p-6" style={{ borderColor: `${accent}33` }} data-testid="market-sizing">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>Market Sizing</div>
            <h3 className="font-display text-xl font-bold mt-1 mb-4 text-white flex items-center gap-2"><Target size={18} style={{ color: accent }} /> TAM · SAM · SOM</h3>
            <div className="space-y-3">
              <SegmentRow label="TAM" value={`$${data.market_sizing.tam.value_usd_billion}B`} desc={data.market_sizing.tam.description} width={100} accent={accent} />
              <SegmentRow label="SAM" value={`$${data.market_sizing.sam.value_usd_billion}B`} desc={data.market_sizing.sam.description}
                width={Math.round((data.market_sizing.sam.value_usd_billion / data.market_sizing.tam.value_usd_billion) * 100)} accent={accent} />
              <SegmentRow label="SOM Y3" value={`$${data.market_sizing.som_year3.value_usd_million}M`} desc={data.market_sizing.som_year3.description}
                width={Math.max(4, Math.round((data.market_sizing.som_year3.value_usd_million / 1000 / data.market_sizing.tam.value_usd_billion) * 100))} accent={accent} />
            </div>
            <div className="text-[10px] text-slate-500 mt-4">Capture target = {data.market_sizing.som_year3_pct_of_sam.toFixed(4)}% of SAM by EoY3 — conservative.</div>
          </Card>

          <Card className="hud-surface p-6" style={{ borderColor: `${accent}33` }} data-testid="unit-economics">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>Unit Economics</div>
            <h3 className="font-display text-xl font-bold mt-1 mb-4 text-white flex items-center gap-2"><TrendingUp size={18} style={{ color: accent }} /> Per-load + per-customer</h3>
            <div className="grid grid-cols-2 gap-3">
              <UeMetric label="Rev / load" value={`$${data.unit_economics.avg_revenue_per_load_usd.toLocaleString()}`} />
              <UeMetric label="Gross margin" value={`${data.unit_economics.avg_gross_margin_pct}%`} />
              <UeMetric label="Gross profit / load" value={`$${data.unit_economics.avg_gross_profit_per_load_usd}`} />
              <UeMetric label="Contribution / load" value={`$${data.unit_economics.contribution_per_load_usd}`} />
              <UeMetric label="CAC" value={`$${data.unit_economics.customer_acquisition_cost_usd}`} />
              <UeMetric label="Payback" value={`${data.unit_economics.customer_payback_loads} loads`} />
              <UeMetric label="LTV (Y3)" value={`$${data.unit_economics.ltv_per_customer_year3_usd.toLocaleString()}`} />
              <UeMetric label="LTV / CAC" value={`${data.unit_economics.ltv_cac_ratio}x`} highlight={accent} />
              <UeMetric label="Rule-of-40 (Y3)" value={`${data.unit_economics.rule_of_40_year3_pct}%`} highlight={accent} />
            </div>
          </Card>
        </div>

        {/* INDUSTRY BENCHMARKS */}
        <Card className="hud-surface p-6" style={{ borderColor: `${accent}33` }} data-testid="industry-benchmarks">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>Industry Reality Check</div>
          <h3 className="font-display text-xl font-bold mt-1 mb-3 text-white flex items-center gap-2"><AlertTriangle size={18} className="text-amber-400" /> Why most freight brokerages fail</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatBlock big={`${data.industry_benchmarks.broker_failure_year1_pct}%`} label="Y1 broker failure" sub="SBA + TIA 2023" />
            <StatBlock big={`${data.industry_benchmarks.broker_failure_year3_pct}%`} label="By-Y3 broker failure" sub="SBA 2023" />
            <StatBlock big={`${data.industry_benchmarks.broker_success_year5_pct}%`} label="Y5 surviving + CFP" sub="SBA 2023" />
            <StatBlock big={`+${data.industry_benchmarks.ai_powered_broker_success_lift_pct}pt`} label="TMS survival lift" sub="FreightWaves 2024" highlight={accent} />
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Sources: {data.industry_benchmarks.sources.join(" · ")}
          </div>
        </Card>

      </div>
    </>
  );
}

/* -------- subcomponents -------- */
function DownloadPill({ icon: Icon, label, sublabel, onClick, accent, loading, testId }) {  return (
    <button
      onClick={onClick}
      disabled={loading}
      data-testid={testId}
      className="text-left p-3 rounded-lg border transition hover:scale-[1.02] disabled:opacity-50"
      style={{ borderColor: `${accent}44`, background: `${accent}0a` }}
    >
      <div className="flex items-center gap-2">
        <Icon size={16} style={{ color: accent }} />
        <div className="text-sm text-white font-semibold">{label}</div>
      </div>
      <div className="text-[10px] mt-1 text-slate-500">{loading ? "Generating…" : sublabel}</div>
    </button>
  );
}

function Metric({ label, value, sub, accent }) {
  return (
    <Card className="hud-surface p-4" style={{ borderColor: `${accent}33` }}>
      <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>{label}</div>
      <div className="font-display text-2xl font-black mt-1 text-white tabular-nums">{value}</div>
      <div className="text-[10px] text-slate-500 mt-1">{sub}</div>
    </Card>
  );
}

function SliderRow({ label, value, onChange, min, max, step, format, accent, testId }) {
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</Label>
        <span className="text-sm font-mono tabular-nums" style={{ color: accent }}>{format(value)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="w-full accent-slate-100"
        style={{ accentColor: accent }}
      />
    </div>
  );
}

function ToggleChip({ label, enabled, onToggle, accent, testId }) {
  return (
    <button
      onClick={onToggle}
      data-testid={testId}
      className="text-left px-3 py-2 rounded border transition text-xs"
      style={{
        borderColor: enabled ? accent : "rgba(255,255,255,0.1)",
        background: enabled ? `${accent}22` : "rgba(255,255,255,0.02)",
        color: enabled ? accent : "#94a3b8",
      }}
    >
      <div className="font-mono uppercase tracking-wider text-[9px] mb-0.5">{enabled ? "ENABLED" : "OFF"}</div>
      <div className="font-semibold">{label}</div>
    </button>
  );
}

function SegmentRow({ label, value, desc, width, accent }) {
  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-white font-mono font-bold">{label}</span>
        <span className="font-mono tabular-nums" style={{ color: accent }}>{value}</span>
      </div>
      <div className="h-3 rounded-full overflow-hidden bg-white/[0.04]">
        <div className="h-full rounded-full transition-all"
             style={{ width: `${width}%`, background: `linear-gradient(90deg, ${accent}, ${accent}cc)` }} />
      </div>
      <div className="text-[10px] text-slate-500 mt-1">{desc}</div>
    </div>
  );
}

function UeMetric({ label, value, highlight }) {
  return (
    <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className="font-display font-bold text-lg mt-1 tabular-nums" style={highlight ? { color: highlight } : { color: "#fff" }}>{value}</div>
    </div>
  );
}

function StatBlock({ big, label, sub, highlight }) {
  return (
    <div className="p-4 rounded-lg border border-white/5 bg-white/[0.02]">
      <div className="font-display text-3xl font-black tabular-nums" style={highlight ? { color: highlight } : { color: "#fff" }}>{big}</div>
      <div className="text-xs text-slate-300 mt-1">{label}</div>
      <div className="text-[9px] text-slate-500 mt-0.5">{sub}</div>
    </div>
  );
}
