import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { ShieldCheck, Plus, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { toast } from "sonner";

const TYPE_LABEL = {
  cargo_liability: "Cargo Liability", contingent_cargo: "Contingent Cargo",
  auto_liability: "Auto Liability", general_liability: "General Liability",
  bmc84_bond: "BMC-84 Bond", eo_professional: "E&O Professional",
};
const STATUS_CLS = {
  active: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  expiring_soon: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  expired: "bg-red-500/15 text-red-300 border-red-500/30",
};

export const InsuranceBinderCard = () => {
  const [d, setD] = useState(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ policy_type: "cargo_liability", insurer: "", policy_number: "", coverage_usd: "", premium_monthly_usd: "", expires: "" });
  const load = () => api.get("/insurance/policies").then(({ data }) => setD(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.insurer || !form.expires) { toast.error("Insurer and expiry date required"); return; }
    try {
      await api.post("/insurance/policies", { ...form, coverage_usd: Number(form.coverage_usd) || 0, premium_monthly_usd: Number(form.premium_monthly_usd) || 0 });
      toast.success("Policy tracked");
      setAdding(false);
      setForm({ policy_type: "cargo_liability", insurer: "", policy_number: "", coverage_usd: "", premium_monthly_usd: "", expires: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Remove this policy from tracking? This cannot be undone.")) return;
    try { await api.delete(`/insurance/policies/${id}`); load(); } catch (e) { toast.error("Delete failed"); }
  };
  if (!d) return null;

  return (
    <Card className="hud-surface p-4" data-testid="insurance-binder-card">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck size={15} className={d.dual_insured ? "text-emerald-400" : "text-amber-400"} />
          <h3 className="font-display text-sm font-bold text-white">Insurance Binders</h3>
          <Badge className={d.dual_insured ? STATUS_CLS.active : STATUS_CLS.expiring_soon} data-testid="dual-insured-badge">
            {d.dual_insured ? "DUAL-INSURED ✓ promise intact" : "DUAL-INSURED AT RISK"}
          </Badge>
          <span className="text-[9px] font-mono text-slate-500">${Number(d.monthly_premium_total_usd).toLocaleString()}/mo premiums</span>
        </div>
        <Button size="sm" onClick={() => setAdding(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold h-7 text-[10px]" data-testid="add-policy-btn">
          <Plus size={12} className="mr-1" /> Track Policy
        </Button>
      </div>
      {(d.alerts || []).length > 0 && (
        <div className="p-2 rounded border border-amber-500/30 bg-amber-500/5 text-[10px] font-mono text-amber-300 mb-2" data-testid="insurance-alerts">
          ⚠ {d.alerts.join(" · ")}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        {(d.policies || []).map((p) => (
          <div key={p.id} className="p-2.5 rounded border border-white/10 bg-white/[0.02]" data-testid={`policy-${p.id}`}>
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-100">{TYPE_LABEL[p.policy_type] || p.policy_type}</span>
              <Badge className={`${STATUS_CLS[p.status] || STATUS_CLS.active} text-[8px] font-mono`}>
                {p.status === "expired" ? "EXPIRED" : `${p.days_to_expiry}d left`}
              </Badge>
            </div>
            <div className="text-[9px] font-mono text-slate-500 mt-1">{p.insurer} · {p.policy_number}</div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-[10px] font-mono text-cyan-300">${Number(p.coverage_usd).toLocaleString()} cover</span>
              <Button size="sm" variant="ghost" onClick={() => remove(p.id)} className="h-5 px-1 text-red-400" data-testid={`policy-delete-${p.id}`}><Trash2 size={11} /></Button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="bg-slate-900 border-cyan-500/20" data-testid="policy-dialog">
          <DialogHeader><DialogTitle>Track Insurance Policy</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <select value={form.policy_type} onChange={(e) => setForm({ ...form, policy_type: e.target.value })}
              className="bg-[#11151F] border border-white/10 rounded px-2 py-2 text-xs text-white col-span-2" data-testid="policy-type-select">
              {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <Input value={form.insurer} onChange={(e) => setForm({ ...form, insurer: e.target.value })} placeholder="Insurer *" className="bg-[#11151F] border-white/10" data-testid="policy-insurer" />
            <Input value={form.policy_number} onChange={(e) => setForm({ ...form, policy_number: e.target.value })} placeholder="Policy #" className="bg-[#11151F] border-white/10" />
            <Input type="number" value={form.coverage_usd} onChange={(e) => setForm({ ...form, coverage_usd: e.target.value })} placeholder="Coverage $" className="bg-[#11151F] border-white/10" />
            <Input type="number" value={form.premium_monthly_usd} onChange={(e) => setForm({ ...form, premium_monthly_usd: e.target.value })} placeholder="Premium $/mo" className="bg-[#11151F] border-white/10" />
            <div className="col-span-2">
              <div className="text-[9px] font-mono uppercase text-slate-500 mb-0.5">Expires *</div>
              <Input type="date" value={form.expires} onChange={(e) => setForm({ ...form, expires: e.target.value })} className="bg-[#11151F] border-white/10" data-testid="policy-expires" />
            </div>
          </div>
          <Button onClick={create} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="policy-save-btn">Track Policy</Button>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default InsuranceBinderCard;
