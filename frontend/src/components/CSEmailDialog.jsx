import React, { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Mail, Send } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * CSEmailDialog · quick-send pre-templated emails to the CS team
 * (Quality / Parts / Distribution / Strategic Accounts).
 *
 * Three canned request types most commonly used by dispatch:
 *   1. Open QN (Quality Notification)
 *   2. Provide Contact Details
 *   3. Provide Disposition Instructions
 *
 * Renders the body in a textarea so the user can tweak before hitting send.
 * Sends via /api/email/send (MOCKED — logs to db.outbound_emails).
 *
 * Usage:
 *   const [open, setOpen] = useState(false);
 *   <CSEmailDialog open={open} onClose={() => setOpen(false)}
 *     prefill={{ reference: "TN-71829", carrier: "XPO" }} />
 */

const TEAMS = [
  { id: "cs_quality",      label: "CS · Quality",            email: "CS-Quality@tennantco.com" },
  { id: "cs_parts",        label: "CS · Parts",              email: "CS-Parts@tennantco.com" },
  { id: "cs_distribution", label: "CS · Distribution",       email: "CS-Distribution@tennantco.com" },
  { id: "cs_strategic",    label: "CS · Strategic Accounts", email: "CS-StrategicAccounts@tennantco.com" },
];

const REQUESTS = [
  {
    id: "open_qn",
    label: "Open a Quality Notification (QN)",
    subject: ({ ref }) => `Quality Notification Request — ${ref || "(reference)"}`,
    body: ({ ref, user }) => (
`Hi team,

Please open a Quality Notification for the following shipment:

Reference: ${ref || "(fill in)"}
Issue summary: 

Steps so far:
• 
• 

Please confirm the QN number when created.

Thanks,
${user?.name || "Dispatch"}
Tennant · Transportation`
    ),
  },
  {
    id: "contact_details",
    label: "Provide contact details",
    subject: ({ ref }) => `Need contact details — ${ref || "(reference)"}`,
    body: ({ ref, user }) => (
`Hi team,

Could you provide the best contact for the customer/account associated with this shipment?

Reference: ${ref || "(fill in)"}
Reason: 

Specifically I need:
• Name and phone
• Email
• Best window to reach them

Thanks in advance,
${user?.name || "Dispatch"}
Tennant · Transportation`
    ),
  },
  {
    id: "disposition",
    label: "Provide disposition instructions",
    subject: ({ ref }) => `Disposition instructions needed — ${ref || "(reference)"}`,
    body: ({ ref, user }) => (
`Hi team,

We have product/freight on hold and need disposition instructions:

Reference: ${ref || "(fill in)"}
Current location: 
Quantity / pieces: 
Reason on hold: 

Options to consider:
• Release to customer as-is
• Return to origin
• Scrap / dispose
• Re-route to (location)

Please advise — thanks!
${user?.name || "Dispatch"}
Tennant · Transportation`
    ),
  },
];

export default function CSEmailDialog({ open, onClose, prefill = {}, user = {} }) {
  const [team, setTeam] = useState(TEAMS[0].id);
  const [requestKind, setRequestKind] = useState(REQUESTS[0].id);
  const [ref, setRef] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [cc, setCc] = useState("");
  const [sending, setSending] = useState(false);

  // Whenever the request kind or reference changes, refresh subject/body
  useEffect(() => {
    if (!open) return;
    setRef(prefill.reference || prefill.carrier || "");
  }, [open, prefill.reference, prefill.carrier]);

  useEffect(() => {
    if (!open) return;
    const r = REQUESTS.find((x) => x.id === requestKind);
    if (!r) return;
    setSubject(r.subject({ ref }));
    setBody(r.body({ ref, user }));
  }, [open, requestKind, ref, user]);

  const teamObj = TEAMS.find((t) => t.id === team);

  const send = async () => {
    if (!teamObj) return;
    setSending(true);
    try {
      const { data } = await api.post("/email/send", {
        to: teamObj.email,
        cc: cc || "",
        subject,
        body_text: body,
        kind: `cs_${requestKind}`,
        ref: ref || null,
      });
      toast.success(`Sent to ${teamObj.label}`, {
        description: `Message ID ${data.message_id} · status: ${data.status}`,
      });
      onClose();
    } catch (e) {
      toast.error("Send failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setSending(false);
    }
  };

  const openMailto = () => {
    if (!teamObj) return;
    const m = `mailto:${teamObj.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}${cc ? `&cc=${encodeURIComponent(cc)}` : ""}`;
    window.location.href = m;
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-2xl" data-testid="cs-email-dialog">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Mail size={16} className="text-cyan-400" /> Email Customer Service
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-3 py-1">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Send to</Label>
              <select
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                data-testid="cs-email-team"
                className="w-full mt-1 bg-[#11151F] border border-white/10 rounded px-2 py-1.5 text-sm text-white"
              >
                {TEAMS.map((t) => (
                  <option key={t.id} value={t.id}>{t.label} — {t.email}</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Request type</Label>
              <select
                value={requestKind}
                onChange={(e) => setRequestKind(e.target.value)}
                data-testid="cs-email-request"
                className="w-full mt-1 bg-[#11151F] border border-white/10 rounded px-2 py-1.5 text-sm text-white"
              >
                {REQUESTS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Reference (BOL / SO / PO)</Label>
              <Input
                value={ref}
                onChange={(e) => setRef(e.target.value)}
                placeholder="TN-71829"
                data-testid="cs-email-ref"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">CC (optional)</Label>
              <Input
                value={cc}
                onChange={(e) => setCc(e.target.value)}
                placeholder="manager@tennantco.com"
                data-testid="cs-email-cc"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
          </div>

          <div>
            <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Subject</Label>
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              data-testid="cs-email-subject"
              className="bg-[#11151F] border-white/10 mt-1 font-mono text-xs"
            />
          </div>

          <div>
            <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Body — edit before sending</Label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              data-testid="cs-email-body"
              rows={12}
              className="w-full mt-1 bg-[#11151F] border border-white/10 rounded px-3 py-2 text-xs font-mono text-slate-100"
            />
          </div>
        </div>

        <DialogFooter className="flex-wrap gap-2">
          <Button variant="outline" onClick={onClose} className="border-white/10 text-slate-300">Cancel</Button>
          <Button
            variant="outline"
            onClick={openMailto}
            data-testid="cs-email-mailto"
            className="border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"
          >
            Open Mail Client
          </Button>
          <Button
            onClick={send}
            disabled={sending}
            data-testid="cs-email-send"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
          >
            <Send size={13} className="mr-1.5" /> {sending ? "Sending…" : "Send Now (MOCKED)"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
