import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import { DollarSign, FileWarning, CheckCircle2, AlertOctagon, Send, Plus, Search } from "lucide-react";

const STATUS_BADGE = {
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  approved: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  paid: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  disputed: "bg-red-500/10 text-red-400 border-red-500/30",
  audit: "bg-purple-500/10 text-purple-400 border-purple-500/30",
};

export default function FreightPay() {
  const [bills, setBills] = useState([]);
  const [summary, setSummary] = useState(null);
  const [carrier, setCarrier] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");

  const load = async () => {
    const [{ data: b }, { data: s }] = await Promise.all([api.get("/freight-bills"), api.get("/freight-bills/summary")]);
    setBills(b); setSummary(s);
  };
  useEffect(() => { load(); }, []);

  const carriers = useMemo(() => ["ALL", ...Array.from(new Set(bills.map((b) => b.carrier))).sort()], [bills]);
  const filtered = bills.filter((b) =>
    (carrier === "ALL" || b.carrier === carrier) &&
    (status === "ALL" || b.status === status) &&
    (!q || b.invoice_no.toLowerCase().includes(q.toLowerCase()) || b.shipment_ref.toLowerCase().includes(q.toLowerCase()))
  );

  const pay = async (id) => {
    await api.post(`/freight-bills/${id}/pay`);
    toast.success("Payment processed");
    load();
  };
  const approve = async (id) => {
    await api.post(`/freight-bills/${id}/approve`);
    toast.success("Bill approved");
    load();
  };
  const submitDispute = async () => {
    if (!selected) return;
    await api.post(`/freight-bills/${selected.bill_id}/dispute`, { reason: disputeReason });
    toast.success("Dispute filed");
    setDisputeOpen(false); setDisputeReason(""); setSelected(null);
    load();
  };

  return (
    <>
      <Topbar title="Freight Audit & Pay" subtitle="Bill tracking · Accessorial audit · Carrier payments" />
      <div className="p-4 md:p-6 space-y-5">

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="Total Billed" value={`$${summary.total_billed.toLocaleString()}`} accent="text-cyan-400" Icon={DollarSign} testid="freight-total" />
            <StatCard label="Paid" value={`$${summary.paid.toLocaleString()}`} accent="text-emerald-400" Icon={CheckCircle2} />
            <StatCard label="Pending" value={`$${summary.pending.toLocaleString()}`} accent="text-yellow-400" Icon={Send} />
            <StatCard label="Disputed" value={`$${summary.disputed.toLocaleString()}`} sub={`${summary.count_disputed} bills`} accent="text-red-400" Icon={AlertOctagon} />
            <StatCard label="Overcharges Detected" value={`$${summary.overcharges_detected.toLocaleString()}`} sub="audit savings" accent="text-purple-400" Icon={FileWarning} />
          </div>
        )}

        <Card className="hud-surface p-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 px-1">Carrier Toggle</div>
          <div className="flex gap-2 overflow-x-auto pb-1" data-testid="freight-carrier-toggle">
            {carriers.map((c) => (
              <button
                key={c}
                onClick={() => setCarrier(c)}
                className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all border ${
                  carrier === c ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan" : "bg-white/[0.02] text-slate-400 border-white/5 hover:border-cyan-500/40"
                }`}
              >{c}</button>
            ))}
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-5 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input data-testid="bill-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search invoice or shipment ref..." className="pl-9 bg-[#131821] border-white/10" />
          </div>
          <div className="md:col-span-7 flex gap-1 overflow-x-auto">
            {["ALL", "pending", "approved", "audit", "disputed", "paid"].map((st) => (
              <button
                key={st} onClick={() => setStatus(st)}
                className={`px-2.5 py-1.5 rounded text-[11px] font-mono uppercase border ${
                  status === st ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/5 text-slate-400 hover:text-white"
                }`}
              >{st}</button>
            ))}
          </div>
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Invoice</th>
                  <th className="text-left py-3 px-4">Carrier</th>
                  <th className="text-left py-3 px-4">Shipment</th>
                  <th className="text-right py-3 px-4">Base</th>
                  <th className="text-right py-3 px-4">Fuel</th>
                  <th className="text-right py-3 px-4">Accessorials</th>
                  <th className="text-right py-3 px-4">Total</th>
                  <th className="text-right py-3 px-4">Variance</th>
                  <th className="text-left py-3 px-4">Status</th>
                  <th className="text-right py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {filtered.map((b) => {
                  const accTotal = (b.accessorials || []).reduce((s, a) => s + a.amount, 0);
                  return (
                    <tr key={b.bill_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                      <td className="py-2.5 px-4 text-cyan-300">{b.invoice_no}</td>
                      <td className="py-2.5 px-4 text-slate-300">{b.carrier}</td>
                      <td className="py-2.5 px-4 text-slate-400">{b.shipment_ref}</td>
                      <td className="py-2.5 px-4 text-right text-slate-300">${b.base_charge.toLocaleString()}</td>
                      <td className="py-2.5 px-4 text-right text-slate-400">${b.fuel_surcharge.toLocaleString()}</td>
                      <td className="py-2.5 px-4 text-right text-slate-400" title={b.accessorials.map((a) => `${a.code}: $${a.amount}`).join(" · ")}>
                        ${accTotal.toFixed(0)} {b.accessorials.length > 0 && <span className="text-[10px] text-slate-500">×{b.accessorials.length}</span>}
                      </td>
                      <td className="py-2.5 px-4 text-right text-white font-bold">${b.total.toLocaleString()}</td>
                      <td className={`py-2.5 px-4 text-right ${b.variance > 0 ? "text-red-400" : "text-emerald-400"}`}>
                        {b.variance > 0 ? "+" : ""}${b.variance.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-4"><Badge className={`${STATUS_BADGE[b.status]} font-mono text-[10px] uppercase`}>{b.status}</Badge></td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="inline-flex gap-1">
                          {b.status === "pending" && (
                            <Button size="sm" data-testid={`approve-${b.bill_id}`} onClick={() => approve(b.bill_id)} className="h-7 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px]">APPROVE</Button>
                          )}
                          {b.status === "approved" && (
                            <Button size="sm" data-testid={`pay-${b.bill_id}`} onClick={() => pay(b.bill_id)} className="h-7 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-[10px]">PAY</Button>
                          )}
                          {b.status !== "paid" && b.status !== "disputed" && (
                            <Button size="sm" onClick={() => { setSelected(b); setDisputeOpen(true); }} className="h-7 bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-[10px]">DISPUTE</Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && <tr><td colSpan={10} className="text-center py-10 text-slate-500">No bills match the current filters.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Dialog open={disputeOpen} onOpenChange={setDisputeOpen}>
          <DialogContent className="bg-[#131821] border-white/10">
            <DialogHeader><DialogTitle className="font-display">Dispute Bill {selected?.invoice_no}</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <Textarea data-testid="dispute-reason" value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} placeholder="Reason for dispute (e.g., unauthorized accessorial, weight discrepancy, double-billed)..." className="bg-[#0B0E14] border-white/10 min-h-[120px]" />
              <Button data-testid="submit-dispute" onClick={submitDispute} className="w-full bg-red-500 hover:bg-red-400 text-white font-bold">SUBMIT DISPUTE</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
}

function StatCard({ label, value, sub, accent, Icon, testid }) {
  return (
    <Card className="hud-surface p-5 relative" data-testid={testid}>
      {Icon && <Icon size={16} className={`absolute top-4 right-4 ${accent} opacity-60`} />}
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
      {sub && <div className="text-[10px] font-mono text-slate-500 mt-1">{sub}</div>}
    </Card>
  );
}
