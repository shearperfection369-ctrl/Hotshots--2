import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { toast } from "sonner";
import { FileText, FileSignature, FileSpreadsheet, FileCheck2, Globe2, Plus } from "lucide-react";

const DOC_TYPES = [
  { id: "BOL", label: "Bill of Lading", icon: FileText, accent: "cyan" },
  { id: "COMMERCIAL_INVOICE", label: "Commercial Invoice", icon: FileSpreadsheet, accent: "emerald" },
  { id: "PACKING_SLIP", label: "Packing Slip", icon: FileSignature, accent: "yellow" },
  { id: "WEIGHT_CERT", label: "Weight Certificate", icon: FileCheck2, accent: "purple" },
  { id: "COO", label: "Certificate of Origin", icon: Globe2, accent: "rose" },
];

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ type: "BOL", shipment_ref: "", shipper: "Tennant Company", consignee: "", origin: "", destination: "", carrier: "", commodity: "", weight: "", pieces: "", value: "", country_origin: "USA" });

  const load = async () => {
    const { data } = await api.get("/documents");
    setDocs(data);
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    try {
      await api.post("/documents", { type: form.type, shipment_ref: form.shipment_ref, data: form });
      toast.success("Document generated");
      setOpen(false);
      load();
    } catch (e) { toast.error("Failed to generate"); }
  };

  return (
    <>
      <Topbar title="Documents" subtitle="BOL · Commercial Invoice · Packing · Weight · COO" />
      <div className="p-4 md:p-6 space-y-5">

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {DOC_TYPES.map(({ id, label, icon: Icon, accent }) => {
            const count = docs.filter((d) => d.type === id).length;
            const map = { cyan: "border-cyan-500/30 text-cyan-400", emerald: "border-emerald-500/30 text-emerald-400", yellow: "border-yellow-500/30 text-yellow-400", purple: "border-purple-500/30 text-purple-400", rose: "border-rose-500/30 text-rose-400" };
            return (
              <button
                key={id}
                onClick={() => { setForm((f) => ({ ...f, type: id })); setOpen(true); }}
                data-testid={`new-doc-${id}`}
                className={`hud-surface text-left p-4 rounded-lg border ${map[accent]} hover:bg-white/[0.03] transition-all`}
              >
                <Icon size={22} />
                <div className="mt-2 text-sm font-display font-semibold text-white">{label}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">{count} generated</div>
              </button>
            );
          })}
        </div>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="bg-[#131821] border-white/10 max-w-2xl">
            <DialogHeader><DialogTitle className="font-display">Generate {DOC_TYPES.find(d => d.id === form.type)?.label}</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3" data-testid="document-form">
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Document Type</Label>
                <Select value={form.type} onValueChange={(v) => setForm((f) => ({ ...f, type: v }))}>
                  <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent>{DOC_TYPES.map((d) => <SelectItem key={d.id} value={d.id}>{d.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <Field label="Shipment Reference" value={form.shipment_ref} onChange={(v) => setForm((f) => ({ ...f, shipment_ref: v }))} testid="doc-ref" />
              <Field label="Shipper" value={form.shipper} onChange={(v) => setForm((f) => ({ ...f, shipper: v }))} />
              <Field label="Consignee" value={form.consignee} onChange={(v) => setForm((f) => ({ ...f, consignee: v }))} />
              <Field label="Origin" value={form.origin} onChange={(v) => setForm((f) => ({ ...f, origin: v }))} />
              <Field label="Destination" value={form.destination} onChange={(v) => setForm((f) => ({ ...f, destination: v }))} />
              <Field label="Carrier" value={form.carrier} onChange={(v) => setForm((f) => ({ ...f, carrier: v }))} />
              <Field label="Commodity" value={form.commodity} onChange={(v) => setForm((f) => ({ ...f, commodity: v }))} />
              <Field label="Weight (lbs)" value={form.weight} onChange={(v) => setForm((f) => ({ ...f, weight: v }))} />
              <Field label="Pieces" value={form.pieces} onChange={(v) => setForm((f) => ({ ...f, pieces: v }))} />
              <Field label="Value (USD)" value={form.value} onChange={(v) => setForm((f) => ({ ...f, value: v }))} />
              {form.type === "COO" && (
                <Field label="Country of Origin" value={form.country_origin} onChange={(v) => setForm((f) => ({ ...f, country_origin: v }))} />
              )}
            </div>
            <Button data-testid="submit-document" onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-4">Generate Document</Button>
          </DialogContent>
        </Dialog>

        <Card className="hud-surface overflow-hidden">
          <div className="px-5 py-3 flex items-center justify-between border-b border-white/5">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Document Archive</div>
              <h3 className="font-display text-lg font-bold mt-1">{docs.length} generated documents</h3>
            </div>
            <Button onClick={() => setOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="quick-new-doc">
              <Plus size={14} className="mr-1" /> NEW
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr><th className="text-left py-3 px-4">Doc ID</th><th className="text-left py-3 px-4">Type</th><th className="text-left py-3 px-4">Shipment</th><th className="text-left py-3 px-4">Created By</th><th className="text-right py-3 px-4">Created</th></tr>
              </thead>
              <tbody className="font-mono">
                {docs.map((d) => (
                  <tr key={d.document_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-4 text-cyan-300">{d.document_id}</td>
                    <td className="py-2.5 px-4 text-slate-300">{DOC_TYPES.find((t) => t.id === d.type)?.label || d.type}</td>
                    <td className="py-2.5 px-4 text-slate-400">{d.shipment_ref}</td>
                    <td className="py-2.5 px-4 text-slate-400">{d.created_by}</td>
                    <td className="py-2.5 px-4 text-right text-slate-500 text-xs">{new Date(d.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {docs.length === 0 && <tr><td colSpan={5} className="text-center py-10 text-slate-500">No documents yet. Click NEW to generate one.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}

function Field({ label, value, onChange, testid }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input data-testid={testid} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 bg-[#0B0E14] border-white/10 text-white" />
    </div>
  );
}
