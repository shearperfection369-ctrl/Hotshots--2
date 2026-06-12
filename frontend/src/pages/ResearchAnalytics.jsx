/* eslint-disable */
import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api, BACKEND_URL } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from "recharts";
import {
  Database, Upload, Trash2, RefreshCw, FlaskConical, Boxes, TrendingUp,
  Factory, Layers3, Wallet, BarChart3, Percent, Activity, FileText, Globe2,
  Sparkles, AlertTriangle, Plus,
} from "lucide-react";

const TABS = [
  { id: "datasets",    label: "Client Datasets",        icon: Database },
  { id: "scp",         label: "Supply Chain Planning",  icon: Boxes },
  { id: "demand",      label: "Demand Planning",        icon: TrendingUp },
  { id: "supply",      label: "Supply Planning",        icon: Factory },
  { id: "sop",         label: "S&OP",                   icon: Layers3 },
  { id: "p-spend",     label: "Parcel Spend Mgmt",      icon: Wallet },
  { id: "p-intel",     label: "Parcel Spend Intel",     icon: BarChart3 },
  { id: "p-margin",    label: "Parcel Margin",          icon: Percent },
  { id: "p-variance",  label: "Parcel Cost Variance",   icon: Activity },
  { id: "p-contract",  label: "Parcel Contract",        icon: FileText },
  { id: "audit",       label: "Freight Audit & Pay",    icon: Sparkles },
  { id: "intl",        label: "International Rollup",   icon: Globe2 },
];

const PALETTE = ["#22d3ee", "#a78bfa", "#fbbf24", "#34d399", "#f87171",
                  "#60a5fa", "#fb923c", "#f472b6", "#a3e635", "#06b6d4"];

// Persist dataset selection across tab switches
const useDatasetSelect = () => {
  const [datasetId, setDatasetId] = useState(localStorage.getItem("ra_dataset_id") || "");
  const change = (id) => {
    setDatasetId(id);
    if (id) localStorage.setItem("ra_dataset_id", id);
    else localStorage.removeItem("ra_dataset_id");
  };
  return [datasetId, change];
};

