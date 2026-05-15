import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { useBrandRefresh } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Download, Mail, FileSpreadsheet, FileText, Copy } from "lucide-react";
import { toast } from "sonner";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  LineChart, Line, Legend, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from "recharts";

const FACILITY_META = {
  GVM: { name: "Golden Valley, MN", color: "#00E5FF" },
  HOM: { name: "Holland, MI", color: "#10B981" },
  LVK: { name: "Louisville, KY", color: "#A78BFA" },
};

export default function Reports() {
  const [kpis, setKpis] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ to: "", cc: "", note: "", format: "both" });
  const [composed, setComposed] = useState(null);
  const loadReports = () => {
    api.get("/kpis").then(({ data }) => setKpis(data));
    api.get("/kpis/weekly-weights").then(({ data }) => setWeekly(data));
  };
  useEffect(() => { loadReports(); }, []);
  useBrandRefresh(() => loadReports());

  const downloadReport = (fmt) => {
    const a = document.createElement("a");
    a.href = `${BACKEND_URL}/api/reports/kpi/download.${fmt}`;
    a.download = `Tennant_KPI_Report.${fmt}`;
    document.body.appendChild(a); a.click(); a.remove();
    toast.success(`Generating ${fmt.toUpperCase()} report…`);
  };

  const composeEmail = async () => {
    try {
      const { data } = await api.post("/reports/kpi/email", emailForm);
      setComposed(data);
      toast.success("Email composed — copy or open in mail client");
    } catch (e) { toast.error("Failed to compose"); }
  };
  const copyBody = () => { navigator.clipboard.writeText(composed?.body || ""); toast.success("Copied"); };

  if (!kpis) return <><Topbar title="KPI Reports" /><div className="p-6 text-slate-400">Loading...</div></>;

  const trend = kpis.trend;
  const carrierScore = kpis.by_carrier.slice(0, 8).map((c) => ({
    ...c,
    on_time_rate: c.total ? Math.round((c.on_time / c.total) * 100) : 0,
  }));
  const radarData = carrierScore.slice(0, 6).map((c) => ({
    carrier: c.carrier.split(" ")[0],
    Score: c.on_time_rate,
    Volume: Math.min(100, c.total * 10),
  }));

  return (
    <>
      <Topbar title="KPI Reports" subtitle="Performance analytics across modes, lanes & carriers" />
      <div className="p-4 md:p-6 space-y-5">

        {/* Report actions */}
        <Card className="hud-surface p-3 flex flex-wrap items-center gap-2" data-testid="kpi-report-actions">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 px-2">Generate Report</div>
          <Button onClick={() => downloadReport("pdf")} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold flex items-center gap-2" data-testid="download-pdf-btn">
            <FileText size={14} /> Download PDF
          </Button>
          <Button onClick={() => downloadReport("xlsx")} variant="outline" className="border-cyan-500/40 text-cyan-300 flex items-center gap-2" data-testid="download-xlsx-btn">
            <FileSpreadsheet size={14} /> Download Excel
          </Button>
          <Button onClick={() => { setComposed(null); setEmailOpen(true); }} className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold flex items-center gap-2 ml-auto" data-testid="email-report-btn">
            <Mail size={14} /> Email Report
          </Button>
        </Card>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KPI label="Total Shipments" value={kpis.totals.total} accent="text-cyan-400" />
          <KPI label="On-Time Rate" value={`${kpis.totals.on_time_rate}%`} accent="text-emerald-400" />
          <KPI label="Total Weight" value={`${(kpis.totals.weight_lbs / 1000).toFixed(1)}K lbs`} accent="text-cyan-400" />
          <KPI label="Total Value" value={`$${(kpis.totals.value_usd / 1000).toFixed(0)}K`} accent="text-emerald-400" />
        </div>

        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">14-Day Cost Trend</div>
          <h3 className="font-display text-lg font-bold mb-4">Spend Analytics</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" />
              <XAxis dataKey="date" stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
              <Legend wrapperStyle={{ fontSize: 12, fontFamily: "JetBrains Mono" }} />
              <Line dataKey="cost" stroke="#00E5FF" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        {/* Weekly Average Weights by Facility */}
        {weekly && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="weekly-weights-tiles">
              {Object.entries(weekly.summary).map(([fac, s]) => {
                const meta = FACILITY_META[fac];
                const deltaColor = s.wow_delta_lbs > 0 ? "text-yellow-400" : s.wow_delta_lbs < 0 ? "text-emerald-400" : "text-slate-400";
                return (
                  <Card key={fac} className="hud-surface p-5">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{meta.name}</div>
                        <div className="font-display text-sm font-bold mt-0.5" style={{ color: meta.color }}>{fac}</div>
                      </div>
                      <div className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-slate-400">12-wk window</div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <div>
                        <div className="text-[9px] font-mono uppercase text-slate-500">Current Week Avg</div>
                        <div className="text-2xl font-mono font-bold tabular-nums" style={{ color: meta.color }}>{Math.round(s.current_week_avg_lbs).toLocaleString()}</div>
                        <div className="text-[10px] font-mono text-slate-500">lbs / shipment</div>
                      </div>
                      <div>
                        <div className="text-[9px] font-mono uppercase text-slate-500">12-wk Avg</div>
                        <div className="text-2xl font-mono font-bold tabular-nums text-white">{Math.round(s.twelve_wk_avg_lbs).toLocaleString()}</div>
                        <div className="text-[10px] font-mono text-slate-500">lbs / shipment</div>
                      </div>
                    </div>
                    <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between text-xs">
                      <span className="text-slate-400">WoW: <span className={`font-mono font-bold ${deltaColor}`}>{s.wow_delta_lbs >= 0 ? "+" : ""}{Math.round(s.wow_delta_lbs).toLocaleString()}</span></span>
                      <span className="text-slate-400">Total: <span className="font-mono text-cyan-300">{(s.twelve_wk_total_lbs / 1000).toFixed(0)}K lbs</span></span>
                    </div>
                  </Card>
                );
              })}
            </div>

            <Card className="hud-surface p-5">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Auto-Tracked from Shipments</div>
              <h3 className="font-display text-lg font-bold mb-4">Weekly Average Weight per Shipment · by Facility</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={weekly.series}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="week" stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                  <YAxis stroke="#475569" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} unit=" lbs" />
                  <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
                  <Legend wrapperStyle={{ fontSize: 12, fontFamily: "JetBrains Mono" }} />
                  <Line dataKey="GVM" name="Golden Valley, MN" stroke="#00E5FF" strokeWidth={2} dot={{ r: 3 }} />
                  <Line dataKey="HOM" name="Holland, MI" stroke="#10B981" strokeWidth={2} dot={{ r: 3 }} />
                  <Line dataKey="LVK" name="Louisville, KY" stroke="#A78BFA" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Carrier Scorecard</div>
            <h3 className="font-display text-lg font-bold mb-4">On-Time Performance by Carrier</h3>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={carrierScore} layout="vertical">
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="#475569" tick={{ fontSize: 10 }} />
                <YAxis dataKey="carrier" type="category" stroke="#475569" tick={{ fontSize: 10 }} width={120} />
                <Tooltip contentStyle={{ background: "#0B0E14", border: "1px solid rgba(0,229,255,0.3)" }} />
                <Bar dataKey="on_time_rate" fill="#10B981" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Carrier Profile</div>
            <h3 className="font-display text-lg font-bold mb-4">Score vs Volume</h3>
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                <PolarAngleAxis dataKey="carrier" stroke="#94A3B8" tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
                <PolarRadiusAxis stroke="#475569" tick={{ fontSize: 9 }} />
                <Radar dataKey="Score" stroke="#00E5FF" fill="#00E5FF" fillOpacity={0.3} />
                <Radar dataKey="Volume" stroke="#A78BFA" fill="#A78BFA" fillOpacity={0.2} />
                <Legend wrapperStyle={{ fontSize: 12, fontFamily: "JetBrains Mono" }} />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        </div>

        {/* === NETWORK-WIDE TRANSPORTATION METRICS (industry-standard, 41 KPIs) === */}
        {kpis.network_metrics && (
          <Card className="hud-surface p-5" data-testid="network-metrics">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Industry-Standard Network Metrics</div>
                <h3 className="font-display text-lg font-bold">CSCMP · ATA · NASSTRAC · ISO Aligned</h3>
              </div>
              <div className="text-[10px] font-mono text-slate-500">
                {Object.values(kpis.network_metrics).reduce((a, v) => a + v.length, 0)} metrics across {Object.keys(kpis.network_metrics).length} categories
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-3">
              {Object.entries(kpis.network_metrics).map(([cat, items]) => (
                <div key={cat} className="p-3 rounded border border-white/5 bg-white/[0.02]" data-testid={`netmetric-section-${cat}`}>
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-300 mb-2">
                    {cat.replace(/_/g, " ")}
                  </div>
                  <div className="space-y-1.5">
                    {items.map((m) => {
                      const onTarget = (m.unit === "$" || m.label.toLowerCase().includes("variance") ||
                                        m.label.toLowerCase().includes("rate") ||
                                        m.label.toLowerCase().includes("co2") ||
                                        m.label.toLowerCase().includes("empty") ||
                                        m.label.toLowerCase().includes("dispute") ||
                                        m.label.toLowerCase().includes("oos") ||
                                        m.label.toLowerCase().includes("violations") ||
                                        m.label.toLowerCase().includes("csa") ||
                                        m.label.toLowerCase().includes("hazmat") ||
                                        m.label.toLowerCase().includes("preventable"))
                        ? m.value <= m.target
                        : m.value >= m.target;
                      const arrow = m.trend > 0 ? "▲" : m.trend < 0 ? "▼" : "—";
                      const trendColor = (m.trend > 0 && !["empty_miles","cost_per_mile","cost_per_pound","cost_per_load","accessorial_pct","detention_spend","claims_freq","damage_rate","shortage_rate","invoice_dispute","fmcsa_csa_avg","oos_rate","hos_violations","co2_per_load","co2_per_ton_mile","preventable_accidents","tender_lead_time","transit_variance"].includes(m.key))
                        ? "text-emerald-300"
                        : (m.trend < 0 && ["empty_miles","cost_per_mile","cost_per_pound","cost_per_load","accessorial_pct","detention_spend","claims_freq","damage_rate","shortage_rate","invoice_dispute","fmcsa_csa_avg","oos_rate","hos_violations","co2_per_load","co2_per_ton_mile","preventable_accidents","tender_lead_time","transit_variance"].includes(m.key))
                          ? "text-emerald-300"
                          : m.trend === 0 ? "text-slate-500" : "text-red-300";
                      return (
                        <div key={m.key} data-testid={`netmetric-${m.key}`} className="flex items-center gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="text-[11px] text-slate-200 truncate">{m.label}</div>
                            <div className="text-[9px] font-mono text-slate-500">
                              Target {m.unit === "$" ? "$" : ""}{m.target}{m.unit !== "$" ? m.unit : ""}
                              {" · BM "}{m.unit === "$" ? "$" : ""}{m.benchmark}{m.unit !== "$" ? m.unit : ""}
                            </div>
                          </div>
                          <div className={`font-mono text-sm font-bold tabular-nums ${onTarget ? "text-emerald-300" : "text-yellow-300"}`}>
                            {m.unit === "$" ? "$" : ""}{m.value.toLocaleString()}{m.unit !== "$" ? m.unit : ""}
                          </div>
                          <span className={`text-[9px] font-mono w-10 text-right ${trendColor}`}>
                            {arrow}{m.trend !== 0 ? Math.abs(m.trend) : ""}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card className="hud-surface overflow-hidden" data-testid="carrier-scorecard-table">
          <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Carrier Scorecard — Industry-Standard (45 metrics each)</div>
              <h3 className="font-display text-lg font-bold">{kpis.carrier_scorecard?.length || 0} carriers · ranked by composite score</h3>
            </div>
            <div className="text-[10px] font-mono text-slate-500">
              Composite weighting: OTD 20% · OTIF 15% · Tender 10% · Billing 10% · POD 10% · Rate 10% · Damage 5% · Claims 10% · OOS 5% · Empty Miles 5%
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[1480px]">
              <thead className="bg-[#0B0E14] text-[9px] font-mono text-slate-500 uppercase tracking-wider sticky top-0">
                <tr>
                  <th className="text-left py-3 px-3">#</th>
                  <th className="text-left py-3 px-3">Carrier</th>
                  <th className="text-center py-3 px-2">Grade</th>
                  <th className="text-right py-3 px-2">Composite</th>
                  <th className="text-right py-3 px-2">Loads</th>
                  <th className="text-right py-3 px-2 text-cyan-400">OTP %</th>
                  <th className="text-right py-3 px-2 text-cyan-400">OTD %</th>
                  <th className="text-right py-3 px-2 text-cyan-400">OTIF %</th>
                  <th className="text-right py-3 px-2 text-cyan-400">Tender %</th>
                  <th className="text-right py-3 px-2 text-yellow-300">Transit Var</th>
                  <th className="text-right py-3 px-2 text-yellow-300">Claims %</th>
                  <th className="text-right py-3 px-2 text-yellow-300">Damage %</th>
                  <th className="text-right py-3 px-2 text-yellow-300">Billing Acc</th>
                  <th className="text-right py-3 px-2 text-yellow-300">EDI %</th>
                  <th className="text-right py-3 px-2 text-yellow-300">POD %</th>
                  <th className="text-right py-3 px-2 text-red-300">CSA</th>
                  <th className="text-right py-3 px-2 text-red-300">OOS %</th>
                  <th className="text-right py-3 px-2 text-red-300">Safety</th>
                  <th className="text-right py-3 px-2 text-emerald-300">$/Mile</th>
                  <th className="text-right py-3 px-2 text-emerald-300">$/Load</th>
                  <th className="text-right py-3 px-2 text-emerald-300">FSC/mi</th>
                  <th className="text-right py-3 px-2 text-emerald-300">Acc %</th>
                  <th className="text-right py-3 px-2 text-emerald-300">Detention $</th>
                  <th className="text-right py-3 px-2 text-purple-300">Empty %</th>
                  <th className="text-right py-3 px-2 text-purple-300">CO₂/load</th>
                  <th className="text-right py-3 px-2 text-purple-300">EV %</th>
                  <th className="text-center py-3 px-2">Trend</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {(kpis.carrier_scorecard || []).map((c, i) => {
                  const gradeColor = c.grade.startsWith("A") ? "text-emerald-300 bg-emerald-500/10 border-emerald-500/30"
                    : c.grade.startsWith("B") ? "text-cyan-300 bg-cyan-500/10 border-cyan-500/30"
                    : c.grade.startsWith("C") ? "text-yellow-300 bg-yellow-500/10 border-yellow-500/30"
                    : "text-red-300 bg-red-500/10 border-red-500/30";
                  const trendIcon = c.trend === "up" ? "▲" : c.trend === "down" ? "▼" : "—";
                  const trendColor = c.trend === "up" ? "text-emerald-400" : c.trend === "down" ? "text-red-400" : "text-slate-500";
                  return (
                    <tr key={c.carrier} className="border-t border-white/5 hover:bg-cyan-500/[0.04]" data-testid={`scorecard-row-${i}`}>
                      <td className="py-2 px-3 text-slate-500 text-[10px]">{i + 1}</td>
                      <td className="py-2 px-3 text-slate-100">{c.carrier}</td>
                      <td className="py-2 px-2 text-center">
                        <span className={`inline-block px-1.5 py-0.5 rounded border text-[10px] font-bold ${gradeColor}`}>
                          {c.grade}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right text-white font-bold">{c.composite_score}</td>
                      <td className="py-2 px-2 text-right text-slate-300">{c.total_loads}</td>
                      <td className="py-2 px-2 text-right text-cyan-200">{c.on_time_pickup_pct}%</td>
                      <td className="py-2 px-2 text-right text-cyan-200">{c.on_time_delivery_pct}%</td>
                      <td className="py-2 px-2 text-right text-cyan-200">{c.on_time_in_full_pct}%</td>
                      <td className="py-2 px-2 text-right text-cyan-200">{c.tender_acceptance_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.transit_variance_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.claims_freq_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.damage_freq_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.billing_accuracy_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.edi_compliance_pct}%</td>
                      <td className="py-2 px-2 text-right text-yellow-200">{c.pod_timeliness_pct}%</td>
                      <td className={`py-2 px-2 text-right ${c.csa_score >= 65 ? "text-red-400" : c.csa_score >= 40 ? "text-yellow-300" : "text-emerald-300"}`}>
                        {c.csa_score}
                      </td>
                      <td className="py-2 px-2 text-right text-red-200">{c.out_of_service_pct}%</td>
                      <td className={`py-2 px-2 text-right text-[10px] ${c.safety_rating === "Satisfactory" ? "text-emerald-300" : "text-yellow-300"}`}>
                        {c.safety_rating?.slice(0, 4)}
                      </td>
                      <td className="py-2 px-2 text-right text-emerald-200">${c.avg_cost_per_mile_usd}</td>
                      <td className="py-2 px-2 text-right text-emerald-200">${c.avg_cost_per_load_usd.toLocaleString()}</td>
                      <td className="py-2 px-2 text-right text-emerald-200">${c.fsc_per_mile_usd}</td>
                      <td className="py-2 px-2 text-right text-emerald-200">{c.accessorial_spend_pct}%</td>
                      <td className="py-2 px-2 text-right text-emerald-200">${c.detention_cost_usd.toLocaleString()}</td>
                      <td className="py-2 px-2 text-right text-purple-200">{c.empty_miles_pct}%</td>
                      <td className="py-2 px-2 text-right text-purple-200">{c.co2_kg_per_load}</td>
                      <td className="py-2 px-2 text-right text-purple-200">{c.ev_fleet_pct}%</td>
                      <td className={`py-2 px-2 text-center ${trendColor}`}>{trendIcon}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Email modal */}
      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-2xl" data-testid="email-report-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Mail size={16} /> Email KPI Report</DialogTitle>
          </DialogHeader>
          {!composed ? (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">To</label>
                <Input value={emailForm.to} onChange={(e) => setEmailForm({ ...emailForm, to: e.target.value })} placeholder="director@tennantco.com" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="email-to-input" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">CC (optional)</label>
                <Input value={emailForm.cc} onChange={(e) => setEmailForm({ ...emailForm, cc: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Format</label>
                <div className="flex gap-2 mt-1">
                  {["pdf", "xlsx", "both"].map((f) => (
                    <button key={f} onClick={() => setEmailForm({ ...emailForm, format: f })} className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${emailForm.format === f ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>{f}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Note (optional)</label>
                <textarea value={emailForm.note} onChange={(e) => setEmailForm({ ...emailForm, note: e.target.value })} rows={3} placeholder="Weekly performance review" className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-sm" />
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Subject</label>
                <Input readOnly value={composed.subject} className="mt-1 bg-[#0B0E14] border-white/10 font-mono text-xs" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Body</label>
                <textarea readOnly value={composed.body} rows={16} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-xs font-mono whitespace-pre-wrap" data-testid="email-body-preview" />
              </div>
            </div>
          )}
          <DialogFooter>
            {!composed ? (
              <>
                <Button variant="outline" onClick={() => setEmailOpen(false)}>Cancel</Button>
                <Button onClick={composeEmail} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="compose-email-btn">Compose</Button>
              </>
            ) : (
              <>
                <Button variant="outline" onClick={copyBody} data-testid="copy-email-body-btn"><Copy size={14} className="mr-1" /> Copy Body</Button>
                <a href={composed.mailto} className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm" data-testid="email-mailto-btn">
                  <Mail size={14} /> Open in Mail Client
                </a>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

const KPI = ({ label, value, accent }) => (
  <Card className="hud-surface p-5">
    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
    <div className={`mt-2 text-3xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
  </Card>
);
