import React, { useCallback, useEffect, useState } from "react";
import { Link2, Loader2, RefreshCw, Unplug, BookOpenCheck } from "lucide-react";
import { toast } from "sonner";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { api } from "../lib/api";

export const QuickBooksCard = () => {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => api.get("/qbo/status").then(({ data }) => setStatus(data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const connect = async () => {
    setBusy("connect");
    try {
      const { data } = await api.get("/qbo/authorize");
      window.open(data.authorization_url, "_blank");
      toast.info("Complete the QuickBooks consent in the new tab, then hit Refresh here");
    } catch (e) { toast.error(e?.response?.data?.detail || "Authorize failed"); } finally { setBusy(""); }
  };

  const disconnect = async () => {
    setBusy("disc");
    try { await api.post("/qbo/disconnect"); toast.success("QuickBooks disconnected"); load(); }
    catch (_) { toast.error("Disconnect failed"); } finally { setBusy(""); }
  };

  const syncRecent = async () => {
    setBusy("sync");
    try {
      const { data } = await api.post("/qbo/sync/recent-invoices");
      const ok = data.results.filter((r) => r.ok).length;
      toast.success(`${ok}/${data.results.length} recent invoices synced to QuickBooks`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Sync failed"); } finally { setBusy(""); }
  };

  if (!status) return null;
  return (
    <Card className="hud-surface p-4 border-emerald-500/25 mb-4" data-testid="quickbooks-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <BookOpenCheck size={15} className="text-emerald-300" />
          <span className="text-[12px] font-black text-white uppercase tracking-wider">QuickBooks Online Sync</span>
          <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono uppercase ${status.connected ? "border-emerald-400/40 text-emerald-300" : "border-slate-500/40 text-slate-400"}`} data-testid="qbo-status-pill">
            {status.connected ? `Connected · ${status.company_name || status.realm_id}` : status.configured ? "Not connected" : "Awaiting credentials"}
          </span>
          <span className="text-[9px] font-mono text-slate-600 uppercase">{status.environment}</span>
        </div>
        <div className="flex gap-2">
          <Button onClick={load} variant="outline" className="h-8 border-white/15 text-slate-300 font-mono text-[10px] uppercase" data-testid="qbo-refresh-btn">
            <RefreshCw size={11} className="mr-1" /> Refresh
          </Button>
          {status.connected ? (
            <>
              <Button onClick={syncRecent} disabled={busy === "sync"} data-testid="qbo-sync-btn"
                      className="h-8 bg-emerald-500 hover:bg-emerald-400 text-black font-bold font-mono text-[10px] uppercase">
                {busy === "sync" ? <Loader2 size={11} className="mr-1 animate-spin" /> : null} Sync Recent Invoices
              </Button>
              <Button onClick={disconnect} disabled={busy === "disc"} variant="outline" data-testid="qbo-disconnect-btn"
                      className="h-8 border-red-500/40 text-red-300 font-mono text-[10px] uppercase">
                <Unplug size={11} className="mr-1" /> Disconnect
              </Button>
            </>
          ) : status.configured ? (
            <Button onClick={connect} disabled={busy === "connect"} data-testid="qbo-connect-btn"
                    className="h-8 bg-emerald-500 hover:bg-emerald-400 text-black font-bold font-mono text-[10px] uppercase">
              {busy === "connect" ? <Loader2 size={11} className="mr-1 animate-spin" /> : <Link2 size={11} className="mr-1" />} Connect to QuickBooks
            </Button>
          ) : null}
        </div>
      </div>
      {!status.configured && (
        <div className="text-[10px] font-mono text-slate-400 space-y-0.5" data-testid="qbo-needs">
          <div className="text-amber-300 uppercase font-bold">Needs Intuit developer credentials in backend/.env:</div>
          {status.needs.map((n) => <div key={n} className="flex gap-1.5"><span className="text-amber-400">▸</span>{n}</div>)}
        </div>
      )}
      {status.connected && (
        <p className="text-[10px] font-mono text-slate-500">
          Shipper invoices push as QBO Invoices (Freight Services item) · payments record via Receive Payment · last sync: {status.last_sync ? status.last_sync.slice(0, 16).replace("T", " ") : "never"}
        </p>
      )}
    </Card>
  );
};
