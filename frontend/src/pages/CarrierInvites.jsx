import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { useBranding } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";
import { Mail, Copy, Trash2, UserPlus, Send, Eye, MailCheck } from "lucide-react";

export default function CarrierInvites() {
  const { brand } = useBranding();
  const brandShort = brand?.short_name || "Orisei Freight";
  const brandCompany = brand?.company_name || "Orisei Freight Solutions LLC";
  const brandPrimary = brand?.primary_color || "#0E3A6B";
  const brandAccent = brand?.accent_color || "#C9A24A";

  const [invites, setInvites] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ carrier_company: "", invitee_email: "", invitee_name: "", expires_days: 14 });
  const [generated, setGenerated] = useState(null);
  const [previewMode, setPreviewMode] = useState("rich"); // rich | text
  const [sending, setSending] = useState(false);

  const load = async () => {
    const { data } = await api.get("/carrier-invites");
    setInvites(data);
  };
  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!form.carrier_company || !form.invitee_email) {
      toast.error("Carrier company and invitee email are required");
      return;
    }
    try {
      const { data } = await api.post("/carrier-invites", form);
      setGenerated(data);
      toast.success(`Invite created for ${form.carrier_company}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create invite");
    }
  };

  const revoke = async (invite_id) => {
    if (!window.confirm("Revoke this invite? It can no longer be used.")) return;
    try {
      await api.delete(`/carrier-invites/${invite_id}`);
      toast.success("Invite revoked");
      load();
    } catch { toast.error("Revoke failed"); }
  };

  const sendEmail = async (inviteId) => {
    if (!inviteId) return;
    setSending(true);
    try {
      const { data } = await api.post(`/carrier-invites/${inviteId}/send-email`);
      toast.success(`Invite emailed to ${data.to_email}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed — check Resend connection");
    } finally {
      setSending(false);
    }
  };

  const copy = (text, label = "Copied") => { navigator.clipboard.writeText(text); toast.success(label); };

  return (
    <>
      <Topbar title="Carrier Invites" subtitle={`Admin-only · invite carriers into the ${brandShort} network`} />
      <div className="p-4 md:p-6 space-y-4">
        <Card className="hud-surface p-4 flex items-center justify-between">
          <div className="text-sm text-slate-300">
            Carriers you invite can view <span className="font-mono" style={{ color: brandAccent }}>their own loads</span>, update statuses,
            upload BOLs &amp; PODs, and track quick-pay — nothing else.
          </div>
          <Button
            onClick={() => {
              setForm({ carrier_company: "", invitee_email: "", invitee_name: "", expires_days: 14 });
              setGenerated(null);
              setPreviewMode("rich");
              setOpen(true);
            }}
            className="font-bold text-black"
            style={{ background: brandAccent }}
            data-testid="new-invite-btn"
          >
            <UserPlus size={14} className="mr-2" /> New Invite
          </Button>
        </Card>

        <Card className="hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono uppercase tracking-wider" style={{ color: brandAccent }}>
              <tr>
                <th className="text-left py-3 px-4">Carrier</th>
                <th className="text-left py-3 px-4">Invitee</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-left py-3 px-4">Emailed</th>
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
                    <td className="py-2.5 px-4" style={{ color: brandAccent }}>{i.carrier_company}</td>
                    <td className="py-2.5 px-4 text-slate-300">{i.invitee_name || "—"}<div className="text-[10px] text-slate-500">{i.invitee_email}</div></td>
                    <td className="py-2.5 px-4"><span className={`px-2 py-0.5 rounded border text-[10px] uppercase ${statusColor}`}>{i.status}</span></td>
                    <td className="py-2.5 px-4 text-xs">
                      {i.email_sent_at
                        ? <span className="inline-flex items-center gap-1 text-emerald-400"><MailCheck size={12} /> {i.email_sent_at.slice(0, 10)}</span>
                        : <span className="text-slate-500">—</span>}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{(i.created_at || "").slice(0, 10)}</td>
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{(i.expires_at || "").slice(0, 10)}</td>
                    <td className="py-2.5 px-4 text-center">
                      <div className="inline-flex gap-1.5 justify-end">
                        {i.status === "pending" && (
                          <>
                            <Button size="sm" variant="outline" disabled={sending}
                              onClick={() => sendEmail(i.invite_id)}
                              className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10"
                              data-testid={`send-email-${i.invite_id}`}>
                              <Send size={11} className="mr-1" /> {i.email_sent_at ? "Resend" : "Email"}
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => revoke(i.invite_id)}
                              className="border-red-500/40 text-red-400 hover:bg-red-500/10" data-testid={`revoke-invite-${i.invite_id}`}>
                              <Trash2 size={11} className="mr-1" /> Revoke
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {invites.length === 0 && (<tr><td colSpan={7} className="text-center py-12 text-slate-500">No invites yet. Click New Invite.</td></tr>)}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Dialog */}
      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setGenerated(null); }}>
        <DialogContent className="bg-[#131821] border max-w-3xl text-white max-h-[92vh] overflow-y-auto"
          style={{ borderColor: `${brandAccent}55` }} data-testid="invite-dialog">
          <DialogHeader>
            <DialogTitle className="font-display flex items-center gap-2" style={{ color: brandAccent }}>
              <UserPlus size={18} /> Invite a Carrier · {brandShort}
            </DialogTitle>
          </DialogHeader>

          {!generated ? (
            <div className="space-y-3">
              <div className="rounded-lg border p-3 text-sm" style={{ borderColor: `${brandAccent}33`, background: `${brandPrimary}22` }}>
                Build a warm, full-color invite to the <strong style={{ color: brandAccent }}>{brandCompany}</strong> carrier network.
                We'll generate a personalized HTML packet, a tracked invite link, and (with Resend connected) email it directly.
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Carrier Company *</label>
                <Input value={form.carrier_company} onChange={(e) => setForm({ ...form, carrier_company: e.target.value })}
                  placeholder="Acme Freight LLC" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-carrier-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Invitee Name</label>
                  <Input value={form.invitee_name} onChange={(e) => setForm({ ...form, invitee_name: e.target.value })}
                    placeholder="Maria Chen" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-name-input" />
                </div>
                <div>
                  <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Email *</label>
                  <Input type="email" value={form.invitee_email} onChange={(e) => setForm({ ...form, invitee_email: e.target.value })}
                    placeholder="dispatch@acmefreight.com" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-email-input" />
                </div>
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Expires in (days)</label>
                <Input type="number" min={1} max={90} value={form.expires_days}
                  onChange={(e) => setForm({ ...form, expires_days: parseInt(e.target.value || 14) })}
                  className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="p-3 rounded border text-sm flex items-start gap-2"
                style={{ background: "rgba(16,185,129,0.07)", borderColor: "rgba(16,185,129,0.35)", color: "rgb(110,231,183)" }}>
                <Mail size={16} className="mt-0.5" />
                <div>
                  Invite created &amp; ready to send. Preview the full-color email below — or just hit
                  <strong> Send via Email</strong> and we'll deliver it through Resend with the {brandShort} logo embedded.
                </div>
              </div>

              <div>
                <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Invite Link</label>
                <div className="flex gap-2 mt-1">
                  <Input readOnly value={generated.invite_link}
                    className="bg-[#0B0E14] border-white/10 font-mono text-xs" data-testid="invite-link" />
                  <Button onClick={() => copy(generated.invite_link, "Link copied")} variant="outline" data-testid="invite-link-copy"><Copy size={14} /></Button>
                </div>
              </div>

              {/* Preview tabs */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-mono uppercase" style={{ color: brandAccent }}>Email Preview</label>
                  <div className="flex gap-1 text-[10px] font-mono">
                    <button
                      onClick={() => setPreviewMode("rich")}
                      className={`px-2 py-0.5 rounded border ${previewMode === "rich" ? "" : "opacity-60"}`}
                      style={{
                        borderColor: `${brandAccent}55`,
                        background: previewMode === "rich" ? brandAccent : "transparent",
                        color: previewMode === "rich" ? brandPrimary : brandAccent,
                      }}
                      data-testid="preview-rich-tab"
                    >
                      <Eye size={10} className="inline mr-1" /> Full Color
                    </button>
                    <button
                      onClick={() => setPreviewMode("text")}
                      className={`px-2 py-0.5 rounded border ${previewMode === "text" ? "" : "opacity-60"}`}
                      style={{
                        borderColor: `${brandAccent}55`,
                        background: previewMode === "text" ? brandAccent : "transparent",
                        color: previewMode === "text" ? brandPrimary : brandAccent,
                      }}
                      data-testid="preview-text-tab"
                    >
                      Plain Text
                    </button>
                  </div>
                </div>

                {previewMode === "rich" ? (
                  <div className="mt-1 rounded-lg overflow-hidden border bg-white" style={{ borderColor: `${brandAccent}33` }}>
                    <iframe
                      title="invite-preview"
                      srcDoc={generated.email_html}
                      sandbox=""
                      data-testid="invite-html-preview"
                      style={{ width: "100%", height: 460, border: 0, background: "#F1F5F9" }}
                    />
                  </div>
                ) : (
                  <textarea readOnly value={generated.email_body} rows={12}
                    className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded px-3 py-2 text-xs font-mono whitespace-pre-wrap"
                    data-testid="invite-text-preview" />
                )}

                <div className="flex flex-wrap gap-2 mt-2">
                  <Button
                    onClick={() => sendEmail(generated.invite.invite_id)}
                    disabled={sending}
                    className="font-bold text-black flex-1 min-w-[180px]"
                    style={{ background: brandAccent }}
                    data-testid="invite-send-email-btn"
                  >
                    <Send size={14} className="mr-1.5" />
                    {sending ? "Sending..." : `Send via Email · ${brandShort}`}
                  </Button>
                  <Button onClick={() => copy(generated.email_body, "Email body copied")}
                    variant="outline" className="border-white/10">
                    <Copy size={14} className="mr-1" /> Copy Text
                  </Button>
                  <a
                    href={`mailto:${form.invitee_email}?subject=${encodeURIComponent(generated.subject || `${brandShort} Carrier Invite`)}&body=${encodeURIComponent(generated.email_body)}`}
                    className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded border text-sm"
                    style={{ borderColor: `${brandAccent}55`, color: brandAccent }}
                    data-testid="invite-mailto"
                  >
                    <Mail size={14} /> Open in Mail Client
                  </a>
                </div>
                <div className="text-[10px] font-mono mt-2 text-slate-500">
                  Tip: Direct sending uses Resend (configure under <strong>Connections → Resend</strong>).
                  Mailto opens your local mail app with the plain-text version.
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            {!generated ? (
              <>
                <Button variant="outline" onClick={() => setOpen(false)} className="border-white/10">Cancel</Button>
                <Button onClick={submit} className="font-bold text-black"
                  style={{ background: brandAccent }} data-testid="invite-create-submit">
                  Create Invite
                </Button>
              </>
            ) : (
              <Button onClick={() => { setOpen(false); setGenerated(null); }}
                className="font-bold text-black" style={{ background: brandAccent }}>
                Done
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
