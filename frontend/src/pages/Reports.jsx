import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
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
  useEffect(() => {
    api.get("/kpis").then(({ data }) => setKpis(data));
    api.get("/kpis/weekly-weights").then(({ data }) => setWeekly(data));
  }, []);

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

        <Card className="hud-surface overflow-hidden">
          <div className="px-5 py-3 border-b border-white/5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Carrier Scorecard — Detailed</div>
            <h3 className="font-display text-lg font-bold">All Carriers</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">Carrier</th>
                <th className="text-right py-3 px-4">Total</th>
                <th className="text-right py-3 px-4">Delivered</th>
                <th className="text-right py-3 px-4">Delayed</th>
                <th className="text-right py-3 px-4">On-Time %</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {kpis.by_carrier.sort((a, b) => b.total - a.total).map((c) => {
                const otp = c.total ? Math.round((c.on_time / c.total) * 100) : 0;
                return (
                  <tr key={c.carrier} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-4 text-slate-300">{c.carrier}</td>
                    <td className="py-2.5 px-4 text-right text-cyan-300">{c.total}</td>
                    <td className="py-2.5 px-4 text-right text-emerald-400">{c.on_time}</td>
                    <td className="py-2.5 px-4 text-right text-red-400">{c.delayed}</td>
                    <td className="py-2.5 px-4 text-right text-white">{otp}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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
