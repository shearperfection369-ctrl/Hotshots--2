import React, { useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { authedDownload } from "../lib/authedDownload";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";
import {
  FileText, Download, Mail, ExternalLink, Upload, History, Copy, ShieldCheck,
} from "lucide-react";
import { useAuth } from "../lib/auth";

/**
 * RoutingGuide page — surfaces the platform's Domestic US / Canada / Mexico
 * Inbound Routing Guide PDF (stored in GridFS) with a one-click "email to
 * customer" button that opens the user's mail client pre-filled with subject,
 * body, and a direct download link to the live PDF.
 *
 * - GET /api/routing-guide/info        — metadata for the active revision
 * - GET /api/routing-guide/pdf         — public PDF stream (so the link works
 *                                        in external supplier mailboxes)
 * - GET /api/routing-guide/email-template?to=…&cc=… — pre-built mailto:
 * - POST /api/routing-guide/upload     — admin uploads a new revision
 * - GET /api/routing-guide/versions    — full revision history
 */
export default function RoutingGuide() {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);

  const [emailOpen, setEmailOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ to: "", cc: "" });
  const [emailPreview, setEmailPreview] = useState(null);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadForm, setUploadForm] = useState({ revision: "", effective_date: "", notes: "" });
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  const isAdmin = user?.role === "admin" || user?.role === "dispatcher";

  const load = async () => {
    setLoading(true);
    try {
      const [a, b] = await Promise.all([
        api.get("/routing-guide/info"),
        api.get("/routing-guide/versions"),
      ]);
      setInfo(a.data);
      setVersions(b.data);
    } catch (e) {
      toast.error("Could not load routing guide");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const pdfHref = `${BACKEND_URL}/api/routing-guide/pdf`;
  const pdfDownloadHref = `${BACKEND_URL}/api/routing-guide/pdf?download=1`;

  // ---------- Email flow ----------
  const openEmail = () => {
    setEmailForm({ to: "", cc: "" });
    setEmailPreview(null);
    setEmailOpen(true);
  };

  const buildAndSendEmail = async () => {
    if (!emailForm.to) { toast.error("Recipient required"); return; }
    try {
      // Call the backend "real" send (currently mocked — logs to outbound_emails).
      // The backend builds the subject and body from the active routing-guide
      // metadata when client doesn't supply them.
      const { data } = await api.post("/routing-guide/send-email", {
        to: emailForm.to,
        cc: emailForm.cc,
        subject: "",
        body_text: "",
        kind: "routing_guide",
      });
      setEmailPreview({
        subject: `Inbound Routing Guide — ${info?.revision || ""} (Eff. ${info?.effective_date || ""})`.trim(),
        body: `Sent to ${data.to} from ${data.from}.\n\nMessage ID: ${data.message_id}\nProvider: ${data.status === "mocked" ? "MOCKED (no email actually sent)" : "SendGrid"}\n\nTo wire real delivery, paste your SendGrid API key into backend/.env as SENDGRID_API_KEY.`,
      });
      toast.success(`Routing guide queued for ${data.to}`, {
        description: data.status === "mocked" ? "Email is MOCKED — see Email Log for full payload" : "Sent via SendGrid",
      });
    } catch (e) {
      toast.error("Could not send — " + (e.response?.data?.detail || e.message));
    }
  };

  const openMailto = async () => {
    // Fall back to a real mailto: launch as well, in case the user wants
    // their personal mail client open with the prefilled draft.
    try {
      const { data } = await api.get("/routing-guide/email-template", {
        params: { to: emailForm.to, cc: emailForm.cc },
      });
      const fullMailto = data.mailto.replace(
        encodeURIComponent("/api/routing-guide/pdf"),
        encodeURIComponent(pdfHref)
      );
      window.location.href = fullMailto;
    } catch (e) {
      toast.error("Could not open mail client");
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(pdfHref);
      toast.success("PDF link copied");
    } catch { toast.error("Copy failed"); }
  };

  // ---------- Upload flow (admin/dispatcher) ----------
  const handleUpload = async (file) => {
    if (!file) return;
    if (!/\.pdf$/i.test(file.name)) { toast.error("Please pick a PDF"); return; }
    const form = new FormData();
    form.append("file", file);
    form.append("revision", uploadForm.revision || "");
    form.append("effective_date", uploadForm.effective_date || "");
    form.append("notes", uploadForm.notes || "");
    setUploading(true);
    try {
      const { data } = await api.post("/routing-guide/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Uploaded ${data.filename}`);
      setUploadOpen(false);
      setUploadForm({ revision: "", effective_date: "", notes: "" });
      await load();
    } catch (e) {
      toast.error("Upload failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <Topbar
        title="Inbound Routing Guide"
        subtitle="Orisei Freight Solutions · Domestic US · Canada · Mexico · Puerto Rico"
      />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">

        {/* Hero card — guide metadata + primary actions */}
        <Card className="hud-surface p-6 lg:col-span-8" data-testid="routing-guide-hero">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/30 shrink-0">
              <FileText size={26} className="text-cyan-400" />
            </div>
            <div className="flex-1 min-w-[260px]">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">
                Routing Guide · Active Revision
              </div>
              <h2 className="font-display text-2xl font-bold mt-1 text-white">
                {info?.title || "Loading…"}
              </h2>
              {info && (
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono">
                  <span className="text-slate-300">
                    <span className="text-slate-500 uppercase tracking-wider">Revision · </span>
                    <span className="text-cyan-300">{info.revision}</span>
                  </span>
                  <span className="text-slate-300">
                    <span className="text-slate-500 uppercase tracking-wider">Effective · </span>
                    <span className="text-emerald-300">{info.effective_date}</span>
                  </span>
                  <span className="text-slate-300">
                    <span className="text-slate-500 uppercase tracking-wider">File · </span>
                    <span className="text-slate-200">{((info.size_bytes || 0) / 1024).toFixed(0)} KB</span>
                  </span>
                </div>
              )}
              {info?.notes && (
                <p className="text-sm text-slate-300 mt-3 max-w-3xl leading-relaxed">
                  {info.notes}
                </p>
              )}
            </div>
          </div>

          {/* Primary actions */}
          <div className="mt-5 flex flex-wrap gap-2">
            <Button
              onClick={openEmail}
              data-testid="rg-email-btn"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
            >
              <Mail size={15} className="mr-1.5" /> EMAIL TO CUSTOMER
            </Button>
            <a
              href={pdfDownloadHref}
              data-testid="rg-download-btn"
              className="inline-flex items-center px-4 py-2 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-xs font-mono uppercase tracking-wider"
            >
              <Download size={13} className="mr-1.5" /> Download PDF
            </a>
            <a
              href={pdfHref}
              target="_blank" rel="noreferrer"
              data-testid="rg-open-btn"
              className="inline-flex items-center px-4 py-2 rounded border border-white/10 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 text-xs font-mono uppercase tracking-wider"
            >
              <ExternalLink size={13} className="mr-1.5" /> Open in new tab
            </a>
            <button
              onClick={copyLink}
              data-testid="rg-copy-link-btn"
              className="inline-flex items-center px-4 py-2 rounded border border-white/10 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 text-xs font-mono uppercase tracking-wider"
            >
              <Copy size={13} className="mr-1.5" /> Copy share link
            </button>
            {isAdmin && (
              <button
                onClick={() => setUploadOpen(true)}
                data-testid="rg-upload-btn"
                className="inline-flex items-center px-4 py-2 rounded border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10 text-xs font-mono uppercase tracking-wider ml-auto"
              >
                <Upload size={13} className="mr-1.5" /> Upload new revision
              </button>
            )}
          </div>
        </Card>

        {/* Side card — what this guide covers */}
        <Card className="hud-surface p-5 lg:col-span-4" data-testid="rg-coverage">
          <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">
            <ShieldCheck size={11} /> What it covers
          </div>
          <ul className="mt-3 space-y-2 text-sm text-slate-300">
            <li className="flex gap-2"><span className="text-cyan-400 mt-0.5">›</span><span>Approved carriers per mode (Small Package · LTL · Full Truckload)</span></li>
            <li className="flex gap-2"><span className="text-cyan-400 mt-0.5">›</span><span>PO number + receiving-location requirements on every BOL</span></li>
            <li className="flex gap-2"><span className="text-cyan-400 mt-0.5">›</span><span>Country-specific instructions for USA, Canada, Mexico, Puerto Rico</span></li>
            <li className="flex gap-2"><span className="text-cyan-400 mt-0.5">›</span><span>Freight terms (Prepaid + Add · Collect · 3rd-Party)</span></li>
            <li className="flex gap-2"><span className="text-cyan-400 mt-0.5">›</span><span>Routing exceptions & escalation contacts</span></li>
          </ul>
          <div className="mt-4 p-3 rounded bg-cyan-500/[0.05] border border-cyan-500/20 text-xs text-cyan-200">
            <span className="font-mono uppercase text-[10px] tracking-wider text-cyan-400">Tip · </span>
            Suppliers must follow this guide on every shipment where we are the routing party.
          </div>
        </Card>

        {/* Version history */}
        <Card className="hud-surface p-5 lg:col-span-12" data-testid="rg-history">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2">
                <History size={12} /> Revision History
              </div>
              <h3 className="font-display text-lg font-bold mt-0.5">All Uploaded Versions · {versions.length}</h3>
            </div>
          </div>
          {loading ? (
            <div className="text-center py-8 text-slate-500">Loading…</div>
          ) : versions.length === 0 ? (
            <div className="text-center py-8 text-slate-500">No revisions on file yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="text-left py-2 px-3">Revision</th>
                    <th className="text-left py-2 px-3">Effective Date</th>
                    <th className="text-left py-2 px-3">Filename</th>
                    <th className="text-right py-2 px-3">Size</th>
                    <th className="text-left py-2 px-3">Uploaded By</th>
                    <th className="text-left py-2 px-3">Uploaded At</th>
                    <th className="text-center py-2 px-3">PDF</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {versions.map((v, i) => (
                    <tr key={v.file_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`rg-version-${i}`}>
                      <td className="py-2 px-3 text-cyan-300">{v.revision || "—"}</td>
                      <td className="py-2 px-3 text-emerald-300 text-xs">{v.effective_date || "—"}</td>
                      <td className="py-2 px-3 text-slate-200 text-xs">{v.filename}</td>
                      <td className="py-2 px-3 text-right text-slate-300">{((v.size_bytes || 0) / 1024).toFixed(0)} KB</td>
                      <td className="py-2 px-3 text-slate-300 text-xs">{v.uploaded_by_name || "—"}</td>
                      <td className="py-2 px-3 text-slate-500 text-xs">{v.uploaded_at ? new Date(v.uploaded_at).toLocaleString() : "—"}</td>
                      <td className="py-2 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => authedDownload("/api/routing-guide/pdf", { filename: "Routing_Guide.pdf", inline: true })}
                          className="text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1 cursor-pointer"
                        ><Download size={12} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* ---------- Email dialog ---------- */}
      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-lg" data-testid="rg-email-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">Email Routing Guide</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">To</Label>
              <Input
                value={emailForm.to}
                onChange={(e) => setEmailForm({ ...emailForm, to: e.target.value })}
                placeholder="supplier@example.com"
                data-testid="rg-email-to"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">CC (optional)</Label>
              <Input
                value={emailForm.cc}
                onChange={(e) => setEmailForm({ ...emailForm, cc: e.target.value })}
                placeholder="transportation@oriseifreight.com"
                data-testid="rg-email-cc"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <div className="text-xs text-slate-400 leading-relaxed pt-2">
              We'll open your default mail client with a pre-written subject, body, and a direct download link
              to the live PDF. The link works for external suppliers — no internal login required.
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEmailOpen(false)}
              className="border-white/10 text-slate-300"
              data-testid="rg-email-cancel"
            >Cancel</Button>
            <Button
              onClick={openMailto}
              variant="outline"
              data-testid="rg-email-mailto"
              className="border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"
              disabled={!emailForm.to}
            >
              Open Mail Client
            </Button>
            <Button
              onClick={buildAndSendEmail}
              data-testid="rg-email-send"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
              disabled={!emailForm.to}
            >
              <Mail size={14} className="mr-1.5" /> Send Now (MOCKED)
            </Button>
          </DialogFooter>
          {emailPreview && (
            <div className="mt-2 p-2 bg-white/[0.02] border border-white/5 rounded text-[11px] text-slate-400">
              <div className="font-mono text-cyan-400 uppercase tracking-wider text-[9px] mb-1">Preview · subject</div>
              <div className="text-slate-200 mb-2">{emailPreview.subject}</div>
              <div className="font-mono text-cyan-400 uppercase tracking-wider text-[9px] mb-1">Body</div>
              <pre className="whitespace-pre-wrap text-slate-300">{emailPreview.body}</pre>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ---------- Upload dialog ---------- */}
      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-md" data-testid="rg-upload-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">Upload New Revision</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Revision Label</Label>
              <Input
                value={uploadForm.revision}
                onChange={(e) => setUploadForm({ ...uploadForm, revision: e.target.value })}
                placeholder="Revision 30"
                data-testid="rg-upload-revision"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Effective Date</Label>
              <Input
                type="date"
                value={uploadForm.effective_date}
                onChange={(e) => setUploadForm({ ...uploadForm, effective_date: e.target.value })}
                data-testid="rg-upload-effective"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Notes (optional)</Label>
              <Input
                value={uploadForm.notes}
                onChange={(e) => setUploadForm({ ...uploadForm, notes: e.target.value })}
                placeholder="Summary of what changed in this revision"
                data-testid="rg-upload-notes"
                className="bg-[#11151F] border-white/10 mt-1"
              />
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={(e) => handleUpload(e.target.files?.[0])}
              className="hidden"
              data-testid="rg-upload-file"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setUploadOpen(false)}
              className="border-white/10 text-slate-300"
              data-testid="rg-upload-cancel"
            >Cancel</Button>
            <Button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              data-testid="rg-upload-pick"
              className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold"
            >
              {uploading ? "Uploading…" : <><Upload size={14} className="mr-1.5" /> Pick PDF & Upload</>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
