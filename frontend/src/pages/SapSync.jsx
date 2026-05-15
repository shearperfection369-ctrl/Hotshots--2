import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { useBrandRefresh } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { Database, RefreshCw, CheckCircle2, Cloud, ChevronRight } from "lucide-react";

const STATUS_BADGE = {
  Open: "bg-yellow-500/10 text-yellow-300 border-yellow-500/30",
  "In Production": "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  "Released to Shipping": "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  Confirmed: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  "Partial Delivery": "bg-purple-500/10 text-purple-300 border-purple-500/30",
  Released: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  "Goods Issued": "bg-purple-500/10 text-purple-300 border-purple-500/30",
  "In Transit": "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  "Partial GR": "bg-yellow-500/10 text-yellow-300 border-yellow-500/30",
  Closed: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
};

export default function SapSync() {
  const [tab, setTab] = useState("so");
  const [config, setConfig] = useState(null);
  const [sales, setSales] = useState([]);
  const [purch, setPurch] = useState([]);
  const [logs, setLogs] = useState([]);
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    const [c, s, p, l] = await Promise.all([
      api.get("/sap/config"), api.get("/sap/sales-orders"),
      api.get("/sap/purchase-orders"), api.get("/sap/sync-logs"),
    ]);
    setConfig(c.data); setSales(s.data.value); setPurch(p.data.value); setLogs(l.data);
  };

  useEffect(() => { load(); }, []);
  useBrandRefresh(() => load());

  const sync = async () => {
    setSyncing(true);
    try {
      const { data } = await api.post("/sap/sync");
      toast.success(`Sync completed in ${data.duration_ms}ms`, {
        description: `${data.sales_count} SOs · ${data.purchase_count} POs`
      });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Sync failed (admin/dispatcher role required)");
    } finally { setSyncing(false); }
  };

  const importsOnly = purch.filter((p) => p.IsImport);

  return (
    <>
      <Topbar title="SAP S/4HANA Sync" subtitle="OData connector · Sales Orders · Purchase Orders" />
      <div className="p-4 md:p-6 space-y-5">

        {config && (
          <Card className="hud-surface p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">OData Connection</div>
                <h3 className="font-display text-lg font-bold flex items-center gap-2">
                  <Database size={18} className="text-cyan-400" />
                  SAP S/4HANA · System {config.system_id}
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 mt-4 text-xs">
                  <Field label="Host" value={config.host} />
                  <Field label="Service" value={config.service} mono />
                  <Field label="Client" value={config.client} />
                  <Field label="Service Account" value={config.user} mono />
                  <Field label="Auth" value={config.auth_type} />
                  <Field label="Status" value={<span className="text-emerald-400 inline-flex items-center gap-1"><CheckCircle2 size={11}/>CONNECTED</span>} />
                </div>
              </div>
              <Button data-testid="sap-sync-btn" onClick={sync} disabled={syncing} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_18px_rgba(0,229,255,0.4)] shrink-0">
                <RefreshCw size={14} className={`mr-2 ${syncing ? "animate-spin" : ""}`} />
                {syncing ? "SYNCING..." : "TRIGGER SYNC"}
              </Button>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <StatCard label="Sales Orders" value={sales.length} accent="text-cyan-400" sub="from SAP" />
          <StatCard label="Purchase Orders" value={purch.length} accent="text-emerald-400" sub="all suppliers" />
          <StatCard label="Inbound Imports" value={importsOnly.length} accent="text-purple-400" sub="via Kuehne+Nagel & intl" />
          <StatCard label="Last Sync" value={logs[0] ? new Date(logs[0].started_at).toLocaleTimeString() : "—"} accent="text-yellow-400" sub={logs[0] ? `${logs[0].duration_ms}ms` : "no syncs yet"} />
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="border-b border-white/5 px-5 py-3 flex items-center gap-1">
            {[
              { id: "so", label: "Sales Orders", count: sales.length },
              { id: "po", label: "Purchase Orders", count: purch.length },
              { id: "imports", label: "Imports Only", count: importsOnly.length },
              { id: "logs", label: "Sync Logs", count: logs.length },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                data-testid={`sap-tab-${t.id}`}
                className={`px-4 py-2 rounded-md text-xs font-mono uppercase tracking-wider transition-all ${
                  tab === t.id ? "bg-cyan-500/15 text-cyan-300" : "text-slate-400 hover:text-white"
                }`}
              >
                {t.label} <span className="opacity-60 ml-1">({t.count})</span>
              </button>
            ))}
          </div>

          {tab === "so" && <SalesTable rows={sales} />}
          {tab === "po" && <PurchaseTable rows={purch} />}
          {tab === "imports" && <PurchaseTable rows={importsOnly} />}
          {tab === "logs" && <LogsTable rows={logs} />}
        </Card>
      </div>
    </>
  );
}

