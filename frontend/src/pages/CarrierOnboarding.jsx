import React, { useEffect, useState } from "react";
import { useBrandRefresh } from "../lib/branding";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";
import { Plus, CheckCircle2, XCircle, AlertTriangle, Shield, FileSignature, Mail } from "lucide-react";
import { DialogFooter } from "../components/ui/dialog";

const STATUS_BADGE = {
  invited: "bg-slate-500/10 text-slate-400 border-slate-500/30",
  in_review: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  rejected: "bg-red-500/10 text-red-400 border-red-500/30",
};

const RATING_BADGE = {
  Satisfactory: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
  Conditional: "text-yellow-400 border-yellow-500/30 bg-yellow-500/10",
  Unsatisfactory: "text-red-400 border-red-500/30 bg-red-500/10",
  NotRated: "text-slate-400 border-slate-500/30 bg-slate-500/10",
};

const blankForm = {
  legal_name: "", dba: "", mc_number: "", dot_number: "", scac: "",
  mode: "TL", contact_name: "", contact_email: "", contact_phone: "",
  insurance_amount: 1000000, insurance_expiry: "",
  safety_rating: "Satisfactory", csa_score: 50, notes: ""
};

export default function CarrierOnboarding() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blankForm);
  const [packetModal, setPacketModal] = useState(null);

  const sendPacket = async (oid) => {
    try {
      const { data } = await api.post(`/carrier-onboarding/${oid}/send-packet`);
      setPacketModal(data);
      toast.success("Onboarding packet composed");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to compose packet");
    }
  };
  const copyText = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

  const load = async () => {
    const { data } = await api.get("/carriers/onboarding");
    setItems(data);
  };
  useEffect(() => { load(); }, []);
  useBrandRefresh(() => load());

  const submit = async () => {
    if (!form.legal_name || !form.contact_email) {
      toast.error("Legal name and contact email required");
      return;
    }
    try {
      await api.post("/carriers/onboarding", form);
      toast.success("Carrier submitted for review");
      setOpen(false);
      setForm(blankForm);
      load();
    } catch { toast.error("Submission failed"); }
  };

  const decide = async (oid, decision) => {
    await api.post(`/carriers/onboarding/${oid}/decision`, { decision });
    toast.success(`Carrier ${decision}`);
    load();
  };

  const toggleDoc = async (oid, field) => {
    await api.post(`/carriers/onboarding/${oid}/toggle`, { field });
    load();
  };

  const counts = items.reduce((acc, i) => { acc[i.status] = (acc[i.status] || 0) + 1; return acc; }, {});

  return (
    <>
      <Topbar title="Carrier Onboarding" subtitle="Vet, qualify and approve new carriers" />
      <div className="p-4 md:p-6 space-y-5">

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard label="In Review" value={counts.in_review || 0} accent="text-yellow-400" />
          <StatCard label="Approved" value={counts.approved || 0} accent="text-emerald-400" />
          <StatCard label="Rejected" value={counts.rejected || 0} accent="text-red-400" />
          <StatCard label="Total Pipeline" value={items.length} accent="text-cyan-400" />
          <Card className="hud-surface p-3 flex items-center justify-center">
            <Button onClick={() => setOpen(true)} data-testid="new-carrier-btn" className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              <Plus size={14} className="mr-1" /> NEW CARRIER
            </Button>
          </Card>
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Carrier</th>
                  <th className="text-left py-3 px-4">MC / DOT</th>
                  <th className="text-left py-3 px-4">SCAC</th>
                  <th className="text-left py-3 px-4">Mode</th>
                  <th className="text-left py-3 px-4">Safety</th>
                  <th className="text-right py-3 px-4">CSA</th>
                  <th className="text-left py-3 px-4">Insurance</th>
                  <th className="text-center py-3 px-4">W-9</th>
                  <th className="text-center py-3 px-4">COI</th>
                  <th className="text-center py-3 px-4">Contract</th>
                  <th className="text-left py-3 px-4">Status</th>
                  <th className="text-right py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {items.map((c) => {
                  const expDate = c.insurance_expiry ? new Date(c.insurance_expiry) : null;
                  const expired = expDate && expDate < new Date();
                  return (
                    <tr key={c.onboarding_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`carrier-row-${c.onboarding_id}`}>
                      <td className="py-2.5 px-4">
                        <div className="text-white">{c.legal_name}</div>
                        <div className="text-[10px] text-slate-500">{c.dba || c.contact_name}</div>
                      </td>
                      <td className="py-2.5 px-4 text-slate-300">{c.mc_number}<br/><span className="text-[10px] text-slate-500">DOT {c.dot_number}</span></td>
                      <td className="py-2.5 px-4 text-cyan-300">{c.scac || "—"}</td>
                      <td className="py-2.5 px-4 text-slate-400">{c.mode}</td>
                      <td className="py-2.5 px-4">
                        <Badge className={`${RATING_BADGE[c.safety_rating]} font-mono text-[10px]`}>{c.safety_rating}</Badge>
                      </td>
                      <td className={`py-2.5 px-4 text-right ${c.csa_score > 65 ? "text-red-400" : c.csa_score > 50 ? "text-yellow-400" : "text-emerald-400"}`}>{c.csa_score}</td>
                      <td className="py-2.5 px-4">
                        <div className={expired ? "text-red-400" : "text-slate-300"}>${(c.insurance_amount / 1000).toFixed(0)}K</div>
                        <div className={`text-[10px] ${expired ? "text-red-400" : "text-slate-500"}`}>exp {c.insurance_expiry} {expired && "⚠"}</div>
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <button onClick={() => toggleDoc(c.onboarding_id, "w9_received")} data-testid={`w9-${c.onboarding_id}`}>
                          {c.w9_received ? <CheckCircle2 size={16} className="text-emerald-400 inline" /> : <XCircle size={16} className="text-slate-600 inline" />}
                        </button>
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <button onClick={() => toggleDoc(c.onboarding_id, "coi_received")}>
                          {c.coi_received ? <CheckCircle2 size={16} className="text-emerald-400 inline" /> : <XCircle size={16} className="text-slate-600 inline" />}
                        </button>
                      </td>
                      <td className="py-2.5 px-4 text-center">
                        <button onClick={() => toggleDoc(c.onboarding_id, "contract_signed")}>
                          {c.contract_signed ? <CheckCircle2 size={16} className="text-emerald-400 inline" /> : <XCircle size={16} className="text-slate-600 inline" />}
                        </button>
                      </td>
                      <td className="py-2.5 px-4"><Badge className={`${STATUS_BADGE[c.status]} font-mono text-[10px] uppercase`}>{c.status}</Badge></td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="inline-flex gap-1 flex-wrap justify-end">
                          <Button size="sm" data-testid={`packet-${c.onboarding_id}`} onClick={() => sendPacket(c.onboarding_id)} className="h-7 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px]">
                            <Mail size={11} className="mr-1" /> PACKET
                          </Button>
                          {c.status === "in_review" && (
                            <>
                              <Button size="sm" data-testid={`approve-${c.onboarding_id}`} onClick={() => decide(c.onboarding_id, "approved")} className="h-7 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px]">APPROVE</Button>
                              <Button size="sm" data-testid={`reject-${c.onboarding_id}`} onClick={() => decide(c.onboarding_id, "rejected")} className="h-7 bg-red-500/10 hover:bg-red-500/20 text-red-300 border border-red-500/30 text-[10px]">REJECT</Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {items.length === 0 && <tr><td colSpan={12} className="text-center py-10 text-slate-500">No carriers in onboarding pipeline.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="bg-[#131821] border-white/10 max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Shield size={18} className="text-cyan-400" /> Add Carrier — Vetting Form</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3" data-testid="carrier-form">
              <F label="Legal Name *" v={form.legal_name} on={(v) => setForm({ ...form, legal_name: v })} tid="legal-name" />
              <F label="DBA" v={form.dba} on={(v) => setForm({ ...form, dba: v })} />
              <F label="MC Number" v={form.mc_number} on={(v) => setForm({ ...form, mc_number: v })} />
              <F label="DOT Number" v={form.dot_number} on={(v) => setForm({ ...form, dot_number: v })} />
              <F label="SCAC" v={form.scac} on={(v) => setForm({ ...form, scac: v })} />
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Mode</Label>
                <Select value={form.mode} onValueChange={(v) => setForm({ ...form, mode: v })}>
                  <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent>{["TL", "LTL", "Parcel", "Ocean", "Air", "Rail"].map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <F label="Contact Name" v={form.contact_name} on={(v) => setForm({ ...form, contact_name: v })} />
              <F label="Contact Email *" v={form.contact_email} on={(v) => setForm({ ...form, contact_email: v })} tid="contact-email" />
              <F label="Contact Phone" v={form.contact_phone} on={(v) => setForm({ ...form, contact_phone: v })} />
              <F label="Insurance Amount (USD)" type="number" v={form.insurance_amount} on={(v) => setForm({ ...form, insurance_amount: parseFloat(v) })} />
              <F label="Insurance Expiry" type="date" v={form.insurance_expiry} on={(v) => setForm({ ...form, insurance_expiry: v })} />
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Safety Rating</Label>
                <Select value={form.safety_rating} onValueChange={(v) => setForm({ ...form, safety_rating: v })}>
                  <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                  <SelectContent>{["Satisfactory", "Conditional", "Unsatisfactory", "NotRated"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <F label="CSA Score (0-100, lower better)" type="number" v={form.csa_score} on={(v) => setForm({ ...form, csa_score: parseInt(v) })} />
            </div>
            <Button data-testid="submit-carrier" onClick={submit} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-4">SUBMIT FOR VETTING</Button>
          </DialogContent>
        </Dialog>

        {/* Onboarding packet modal */}
        <Dialog open={!!packetModal} onOpenChange={(o) => !o && setPacketModal(null)}>
          <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-2xl" data-testid="packet-modal">
            <DialogHeader>
              <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Mail size={16} /> Tennant Onboarding Packet</DialogTitle>
            </DialogHeader>
            {packetModal && (
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-mono uppercase text-cyan-400">To</label>
                  <Input readOnly value={packetModal.to || "(no email on file)"} className="mt-1 bg-[#0B0E14] border-white/10" />
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase text-cyan-400">Subject</label>
                  <Input readOnly value={packetModal.subject} className="mt-1 bg-[#0B0E14] border-white/10 font-mono text-xs" />
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase text-cyan-400">Body</label>
                  <textarea readOnly value={packetModal.body} rows={14} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-xs font-mono whitespace-pre-wrap" data-testid="packet-body" />
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => copyText(packetModal?.body || "")} data-testid="packet-copy">Copy Body</Button>
              <a href={packetModal?.mailto || "#"} data-testid="packet-mailto"
                className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm">
                <Mail size={14} /> Open in Mail Client
              </a>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
}

function F({ label, v, on, type = "text", tid }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input data-testid={tid} type={type} value={v} onChange={(e) => on(e.target.value)} className="mt-1 bg-[#0B0E14] border-white/10" />
    </div>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <Card className="hud-surface p-5">
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-2 text-3xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
    </Card>
  );
}
