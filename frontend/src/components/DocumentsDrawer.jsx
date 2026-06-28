/**
 * <DocumentsDrawer booking={...} onClose={fn} />
 *
 * Right-side panel that surfaces the full export/import documentation suite
 * for a containerized booking:
 *
 *   • One-click generators for AES Worksheet, Commercial Invoice, Packing
 *     List, Certificate of Origin, Phytosanitary Application, Letter of
 *     Credit, ISF-10, CBP 7501 prep, Broker Cover Letter, SED.
 *   • Upload-external-PDF flow (carrier-issued BL, USDA-issued phyto cert,
 *     signed LC from issuing bank, etc.).
 *   • AES ITN capture form — paste the X-prefixed ITN after manual
 *     AESDirect filing and it auto-creates an ITN_RECEIPT doc record.
 *   • Live doc tracker showing every internal + external doc with status
 *     pills (DRAFT / READY / FILED / RECEIVED / EXPIRED / VOID).
 */
import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText, Download, Upload, ScrollText, Award, Trash2, Plus, RefreshCw, ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { api, BACKEND_URL } from "@/lib/api";
import { authedDownload } from "@/lib/authedDownload";

const GENERATORS = [
  { slug: "aes-worksheet",        label: "AES Filing Worksheet",       blurb: "EEI prep for AESDirect" },
  { slug: "commercial-invoice",   label: "Commercial Invoice",          blurb: "HTS + value + parties" },
  { slug: "packing-list",         label: "Packing List",                blurb: "Per-container detail" },
  { slug: "certificate-of-origin",label: "Certificate of Origin",       blurb: "USMCA / Form A / generic" },
  { slug: "phyto-application",    label: "Phytosanitary Application",   blurb: "USDA-APHIS PPQ Form 572" },
  { slug: "letter-of-credit",     label: "Letter of Credit",            blurb: "UCP 600 presentation copy" },
  { slug: "sed",                  label: "Shipper's Export Declaration",blurb: "Legacy SED format" },
  { slug: "isf-10",               label: "ISF-10 Filing",               blurb: "Importer Security · CBP" },
  { slug: "cbp-7501-prep",        label: "CBP Entry Summary (7501)",    blurb: "Import duty calculation" },
  { slug: "broker-cover-letter",  label: "Broker Cover Letter",         blurb: "Hand-off to customs broker" },
];

const STATUS_COLOR = {
  DRAFT:    "bg-slate-500/15 text-slate-300 border-slate-500/40",
  READY:    "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  FILED:    "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  RECEIVED: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  EXPIRED:  "bg-red-500/15 text-red-300 border-red-500/40",
  VOID:     "bg-zinc-500/15 text-zinc-400 border-zinc-500/40",
};

const DOC_TYPE_LABEL = {
  AES_WORKSHEET: "AES Worksheet",
  ITN_RECEIPT: "ITN Receipt",
  COMMERCIAL_INVOICE: "Commercial Invoice",
  PACKING_LIST: "Packing List",
  CERTIFICATE_OF_ORIGIN: "Certificate of Origin",
  PHYTOSANITARY_PREP: "Phyto Application",
  PHYTOSANITARY_CERT: "Phyto Certificate",
  LETTER_OF_CREDIT: "Letter of Credit",
  SED: "SED",
  ISF_10: "ISF-10",
  CBP_7501_PREP: "CBP 7501",
  BROKER_COVER_LETTER: "Broker Cover Letter",
  BOL_OCEAN: "Ocean BL",
  DOCK_RECEIPT: "Dock Receipt",
  DELIVERY_ORDER: "Delivery Order",
  OTHER: "Other",
};