function Field({ label, value, mono }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-slate-300 mt-0.5 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function StatCard({ label, value, sub, accent }) {
  return (
    <Card className="hud-surface p-5">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
      {sub && <div className="text-[10px] font-mono text-slate-500 mt-1">{sub}</div>}
    </Card>
  );
}

function SalesTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          <tr>
            <th className="text-left py-3 px-4">SO #</th>
            <th className="text-left py-3 px-4">Customer</th>
            <th className="text-left py-3 px-4">Material</th>
            <th className="text-right py-3 px-4">Qty</th>
            <th className="text-right py-3 px-4">Net Amount</th>
            <th className="text-left py-3 px-4">Plant</th>
            <th className="text-right py-3 px-4">Req. Delivery</th>
            <th className="text-left py-3 px-4">Status</th>
            <th className="text-left py-3 px-4">Incoterms</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((r) => (
            <tr key={r.SalesOrder} className="border-t border-white/5 hover:bg-white/[0.02]">
              <td className="py-2.5 px-4 text-cyan-300">{r.SalesOrder}</td>
              <td className="py-2.5 px-4 text-slate-300">{r.SoldToPartyName}<br/><span className="text-[10px] text-slate-500">{r.SoldToParty}</span></td>
              <td className="py-2.5 px-4 text-slate-300">{r.MaterialDescription}<br/><span className="text-[10px] text-slate-500">{r.Material}</span></td>
              <td className="py-2.5 px-4 text-right text-slate-300">{r.RequestedQuantity}</td>
              <td className="py-2.5 px-4 text-right text-emerald-400">${r.NetAmount.toLocaleString()}</td>
              <td className="py-2.5 px-4 text-slate-400">{r.PlantName}</td>
              <td className="py-2.5 px-4 text-right text-slate-400 text-xs">{r.RequestedDeliveryDate}</td>
              <td className="py-2.5 px-4"><Badge className={`${STATUS_BADGE[r.OverallStatus] || ""} font-mono text-[10px] uppercase`}>{r.OverallStatus}</Badge></td>
              <td className="py-2.5 px-4 text-slate-400 text-xs">{r.IncoTerms}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PurchaseTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          <tr>
            <th className="text-left py-3 px-4">PO #</th>
            <th className="text-left py-3 px-4">Supplier</th>
            <th className="text-left py-3 px-4">Component</th>
            <th className="text-right py-3 px-4">Qty</th>
            <th className="text-right py-3 px-4">Unit $</th>
            <th className="text-right py-3 px-4">Net Amount</th>
            <th className="text-left py-3 px-4">Plant</th>
            <th className="text-right py-3 px-4">Delivery</th>
            <th className="text-left py-3 px-4">Status</th>
            <th className="text-center py-3 px-4">Import</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((r) => (
            <tr key={r.PurchaseOrder} className="border-t border-white/5 hover:bg-white/[0.02]">
              <td className="py-2.5 px-4 text-cyan-300">{r.PurchaseOrder}</td>
              <td className="py-2.5 px-4 text-slate-300">{r.SupplierName}<br/><span className="text-[10px] text-slate-500">{r.Supplier}</span></td>
              <td className="py-2.5 px-4 text-slate-300">{r.MaterialDescription}<br/><span className="text-[10px] text-slate-500">{r.Material}</span></td>
              <td className="py-2.5 px-4 text-right text-slate-300">{r.OrderQuantity}</td>
              <td className="py-2.5 px-4 text-right text-slate-300">${r.NetPriceAmount}</td>
              <td className="py-2.5 px-4 text-right text-emerald-400">${r.NetAmount.toLocaleString()}</td>
              <td className="py-2.5 px-4 text-slate-400">{r.PlantName}</td>
              <td className="py-2.5 px-4 text-right text-slate-400 text-xs">{r.DeliveryDate}</td>
              <td className="py-2.5 px-4"><Badge className={`${STATUS_BADGE[r.OverallStatus] || ""} font-mono text-[10px] uppercase`}>{r.OverallStatus}</Badge></td>
              <td className="py-2.5 px-4 text-center">{r.IsImport ? <span className="text-purple-300 text-[10px] font-mono">K+N</span> : <span className="text-slate-600">—</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LogsTable({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          <tr>
            <th className="text-left py-3 px-4">Log ID</th>
            <th className="text-left py-3 px-4">Started</th>
            <th className="text-right py-3 px-4">Duration</th>
            <th className="text-right py-3 px-4">Sales</th>
            <th className="text-right py-3 px-4">Purchase</th>
            <th className="text-left py-3 px-4">Status</th>
          </tr>
        </thead>
        <tbody className="font-mono">
          {rows.map((r) => (
            <tr key={r.log_id} className="border-t border-white/5 hover:bg-white/[0.02]">
              <td className="py-2.5 px-4 text-cyan-300">{r.log_id}</td>
              <td className="py-2.5 px-4 text-slate-400 text-xs">{new Date(r.started_at).toLocaleString()}</td>
              <td className="py-2.5 px-4 text-right text-slate-300">{r.duration_ms}ms</td>
              <td className="py-2.5 px-4 text-right text-slate-300">{r.sales_count}</td>
              <td className="py-2.5 px-4 text-right text-slate-300">{r.purchase_count}</td>
              <td className="py-2.5 px-4 text-emerald-400">✓ {r.status}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-slate-500">No sync logs yet — trigger a sync above.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
