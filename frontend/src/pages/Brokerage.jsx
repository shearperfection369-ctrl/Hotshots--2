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
  Wallet,
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
      const res = await fetch(`${BACKEND_URL}/api/brokerage/forms/fill`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("session_token") || ""}` },
        body: JSON.stringify({ form_id: active.id, fields }),
      });
      if (!res.ok) throw new Error("PDF generation failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${active.id}-${Date.now()}.pdf`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`Saved ${active.name}.pdf`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
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
  return (
    <MarkdownDocTab
      endpoint="/brokerage/business-plan"
      eyebrow="Operating Document"
      title="Orisei Freight Solutions · Business Plan"
      icon={BookOpen}
      testidScope="brokerage-plan"
    />
  );
}

// ============================================================
//                     COST ANALYSIS TAB
// ============================================================
function CostAnalysisTab() {
  return (
    <MarkdownDocTab
      endpoint="/brokerage/cost-analysis"
      eyebrow="Real-World Cost"
      title="Hardware · Services · Operating Spend"
      icon={Wallet}
      testidScope="brokerage-costs"
    />
  );
}

// ============================================================
//        SHARED · Markdown document tab renderer
// ============================================================
function MarkdownDocTab({ endpoint, eyebrow, title, icon: Icon, testidScope }) {
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
