import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Plus, FileWarning, DollarSign, TrendingUp, CheckCircle2, XCircle } from "lucide-react";

const STATUS_STYLES = {
  open: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  filed: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  acknowledged: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  settled: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  partial: "bg-emerald-500/5 text-emerald-300 border-emerald-500/20",
  denied: "bg-red-500/10 text-red-400 border-red-500/30",
};

export default function Claims() {
  const [data, setData] = useState({ claims: [], summary: {}, claim_types: [], claim_statuses: [] });
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [openNew, setOpenNew] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({
    shipment_id: "",
    carrier: "",
    bol_no: "",
    claim_type: "damage",
    amount_claimed_usd: 0,
    incident_date: new Date().toISOString().slice(0, 10),
    description: "",
    notes: "",
  });

  const load = async () => {
    const { data } = await api.get("/claims");
    setData(data);
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    return data.claims.filter((c) => statusFilter === "ALL" ? true : c.status === statusFilter);
  }, [data.claims, statusFilter]);

  const create = async () => {
    try {
      await api.post("/claims", form);
      toast.success("Claim filed");
      setOpenNew(false);
      setForm({ shipment_id: "", carrier: "", bol_no: "", claim_type: "damage", amount_claimed_usd: 0, incident_date: new Date().toISOString().slice(0, 10), description: "", notes: "" });
      load();
    } catch (e) { toast.error("Failed to file claim"); }
  };

  const saveEdit = async () => {
    if (!edit) return;
    try {
      await api.put(`/claims/${edit.claim_id}`, {
        status: edit.status,
        amount_recovered_usd: Number(edit.amount_recovered_usd) || 0,
        notes: edit.notes || "",
      });
      toast.success(`Claim ${edit.claim_id} updated`);
      setEdit(null);
      load();
    } catch (e) { toast.error("Update failed"); }
  };

  const s = data.summary || {};

  return (
    <>
      <Topbar title="Freight Payments & Claims" subtitle="File, reconcile, and recover" />
      <div className="p-4 md:p-6 space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Tile label="Total Claims" value={s.total_claims ?? 0} accent="text-cyan-400" Icon={FileWarning} />
          <Tile label="Open / Filed" value={s.open_count ?? 0} accent="text-yellow-400" Icon={FileWarning} />
          <Tile label="Settled" value={s.settled_count ?? 0} accent="text-emerald-400" Icon={CheckCircle2} />
          <Tile label="Total Claimed" value={`$${(s.total_claimed_usd || 0).toLocaleString()}`} accent="text-cyan-300" Icon={DollarSign} />
          <Tile label={`Recovered (${s.recovery_rate_pct || 0}%)`} value={`$${(s.total_recovered_usd || 0).toLocaleString()}`} accent="text-emerald-400" Icon={TrendingUp} />
        </div>

        <Card className="hud-surface p-3 flex flex-wrap items-center gap-2">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mr-2">Status</div>
          {["ALL", ...(data.claim_statuses || [])].map((st) => (
            <button key={st} onClick={() => setStatusFilter(st)} data-testid={`claims-filter-${st}`}
              className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${statusFilter === st ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>{st}</button>
          ))}
          <Button onClick={() => setOpenNew(true)} className="ml-auto bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="new-claim-btn"><Plus size={14} className="mr-1" /> New Claim</Button>
        </Card>

        <Card className="hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-3">Claim ID</th>
                <th className="text-left py-3 px-3">Shipment</th>
                <th className="text-left py-3 px-3">Carrier</th>
                <th className="text-left py-3 px-3">Type</th>
                <th className="text-right py-3 px-3">Claimed</th>
                <th className="text-right py-3 px-3">Recovered</th>
                <th className="text-right py-3 px-3">Net</th>
                <th className="text-left py-3 px-3">Filed</th>
                <th className="text-left py-3 px-3">Status</th>
                <th className="text-center py-3 px-3">Actions</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {filtered.map((c) => {
                const net = (c.amount_claimed_usd || 0) - (c.amount_recovered_usd || 0);
                return (
                  <tr key={c.claim_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`claim-row-${c.claim_id}`}>
                    <td className="py-2.5 px-3 text-cyan-300">{c.claim_id}</td>
                    <td className="py-2.5 px-3 text-slate-300 text-xs">{c.shipment_id || "—"}<div className="text-[10px] text-slate-500">BOL {c.bol_no || "—"}</div></td>
                    <td className="py-2.5 px-3 text-slate-300">{c.carrier}</td>
                    <td className="py-2.5 px-3 text-slate-400 uppercase text-xs">{c.claim_type.replace("_", " ")}</td>
                    <td className="py-2.5 px-3 text-right text-cyan-300">${c.amount_claimed_usd.toLocaleString()}</td>
                    <td className="py-2.5 px-3 text-right text-emerald-400">${(c.amount_recovered_usd || 0).toLocaleString()}</td>
                    <td className={`py-2.5 px-3 text-right ${net > 0 ? "text-red-400" : "text-emerald-300"}`}>${net.toLocaleString()}</td>
                    <td className="py-2.5 px-3 text-slate-400 text-xs">{c.filed_date}</td>
                    <td className="py-2.5 px-3"><span className={`px-2 py-0.5 rounded border text-[10px] font-mono uppercase ${STATUS_STYLES[c.status] || ""}`}>{c.status}</span></td>
                    <td className="py-2.5 px-3 text-center">
                      <Button size="sm" variant="outline" onClick={() => setEdit({ ...c })} data-testid={`edit-claim-${c.claim_id}`}>Manage</Button>
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (<tr><td colSpan={10} className="text-center py-12 text-slate-500">No claims match.</td></tr>)}
            </tbody>
          </table>
        </Card>
      </div>

      {/* New claim */}
      <Dialog open={openNew} onOpenChange={setOpenNew}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-2xl" data-testid="new-claim-dialog">
          <DialogHeader><DialogTitle className="font-display text-cyan-300">File a New Claim</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <FieldText label="Shipment ID" value={form.shipment_id} onChange={(v) => setForm({ ...form, shipment_id: v })} testid="new-claim-shipment" />
            <FieldText label="BOL #" value={form.bol_no} onChange={(v) => setForm({ ...form, bol_no: v })} />
            <FieldText label="Carrier" value={form.carrier} onChange={(v) => setForm({ ...form, carrier: v })} testid="new-claim-carrier" />
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Type</label>
              <Select value={form.claim_type} onValueChange={(v) => setForm({ ...form, claim_type: v })}>
                <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent>{data.claim_types.map((t) => <SelectItem key={t} value={t}>{t.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Amount Claimed (USD)</label>
              <Input type="number" value={form.amount_claimed_usd} onChange={(e) => setForm({ ...form, amount_claimed_usd: parseFloat(e.target.value || 0) })} className="mt-1 bg-[#0B0E14] border-white/10 font-mono" data-testid="new-claim-amount" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Incident Date</label>
              <Input type="date" value={form.incident_date} onChange={(e) => setForm({ ...form, incident_date: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" />
            </div>
            <div className="col-span-2">
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Description</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-sm" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpenNew(false)}>Cancel</Button>
            <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="new-claim-submit">File Claim</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit claim */}
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-lg" data-testid="edit-claim-dialog">
          <DialogHeader><DialogTitle className="font-display text-cyan-300">Manage Claim {edit?.claim_id}</DialogTitle></DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div className="text-sm text-slate-300">{edit.description}</div>
              <div className="text-xs text-slate-500">Claimed: <span className="text-cyan-300 font-mono">${edit.amount_claimed_usd.toLocaleString()}</span></div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Status</label>
                <Select value={edit.status} onValueChange={(v) => setEdit({ ...edit, status: v })}>
                  <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent>{data.claim_statuses.map((st) => <SelectItem key={st} value={st}>{st}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Amount Recovered</label>
                <Input type="number" value={edit.amount_recovered_usd ?? 0} onChange={(e) => setEdit({ ...edit, amount_recovered_usd: parseFloat(e.target.value || 0) })} className="mt-1 bg-[#0B0E14] border-white/10 font-mono" data-testid="edit-claim-recovered" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Notes</label>
                <textarea value={edit.notes || ""} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} rows={2} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-sm" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)}>Cancel</Button>
            <Button onClick={saveEdit} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="edit-claim-save">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Tile({ label, value, accent, Icon }) {
  return (
    <Card className="hud-surface p-4 flex items-start gap-3">
      <div className="p-2 rounded bg-cyan-500/10 border border-cyan-500/20"><Icon size={16} className="text-cyan-400" /></div>
      <div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
        <div className={`text-2xl font-mono font-bold mt-1 tabular-nums ${accent}`}>{value}</div>
      </div>
    </Card>
  );
}

function FieldText({ label, value, onChange, testid }) {
  return (
    <div>
      <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">{label}</label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 bg-[#0B0E14] border-white/10 font-mono" data-testid={testid} />
    </div>
  );
}