export function DocumentsDrawer({ booking, onClose }) {
  const [docs, setDocs] = useState([]);
  const [aesFiling, setAesFiling] = useState(booking?.aes_filing || null);
  const [tick, setTick] = useState(0);
  const [itnForm, setItnForm] = useState({ itn: "", port_of_export: booking?.pol || "", license_code: "C33", filed_by: "" });

  const load = async () => {
    try {
      const { data: list } = await api.get(`/international/container-bookings/${booking.booking_id}/docs`);
      setDocs(list.items || []);
      const { data: full } = await api.get(`/international/container-bookings/${booking.booking_id}`);
      setAesFiling(full.aes_filing || null);
    } catch (e) { /* silent */ }
  };
  useEffect(() => { load(); }, [tick, booking?.booking_id]);

  const generatePdf = (slug) => {
    authedDownload(
      `/international/container-bookings/${booking.booking_id}/pdf/${slug}`,
      `${slug.toUpperCase()}_${booking.booking_id}.pdf`,
    );
  };

  const submitItn = async () => {
    if (!itnForm.itn || itnForm.itn.length < 14) {
      toast.error("ITN must be 14+ chars (X-prefixed)");
      return;
    }
    try {
      await api.post(`/international/container-bookings/${booking.booking_id}/aes/filing`, itnForm);
      toast.success(`ITN ${itnForm.itn} captured`);
      setItnForm({ ...itnForm, itn: "" });
      setTick((t) => t + 1);
    } catch (e) {
      console.error(e); toast.error("Failed to capture ITN");
    }
  };

  const deleteDoc = async (doc) => {
    if (!confirm(`Delete ${DOC_TYPE_LABEL[doc.doc_type] || doc.doc_type} record?`)) return;
    try {
      await api.delete(`/international/container-bookings/${booking.booking_id}/docs/${doc.doc_id}`);
      toast.success("Doc removed");
      setTick((t) => t + 1);
    } catch { toast.error("Delete failed"); }
  };

  const updateStatus = async (doc, newStatus) => {
    try {
      await api.put(`/international/container-bookings/${booking.booking_id}/docs/${doc.doc_id}/status`,
        { status: newStatus });
      toast.success(`Status set to ${newStatus}`);
      setTick((t) => t + 1);
    } catch { toast.error("Update failed"); }
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className="bg-[#0B0E14] border-cyan-500/40 max-w-5xl max-h-[90vh] overflow-y-auto"
        data-testid="docs-drawer"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <ScrollText size={18} className="text-cyan-400" />
            Documentation · {booking.booking_number}
            <span className="text-slate-500 text-xs font-mono ml-2">{booking.pol} → {booking.pod}</span>
          </DialogTitle>
        </DialogHeader>

        {/* AES filing capture */}
        <section className="rounded-lg border border-amber-500/40 bg-amber-500/[0.04] p-4 space-y-3"
          data-testid="aes-capture-section">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award size={16} className="text-amber-400" />
              <h3 className="font-bold text-amber-200">AES ITN</h3>
              {aesFiling?.itn && (
                <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/40 border font-mono"
                  data-testid="aes-itn-badge">
                  {aesFiling.itn}
                </Badge>
              )}
            </div>
            <a href="https://aesdirect.census.gov" target="_blank" rel="noreferrer noopener"
               className="text-[11px] text-cyan-300 hover:underline flex items-center gap-1">
              AESDirect <ExternalLink size={10} />
            </a>
          </div>
          {!aesFiling?.itn ? (
            <>
              <p className="text-xs text-slate-400 leading-relaxed">
                Generate the AES Worksheet PDF below, file via AESDirect, then paste the
                X-prefixed ITN here so it&apos;s linked to this shipment.
              </p>
              <div className="grid grid-cols-4 gap-2 items-end">
                <div className="col-span-2">
                  <Label className="text-[10px] font-mono uppercase">ITN *</Label>
                  <Input value={itnForm.itn} onChange={(e) => setItnForm({ ...itnForm, itn: e.target.value.toUpperCase() })}
                    placeholder="X20260628000123" className="bg-[#0B1320] border-white/10 font-mono"
                    data-testid="aes-itn-input" />
                </div>
                <div>
                  <Label className="text-[10px] font-mono uppercase">Port of Export</Label>
                  <Input value={itnForm.port_of_export} onChange={(e) => setItnForm({ ...itnForm, port_of_export: e.target.value })}
                    placeholder="2704" className="bg-[#0B1320] border-white/10"
                    data-testid="aes-port-input" />
                </div>
                <Button onClick={submitItn} className="bg-amber-500 text-black font-bold" data-testid="aes-itn-submit">
                  Capture
                </Button>
              </div>
            </>
          ) : (
            <p className="text-xs text-emerald-200 font-mono">
              Filed at {aesFiling.filed_at?.slice(0, 16)?.replace("T", " ")} · port {aesFiling.port_of_export}
              {aesFiling.license_code && ` · license ${aesFiling.license_code}`}
            </p>
          )}
        </section>

        {/* PDF generators grid */}
        <section className="space-y-3" data-testid="docs-generators">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-cyan-200 flex items-center gap-2">
              <FileText size={14} /> Generate Branded Documents
            </h3>
            <span className="text-[10px] font-mono text-slate-500">All PDFs use the Orisei heraldic template</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {GENERATORS.map((g) => (
              <button key={g.slug} onClick={() => generatePdf(g.slug)}
                data-testid={`gen-${g.slug}`}
                className="flex items-start gap-3 p-3 rounded-md border border-white/5 bg-[#0F1421]
                  hover:border-cyan-500/40 hover:bg-cyan-500/[0.04] transition-colors text-left">
                <Download size={14} className="text-cyan-400 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-100">{g.label}</div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{g.blurb}</div>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* External upload + manual doc tracker entry */}
        <section className="space-y-3 pt-2 border-t border-white/5">
          <UploadCard bookingId={booking.booking_id} onSaved={() => setTick((t) => t + 1)} />
        </section>

        {/* Live doc tracker list */}
        <section className="space-y-3 pt-2 border-t border-white/5">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-cyan-200 flex items-center gap-2">
              <ScrollText size={14} /> Tracked Documents · {docs.length}
            </h3>
            <Button size="sm" variant="ghost" onClick={() => setTick((t) => t + 1)}
              data-testid="docs-refresh">
              <RefreshCw size={12} className="mr-1" /> Refresh
            </Button>
          </div>
          {docs.length === 0 ? (
            <div className="text-center text-slate-500 text-sm py-6">
              No tracked documents yet. Generate a PDF above or upload an external doc.
            </div>
          ) : (
            <div className="space-y-2" data-testid="docs-list">
              {docs.map((d) => (
                <div key={d.doc_id} className="flex items-center gap-3 p-2.5 rounded border border-white/5 bg-[#0F1421]"
                  data-testid={`doc-row-${d.doc_id}`}>
                  <Badge className={`${STATUS_COLOR[d.status] || ""} border font-mono text-[10px]`}>
                    {d.status}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm">
                      <span className="font-medium">{DOC_TYPE_LABEL[d.doc_type] || d.doc_type}</span>
                      {d.reference_number && (
                        <span className="ml-2 font-mono text-[11px] text-cyan-300">{d.reference_number}</span>
                      )}
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {d.source} {d.counterparty && `· ${d.counterparty}`}
                      {d.filed_with_agency && ` · ${d.filed_with_agency}`}
                      {d.filename && ` · ${d.filename}`}
                    </div>
                  </div>
                  <Select value={d.status} onValueChange={(v) => updateStatus(d, v)}>
                    <SelectTrigger className="bg-[#0B1320] border-white/10 h-7 text-[11px] w-28"
                      data-testid={`doc-status-${d.doc_id}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                      {["DRAFT", "READY", "FILED", "RECEIVED", "EXPIRED", "VOID"].map((s) => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {d.file_id && (
                    <a
                      href={`${BACKEND_URL}/api/international/container-bookings/${booking.booking_id}/docs/${d.doc_id}/file`}
                      onClick={(e) => {
                        e.preventDefault();
                        authedDownload(
                          `/international/container-bookings/${booking.booking_id}/docs/${d.doc_id}/file`,
                          d.filename || "doc.pdf",
                        );
                      }}
                      data-testid={`doc-download-${d.doc_id}`}
                      className="text-cyan-300 hover:underline text-[11px] flex items-center gap-1">
                      <Download size={11} /> File
                    </a>
                  )}
                  <button onClick={() => deleteDoc(d)}
                    data-testid={`doc-delete-${d.doc_id}`}
                    className="text-red-300/70 hover:text-red-300">
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </DialogContent>
    </Dialog>
  );
}

/* Upload an external PDF (carrier BL, supplier invoice, signed LC, USDA-
   issued phytosanitary cert, etc.) and attach to this booking. */
function UploadCard({ bookingId, onSaved }) {
  const [doc_type, setType] = useState("BOL_OCEAN");
  const [reference_number, setRef] = useState("");
  const [counterparty, setCpty] = useState("");
  const [filed_with_agency, setAgency] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!file) { toast.error("Choose a file to upload"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("doc_type", doc_type);
      fd.append("status", "RECEIVED");
      if (reference_number) fd.append("reference_number", reference_number);
      if (counterparty) fd.append("counterparty", counterparty);
      if (filed_with_agency) fd.append("filed_with_agency", filed_with_agency);
      fd.append("file", file);
      await api.post(`/international/container-bookings/${bookingId}/docs/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("File uploaded");
      setRef(""); setCpty(""); setAgency(""); setFile(null);
      onSaved();
    } catch (e) {
      console.error(e); toast.error("Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="docs-upload-card">
      <h3 className="font-bold text-cyan-200 flex items-center gap-2">
        <Upload size={14} /> Upload External Document
      </h3>
      <p className="text-[11px] text-slate-500 leading-relaxed">
        Attach carrier-issued bills of lading, supplier invoices, USDA-issued
        phytosanitary certificates, bank-signed letters of credit, customs
        clearance receipts, or any other partner-issued PDF.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label className="text-[10px] font-mono uppercase">Doc type</Label>
          <Select value={doc_type} onValueChange={setType}>
            <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="upload-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#0B0E14] border-cyan-500/30 max-h-72">
              {Object.entries(DOC_TYPE_LABEL).map(([code, label]) => (
                <SelectItem key={code} value={code} data-testid={`upload-type-${code}`}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-[10px] font-mono uppercase">Reference #</Label>
          <Input value={reference_number} onChange={(e) => setRef(e.target.value)}
            placeholder="LC# / Phyto# / Master BL#" className="bg-[#0B1320] border-white/10"
            data-testid="upload-ref" />
        </div>
        <div>
          <Label className="text-[10px] font-mono uppercase">Counterparty</Label>
          <Input value={counterparty} onChange={(e) => setCpty(e.target.value)}
            placeholder="HSBC / USDA-APHIS / supplier name" className="bg-[#0B1320] border-white/10"
            data-testid="upload-counterparty" />
        </div>
        <div>
          <Label className="text-[10px] font-mono uppercase">Issuing agency / bank</Label>
          <Input value={filed_with_agency} onChange={(e) => setAgency(e.target.value)}
            placeholder="USDA-APHIS / CBP / Issuing Bank" className="bg-[#0B1320] border-white/10"
            data-testid="upload-agency" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <input type="file" accept=".pdf,.png,.jpg,.jpeg"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          data-testid="upload-file"
          className="text-xs text-slate-400 file:bg-cyan-500/10 file:text-cyan-300 file:border file:border-cyan-500/30 file:rounded file:px-3 file:py-1 file:mr-3" />
        <Button onClick={submit} disabled={busy || !file} className="bg-cyan-500 text-black font-bold ml-auto"
          data-testid="upload-submit">
          <Plus size={13} className="mr-1" /> Attach
        </Button>
      </div>
    </div>
  );
}
