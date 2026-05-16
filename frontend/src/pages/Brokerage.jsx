import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  Truck, DollarSign, FileText, Sparkles, TrendingUp, TrendingDown, BarChart3,
  Building2, Calculator, Plug, Send, CheckCircle2, AlertCircle, Loader2, Download,
  ArrowUpRight, ArrowDownRight, Zap, Receipt, FileSpreadsheet, Bot, Plus, BookOpen, Printer,
  Wallet, Server, Mail, Linkedin, Eye,
} from "lucide-react";
import { api, BACKEND_URL } from "../lib/api";
import { useBrandRefresh } from "../lib/branding";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Brokerage — single-page hub for the freight-brokerage operation.
 * Sections: Dashboard · Load Boards · Accounting · Forms · AI Assistant
 */
const TABS = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "boards",    label: "Load Boards", icon: Truck },
  { id: "accounting", label: "Accounting", icon: Calculator },
  { id: "forms",     label: "Forms Library", icon: FileText },
  { id: "plan",      label: "Business Plan", icon: BookOpen },
  { id: "costs",     label: "Cost Analysis", icon: Wallet },
  { id: "infra",     label: "Self-Host", icon: Server },
  { id: "ai",        label: "AI Assistant", icon: Sparkles },
];

export default function Brokerage() {
  const [tab, setTab] = useState("dashboard");
  const [dash, setDash] = useState(null);
  const loadDash = () => api.get("/brokerage/dashboard").then(({ data }) => setDash(data)).catch(() => {});
  useEffect(() => { loadDash(); const t = setInterval(loadDash, 30_000); return () => clearInterval(t); }, []);
  useBrandRefresh(() => loadDash());

  return (
    <>
      <Topbar title="Brokerage · Command Deck" subtitle="Load boards · margins · accounting · compliance · AI" />
      <div className="p-4 md:p-6 space-y-4">
        {/* Tab strip */}
        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="brokerage-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`brokerage-tab-${id}`}
              className={`group inline-flex items-center gap-2 px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition border whitespace-nowrap ${
                tab === id
                  ? "bg-cyan-500 text-black border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.35)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-200"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "dashboard" && <DashboardTab dash={dash} refresh={loadDash} />}
        {tab === "boards"    && <BoardsTab refresh={loadDash} />}
        {tab === "accounting" && <AccountingTab refresh={loadDash} />}
        {tab === "forms"     && <FormsTab />}
        {tab === "plan"      && <BusinessPlanTab />}
        {tab === "costs"     && <CostAnalysisTab />}
        {tab === "infra"     && <HomeOfficeTab />}
        {tab === "ai"        && <AITab />}
      </div>
    </>
  );
}

// ============================================================
//                     DASHBOARD TAB
// ============================================================
function DashboardTab({ dash, refresh }) {
  if (!dash) return <Loader />;
  const { pnl, margins, top_loads, quickbooks, boards_meta } = dash;
  const meta = Object.fromEntries(boards_meta.map((b) => [b.id, b]));
  return (
    <div className="space-y-4">
      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="brokerage-kpi-strip">
        <Kpi label="Revenue (YTD)"   value={`$${fmt(pnl.revenue_usd)}`}   accent="text-emerald-300" icon={DollarSign} />
        <Kpi label="Gross Margin"    value={`$${fmt(pnl.gross_margin_usd)}`} sub={`${pnl.gross_margin_pct}% of revenue`} accent="text-cyan-300" icon={TrendingUp} />
        <Kpi label="A/R Open"         value={`$${fmt(pnl.ar_open_usd)}`}    sub={`${pnl.invoice_count} invoices`} accent="text-yellow-300" icon={Receipt} />
        <Kpi label="Net Income"      value={`$${fmt(pnl.net_income_usd)}`}  accent={pnl.net_income_usd >= 0 ? "text-emerald-300" : "text-red-300"} icon={pnl.net_income_usd >= 0 ? ArrowUpRight : ArrowDownRight} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* AI top loads */}
        <Card className="hud-surface p-4 lg:col-span-2" data-testid="brokerage-top-loads">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">AI Match · Cross-Board</div>
              <h3 className="font-display text-lg font-bold flex items-center gap-2"><Sparkles size={16} className="text-cyan-400" /> Top Loads Right Now</h3>
            </div>
            <button onClick={refresh} className="text-[10px] font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-200">Refresh</button>
          </div>
          <div className="space-y-2">
            {top_loads.map((l) => {
              const board = meta[l.board_id] || {};
              return (
                <div key={l.load_id} className="grid grid-cols-12 gap-2 items-center p-2.5 rounded bg-white/[0.02] border border-white/5 hover:border-cyan-500/30 transition">
                  <div className="col-span-3 flex items-center gap-2">
                    <div className="w-2 h-8 rounded-sm" style={{ background: board.color || "#06B6D4" }} />
                    <div className="min-w-0">
                      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{board.name}</div>
                      <div className="text-xs text-slate-200 truncate" title={l.load_id}>{l.load_id}</div>
                    </div>
                  </div>
                  <div className="col-span-3 text-xs text-slate-200 truncate">
                    {l.origin} → {l.destination}
                    <div className="text-[10px] text-slate-500 font-mono">{l.miles}mi · {l.equipment}</div>
                  </div>
                  <div className="col-span-2 font-mono text-sm text-slate-200 text-right">
                    ${fmt(l.rate_usd)}
                    <div className="text-[10px] text-slate-500">${l.rpm}/mi</div>
                  </div>
                  <div className="col-span-2 font-mono text-sm text-emerald-300 text-right">
                    ${fmt(l.forecast_margin_usd)}
                    <div className="text-[10px] text-slate-500">{l.margin_pct}% margin</div>
                  </div>
                  <div className="col-span-2 flex flex-col items-end gap-1">
                    <ScoreBadge score={l.ai_score} />
                    <div className="flex gap-1 flex-wrap justify-end">
                      {l.ai_tags?.map((t) => <span key={t} className="text-[8px] font-mono uppercase px-1 py-0.5 rounded bg-cyan-500/10 text-cyan-300">{t}</span>)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* QuickBooks status */}
        <Card className="hud-surface p-4" data-testid="brokerage-qb-card">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Integration</div>
          <h3 className="font-display text-lg font-bold flex items-center gap-2"><Plug size={16} className="text-cyan-400" /> QuickBooks Online</h3>
          <QbControls qb={quickbooks} onChange={refresh} />
        </Card>
      </div>

      {/* Margin by board */}
      <Card className="hud-surface p-4" data-testid="brokerage-margin-table">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Margin Scorecard</div>
            <h3 className="font-display text-lg font-bold">By Load Board</h3>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              <tr><th className="text-left py-2 px-3">Board</th><th className="text-right py-2 px-3">Booked</th><th className="text-right py-2 px-3">Settled</th><th className="text-right py-2 px-3">Forecast Margin</th><th className="text-right py-2 px-3">Settled Margin</th><th className="text-right py-2 px-3">Win %</th></tr>
            </thead>
            <tbody className="font-mono">
              {margins.by_board.map((b) => (
                <tr key={b.board_id} className="border-t border-white/5">
                  <td className="py-2.5 px-3"><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: b.color }} />{b.name}</td>
                  <td className="py-2.5 px-3 text-right text-slate-200 tabular-nums">{b.loads_booked}</td>
                  <td className="py-2.5 px-3 text-right text-slate-200 tabular-nums">{b.loads_settled}</td>
                  <td className="py-2.5 px-3 text-right text-slate-300 tabular-nums">${fmt(b.forecast_margin_usd)}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-300 tabular-nums">${fmt(b.settled_margin_usd)}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums">
                    <span className={b.win_rate >= 90 ? "text-emerald-300" : b.win_rate >= 70 ? "text-yellow-300" : "text-red-300"}>{b.win_rate}%</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function QbControls({ qb, onChange }) {
  const [busy, setBusy] = useState(false);
  const connect = async () => {
    setBusy(true);
    try {
      await api.post("/brokerage/quickbooks/connect", { company: "" });
      toast.success("Connected to QuickBooks (mocked OAuth)");
      onChange();
    } catch (e) { toast.error("Connect failed"); } finally { setBusy(false); }
  };
  const sync = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/brokerage/quickbooks/sync");
      toast.success(`Synced · ${data.synced_invoices} invoices, ${data.synced_expenses} expenses`);
      onChange();
    } catch (e) { toast.error("Sync failed"); } finally { setBusy(false); }
  };
  const disconnect = async () => {
    if (!window.confirm("Disconnect QuickBooks?")) return;
    setBusy(true);
    try {
      await api.post("/brokerage/quickbooks/disconnect");
      toast.success("Disconnected");
      onChange();
    } catch (e) { toast.error("Failed"); } finally { setBusy(false); }
  };
  if (!qb?.connected) {
    return (
      <div className="mt-3 space-y-3">
        <Badge className="bg-slate-500/20 text-slate-300 border-slate-500/30">Not connected</Badge>
        <p className="text-xs text-slate-400">Sync invoices, expenses, and the P&L straight into QuickBooks Online. (Mocked OAuth — flip to real flow when you have a Dev App.)</p>
        <Button onClick={connect} disabled={busy} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="qb-connect-btn">
          {busy ? <Loader2 className="animate-spin" size={14} /> : <Plug size={13} className="mr-1.5" />} Connect to QuickBooks
        </Button>
      </div>
    );
  }
  return (
    <div className="mt-3 space-y-3" data-testid="qb-connected">
      <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30"><CheckCircle2 size={11} className="mr-1" /> Connected</Badge>
      <div className="text-xs text-slate-400">{qb.company}</div>
      <div className="text-[10px] font-mono text-slate-500">Realm: {qb.realm_id}</div>
      <div className="text-xs text-slate-300">{qb.pending_invoices} invoices · {qb.pending_expenses} expenses pending</div>
      {qb.last_sync_at && <div className="text-[10px] font-mono text-slate-500">Last sync: {new Date(qb.last_sync_at).toLocaleString()}</div>}
      <Button onClick={sync} disabled={busy} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="qb-sync-btn">
        {busy ? <Loader2 className="animate-spin" size={14} /> : <Zap size={13} className="mr-1.5" />} Sync Now
      </Button>
      <button onClick={disconnect} className="w-full text-[10px] font-mono uppercase tracking-wider text-slate-500 hover:text-red-400">Disconnect</button>
    </div>
  );
}

// ============================================================
//                     BOARDS TAB
// ============================================================
function BoardsTab({ refresh }) {
  const [boards, setBoards] = useState([]);
  const [active, setActive] = useState("dat");
  const [loads, setLoads] = useState([]);
  const [book, setBook] = useState(null);
  const [carrier, setCarrier] = useState("");
  const [carrierMc, setCarrierMc] = useState("");

  useEffect(() => { api.get("/brokerage/boards").then(({ data }) => setBoards(data.boards)).catch(() => {}); }, []);
  useEffect(() => {
    if (!active) return;
    api.get(`/brokerage/boards/${active}/loads`).then(({ data }) => setLoads(data.loads)).catch(() => {});
  }, [active]);

  const doBook = async () => {
    if (!book || !carrier.trim()) { toast.error("Carrier name required"); return; }
    try {
      await api.post("/brokerage/loads/book", {
        load_id: book.load_id, board_id: book.board_id, carrier_name: carrier, carrier_mc: carrierMc,
      });
      toast.success(`Booked ${book.load_id}`);
      setBook(null); setCarrier(""); setCarrierMc(""); refresh();
    } catch (e) { toast.error("Booking failed"); }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="boards-grid">
        {boards.map((b) => (
          <button
            key={b.id}
            onClick={() => setActive(b.id)}
            data-testid={`board-${b.id}`}
            className={`text-left p-3 rounded border transition relative overflow-hidden ${
              active === b.id ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 hover:border-white/30 bg-white/[0.02]"
            }`}
          >
            <div className="absolute inset-y-0 left-0 w-1" style={{ background: b.color }} />
            <div className="ml-2">
              <div className="text-xs font-bold text-slate-200">{b.name}</div>
              <div className="text-[10px] font-mono text-slate-500 mt-0.5">{b.subscription_tier}</div>
              <div className="text-[10px] font-mono text-cyan-300 mt-1">{b.live_loads} live</div>
            </div>
          </button>
        ))}
      </div>

      <Card className="hud-surface p-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">{active.toUpperCase()} · Live Postings</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              <tr><th className="text-left py-2 px-3">Load</th><th className="text-left py-2 px-3">Lane</th><th className="text-right py-2 px-3">Rate</th><th className="text-right py-2 px-3">RPM</th><th className="text-right py-2 px-3">Margin</th><th className="text-right py-2 px-3">AI</th><th className="text-right py-2 px-3"></th></tr>
            </thead>
            <tbody className="font-mono">
              {loads.map((l) => (
                <tr key={l.load_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="py-2.5 px-3">
                    <div className="text-slate-200">{l.load_id}</div>
                    <div className="text-[10px] text-slate-500">{l.equipment} · {l.weight_lbs.toLocaleString()}lbs</div>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">{l.origin} → {l.destination}<div className="text-[10px] text-slate-500">{l.miles}mi</div></td>
                  <td className="py-2.5 px-3 text-right text-slate-200 tabular-nums">${fmt(l.rate_usd)}</td>
                  <td className="py-2.5 px-3 text-right text-slate-300 tabular-nums">${l.rpm}</td>
                  <td className="py-2.5 px-3 text-right text-emerald-300 tabular-nums">${fmt(l.forecast_margin_usd)}<div className="text-[10px] text-slate-500">{l.margin_pct}%</div></td>
                  <td className="py-2.5 px-3 text-right"><ScoreBadge score={l.ai_score} compact /></td>
                  <td className="py-2.5 px-3 text-right">
                    <Button size="sm" data-testid={`book-${l.load_id}`} onClick={() => setBook(l)} className="h-7 bg-cyan-500/10 border-cyan-500/40 hover:bg-cyan-500 hover:text-black text-cyan-300 text-[10px] font-mono uppercase">
                      Book
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Dialog open={!!book} onOpenChange={(v) => !v && setBook(null)}>
        <DialogContent className="max-w-md bg-[#0B0E14] border-cyan-500/40">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Truck size={16} className="text-cyan-400" /> Book Load</DialogTitle>
            <DialogDescription className="text-xs">{book?.load_id} · {book?.origin} → {book?.destination}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-[10px] font-mono uppercase">Carrier Name *</Label><Input value={carrier} onChange={(e) => setCarrier(e.target.value)} data-testid="book-carrier-name" /></div>
            <div><Label className="text-[10px] font-mono uppercase">MC Number</Label><Input value={carrierMc} onChange={(e) => setCarrierMc(e.target.value)} data-testid="book-carrier-mc" placeholder="MC-123456" /></div>
            <div className="text-[10px] text-slate-500">Forecast margin <span className="text-emerald-300">${fmt(book?.forecast_margin_usd || 0)}</span> ({book?.margin_pct}%) will be added to the scorecard.</div>
          </div>
          <DialogFooter>
            <Button onClick={() => setBook(null)} variant="ghost">Cancel</Button>
            <Button onClick={doBook} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="book-confirm">Confirm Booking</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================
//                     ACCOUNTING TAB
// ============================================================
function AccountingTab({ refresh }) {
  const [pnl, setPnl] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [showInv, setShowInv] = useState(false);
  const [showExp, setShowExp] = useState(false);

  const load = () => Promise.all([
    api.get("/brokerage/accounting/pnl").then((r) => setPnl(r.data)),
    api.get("/brokerage/accounting/invoices").then((r) => setInvoices(r.data.invoices)),
    api.get("/brokerage/accounting/expenses").then((r) => setExpenses(r.data.expenses)),
  ]);
  useEffect(() => { load(); }, []);

  const reloadAll = () => { load(); refresh(); };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Revenue"        value={pnl ? `$${fmt(pnl.revenue_usd)}` : "—"} icon={DollarSign} accent="text-emerald-300" />
        <Kpi label="Carrier Pay"    value={pnl ? `$${fmt(pnl.carrier_pay_usd)}` : "—"} icon={Truck} accent="text-slate-200" />
        <Kpi label="Operating Exp." value={pnl ? `$${fmt(pnl.operating_expenses_usd)}` : "—"} icon={Receipt} accent="text-orange-300" />
        <Kpi label="Net Income"     value={pnl ? `$${fmt(pnl.net_income_usd)}` : "—"} icon={ArrowUpRight} accent={pnl?.net_income_usd >= 0 ? "text-emerald-300" : "text-red-300"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="hud-surface p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">A/R Aging</div>
              <h3 className="font-display text-lg font-bold">Open Invoices</h3>
            </div>
            <Button onClick={() => setShowInv(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" size="sm" data-testid="invoice-add-btn"><Plus size={13} className="mr-1" /> Invoice</Button>
          </div>
          {pnl && (
            <div className="grid grid-cols-4 gap-2 mb-3">
              {[["Current", pnl.aging.current, "text-emerald-300"], ["31-60", pnl.aging["31_60"], "text-yellow-300"], ["61-90", pnl.aging["61_90"], "text-orange-300"], ["90+", pnl.aging.over_90, "text-red-300"]].map(([l, v, c]) => (
                <div key={l} className="p-2 rounded bg-white/[0.02] border border-white/5">
                  <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{l}</div>
                  <div className={`font-mono text-sm font-bold tabular-nums ${c}`}>${fmt(v)}</div>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1" data-testid="invoices-list">
            {invoices.map((i) => (
              <div key={i.invoice_id} className="flex items-center justify-between p-2 rounded border border-white/5 hover:bg-white/[0.02] text-xs">
                <div className="min-w-0">
                  <div className="text-slate-200 font-mono">{i.invoice_id}</div>
                  <div className="text-[10px] text-slate-500 truncate">{i.customer}</div>
                </div>
                <div className="text-right shrink-0 ml-3">
                  <div className={`font-mono tabular-nums ${i.status === "paid" ? "text-emerald-300" : "text-slate-200"}`}>${fmt(i.amount_usd)}</div>
                  {i.status === "open" ? (
                    <button onClick={async () => { await api.post(`/brokerage/accounting/invoices/${i.invoice_id}/pay`); toast.success("Marked paid"); reloadAll(); }} className="text-[10px] font-mono uppercase tracking-wider text-emerald-300 hover:text-emerald-200">Mark Paid</button>
                  ) : <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[9px]">PAID</Badge>}
                </div>
              </div>
            ))}
            {invoices.length === 0 && <div className="text-xs text-slate-500 italic text-center py-3">No invoices yet.</div>}
          </div>
        </Card>

        <Card className="hud-surface p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Operating Expenses</div>
              <h3 className="font-display text-lg font-bold">Expense Ledger</h3>
            </div>
            <Button onClick={() => setShowExp(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" size="sm" data-testid="expense-add-btn"><Plus size={13} className="mr-1" /> Expense</Button>
          </div>
          {pnl?.expenses_by_category?.length > 0 && (
            <div className="mb-3 space-y-1">
              {pnl.expenses_by_category.slice(0, 5).map((c) => (
                <div key={c.category} className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">{c.category}</span>
                  <span className="font-mono tabular-nums text-slate-300">${fmt(c.amount)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1" data-testid="expenses-list">
            {expenses.map((e) => (
              <div key={e.expense_id} className="flex items-center justify-between p-2 rounded border border-white/5 hover:bg-white/[0.02] text-xs">
                <div className="min-w-0">
                  <div className="text-slate-200">{e.vendor}</div>
                  <div className="text-[10px] text-slate-500">{e.category} · {e.paid_date}</div>
                </div>
                <div className="font-mono tabular-nums text-orange-300 shrink-0">${fmt(e.amount_usd)}</div>
              </div>
            ))}
            {expenses.length === 0 && <div className="text-xs text-slate-500 italic text-center py-3">No expenses logged.</div>}
          </div>
        </Card>
      </div>

      <InvoiceDialog open={showInv} onClose={() => setShowInv(false)} onSaved={reloadAll} />
      <ExpenseDialog open={showExp} onClose={() => setShowExp(false)} onSaved={reloadAll} />
    </div>
  );
}

function InvoiceDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({ customer: "", customer_email: "", load_ref: "", amount_usd: "", due_date: "" });
  const submit = async () => {
    try {
      await api.post("/brokerage/accounting/invoices", { ...form, amount_usd: Number(form.amount_usd) });
      toast.success("Invoice created");
      onClose(); onSaved();
      setForm({ customer: "", customer_email: "", load_ref: "", amount_usd: "", due_date: "" });
    } catch (e) { toast.error("Failed"); }
  };
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40">
        <DialogHeader><DialogTitle>New Invoice</DialogTitle></DialogHeader>
        <div className="space-y-2">
          {[["customer", "Customer *"], ["customer_email", "Email"], ["load_ref", "Load Ref"], ["amount_usd", "Amount (USD) *"], ["due_date", "Due Date (YYYY-MM-DD) *"]].map(([k, l]) => (
            <div key={k}><Label className="text-[10px] font-mono uppercase">{l}</Label><Input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`invoice-${k}`} /></div>
          ))}
        </div>
        <DialogFooter><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="invoice-submit">Create</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ExpenseDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState({ category: "", vendor: "", amount_usd: "", paid_date: "", notes: "" });
  const submit = async () => {
    try {
      await api.post("/brokerage/accounting/expenses", { ...form, amount_usd: Number(form.amount_usd) });
      toast.success("Expense logged");
      onClose(); onSaved();
      setForm({ category: "", vendor: "", amount_usd: "", paid_date: "", notes: "" });
    } catch (e) { toast.error("Failed"); }
  };
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40">
        <DialogHeader><DialogTitle>New Expense</DialogTitle></DialogHeader>
        <div className="space-y-2">
          {[["category", "Category * (e.g. Fuel, Insurance, Software)"], ["vendor", "Vendor *"], ["amount_usd", "Amount (USD) *"], ["paid_date", "Paid Date (YYYY-MM-DD) *"], ["notes", "Notes"]].map(([k, l]) => (
            <div key={k}><Label className="text-[10px] font-mono uppercase">{l}</Label><Input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} data-testid={`expense-${k}`} /></div>
          ))}
        </div>
        <DialogFooter><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="expense-submit">Log</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                     FORMS TAB
// ============================================================
function FormsTab() {
  const [forms, setForms] = useState([]);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState({});
  useEffect(() => { api.get("/brokerage/forms").then(({ data }) => setForms(data.forms)).catch(() => {}); }, []);

  const grouped = useMemo(() => {
    const g = {};
    for (const f of forms) { (g[f.category] = g[f.category] || []).push(f); }
    return g;
  }, [forms]);

  const download = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const res = await api.post(
        "/brokerage/forms/fill",
        { form_id: active.id, fields },
        { responseType: "blob" }
      );
      // Guard: if the backend somehow returned JSON (e.g. an error envelope), surface it
      const ct = res.headers?.["content-type"] || "";
      if (!ct.toLowerCase().includes("pdf")) {
        const text = await res.data.text();
        throw new Error(text || "Unexpected response from server");
      }
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${active.id}-${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(`Saved ${active.name}.pdf`);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "PDF generation failed";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="hud-surface p-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Compliance · Operational · Accounting</div>
        <div className="space-y-4">
          {Object.entries(grouped).map(([cat, list]) => (
            <div key={cat}>
              <div className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">{cat}</div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {list.map((f) => (
                  <button key={f.id} onClick={() => { setActive(f); setFields({}); }}
                    data-testid={`form-${f.id}`}
                    className={`text-left p-3 rounded border transition ${active?.id === f.id ? "border-cyan-400 bg-cyan-500/10" : "border-white/10 bg-white/[0.02] hover:border-cyan-500/40"}`}>
                    <div className="flex items-start gap-2">
                      <FileSpreadsheet size={14} className="text-cyan-400 mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm text-slate-200 truncate">{f.name}</div>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5">
                          {f.fmcsa && <span className="text-yellow-300 mr-2">FMCSA</span>}
                          {f.expires_in_days && <span>Renews every {f.expires_in_days}d</span>}
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {active && (
        <Card className="hud-surface p-4" data-testid="form-fill-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">{active.category}</div>
              <h3 className="font-display text-lg font-bold">{active.name}</h3>
            </div>
            <Button onClick={download} disabled={busy} className="bg-cyan-500 text-black font-bold" data-testid="form-download">
              {busy ? <Loader2 size={14} className="animate-spin mr-1.5" /> : <Download size={13} className="mr-1.5" />} Generate PDF
            </Button>
          </div>
          <p className="text-xs text-slate-400 mb-3">Fill any of the fields below — blanks render as signature/fill-in lines on the PDF.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {["carrier_name", "mc_number", "dot_number", "email", "phone", "effective_date", "load_id", "origin", "destination", "rate_usd", "amount", "due_date"].map((k) => (
              <div key={k}>
                <Label className="text-[10px] font-mono uppercase">{k.replace(/_/g, " ")}</Label>
                <Input value={fields[k] || ""} onChange={(e) => setFields({ ...fields, [k]: e.target.value })} data-testid={`form-field-${k}`} />
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================================================
//                     AI TAB
// ============================================================
function AITab() {
  const [history, setHistory] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!q.trim() || busy) return;
    const userMsg = q;
    setHistory([...history, { role: "user", text: userMsg }]);
    setQ(""); setBusy(true);
    try {
      const { data } = await api.post("/brokerage/ai/ask", { question: userMsg });
      setHistory((h) => [...h, { role: "ai", text: data.answer }]);
    } catch (e) {
      setHistory((h) => [...h, { role: "ai", text: "Sorry — the AI is unavailable right now.", error: true }]);
    } finally { setBusy(false); }
  };
  const presets = [
    "Which load board has my best margins?",
    "Why is my net income trending negative?",
    "What invoices should I chase first?",
    "How can I cut my biggest expense category?",
  ];
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card className="hud-surface p-4 lg:col-span-2" data-testid="ai-chat-card">
        <div className="flex items-center gap-2 mb-3">
          <Bot size={18} className="text-cyan-400" />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">LEDGER · Brokerage AI</div>
            <h3 className="font-display text-lg font-bold">Claude Sonnet 4.5 · context-aware</h3>
          </div>
        </div>
        <div className="space-y-3 min-h-[300px] max-h-[60vh] overflow-y-auto bg-black/30 rounded p-3 border border-white/5 mb-3" data-testid="ai-chat-history">
          {history.length === 0 && (
            <div className="text-xs text-slate-500 italic text-center py-12">
              Ask LEDGER anything about your P&L, margins, A/R aging, or load-board mix.<br/>
              It can see your live numbers right now.
            </div>
          )}
          {history.map((m, i) => (
            <div key={i} className={m.role === "user" ? "ml-12" : "mr-12"}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-1">{m.role === "user" ? "You" : "Ledger AI"}</div>
              <div className={`p-3 rounded text-sm whitespace-pre-wrap ${m.role === "user" ? "bg-cyan-500/10 border border-cyan-500/30 text-slate-100" : m.error ? "bg-red-500/10 border border-red-500/30 text-red-200" : "bg-white/[0.02] border border-white/10 text-slate-200"}`}>{m.text}</div>
            </div>
          ))}
          {busy && <div className="text-center text-slate-400"><Loader2 className="inline animate-spin" /> Ledger is thinking…</div>}
        </div>
        <div className="flex gap-2">
          <Textarea value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything…" rows={2} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} data-testid="ai-input" className="bg-black/30 font-mono text-sm" />
          <Button onClick={submit} disabled={busy || !q.trim()} className="bg-cyan-500 text-black font-bold self-end" data-testid="ai-send"><Send size={14} /></Button>
        </div>
      </Card>

      <Card className="hud-surface p-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Suggested Questions</div>
        <div className="space-y-2">
          {presets.map((p) => (
            <button key={p} onClick={() => { setQ(p); }} className="block w-full text-left text-xs p-2.5 rounded border border-white/10 hover:border-cyan-500/40 hover:bg-cyan-500/[0.05] text-slate-300">{p}</button>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//                     BUSINESS PLAN TAB
// ============================================================
function BusinessPlanTab() {
  const [showPitch, setShowPitch] = useState(false);
  const extraActions = (
    <Button
      onClick={() => setShowPitch(true)}
      data-testid="business-plan-email-investor-btn"
      className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase tracking-wider"
    >
      <Mail size={13} className="mr-1.5" /> Email to Investor
    </Button>
  );
  return (
    <>
      <MarkdownDocTab
        endpoint="/brokerage/business-plan"
        eyebrow="Operating Document"
        title="Orisei Freight Solutions · Business Plan"
        icon={BookOpen}
        testidScope="brokerage-plan"
        extraActions={extraActions}
      />
      <InvestorPitchDialog open={showPitch} onClose={() => setShowPitch(false)} />
    </>
  );
}

// ============================================================
//                     HOME OFFICE / SELF-HOST TAB
// ============================================================
function HomeOfficeTab() {
  return (
    <MarkdownDocTab
      endpoint="/brokerage/home-office-setup"
      eyebrow="Self-Hosting Blueprint"
      title="Home-Office Server Setup · 14-Day Build Plan"
      icon={Server}
      testidScope="brokerage-infra"
    />
  );
}

// ============================================================
//                     COST ANALYSIS TAB
// ============================================================
function CostAnalysisTab() {
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [showAll, setShowAll] = useState(false);

  const load = () => {
    api.get("/brokerage/cost-summary").then(({ data }) => setSummary(data)).catch(() => {});
    api.get("/brokerage/cost-history?days=30").then(({ data }) => setHistory(data.snapshots || [])).catch(() => {});
  };
  useEffect(() => { load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, []);

  return (
    <div className="space-y-4">
      <LiveCostSnapshot
        summary={summary}
        history={history}
        showAll={showAll}
        onToggleAll={() => setShowAll((s) => !s)}
        onRefresh={load}
      />
      <MarkdownDocTab
        endpoint="/brokerage/cost-analysis"
        eyebrow="Real-World Cost"
        title="Hardware · Services · Operating Spend"
        icon={Wallet}
        testidScope="brokerage-costs"
      />
    </div>
  );
}

function LiveCostSnapshot({ summary, history, showAll, onToggleAll, onRefresh }) {
  if (!summary) {
    return (
      <Card className="hud-surface p-4 flex items-center justify-center text-slate-500" data-testid="cost-snapshot-loading">
        <Loader2 className="animate-spin mr-2" size={14} /> Loading live spend snapshot…
      </Card>
    );
  }
  const itemsToShow = showAll ? summary.items : summary.items.filter((i) => i.enabled);
  const grouped = itemsToShow.reduce((acc, it) => { (acc[it.category] ||= []).push(it); return acc; }, {});

  // Trend math
  const series = (history || []).map((s) => s.projected_monthly_total_usd || 0);
  const last = series.length ? series[series.length - 1] : summary.projected_monthly_total_usd;
  const first = series.length ? series[0] : last;
  const deltaUsd = last - first;
  const deltaPct = first ? ((deltaUsd / first) * 100) : 0;
  const deltaUp = deltaUsd >= 0;

  return (
    <Card className="hud-surface p-5" data-testid="cost-snapshot-card">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3 mb-4">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-1.5">
            <Zap size={11} /> Live Snapshot · Auto-refresh 60s
          </div>
          <h3 className="font-display text-xl font-black flex items-center gap-2">
            <Wallet size={18} className="text-cyan-400" /> Real-time Operating Spend
          </h3>
          <div className="text-[10px] font-mono text-slate-500 mt-1">
            From {summary.enabled_count} enabled connection{summary.enabled_count === 1 ? "" : "s"} · MTD settled carrier pay ${fmt(summary.settled_carrier_pay_mtd_usd)} · {series.length} days persisted
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onToggleAll}
            data-testid="cost-snapshot-toggle-all"
            className="text-[10px] font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-200 border border-white/10 hover:border-cyan-400/40 rounded px-2.5 py-1"
          >
            {showAll ? "Enabled only" : "Show all"}
          </button>
          <button
            onClick={onRefresh}
            data-testid="cost-snapshot-refresh"
            className="text-[10px] font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-200 border border-white/10 hover:border-cyan-400/40 rounded px-2.5 py-1"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* 30-day spend velocity sparkline */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4" data-testid="cost-snapshot-sparkline">
        <div className="md:col-span-2 rounded border border-white/5 bg-white/[0.02] p-3">
          <div className="flex items-center justify-between mb-1.5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">30-day projected-monthly trend</div>
            <div className="text-[10px] font-mono text-slate-500">{series.length ? `${series.length} days` : "no history yet"}</div>
          </div>
          <Sparkline values={series} testid="cost-snapshot-sparkline-svg" />
        </div>
        <div className="rounded border border-white/5 bg-white/[0.02] p-3 flex flex-col justify-center" data-testid="cost-snapshot-velocity">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500 flex items-center gap-1">
            {deltaUp ? <ArrowUpRight size={11} className="text-emerald-400" /> : <ArrowDownRight size={11} className="text-red-400" />}
            Spend velocity · 30d
          </div>
          <div className={`font-display text-2xl font-black mt-1 ${deltaUp ? "text-emerald-300" : "text-red-300"}`}>
            {deltaUp ? "+" : ""}${fmt(Math.abs(deltaUsd))}
          </div>
          <div className="text-[11px] font-mono text-slate-500">
            {deltaUp ? "+" : ""}{deltaPct.toFixed(1)}% vs 30d ago
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" data-testid="cost-snapshot-kpis">
        <Kpi label="Projected · monthly" value={`$${fmt(summary.projected_monthly_total_usd)}`} sub="infra + LLM + enabled SaaS + variable est." accent="text-cyan-300" icon={DollarSign} />
        <Kpi label="Fixed SaaS · enabled"  value={`$${fmt(summary.fixed_saas_monthly_usd)}`}    sub={`${summary.items.filter((i) => i.enabled && i.model === "fixed").length} subscriptions`} accent="text-emerald-300" icon={Receipt} />
        <Kpi label="Variable · MTD est."    value={`$${fmt(summary.variable_mtd_estimate_usd)}`} sub="factoring · per-tx" accent="text-yellow-300" icon={TrendingUp} />
        <Kpi label="Baseline infra + LLM"   value={`$${fmt(summary.baseline.total_usd)}`}      sub={summary.baseline.tier} accent="text-slate-300" icon={Plug} />
      </div>

      {/* Per-provider table grouped by category */}
      <div className="space-y-4" data-testid="cost-snapshot-table">
        {Object.entries(grouped).map(([category, list]) => (
          <div key={category}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1.5">{category}</div>
            <div className="rounded border border-white/5 overflow-hidden">
              <div className="grid grid-cols-12 gap-2 px-3 py-1.5 bg-white/[0.02] text-[10px] font-mono uppercase tracking-wider text-slate-500">
                <div className="col-span-4">Provider</div>
                <div className="col-span-3">Plan</div>
                <div className="col-span-2 text-right">Monthly</div>
                <div className="col-span-2 text-right">MTD est.</div>
                <div className="col-span-1 text-right">Status</div>
              </div>
              {list.map((it) => (
                <div key={it.provider_id} className="grid grid-cols-12 gap-2 px-3 py-2 border-t border-white/5 text-xs items-center hover:bg-white/[0.02]" data-testid={`cost-row-${it.provider_id}`}>
                  <div className="col-span-4 text-slate-200 truncate">{it.name}{it.note && <div className="text-[9px] font-mono text-slate-500 truncate">{it.note}</div>}</div>
                  <div className="col-span-3 text-slate-400 font-mono text-[11px] truncate">{it.plan}</div>
                  <div className="col-span-2 text-right tabular-nums font-mono">
                    {it.model === "fixed" ? <span className={it.enabled ? "text-emerald-300" : "text-slate-500"}>${fmt(it.monthly_cost_usd)}</span> : <span className="text-yellow-300">variable</span>}
                  </div>
                  <div className="col-span-2 text-right tabular-nums font-mono text-slate-400">
                    {it.mtd_estimate_usd ? `$${fmt(it.mtd_estimate_usd)}` : "—"}
                    {it.tuner_label && (
                      <div className="text-[9px] text-slate-600 truncate" title={it.tuner_label}>{it.tuner_label}</div>
                    )}
                  </div>
                  <div className="col-span-1 text-right">
                    {it.enabled
                      ? <span className="inline-flex items-center text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">on</span>
                      : <span className="inline-flex items-center text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/[0.04] text-slate-500 border border-white/10">off</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {!itemsToShow.length && (
          <div className="text-center py-6 text-xs text-slate-500" data-testid="cost-snapshot-empty">
            No connections enabled yet. Open <span className="text-cyan-300">Connections · Keys</span> to wire up Macropoint, Triumph, DAT, or any other provider.
          </div>
        )}
      </div>
    </Card>
  );
}

// Tiny SVG sparkline — zero deps, fits in 100% × 64px container.
function Sparkline({ values, testid }) {
  if (!values || values.length < 2) {
    return (
      <div className="h-16 flex items-center justify-center text-[10px] font-mono text-slate-600" data-testid={testid}>
        Trend appears after 2+ daily snapshots.
      </div>
    );
  }
  const W = 600, H = 64, P = 4;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = (W - 2 * P) / (values.length - 1);
  const points = values.map((v, i) => {
    const x = P + i * step;
    const y = H - P - ((v - min) / range) * (H - 2 * P);
    return [x, y];
  });
  const line = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${(W - P).toFixed(1)},${(H - P).toFixed(1)} L${P},${(H - P).toFixed(1)} Z`;
  const lastX = points[points.length - 1][0];
  const lastY = points[points.length - 1][1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-16" data-testid={testid} preserveAspectRatio="none">
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#22D3EE" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#22D3EE" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#spark-fill)" />
      <path d={line} fill="none" stroke="#22D3EE" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r="2.8" fill="#67E8F9" stroke="#0F172A" strokeWidth="1" />
    </svg>
  );
}

// ============================================================
//        SHARED · Markdown document tab renderer
// ============================================================
function MarkdownDocTab({ endpoint, eyebrow, title, icon: Icon, testidScope, extraActions }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.get(endpoint)
      .then(({ data }) => { if (!cancelled) { setDoc(data); setErr(null); } })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || "Failed to load document"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [endpoint]);

  const downloadMd = () => {
    if (!doc?.markdown) return;
    const blob = new Blob([doc.markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = doc.filename || "document.md";
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  };

  if (loading) return <Loader />;
  if (err) {
    return (
      <Card className="hud-surface p-6 border-red-500/40" data-testid={`${testidScope}-error`}>
        <div className="flex items-center gap-2 text-red-300"><AlertCircle size={16} /> {err}</div>
      </Card>
    );
  }

  const wordCount = doc?.markdown ? doc.markdown.split(/\s+/).filter(Boolean).length : 0;

  return (
    <div className="space-y-4" data-testid={`${testidScope}-tab`}>
      <Card className="hud-surface p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3" data-testid={`${testidScope}-header`}>
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">{eyebrow}</div>
          <h3 className="font-display text-xl font-black flex items-center gap-2">
            <Icon size={18} className="text-cyan-400" /> {title}
          </h3>
          <div className="text-[10px] font-mono text-slate-500 mt-1">
            {doc?.filename} · {wordCount.toLocaleString()} words · Updated {doc?.updated_at ? new Date(doc.updated_at).toLocaleDateString() : "—"}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {extraActions}
          <Button
            onClick={() => window.print()}
            data-testid={`${testidScope}-print-btn`}
            className="bg-white/5 border border-white/10 hover:border-cyan-400/40 hover:text-cyan-200 text-slate-300 font-mono text-[11px] uppercase tracking-wider"
          >
            <Printer size={13} className="mr-1.5" /> Print
          </Button>
          <Button
            onClick={downloadMd}
            data-testid={`${testidScope}-download-btn`}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase tracking-wider"
          >
            <Download size={13} className="mr-1.5" /> Download .md
          </Button>
        </div>
      </Card>

      <Card className="hud-surface p-6 md:p-10" data-testid={`${testidScope}-body`}>
        <article className="brokerage-plan-prose mx-auto max-w-3xl text-slate-200">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{doc?.markdown || ""}</ReactMarkdown>
        </article>
      </Card>
    </div>
  );
}

// ============================================================
//             INVESTOR PITCH DIALOG (email)
// ============================================================
const PITCH_LS_KEY = "investor_pitch_defaults_v1";
function InvestorPitchDialog({ open, onClose }) {
  const [toEmail, setToEmail] = useState("");
  const [toName, setToName] = useState("");
  const [founderName, setFounderName] = useState("Oliver Cummins");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [attachPdf, setAttachPdf] = useState(true);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);

  // Persist + restore defaults across sessions
  useEffect(() => {
    if (!open) return;
    try {
      const saved = JSON.parse(localStorage.getItem(PITCH_LS_KEY) || "{}");
      if (saved.founderName) setFounderName(saved.founderName);
      if (saved.linkedinUrl) setLinkedinUrl(saved.linkedinUrl);
      if (saved.replyTo) setReplyTo(saved.replyTo);
    } catch (_) {}
    api.get("/brokerage/investor-outreach?limit=10").then(({ data }) => setHistory(data.items || [])).catch(() => {});
  }, [open]);

  const persist = () => {
    try {
      localStorage.setItem(PITCH_LS_KEY, JSON.stringify({ founderName, linkedinUrl, replyTo }));
    } catch (_) {}
  };

  const payload = () => ({
    to_email: toEmail.trim(),
    to_name: toName.trim() || null,
    subject: subject.trim() || null,
    personal_note: note.trim() || null,
    founder_name: founderName.trim() || null,
    linkedin_url: linkedinUrl.trim() || null,
    reply_to: replyTo.trim() || null,
    attach_pdf: attachPdf,
  });

  const doPreview = async () => {
    if (!toEmail.trim()) { toast.error("Recipient email required"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/brokerage/investor-pitch/preview", payload());
      setPreview(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Preview failed");
    } finally {
      setBusy(false);
    }
  };

  const doSend = async ({ dryRun }) => {
    if (!toEmail.trim()) { toast.error("Recipient email required"); return; }
    persist();
    setBusy(true);
    try {
      const { data } = await api.post("/brokerage/investor-pitch", { ...payload(), dry_run: !!dryRun });
      if (dryRun) {
        toast.success(`Dry-run recorded · ${data.pdf_size_kb || 0} KB PDF prepared`);
      } else {
        toast.success(`Sent to ${toEmail}`);
      }
      // Refresh history
      api.get("/brokerage/investor-outreach?limit=10").then(({ data }) => setHistory(data.items || [])).catch(() => {});
      if (!dryRun) {
        setToEmail(""); setToName(""); setNote(""); setSubject("");
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || "Send failed";
      if (msg.includes("Resend connection not configured")) {
        toast.error("Resend not configured — open Connections · Keys to add the API key.", { duration: 5000 });
      } else {
        toast.error(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-3xl bg-slate-900 border-cyan-500/20 max-h-[90vh] overflow-y-auto" data-testid="investor-pitch-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-xl flex items-center gap-2">
            <Mail size={18} className="text-cyan-400" /> Email Business Plan to Investor
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Sends a polished HTML email (with the business-plan PDF attached) via Resend. Configure Resend in <span className="text-cyan-300">Connections · Keys</span> first, or use Dry Run to preview without sending.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 py-2">
          <Field label="Recipient email" required>
            <Input type="email" value={toEmail} onChange={(e) => setToEmail(e.target.value)} placeholder="investor@example.com" data-testid="pitch-to-email" className="bg-slate-950 border-white/10" />
          </Field>
          <Field label="Recipient name">
            <Input value={toName} onChange={(e) => setToName(e.target.value)} placeholder="Jane Doe" data-testid="pitch-to-name" className="bg-slate-950 border-white/10" />
          </Field>
          <Field label="Founder name (signature)">
            <Input value={founderName} onChange={(e) => setFounderName(e.target.value)} data-testid="pitch-founder-name" className="bg-slate-950 border-white/10" />
          </Field>
          <Field label="LinkedIn profile URL">
            <Input value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} placeholder="https://linkedin.com/in/oliver-cummins" data-testid="pitch-linkedin" className="bg-slate-950 border-white/10" />
          </Field>
          <Field label="Reply-to (optional)">
            <Input type="email" value={replyTo} onChange={(e) => setReplyTo(e.target.value)} placeholder="oliver@oriseifreight.com" data-testid="pitch-reply-to" className="bg-slate-950 border-white/10" />
          </Field>
          <Field label="Custom subject (optional)">
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="defaults to '… Business Plan & Founder Introduction'" data-testid="pitch-subject" className="bg-slate-950 border-white/10" />
          </Field>
          <div className="md:col-span-2 space-y-1">
            <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Personal note (top of email)</Label>
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} placeholder="Jane — great meeting you at MN CSCMP last month. Here's the plan I mentioned for the Twin Cities brokerage. Would love your read." data-testid="pitch-note" className="bg-slate-950 border-white/10 text-sm" />
          </div>
          <label className="md:col-span-2 flex items-center gap-2 cursor-pointer text-xs text-slate-300">
            <input type="checkbox" checked={attachPdf} onChange={(e) => setAttachPdf(e.target.checked)} data-testid="pitch-attach-pdf" className="accent-cyan-500" />
            Attach the business plan as a PDF (~50 KB)
          </label>
        </div>

        {preview && (
          <div className="rounded border border-cyan-500/30 bg-slate-950 p-3 space-y-2" data-testid="pitch-preview">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Email preview</div>
              <div className="text-[10px] font-mono text-slate-500">Subject: {preview.subject} {preview.pdf_size_kb ? `· PDF ${preview.pdf_size_kb} KB` : ""}</div>
            </div>
            <iframe srcDoc={preview.html} title="Pitch preview" className="w-full h-72 rounded bg-white" data-testid="pitch-preview-iframe" />
          </div>
        )}

        {history.length > 0 && (
          <div className="rounded border border-white/5 bg-white/[0.02] p-3" data-testid="pitch-history">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Recent outreach · {history.length}</div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {history.map((h) => (
                <div key={h.id} className="flex items-center justify-between text-[11px] font-mono">
                  <div className="text-slate-300 truncate">{h.to_email} {h.to_name && <span className="text-slate-500">· {h.to_name}</span>}</div>
                  <div className={`uppercase text-[9px] ${h.status === "sent" ? "text-emerald-300" : h.status === "dry_run" ? "text-cyan-300" : "text-red-300"}`}>{h.status}</div>
                  <div className="text-slate-600 ml-2">{new Date(h.sent_at).toLocaleDateString()}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 flex-wrap">
          <Button onClick={doPreview} disabled={busy} data-testid="pitch-preview-btn" className="bg-white/5 border border-white/10 text-slate-300 hover:border-cyan-400/40 font-mono text-[11px] uppercase mr-auto">
            <Eye size={12} className="mr-1.5" /> Preview
          </Button>
          <Button onClick={() => doSend({ dryRun: true })} disabled={busy} data-testid="pitch-dryrun-btn" className="bg-white/5 border border-white/10 text-slate-300 hover:border-yellow-400/40 font-mono text-[11px] uppercase">
            Dry Run
          </Button>
          <Button onClick={() => doSend({ dryRun: false })} disabled={busy} data-testid="pitch-send-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase">
            {busy ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <Send size={12} className="mr-1.5" />} Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, required, children }) {
  return (
    <div className="space-y-1">
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  );
}


// ============================================================
//                     SHARED
// ============================================================
function Kpi({ label, value, sub, accent = "text-cyan-300", icon: Icon }) {
  return (
    <Card className="hud-surface p-3">
      <div className="flex items-center justify-between mb-1">
        <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-500">{label}</div>
        {Icon && <Icon size={12} className="text-slate-500" />}
      </div>
      <div className={`font-display text-2xl font-black tabular-nums ${accent}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
    </Card>
  );
}

function ScoreBadge({ score, compact }) {
  const color = score >= 85 ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" : score >= 70 ? "text-cyan-300 border-cyan-500/40 bg-cyan-500/10" : "text-slate-400 border-white/10 bg-white/[0.02]";
  return <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[10px] font-bold tabular-nums border ${color}`}>{compact ? "" : <Sparkles size={9} />} {Math.round(score)}</span>;
}

function Loader() { return <div className="flex items-center justify-center p-12 text-slate-500"><Loader2 className="animate-spin mr-2" size={16} /> Loading…</div>; }

function fmt(n) {
  if (n == null) return "0";
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
}
