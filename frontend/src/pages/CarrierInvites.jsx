import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";
import { Mail, Copy, Trash2, UserPlus, Send } from "lucide-react";

export default function CarrierInvites() {
  const [invites, setInvites] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ carrier_company: "", invitee_email: "", invitee_name: "", expires_days: 14 });
  const [generated, setGenerated] = useState(null);

  const load = async () => {
    const { data } = await api.get("/carrier-invites");
    setInvites(data);
  };
  useEffect(() => { load(); }, []);

  const submit = async () => {
    try {
      const { data } = await api.post("/carrier-invites", form);
      setGenerated(data);
      toast.success(`Invite created for ${form.carrier_company}`);
      load();
    } catch (e) { toast.error("Failed to create invite"); }
  };

  const revoke = async (invite_id) => {
    if (!window.confirm("Revoke this invite? It can no longer be used.")) return;
    try {
      await api.delete(`/carrier-invites/${invite_id}`);
      toast.success("Invite revoked");
      load();
    } catch (e) { toast.error("Revoke failed"); }
  };

  const copy = (text, label = "Copied") => { navigator.clipboard.writeText(text); toast.success(label); };

  const fullLink = (link) => `${window.location.origin}${link}`;

  return (
    <>
      <Topbar title="Carrier Invites" subtitle="Admin-only · invite carriers to a scoped read-only portal" />
      <div className="p-4 md:p-6 space-y-4">
        <Card className="hud-surface p-4 flex items-center justify-between">
          <div className="text-sm text-slate-300">Carriers you invite can only see <span className="text-cyan-300 font-mono">their own loads</span>, tracking, and BOL upload — nothing else.</div>
          <Button onClick={() => { setForm({ carrier_company: "", invitee_email: "", invitee_name: "", expires_days: 14 }); setGenerated(null); setOpen(true); }} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="new-invite-btn">
            <UserPlus size={14} className="mr-2" /> New Invite
          </Button>
        </Card>

        <Card className="hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">Carrier</th>
                <th className="text-left py-3 px-4">Invitee</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-left py-3 px-4">Created</th>
                <th className="text-left py-3 px-4">Expires</th>
                <th className="text-center py-3 px-4">Actions</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {invites.map((i) => {
                const statusColor = {
                  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
                  accepted: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
                  revoked: "bg-red-500/10 text-red-400 border-red-500/30",
                  expired: "bg-slate-500/10 text-slate-400 border-slate-500/30",
                }[i.status] || "";
                return (
                  <tr key={i.invite_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`invite-row-${i.invite_id}`}>
                    <td className="py-2.5 px-4 text-cyan-300">{i.carrier_company}</td>
                    <td className="py-2.5 px-4 text-slate-300">{i.invitee_name || "—"}<div className="text-[10px] text-slate-500">{i.invitee_email}</div></td>
                    <td className="py-2.5 px-4"><span className={`px-2 py-0.5 rounded border text-[10px] uppercase ${statusColor}`}>{i.status}</span></td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{(i.created_at || "").slice(0, 10)}</td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{(i.expires_at || "").slice(0, 10)}</td>
                    <td className="py-2.5 px-4 text-center">
                      {i.status === "pending" && (
                        <Button size="sm" variant="outline" onClick={() => revoke(i.invite_id)} className="border-red-500/40 text-red-400 hover:bg-red-500/10" data-testid={`revoke-invite-${i.invite_id}`}>
                          <Trash2 size={12} className="mr-1" /> Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {invites.length === 0 && (<tr><td colSpan={6} className="text-center py-12 text-slate-500">No invites yet. Click New Invite.</td></tr>)}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Dialog */}
      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setGenerated(null); }}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-xl" data-testid="invite-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><UserPlus size={18} /> Invite a Carrier</DialogTitle>
          </DialogHeader>
          {!generated ? (
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Carrier Company</label>
                <Input value={form.carrier_company} onChange={(e) => setForm({ ...form, carrier_company: e.target.value })} placeholder="XPO Logistics" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-carrier-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono uppercase text-cyan-400">Invitee Name</label>
                  <Input value={form.invitee_name} onChange={(e) => setForm({ ...form, invitee_name: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-name-input" />
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase text-cyan-400">Email</label>
                  <Input type="email" value={form.invitee_email} onChange={(e) => setForm({ ...form, invitee_email: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-email-input" />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Expires in (days)</label>
                <Input type="number" min={1} max={90} value={form.expires_days} onChange={(e) => setForm({ ...form, expires_days: parseInt(e.target.value || 14) })} className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-3 rounded bg-emerald-500/[0.06] border border-emerald-500/30 text-emerald-300 text-sm flex items-start gap-2">
                <Mail size={16} className="mt-0.5" />
                <div>Invite created. Share the link below — or use the email helper.</div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Invite Link</label>
                <div className="flex gap-2 mt-1">
                  <Input readOnly value={fullLink(generated.invite_link)} className="bg-[#0B0E14] border-white/10 font-mono text-xs" data-testid="invite-link" />
                  <Button onClick={() => copy(fullLink(generated.invite_link), "Link copied")} variant="outline" data-testid="invite-link-copy"><Copy size={14} /></Button>
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase text-cyan-400">Email Body (mock — copy or use mailto)</label>
                <textarea readOnly value={generated.email_body} rows={9} className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-xs font-mono" />
                <div className="flex gap-2 mt-2">
                  <Button onClick={() => copy(generated.email_body, "Email body copied")} variant="outline" className="flex-1"><Copy size={14} className="mr-1" /> Copy Body</Button>
                  <a href={`mailto:${form.invitee_email}?subject=${encodeURIComponent("Tennant TMS Carrier Portal Invite")}&body=${encodeURIComponent(generated.email_body)}`}
                    className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-sm" data-testid="invite-mailto">
                    <Send size={14} /> Open in Mail Client
                  </a>
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            {!generated ? (
              <>
                <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
                <Button onClick={submit} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="invite-create-submit">Create Invite</Button>
              </>
            ) : (
              <Button onClick={() => { setOpen(false); setGenerated(null); }} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Done</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