export default function ResearchAnalytics() {
  const [tab, setTab] = useState("datasets");
  const [datasetId, setDatasetId] = useDatasetSelect();
  const [datasets, setDatasets] = useState([]);
  const loadDatasets = () => api.get("/research-analytics/datasets")
    .then(({ data }) => setDatasets(data.items || []));
  useEffect(() => { loadDatasets(); }, []);

  const activeDataset = datasets.find((d) => d.dataset_id === datasetId);

  return (
    <>
      <Topbar title="Research & Analytics" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <Card className="hud-surface p-6 border-purple-500/20" data-testid="ra-header">
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-purple-300">
                International Logistics · Supply-chain Intelligence · Parcel Spend
              </div>
              <h1 className="font-display text-4xl font-black mt-2 bg-gradient-to-r from-purple-300 via-cyan-300 to-amber-300 bg-clip-text text-transparent">
                Research & Analytics
              </h1>
              <p className="text-sm text-slate-400 mt-3 max-w-3xl leading-relaxed">
                Drop a client's shipment CSV, get instant S&OP, demand forecast, parcel
                spend intelligence, margin analysis, and contract leverage points.
                Built on the same MAD-based anomaly engine as Audit ML.
              </p>
            </div>
            <DatasetSelector value={datasetId} onChange={setDatasetId}
                              datasets={datasets} activeDataset={activeDataset} />
          </div>
          <div className="flex flex-wrap gap-2 mt-6 border-t border-white/5 pt-5">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)}
                data-testid={`ra-tab-${t.id}`}
                className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition flex items-center gap-2 ${
                  tab === t.id
                    ? "bg-purple-500/20 text-purple-200 border border-purple-500/40"
                    : "text-slate-400 hover:text-purple-200 border border-transparent hover:bg-white/5"
                }`}>
                <t.icon size={12} /> {t.label}
              </button>
            ))}
          </div>
        </Card>

        {tab === "datasets" && <DatasetsTab datasets={datasets} reload={loadDatasets} setDatasetId={setDatasetId} />}
        {tab === "scp" && <ScpTab datasetId={datasetId} />}
        {tab === "demand" && <DemandTab datasetId={datasetId} />}
        {tab === "supply" && <SupplyTab datasetId={datasetId} />}
        {tab === "sop" && <SopTab datasetId={datasetId} />}
        {tab === "p-spend" && <ParcelSpendTab datasetId={datasetId} />}
        {tab === "p-intel" && <ParcelIntelTab datasetId={datasetId} />}
        {tab === "p-margin" && <ParcelMarginTab datasetId={datasetId} />}
        {tab === "p-variance" && <ParcelVarianceTab datasetId={datasetId} />}
        {tab === "p-contract" && <ParcelContractTab datasetId={datasetId} />}
        {tab === "audit" && <FreightAuditTab datasetId={datasetId} />}
        {tab === "intl" && <IntlRollupTab datasetId={datasetId} />}
      </div>
    </>
  );
}

// ============================ Dataset selector ============================
function DatasetSelector({ value, onChange, datasets, activeDataset }) {
  return (
    <div className="text-right">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mb-1">
        Active dataset
      </div>
      <select value={value} onChange={(e) => onChange(e.target.value)}
              data-testid="ra-dataset-select"
              className="bg-[#0B1320] border border-purple-500/30 text-white text-sm px-3 py-2 rounded min-w-[260px]">
        <option value="">All bookings (default)</option>
        {datasets.map((d) => (
          <option key={d.dataset_id} value={d.dataset_id}>
            {d.client_name} · {d.dataset_name} ({d.row_count} rows)
          </option>
        ))}
      </select>
      {activeDataset && (
        <div className="text-[10px] text-slate-500 font-mono mt-1">
          {activeDataset.row_count} rows · {(activeDataset.uploaded_at || "").slice(0, 10)}
        </div>
      )}
    </div>
  );
}

// ============================ 0 · DATASETS UPLOAD ============================
function DatasetsTab({ datasets, reload, setDatasetId }) {
  const [form, setForm] = useState({ client_id: "", client_name: "", dataset_name: "", dataset_type: "parcel" });
  const [file, setFile] = useState(null);
  const [template, setTemplate] = useState(null);
  const [uploading, setUploading] = useState(false);
  useEffect(() => {
    api.get("/research-analytics/sample-csv-template").then(({ data }) => setTemplate(data));
  }, []);

  const upload = async () => {
    if (!file) return toast.error("Choose a CSV file");
    if (!form.client_id || !form.client_name || !form.dataset_name) return toast.error("All fields required");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("client_id", form.client_id);
      fd.append("client_name", form.client_name);
      fd.append("dataset_name", form.dataset_name);
      fd.append("dataset_type", form.dataset_type);
      const tok = localStorage.getItem("tms_session_token") || "";
      const r = await fetch(`${BACKEND_URL}/api/research-analytics/datasets/upload`, {
        method: "POST", body: fd, credentials: "include",
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
      });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      toast.success(`Loaded ${data.row_count} rows`);
      setDatasetId(data.dataset_id);
      setFile(null); setForm({ client_id: "", client_name: "", dataset_name: "", dataset_type: "parcel" });
      reload();
    } catch (e) { toast.error("Upload failed: " + (e.message || "").slice(0, 200)); }
    finally { setUploading(false); }
  };
  const downloadSample = () => {
    if (!template) return;
    const blob = new Blob([template.sample_csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "sample_logistics.csv"; a.click();
    URL.revokeObjectURL(url);
  };
  const remove = async (id) => {
    if (!window.confirm("Delete dataset and all rows?")) return;
    await api.delete(`/research-analytics/datasets/${id}`);
    toast.success("Deleted"); reload();
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="ds-upload-card">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Upload size={16} className="text-purple-300" /> Upload client dataset
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          CSV with shipment-level data. Recognized columns: <span className="font-mono text-cyan-300">
          {template?.recognized_columns.slice(0, 12).join(", ")}…</span>
          <button className="text-purple-300 underline ml-2" onClick={downloadSample} data-testid="ds-sample">
            download sample
          </button>
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <F label="Client ID *" value={form.client_id} onChange={(v) => setForm({ ...form, client_id: v })} testId="ds-client-id" />
          <F label="Client name *" value={form.client_name} onChange={(v) => setForm({ ...form, client_name: v })} testId="ds-client-name" />
          <F label="Dataset name *" value={form.dataset_name} onChange={(v) => setForm({ ...form, dataset_name: v })} testId="ds-name" />
          <Select label="Type" value={form.dataset_type} onChange={(v) => setForm({ ...form, dataset_type: v })}
                  opts={["parcel", "ocean", "air", "ltl", "tl", "mixed"]} />
        </div>
        <div className="mt-3 flex gap-2 items-end">
          <div className="flex-1">
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">CSV file</Label>
            <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0])}
                   className="text-xs text-slate-300 file:bg-purple-500 file:text-black file:border-0 file:px-3 file:py-1 file:rounded file:mr-3 file:text-xs"
                   data-testid="ds-file" />
          </div>
          <Button onClick={upload} disabled={uploading}
                   className="bg-purple-500 hover:bg-purple-400 text-white" data-testid="ds-upload">
            {uploading ? "Uploading…" : <><Upload size={14} className="mr-2" /> Upload</>}
          </Button>
        </div>
      </Card>

      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Uploaded datasets · {datasets.length}</h3>
        {datasets.length === 0 ? <Empty msg="No datasets yet — upload a client CSV to get started." /> : (
          <div className="space-y-1.5">
            {datasets.map((d) => (
              <div key={d.dataset_id} className="px-3 py-2 rounded border bg-white/[0.02] flex justify-between items-center flex-wrap gap-2"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={`ds-row-${d.dataset_id}`}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm">
                    <span className="font-bold">{d.client_name}</span>
                    <span className="text-slate-500 ml-2">· {d.dataset_name}</span>
                    <span className="text-[10px] font-mono uppercase tracking-wider text-purple-300 ml-2 px-1.5 py-0.5 border border-purple-500/30 rounded">{d.dataset_type}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    {d.dataset_id} · {d.row_count} rows · {d.columns.length} cols · {(d.uploaded_at || "").slice(0, 16)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setDatasetId(d.dataset_id)} className="text-cyan-300 h-7 text-xs">Use</Button>
                  <Button size="sm" variant="ghost" onClick={() => remove(d.dataset_id)} className="text-red-400 h-7 w-7 p-0">
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ 1 · SCP ============================
function ScpTab({ datasetId }) {
  const [data, setData] = useState(null);
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const load = () => api.get("/research-analytics/supply-chain-planning",
    { params: { dataset_id: datasetId || undefined, service_level: serviceLevel } })
    .then(({ data }) => setData(data));
  useEffect(() => { load(); }, [datasetId, serviceLevel]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5" data-testid="scp-card">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Boxes size={16} className="text-purple-300" /> Supply Chain Planning
        </h3>
        <div className="flex items-center gap-3 mb-4">
          <Label className="text-[10px] font-mono uppercase text-slate-400">Service level</Label>
          <select value={serviceLevel} onChange={(e) => setServiceLevel(parseFloat(e.target.value))}
                  className="bg-[#0B1320] border border-white/10 text-white text-xs px-2 py-1 rounded">
            {[0.90, 0.95, 0.97, 0.99, 0.999].map((v) => <option key={v} value={v}>{(v * 100).toFixed(1)}%</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Lanes analyzed" value={data.lanes_analyzed} color="cyan" />
          <Stat label="Network nodes" value={data.nodes} />
          <Stat label="Countries" value={data.countries_in_network} color="amber" />
          <Stat label="Z-score (SS)" value={data.z_score} color="purple" />
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Lead-time + safety-stock by lane</h3>
        {data.lanes.length === 0 ? <Empty msg="No lead-time data in dataset (column: transit_days)" /> : (
          <div className="space-y-1.5">
            {data.lanes.slice(0, 20).map((l, i) => (
              <div key={i} className="px-3 py-2 rounded border bg-white/[0.02] grid grid-cols-2 md:grid-cols-6 gap-2 text-xs"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }}>
                <span className="font-mono col-span-2">{l.lane}</span>
                <span><span className="text-slate-500">avg LT </span>{l.avg_lead_time_days}d</span>
                <span><span className="text-slate-500">σ </span>{l.stdev_days}d</span>
                <span><span className="text-slate-500">SS </span><span className="text-purple-300">{l.safety_stock_days}d</span></span>
                <span><span className="text-slate-500">reorder </span><span className="text-cyan-300">{l.reorder_point_days}d</span></span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ 2 · DEMAND ============================
function DemandTab({ datasetId }) {
  const [data, setData] = useState(null);
  const [params, setParams] = useState({ horizon_periods: 12, period: "month", seasonality: 12 });
  const run = () => api.post("/research-analytics/demand-planning",
    { ...params, dataset_id: datasetId || undefined }).then(({ data }) => setData(data));
  useEffect(() => { run(); }, [datasetId]);
  const chartData = useMemo(() => {
    if (!data) return [];
    return [
      ...(data.history || []).map((h) => ({ label: h.period, actual: h.actual })),
      ...(data.forecast || []).map((f) => ({ label: f.period, forecast: f.forecast, low: f.low_80, high: f.high_80 })),
    ];
  }, [data]);
  return (
    <>
      <Card className="hud-surface p-5" data-testid="demand-card">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <TrendingUp size={16} className="text-cyan-300" /> Demand Planning · Forecast
        </h3>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <Select label="Period" value={params.period} onChange={(v) => setParams({ ...params, period: v })} opts={["month", "week", "quarter"]} />
          <F label="Horizon" type="number" value={params.horizon_periods} onChange={(v) => setParams({ ...params, horizon_periods: parseInt(v) || 12 })} />
          <F label="Seasonality" type="number" value={params.seasonality} onChange={(v) => setParams({ ...params, seasonality: parseInt(v) || 12 })} />
        </div>
        <Button onClick={run} className="bg-cyan-500 text-black hover:bg-cyan-400" data-testid="demand-run">Run forecast</Button>
        {data && (
          <>
            <div className="grid grid-cols-3 gap-3 mt-4 mb-4">
              <Stat label="Method" value={data.method?.replace(/_/g, " ")} />
              <Stat label="Baseline" value={data.baseline} color="cyan" />
              <Stat label="Last observed" value={data.last_observed} color="amber" />
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.5}/>
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="label" stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
                  <Area type="monotone" dataKey="actual" stroke="#22d3ee" fill="url(#g1)" />
                  <Line type="monotone" dataKey="forecast" stroke="#a78bfa" strokeWidth={2} strokeDasharray="4 4" />
                  <Area type="monotone" dataKey="high" stroke="none" fill="#a78bfa" fillOpacity={0.15} />
                  <Area type="monotone" dataKey="low" stroke="none" fill="#0b1320" fillOpacity={0.5} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </Card>
    </>
  );
}

// ============================ 3 · SUPPLY ============================
function SupplyTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/supply-planning", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Factory size={16} className="text-purple-300" /> Supply Planning
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Total shipments" value={data.total_shipments} />
          <Stat label="Carriers" value={data.supplier_count} color="cyan" />
          <Stat label="HHI" value={data.hhi_concentration} color="purple" />
          <Stat label="Concentration" value={data.concentration_verdict}
                color={data.concentration_verdict === "HIGH" ? "red" : data.concentration_verdict === "MODERATE" ? "amber" : "emerald"} />
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Carrier mix (top 10 by shipments)</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.carriers.slice(0, 10)} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis type="number" stroke="#64748b" fontSize={10} />
              <YAxis type="category" dataKey="carrier" stroke="#64748b" fontSize={10} width={120} />
              <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
              <Bar dataKey="shipments" fill="#a78bfa" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </>
  );
}

// ============================ 4 · SOP ============================
function SopTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/sop", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Layers3 size={16} className="text-cyan-300" /> S&OP · Demand vs Supply
        </h3>
        <div className="grid grid-cols-3 gap-3 mb-4">
          <Stat label="Avg shipments / period" value={data.avg_shipments_per_period} color="cyan" />
          <Stat label="Avg spend / period" value={`$${data.avg_spend_per_period_usd.toLocaleString()}`} color="amber" />
          <Stat label="D-S alignment" value={`${data.demand_supply_alignment_pct}%`} color="emerald" />
        </div>
        <div className="h-72">
          <ResponsiveContainer>
            <LineChart data={data.periods}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="period" stroke="#64748b" fontSize={10} />
              <YAxis yAxisId="ship" stroke="#22d3ee" fontSize={10} />
              <YAxis yAxisId="spend" orientation="right" stroke="#fbbf24" fontSize={10} />
              <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line yAxisId="ship" dataKey="shipments" stroke="#22d3ee" strokeWidth={2} />
              <Line yAxisId="spend" dataKey="spend_usd" stroke="#fbbf24" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </>
  );
}

// ============================ 5 · PARCEL SPEND ============================
function ParcelSpendTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/parcel-spend-management", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Wallet size={16} className="text-amber-300" /> Parcel Spend Management
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Stat label="Total spend" value={`$${data.total_spend_usd.toLocaleString()}`} color="amber" />
          <Stat label="Shipments" value={data.shipment_count} color="cyan" />
          <Stat label="Avg / shipment" value={`$${data.avg_cost_per_shipment}`} />
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Spend by carrier</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data.by_carrier.slice(0, 6)} dataKey="spend_usd" nameKey="name" outerRadius={80} label>
                  {data.by_carrier.slice(0, 6).map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Monthly trend</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={data.by_month}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="month" stroke="#64748b" fontSize={9} />
                <YAxis stroke="#64748b" fontSize={10} />
                <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
                <Bar dataKey="spend_usd" fill="#fbbf24" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </>
  );
}

// ============================ 6 · PARCEL INTEL ============================
function ParcelIntelTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/parcel-spend-intelligence", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <BarChart3 size={16} className="text-cyan-300" /> Parcel Spend Intelligence
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Total spend" value={`$${data.total_spend_usd.toLocaleString()}`} color="amber" />
          <Stat label="Accessorials" value={`$${data.accessorial_spend_usd.toLocaleString()}`} color="red" />
          <Stat label="Accessorial %" value={`${data.accessorial_share_pct}%`} color={data.accessorial_share_pct > 15 ? "red" : "emerald"} />
          <Stat label="Dim-weight pkgs" value={data.dim_weight_affected_shipments} color="purple" />
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Accessorial breakdown</h3>
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={data.accessorials.slice(0, 8)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="code" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={10} />
              <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
              <Bar dataKey="spend_usd" fill="#f87171" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Recommendations</h3>
        <ul className="space-y-1 text-xs text-slate-300 list-disc list-inside">
          {data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      </Card>
    </>
  );
}

// ============================ 7 · PARCEL MARGIN ============================
function ParcelMarginTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/parcel-margin", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  if (data.samples === 0) return <Card className="hud-surface p-8 text-center text-slate-500 italic">{data.note}</Card>;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Percent size={16} className="text-emerald-300" /> Parcel Margin Analysis
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Samples" value={data.samples} color="cyan" />
          <Stat label="Avg margin" value={`${data.avg_margin_pct}%`} color="emerald" />
          <Stat label="Median margin" value={`${data.median_margin_pct}%`} />
          <Stat label="Loss makers" value={data.loss_makers} color={data.loss_makers > 0 ? "red" : "emerald"} />
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3 text-emerald-300">Top winners</h3>
          <div className="space-y-1 text-xs">
            {data.top_winners.map((w, i) => (
              <div key={i} className="flex justify-between px-2 py-1 bg-emerald-500/5 rounded">
                <span>{w.carrier} · {w.service}</span>
                <span className="font-mono text-emerald-300">+{w.margin_pct}% (${w.margin_usd})</span>
              </div>
            ))}
          </div>
        </Card>
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3 text-red-300">Top losers</h3>
          <div className="space-y-1 text-xs">
            {data.top_losers.map((w, i) => (
              <div key={i} className="flex justify-between px-2 py-1 bg-red-500/5 rounded">
                <span>{w.carrier} · {w.service}</span>
                <span className="font-mono text-red-300">{w.margin_pct}% (${w.margin_usd})</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

// ============================ 8 · PARCEL VARIANCE ============================
function ParcelVarianceTab({ datasetId }) {
  const [data, setData] = useState(null);
  const [threshold, setThreshold] = useState(1.5);
  const load = () => api.get("/research-analytics/parcel-cost-variance",
    { params: { dataset_id: datasetId || undefined, z_threshold: threshold } })
    .then(({ data }) => setData(data));
  useEffect(() => { load(); }, [datasetId, threshold]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Activity size={16} className="text-amber-300" /> Parcel Cost Variance
        </h3>
        <div className="flex items-center gap-3 mb-3">
          <Label className="text-[10px] font-mono uppercase text-slate-400">Z-threshold</Label>
          <Input type="number" step="0.1" value={threshold} onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  className="w-24 bg-[#0B1320] border-white/10 text-white text-xs" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Stat label="Cells modeled" value={data.cells_modeled} />
          <Stat label="Anomalies" value={data.anomaly_count} color={data.anomaly_count > 0 ? "amber" : "emerald"} />
          <Stat label="Est. overpay" value={`$${data.estimated_overpayment_usd.toLocaleString()}`} color="red" />
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Top anomalies</h3>
        {data.anomalies.length === 0 ? <Empty msg="No anomalies above threshold." /> : (
          <div className="space-y-1.5">
            {data.anomalies.slice(0, 20).map((a, i) => (
              <div key={i} className={`px-3 py-2 rounded border ${a.direction === "OVER" ? "border-red-500/30 bg-red-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
                <div className="flex justify-between text-xs">
                  <span>{a.service} · Zone {a.zone}</span>
                  <span className="font-mono">{a.direction} · z={a.z_score}</span>
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  ${a.cost_usd} vs median ${a.median_usd} (Δ ${a.delta_usd})
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ 9 · PARCEL CONTRACT ============================
function ParcelContractTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/parcel-contract", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5 border-purple-500/20">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <FileText size={16} className="text-purple-300" /> Parcel Contract Negotiation
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Spend leverage" value={`$${data.total_parcel_spend_usd.toLocaleString()}`} color="amber" />
          <Stat label="Top carrier" value={`${data.top_carrier.name} (${data.top_carrier.share_pct}%)`} />
          <Stat label="Est. savings" value={`$${data.estimated_savings_usd.toLocaleString()}`} color="emerald" />
          <Stat label="Savings %" value={`${data.estimated_savings_pct}%`} color="emerald" />
        </div>
        <div className="mt-4 p-4 rounded border border-purple-500/30 bg-purple-500/5">
          <div className="text-xs text-purple-300 font-mono uppercase tracking-wider mb-2">Recommended term</div>
          <div className="font-display text-2xl font-bold text-white">{data.recommended_term_years} year{data.recommended_term_years > 1 ? "s" : ""}</div>
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Leverage points</h3>
        <div className="space-y-2">
          {data.leverage_points.map((l, i) => (
            <div key={i} className="px-3 py-2 rounded border bg-cyan-500/5 border-cyan-500/20">
              <div className="text-sm font-medium text-cyan-300">{l.point}</div>
              <div className="text-xs text-slate-400 mt-0.5">→ {l.action}</div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ============================ 10 · FREIGHT AUDIT ============================
function FreightAuditTab({ datasetId }) {
  const [data, setData] = useState(null);
  const [z, setZ] = useState(2.0);
  useEffect(() => {
    api.get("/research-analytics/freight-audit-analytics", { params: { dataset_id: datasetId || undefined, z_threshold: z } })
      .then(({ data }) => setData(data));
  }, [datasetId, z]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Sparkles size={16} className="text-purple-300" /> Freight Audit & Pay Analytics
        </h3>
        <div className="flex items-center gap-3 mb-3">
          <Label className="text-[10px] font-mono uppercase text-slate-400">Z-threshold</Label>
          <Input type="number" step="0.1" value={z} onChange={(e) => setZ(parseFloat(e.target.value))}
                  className="w-24 bg-[#0B1320] border-white/10 text-white text-xs" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Stat label="Lanes modeled" value={data.lanes_modeled} color="cyan" />
          <Stat label="Anomalies" value={data.anomalies} color="amber" />
          <Stat label="Recovery $" value={`$${data.estimated_recovery_usd.toLocaleString()}`} color="emerald" />
        </div>
      </Card>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-sm font-bold mb-3">Top anomalies</h3>
        <div className="space-y-1">
          {data.top_anomalies.slice(0, 20).map((a, i) => (
            <div key={i} className={`px-3 py-2 rounded border text-xs ${a.direction === "OVER" ? "border-red-500/30 bg-red-500/5" : "border-amber-500/20 bg-amber-500/5"}`}>
              <div className="flex justify-between">
                <span>{a.lane} · {a.service}</span>
                <span className="font-mono">{a.direction} · z={a.z_score}</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                Invoice ${a.invoice_usd} vs median ${a.median_usd} (Δ ${a.delta_usd})
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

// ============================ INTL ROLLUP ============================
function IntlRollupTab({ datasetId }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api.get("/research-analytics/international-rollup", { params: { dataset_id: datasetId || undefined } })
      .then(({ data }) => setData(data));
  }, [datasetId]);
  if (!data) return <Empty msg="Loading…" />;
  return (
    <>
      <Card className="hud-surface p-5">
        <h3 className="font-display text-lg font-bold mb-3 flex items-center gap-2">
          <Globe2 size={16} className="text-cyan-300" /> International Logistics Rollup
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Total shipments" value={data.total_shipments} />
          <Stat label="Cross-border" value={data.cross_border_shipments} color="cyan" />
          <Stat label="Country pairs" value={data.unique_country_pairs} color="amber" />
          <Stat label="Unique HS codes" value={data.unique_hs_codes} color="purple" />
        </div>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Top country pairs</h3>
          {data.top_country_pairs.length === 0 ? <Empty msg="No cross-border data" /> : (
            <div className="space-y-1 text-xs">
              {data.top_country_pairs.slice(0, 10).map((p, i) => (
                <div key={i} className="flex justify-between px-2 py-1 bg-white/[0.02] rounded">
                  <span className="font-mono">{p.lane}</span>
                  <span className="text-cyan-300">{p.count}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Top HS codes</h3>
          {data.top_hs_codes.length === 0 ? <Empty msg="No HS code data — add hs_code column" /> : (
            <div className="space-y-1 text-xs">
              {data.top_hs_codes.slice(0, 10).map((h, i) => (
                <div key={i} className="flex justify-between px-2 py-1 bg-white/[0.02] rounded">
                  <span className="font-mono">{h.hs_code}</span>
                  <span className="text-purple-300">{h.count}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Mode mix</h3>
          {data.mode_mix.length === 0 ? <Empty msg="No mode data" /> : (
            <div className="h-56">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={data.mode_mix} dataKey="count" nameKey="mode" outerRadius={70} label>
                    {data.mode_mix.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0b1320", border: "1px solid #334155", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
        <Card className="hud-surface p-5">
          <h3 className="font-display text-sm font-bold mb-3">Currency mix</h3>
          {data.currency_mix.length === 0 ? <Empty msg="No currency data" /> : (
            <div className="space-y-1 text-xs">
              {data.currency_mix.map((c, i) => (
                <div key={i} className="flex justify-between px-2 py-1 bg-white/[0.02] rounded">
                  <span className="font-mono">{c.currency}</span>
                  <span className="text-amber-300">{c.count}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

// ============================ shared bits ============================
function F({ label, value, onChange, type = "text", testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)}
             data-testid={testId} className="bg-[#0B1320] border-white/10 text-white" />
    </div>
  );
}
function Select({ label, value, onChange, opts }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      <select value={value} onChange={(e) => onChange(e.target.value)}
              className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10">
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}
function Stat({ label, value, color = "cyan" }) {
  const cls = color === "emerald" ? "text-emerald-300" : color === "amber" ? "text-amber-300" :
              color === "red" ? "text-red-300" : color === "purple" ? "text-purple-300" :
              color === "slate" ? "text-slate-300" : "text-cyan-300";
  return (
    <div className="p-3 rounded border bg-white/[0.02]" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className={`font-display text-xl font-bold mt-1 ${cls} truncate`}>{value}</div>
    </div>
  );
}
function Empty({ msg }) { return <Card className="hud-surface p-8 text-center text-slate-500 text-sm italic">{msg}</Card>; }
