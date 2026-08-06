import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { Trash2, Plus, TrendingUp } from "lucide-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export const TcMoney = () => {
  const [pnl, setPnl] = useState(null);
  const [exp, setExp] = useState(null);
  const [form, setForm] = useState({ date: "", category: "supplies", vendor: "", desc: "", amount: "" });

  const load = useCallback(() => {
    api.get("/truck-cleaning/pnl").then(({ data }) => setPnl(data)).catch(() => {});
    api.get("/truck-cleaning/expenses").then(({ data }) => setExp(data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async (e) => {
    e.preventDefault();
    if (!Number(form.amount)) { toast.error("Amount required"); return; }
    try {
      await api.post("/truck-cleaning/expenses", { ...form, amount: Number(form.amount) });
      toast.success("Expense logged");
      setForm({ date: "", category: "supplies", vendor: "", desc: "", amount: "" });
      load();
    } catch (e2) { toast.error(e2?.response?.data?.detail || "Save failed"); }
  };
  const del = async (id) => {
    try { await api.delete(`/truck-cleaning/expenses/${id}`); load(); } catch { toast.error("Delete failed"); }
  };

  if (!pnl || !exp) return <div className="text-slate-500 font-mono text-sm">Loading P&L…</div>;
  return (
    <div className="space-y-4" data-testid="tc-money">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="tc-pnl-tiles">
        {[["Revenue (jobs done)", `$${pnl.revenue.toLocaleString()}`, "#F59E0B"],
          ["Expenses logged", `$${pnl.expenses_total.toLocaleString()}`, "#F87171"],
          ["Net (rev − exp)", `$${pnl.net.toLocaleString()}`, pnl.net >= 0 ? "#34D399" : "#F87171"],
          ["Est. COGS in revenue", `$${pnl.cogs_estimate.toLocaleString()}`, "#94A3B8"]].map(([l, v, c]) => (
          <div key={l} className="p-3 rounded-2xl border border-white/10 bg-slate-950/70">
            <div className="text-xl font-black tabular-nums" style={{ color: c }}>{v}</div>
            <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{l}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-pnl-chart">
          <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2"><TrendingUp size={14} className="text-emerald-400" /> Revenue vs Expenses by month</h3>
          <div style={{ height: 220 }}>
            <ResponsiveContainer>
              <AreaChart data={pnl.series}>
                <XAxis dataKey="month" tick={{ fill: "#64748B", fontSize: 10 }} />
                <YAxis tick={{ fill: "#64748B", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0D1117", border: "1px solid #ffffff20", fontSize: 12 }} />
                <Area dataKey="revenue" stroke="#F59E0B" fill="#F59E0B22" name="Revenue" />
                <Area dataKey="expenses" stroke="#F87171" fill="#F8717122" name="Expenses" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {Object.entries(pnl.by_category).map(([k, v]) => (
              <span key={k} className="px-2.5 py-1 rounded-full border border-white/10 text-[10px] font-mono text-slate-400">{k}: ${v.toLocaleString()}</span>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-expense-panel">
          <h3 className="text-sm font-bold text-white mb-3">Log an expense</h3>
          <form onSubmit={add} className="grid grid-cols-2 gap-2 mb-3" data-testid="tc-expense-form">
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })}
              className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-slate-300" data-testid="tc-exp-date" />
            <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
              className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-slate-300" data-testid="tc-exp-category">
              {(exp.categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} placeholder="Vendor (Amazon, Harbor Freight…)"
              className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white" data-testid="tc-exp-vendor" />
            <input type="number" step="0.01" min="0" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="Amount $ *"
              className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white" data-testid="tc-exp-amount" />
            <input value={form.desc} onChange={(e) => setForm({ ...form, desc: e.target.value })} placeholder="What was it for?"
              className="h-10 px-3 rounded-xl bg-[#11151F] border border-white/10 text-sm text-white col-span-2" data-testid="tc-exp-desc" />
            <button className="col-span-2 h-10 rounded-full bg-amber-500 text-black text-xs font-black flex items-center justify-center gap-1" data-testid="tc-exp-submit">
              <Plus size={13} /> LOG EXPENSE
            </button>
          </form>
          <div className="space-y-1.5 max-h-[220px] overflow-y-auto">
            {exp.expenses.map((x) => (
              <div key={x.expense_id} className="p-2.5 rounded-lg border border-white/10 bg-white/[0.02] flex items-center justify-between" data-testid={`tc-exp-row-${x.expense_id}`}>
                <div>
                  <div className="text-xs text-white">{x.vendor || x.category}{x.desc ? ` — ${x.desc}` : ""}</div>
                  <div className="text-[9px] font-mono text-slate-500">{x.date} · {x.category}</div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-red-300">-${x.amount.toLocaleString()}</span>
                  <button onClick={() => del(x.expense_id)} className="text-red-400/60 hover:text-red-300" data-testid={`tc-exp-del-${x.expense_id}`}><Trash2 size={12} /></button>
                </div>
              </div>
            ))}
            {!exp.expenses.length && <div className="py-6 text-center text-slate-500 text-sm">No expenses yet — log fuel, supplies and gear here for a true P&L.</div>}
          </div>
        </Card>
      </div>
    </div>
  );
};
