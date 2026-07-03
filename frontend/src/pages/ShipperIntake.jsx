/**
 * /shipper-intake — Admin page for creating, tracking, and emailing
 * branded shipper intake templates. Shippers complete the form via the
 * public URL and their submission auto-creates a `pending_review`
 * brokerage booking that surfaces in /workflow.
 */
import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Send, FileText, ClipboardCopy, Plus, RefreshCw, CheckCircle2, Clock, XCircle, Mail } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { authedDownload } from "@/lib/authedDownload";

const STATUS_STYLE = {
  pending:   { badge: "bg-slate-500/15 text-slate-300 border-slate-500/40",  icon: Clock,        label: "Awaiting shipper" },
  submitted: { badge: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40", icon: CheckCircle2, label: "Submitted" },
  booked:    { badge: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",     icon: CheckCircle2, label: "Booked" },
  expired:   { badge: "bg-red-500/15 text-red-300 border-red-500/40",       icon: XCircle,      label: "Expired" },
};

export default function ShipperIntake() {
  const [rows, setRows] = useState([]);
  const [newOpen, setNewOpen] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api.get("/intake/requests").then(({ data }) => setRows(data.items || [])).catch(() => {});
  }, [tick]);

  const copyLink = (url) => {
    navigator.clipboard.writeText(url);
    toast.success("Link copied to clipboard");
  };

  const emailIt = async (id) => {
    try {
      const { data } = await api.post(`/intake/requests/${id}/email`);
      toast.success(`Sent via ${data.via}`);
      setTick((t) => t + 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Email failed — set a shipper email first");
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" data-testid="shipper-intake-page">
      <header className="mb-6 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 font-mono text-[11px] uppercase tracking-[0.18em] mb-1.5">
            <Send size={14} /> Shipper Intake · Branded Template
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter">
            Branded Shipper Intake
          </h1>
          <p className="text-slate-400 text-sm mt-2 max-w-2xl">
            Send a shipper a one-click intake link. Submissions auto-create a
            <span className="text-amber-300"> pending_review </span>
            booking in your Workflow inbox — no manual keying required.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setTick((t) => t + 1)} size="sm"
            className="border-cyan-500/40" data-testid="intake-refresh">
            <RefreshCw size={13} className="mr-1" /> Refresh
          </Button>
          <Button onClick={() => setNewOpen(true)} className="bg-cyan-500 text-black font-bold"
            data-testid="new-intake-btn">
            <Plus size={14} className="mr-1" /> New Intake Request
          </Button>
        </div>
      </header>

      {rows.length === 0 ? (
        <Card className="bg-[#0F1421] border-white/5">
          <CardContent className="py-10 text-center text-slate-500">
            <Send size={32} className="mx-auto mb-3 opacity-40" />
            <div className="text-sm">No intake requests yet.</div>
            <div className="text-[11px] text-slate-600 mt-1">Click &quot;New Intake Request&quot; to send your first shipper form.</div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="intake-list">
          {rows.map((r) => {
            const style = STATUS_STYLE[r.status] || STATUS_STYLE.pending;
            const Icon = style.icon;
            return (
              <Card key={r.request_id} className="bg-[#0F1421] border-white/5"
                data-testid={`intake-row-${r.request_id}`}>
                <CardContent className="p-4 flex justify-between items-start gap-4 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className={`${style.badge} border font-mono text-[10px]`}>
                        <Icon size={10} className="inline mr-1" /> {style.label}
                      </Badge>
                      <span className="font-mono text-cyan-300 text-sm">{r.request_id}</span>
                      <span className="text-slate-500 text-xs">·</span>
                      <span className="text-slate-300">{r.shipper_name}</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1 font-mono">
                      {r.shipper_email && `→ ${r.shipper_email} · `}
                      created {r.created_at?.slice(0, 10)} · expires {r.expires_at?.slice(0, 10)}
                      {r.linked_booked_id && ` · booked as ${r.linked_booked_id}`}
                    </div>
                    <div className="text-[11px] text-cyan-400 mt-2 font-mono truncate">
                      {r.submit_url}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 items-end">
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" className="h-7 text-[11px]"
                        onClick={() => copyLink(r.submit_url)}
                        data-testid={`intake-copy-${r.request_id}`}>
                        <ClipboardCopy size={11} className="mr-1" /> Copy link
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 text-[11px] border-amber-500/40 text-amber-200"
                        onClick={() => emailIt(r.request_id)}
                        data-testid={`intake-email-${r.request_id}`}>
                        <Mail size={11} className="mr-1" /> Email
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 text-[11px] border-cyan-500/40 text-cyan-200"
                        onClick={() => authedDownload(`/intake/requests/${r.request_id}/pdf`, `Intake_${r.request_id}.pdf`)}
                        data-testid={`intake-pdf-${r.request_id}`}>
                        <FileText size={11} className="mr-1" /> PDF
                      </Button>
                    </div>
                    {r.last_emailed_at && (
                      <div className="text-[10px] text-slate-500 font-mono">
                        emailed {r.last_emailed_at.slice(0, 16).replace("T", " ")} · via {r.last_email_delivery_via}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {newOpen && (
        <NewRequestDialog onClose={() => setNewOpen(false)}
          onSaved={() => { setNewOpen(false); setTick((t) => t + 1); }} />
      )}
    </div>
  );
}

function NewRequestDialog({ onClose, onSaved }) {
  const [form, setForm] = useState({
    shipper_name: "", shipper_email: "", shipper_contact_name: "",
    prefill_origin: "", prefill_destination: "", prefill_commodity: "",
    prefill_equipment: "Dry Van", prefill_pickup_date: "", prefill_delivery_date: "",
    expires_in_days: 30, note_to_shipper: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async () => {
    if (!form.shipper_name.trim()) { toast.error("Shipper name is required"); return; }
    try {
      await api.post("/intake/requests", { ...form,
        expires_in_days: Number(form.expires_in_days) || 30 });
      toast.success(`Intake request created for ${form.shipper_name}`);
      onSaved();
    } catch (e) {
      console.error(e); toast.error("Failed to create intake");
    }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40 max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Shipper Intake Request</DialogTitle>
          <DialogDescription className="text-xs text-slate-500">
            Optional prefills appear as hints on the shipper&apos;s form.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <F l="Shipper name *" v={form.shipper_name} on={(v) => set("shipper_name", v)} t="intake-shipper-name" />
          <F l="Shipper email" type="email" v={form.shipper_email} on={(v) => set("shipper_email", v)} t="intake-shipper-email" />
          <F l="Contact name" v={form.shipper_contact_name} on={(v) => set("shipper_contact_name", v)} t="intake-contact-name" />
          <F l="Expires (days)" type="number" v={form.expires_in_days} on={(v) => set("expires_in_days", v)} t="intake-expires" />
          <F l="Prefill · origin" v={form.prefill_origin} on={(v) => set("prefill_origin", v)} t="intake-origin" />
          <F l="Prefill · destination" v={form.prefill_destination} on={(v) => set("prefill_destination", v)} t="intake-dest" />
          <F l="Prefill · commodity" v={form.prefill_commodity} on={(v) => set("prefill_commodity", v)} t="intake-commodity" />
          <F l="Prefill · equipment" v={form.prefill_equipment} on={(v) => set("prefill_equipment", v)} t="intake-equip" />
          <F l="Prefill · pickup date" type="date" v={form.prefill_pickup_date} on={(v) => set("prefill_pickup_date", v)} t="intake-pickup" />
          <F l="Prefill · delivery date" type="date" v={form.prefill_delivery_date} on={(v) => set("prefill_delivery_date", v)} t="intake-delivery" />
          <div className="col-span-2">
            <Label className="text-[10px] font-mono uppercase">Note to shipper (optional)</Label>
            <Input value={form.note_to_shipper} onChange={(e) => set("note_to_shipper", e.target.value)}
              placeholder="A short greeting or context for the shipper…" className="bg-[#0B1320] border-white/10"
              data-testid="intake-note" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="intake-submit">
            Create Intake Link
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function F({ l, v, on, type = "text", t }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 block">{l}</Label>
      <Input type={type} value={v} onChange={(e) => on(e.target.value)}
        className="bg-[#0B1320] border-white/10 text-white" data-testid={t} />
    </div>
  );
}
