import React, { useEffect, useState, useMemo } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";
import {
  FileText, FileSignature, FileSpreadsheet, FileCheck2, Globe2, Plus, Download,
  Pencil, Mail, History, Eye, Copy, Search, Wand2
} from "lucide-react";

const DOC_TYPES = [
  { id: "BOL", label: "Bill of Lading", icon: FileText, accent: "cyan" },
  { id: "COMMERCIAL_INVOICE", label: "Commercial Invoice", icon: FileSpreadsheet, accent: "emerald" },
  { id: "PACKING_SLIP", label: "Packing Slip", icon: FileSignature, accent: "yellow" },
  { id: "WEIGHT_CERT", label: "Weight Certificate", icon: FileCheck2, accent: "purple" },
  { id: "COO", label: "Certificate of Origin", icon: Globe2, accent: "rose" },
];

const ACCENT_MAP = {
  cyan: "border-cyan-500/30 text-cyan-400",
  emerald: "border-emerald-500/30 text-emerald-400",
  yellow: "border-yellow-500/30 text-yellow-400",
  purple: "border-purple-500/30 text-purple-400",
  rose: "border-rose-500/30 text-rose-400",
};

// Editable fields presented in the create + amend dialogs, in stable order.
const EDIT_FIELDS = [
  { key: "shipper", label: "Shipper" },
  { key: "consignee", label: "Consignee" },
  { key: "origin", label: "Origin" },
  { key: "destination", label: "Destination" },
  { key: "carrier", label: "Carrier" },
  { key: "commodity", label: "Commodity" },
  { key: "weight", label: "Weight (lbs)" },
  { key: "pieces", label: "Pieces" },
  { key: "value", label: "Value (USD)" },
  { key: "bol_no", label: "BOL #" },
  { key: "pro_no", label: "PRO #" },
  { key: "country_origin", label: "Country of Origin" },
];

const EMPTY_FORM = {
  type: "BOL", shipment_ref: "",
  shipper: "Tennant Company", consignee: "", origin: "", destination: "",
  carrier: "", commodity: "", weight: "", pieces: "", value: "",
  bol_no: "", pro_no: "", country_origin: "USA",
};

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [shipments, setShipments] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [filter, setFilter] = useState("BOL"); // ALL | BOL | COMMERCIAL_INVOICE | ...
  const [q, setQ] = useState("");

  // Dialogs
  const [amend, setAmend] = useState(null);     // { doc, form, reason }
  const [emailModal, setEmailModal] = useState(null); // { doc, to, cc, message, preview? }
  const [historyDoc, setHistoryDoc] = useState(null); // doc
  const [genFromShip, setGenFromShip] = useState(false);
  const [genShipId, setGenShipId] = useState("");

  const load = async () => {
    const { data } = await api.get("/documents");
    setDocs(data);
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    api.get("/shipments?limit=200").then(({ data }) => setShipments(data)).catch(() => { /* ignore */ });
  }, []);

  // -------- Create flow ----------
  const create = async () => {
    try {
      const { data } = await api.post("/documents", {
        type: form.type,
        shipment_ref: form.shipment_ref,
        data: form,
      });
      toast.success("Document generated", {
        description: (
          <a
            href={`${BACKEND_URL}/api/documents/${data.document_id}/pdf`}
            target="_blank" rel="noreferrer"
            className="text-cyan-300 underline"
          >Download PDF →</a>
        ),
      });
      setOpen(false);
      setForm(EMPTY_FORM);
      load();
    } catch (e) { toast.error("Failed to generate"); }
  };

  // -------- Amend flow ----------
  const startAmend = (doc) => {
    setAmend({
      doc,
      form: { ...EMPTY_FORM, ...(doc.data || {}) },
      reason: "",
    });
  };
  const saveAmend = async () => {
    if (!amend) return;
    try {
      await api.patch(`/documents/${amend.doc.document_id}`, {
        data: amend.form,
        reason: amend.reason,
      });
      toast.success(`Amended ${amend.doc.document_id} · revision saved`);
      setAmend(null);
      load();
    } catch (e) { toast.error("Amendment failed"); }
  };

  // -------- Email flow ----------
  const startEmail = (doc) => {
    const data = doc.data || {};
    const defaultTo = data.consignee_email || "";
    setEmailModal({
      doc, to: defaultTo, cc: "", message: "",
      preview: null,
    });
  };
  const submitEmail = async () => {
    if (!emailModal) return;
    try {
      const { data } = await api.post(`/documents/${emailModal.doc.document_id}/email`, {
        to: emailModal.to, cc: emailModal.cc, message: emailModal.message,
      });
      setEmailModal({ ...emailModal, preview: data });
    } catch (e) { toast.error("Email build failed"); }
  };

  // -------- Generate-from-shipment flow ----------
  const generateFromShipment = async () => {
    if (!genShipId) { toast.error("Pick a shipment first"); return; }
    try {
      const { data } = await api.post(`/shipments/${genShipId}/generate-bol`, {});
      toast.success(`Generated ${data.document_id} from shipment`);
      setGenFromShip(false); setGenShipId("");
      setFilter("BOL");
      load();
    } catch (e) { toast.error("Could not generate BOL from shipment"); }
  };

  // -------- Filter / search ----------
  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return docs.filter((d) => {
      if (filter !== "ALL" && d.type !== filter) return false;
      if (!ql) return true;
      const hay = [d.document_id, d.shipment_ref, d.type, d.created_by, d.data?.consignee, d.data?.carrier, d.data?.origin, d.data?.destination]
        .filter(Boolean).join(" ").toLowerCase();
      return hay.includes(ql);
    });
  }, [docs, filter, q]);

  const counts = useMemo(() => {
    const c = { ALL: docs.length };
    for (const t of DOC_TYPES) c[t.id] = docs.filter((d) => d.type === t.id).length;
    return c;
  }, [docs]);

  return (
    <>
      <Topbar title="Documents" subtitle="All BOLs, invoices, packing slips & origin certificates · view, amend, email" />
      <div className="p-4 md:p-6 space-y-5">

        {/* Type cards (open the create dialog for that type) */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {DOC_TYPES.map(({ id, label, icon: Icon, accent }) => (
            <button
              key={id}
              onClick={() => { setForm({ ...EMPTY_FORM, type: id }); setOpen(true); }}
              data-testid={`new-doc-${id}`}
              className={`hud-surface text-left p-4 rounded-lg border ${ACCENT_MAP[accent]} hover:bg-white/[0.03] transition-all`}
            >
              <Icon size={22} />
              <div className="mt-2 text-sm font-display font-semibold text-white">{label}</div>
              <div className="text-[10px] font-mono text-slate-500 mt-1">{counts[id] || 0} stored</div>
            </button>
          ))}
        </div>

        {/* Filter pills + Search + Generate-from-shipment */}
        <Card className="hud-surface p-3" data-testid="docs-toolbar">
          <div className="flex flex-wrap items-center gap-2">
            {["ALL", ...DOC_TYPES.map((d) => d.id)].map((id) => {
              const label = id === "ALL" ? "All" : DOC_TYPES.find((d) => d.id === id)?.label;
              const active = filter === id;
              return (
                <button
                  key={id}
                  onClick={() => setFilter(id)}
                  data-testid={`filter-${id}`}
                  className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider border transition-colors ${active ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40" : "border-white/10 text-slate-400 hover:text-white"}`}
                >
                  {label} <span className="opacity-60">({counts[id] || 0})</span>
                </button>
              );
            })}
            <div className="flex-1 min-w-[220px] relative ml-auto">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <Input
                value={q} onChange={(e) => setQ(e.target.value)}
                placeholder="Search by Doc ID, shipment, consignee, carrier…"
                data-testid="docs-search"
                className="pl-9 bg-[#0B0E14] border-white/10"
              />
            </div>
            <Button
              data-testid="gen-bol-from-shipment-btn"
              onClick={() => setGenFromShip(true)}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
            >
              <Wand2 size={14} className="mr-1.5" /> BOL FROM SHIPMENT
            </Button>
          </div>
        </Card>

        {/* Document archive table */}
        <Card className="hud-surface overflow-hidden" data-testid="docs-archive">
          <div className="px-5 py-3 flex items-center justify-between border-b border-white/5">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Document Archive</div>
              <h3 className="font-display text-lg font-bold mt-1">{filtered.length} of {docs.length} {filter === "ALL" ? "documents" : DOC_TYPES.find((d) => d.id === filter)?.label.toLowerCase() + "s"}</h3>
            </div>
            <Button onClick={() => { setForm({ ...EMPTY_FORM, type: filter === "ALL" ? "BOL" : filter }); setOpen(true); }}
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="quick-new-doc">
              <Plus size={14} className="mr-1" /> NEW
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Doc ID · Rev</th>
                  <th className="text-left py-3 px-4">Type</th>
                  <th className="text-left py-3 px-4">Shipment</th>
                  <th className="text-left py-3 px-4">Consignee → Dest</th>
                  <th className="text-left py-3 px-4">Carrier</th>
                  <th className="text-right py-3 px-4">Updated</th>
                  <th className="text-center py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {filtered.map((d) => {
                  const data = d.data || {};
                  const isAmended = (d.amendments || []).length > 0;
                  return (
                    <tr key={d.document_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`doc-row-${d.document_id}`}>
                      <td className="py-2.5 px-4">
                        <div className="text-cyan-300">{d.document_id}</div>
                        {isAmended && (
                          <button
                            onClick={() => setHistoryDoc(d)}
                            data-testid={`doc-history-${d.document_id}`}
                            className="text-[10px] font-mono text-yellow-400 hover:text-yellow-300 inline-flex items-center gap-1 mt-0.5"
                          >
                            <History size={10} /> Rev {d.version} · {d.amendments.length} amendment{d.amendments.length === 1 ? "" : "s"}
                          </button>
                        )}
                      </td>
                      <td className="py-2.5 px-4 text-slate-300">{DOC_TYPES.find((t) => t.id === d.type)?.label || d.type}</td>
                      <td className="py-2.5 px-4 text-slate-400">{d.shipment_ref || "—"}</td>
                      <td className="py-2.5 px-4 text-slate-300 text-xs">
                        <span className="text-white">{data.consignee || "—"}</span>
                        <div className="text-slate-500">{data.origin || "—"} → {data.destination || "—"}</div>
                      </td>
                      <td className="py-2.5 px-4 text-slate-300">{data.carrier || "—"}</td>
                      <td className="py-2.5 px-4 text-right text-slate-500 text-xs">
                        {new Date(d.updated_at || d.created_at).toLocaleString()}
                      </td>
                      <td className="py-2.5 px-4">
                        <div className="inline-flex items-center gap-0.5 flex-wrap justify-center">
                          <a
                            href={`${BACKEND_URL}/api/documents/${d.document_id}/pdf`}
                            target="_blank" rel="noreferrer"
                            data-testid={`view-pdf-${d.document_id}`}
                            title="View PDF"
                            className="p-1.5 rounded text-cyan-300 hover:bg-cyan-500/10 inline-flex items-center"
                          ><Eye size={13} /></a>
                          <a
                            href={`${BACKEND_URL}/api/documents/${d.document_id}/pdf`}
                            download
                            data-testid={`download-pdf-${d.document_id}`}
                            title="Download PDF"
                            className="p-1.5 rounded text-cyan-300 hover:bg-cyan-500/10 inline-flex items-center"
                          ><Download size={13} /></a>
                          <button
                            onClick={() => startEmail(d)}
                            data-testid={`email-doc-${d.document_id}`}
                            title="Email this document"
                            className="p-1.5 rounded text-emerald-300 hover:bg-emerald-500/10 inline-flex items-center"
                          ><Mail size={13} /></button>
                          <button
                            onClick={() => startAmend(d)}
                            data-testid={`amend-doc-${d.document_id}`}
                            title="Amend (creates a new revision)"
                            className="p-1.5 rounded text-yellow-300 hover:bg-yellow-500/10 inline-flex items-center"
                          ><Pencil size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr><td colSpan={7} className="text-center py-10 text-slate-500">
                    {docs.length === 0 ? "No documents yet. Click a type card above to generate one." : "No documents match the current filter."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* ---------- Create dialog ---------- */}
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
            {EDIT_FIELDS.map((f) => (
              <Field key={f.key} label={f.label} value={form[f.key] || ""} onChange={(v) => setForm((cur) => ({ ...cur, [f.key]: v }))} testid={`doc-field-${f.key}`} />
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button data-testid="submit-document" onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Generate Document</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------- Amend dialog ---------- */}
      <Dialog open={!!amend} onOpenChange={(o) => !o && setAmend(null)}>
        <DialogContent className="bg-[#131821] border-yellow-500/30 max-w-2xl" data-testid="amend-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-yellow-300 flex items-center gap-2">
              <Pencil size={16} /> Amend {amend?.doc.document_id} · {DOC_TYPES.find((d) => d.id === amend?.doc.type)?.label}
            </DialogTitle>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              Current revision: {amend?.doc.version || 1} — saving creates revision {(amend?.doc.version || 1) + 1}.
            </div>
          </DialogHeader>
          {amend && (
            <>
              <div className="grid grid-cols-2 gap-3 max-h-[55vh] overflow-y-auto pr-1">
                {EDIT_FIELDS.map((f) => (
                  <Field
                    key={f.key} label={f.label}
                    value={amend.form[f.key] ?? ""}
                    onChange={(v) => setAmend({ ...amend, form: { ...amend.form, [f.key]: v } })}
                    testid={`amend-field-${f.key}`}
                  />
                ))}
              </div>
              <div className="mt-3">
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Reason for amendment</Label>
                <Input
                  value={amend.reason}
                  onChange={(e) => setAmend({ ...amend, reason: e.target.value })}
                  placeholder="e.g., weight increased after re-weigh"
                  data-testid="amend-reason"
                  className="mt-1 bg-[#0B0E14] border-white/10"
                />
              </div>
            </>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAmend(null)}>Cancel</Button>
            <Button onClick={saveAmend} data-testid="amend-save" className="bg-yellow-500 hover:bg-yellow-400 text-black font-bold">
              Save Revision
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------- Email dialog ---------- */}
      <Dialog open={!!emailModal} onOpenChange={(o) => !o && setEmailModal(null)}>
        <DialogContent className="bg-[#131821] border-emerald-500/30 max-w-2xl" data-testid="email-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-emerald-300 flex items-center gap-2">
              <Mail size={16} /> Email {emailModal?.doc.document_id} · {DOC_TYPES.find((d) => d.id === emailModal?.doc.type)?.label}
            </DialogTitle>
          </DialogHeader>
          {emailModal && !emailModal.preview && (
            <div className="space-y-3">
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">To</Label>
                <Input
                  value={emailModal.to}
                  onChange={(e) => setEmailModal({ ...emailModal, to: e.target.value })}
                  placeholder="recipient@company.com"
                  data-testid="email-to" className="mt-1 bg-[#0B0E14] border-white/10"
                />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">CC (optional)</Label>
                <Input
                  value={emailModal.cc}
                  onChange={(e) => setEmailModal({ ...emailModal, cc: e.target.value })}
                  data-testid="email-cc" className="mt-1 bg-[#0B0E14] border-white/10"
                />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Message (optional)</Label>
                <textarea
                  value={emailModal.message}
                  onChange={(e) => setEmailModal({ ...emailModal, message: e.target.value })}
                  placeholder="Add a personal note (will appear under the document summary)…"
                  data-testid="email-message"
                  className="w-full mt-1 bg-[#0B0E14] border border-white/10 rounded p-2 text-sm font-mono h-28 resize-none"
                />
              </div>
            </div>
          )}
          {emailModal?.preview && (
            <div className="space-y-3" data-testid="email-preview">
              <div>
                <Label className="text-[10px] font-mono uppercase text-cyan-400">Subject</Label>
                <div className="mt-1 p-2 bg-[#0B0E14] border border-white/10 rounded text-sm text-slate-200">{emailModal.preview.subject}</div>
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase text-cyan-400">Body</Label>
                <pre className="mt-1 p-3 bg-[#0B0E14] border border-white/10 rounded text-xs text-slate-300 whitespace-pre-wrap font-mono max-h-72 overflow-y-auto">{emailModal.preview.body}</pre>
              </div>
              <div className="flex gap-2">
                <a
                  href={emailModal.preview.mailto}
                  data-testid="email-open-mailto"
                  className="flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 text-xs font-mono uppercase tracking-wider"
                >
                  <Mail size={14} /> Open in mail client
                </a>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(`${emailModal.preview.subject}\n\n${emailModal.preview.body}`);
                    toast.success("Email copied to clipboard");
                  }}
                  data-testid="email-copy"
                  className="inline-flex items-center gap-2 px-3 py-2 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-xs font-mono uppercase tracking-wider"
                >
                  <Copy size={14} /> Copy
                </button>
                <a
                  href={`${BACKEND_URL}/api/documents/${emailModal.doc.document_id}/pdf`}
                  target="_blank" rel="noreferrer"
                  data-testid="email-view-pdf"
                  className="inline-flex items-center gap-2 px-3 py-2 rounded border border-white/10 text-slate-300 hover:bg-white/5 text-xs font-mono uppercase tracking-wider"
                >
                  <Eye size={14} /> View PDF
                </a>
              </div>
            </div>
          )}
          <DialogFooter>
            {emailModal?.preview ? (
              <Button onClick={() => setEmailModal(null)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Done</Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => setEmailModal(null)}>Cancel</Button>
                <Button onClick={submitEmail} data-testid="email-build" className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold" disabled={!emailModal?.to}>
                  Build Email
                </Button>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------- Amendment history ---------- */}
      <Dialog open={!!historyDoc} onOpenChange={(o) => !o && setHistoryDoc(null)}>
        <DialogContent className="bg-[#131821] border-cyan-500/30 max-w-2xl" data-testid="history-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2">
              <History size={16} /> {historyDoc?.document_id} · Amendment trail
            </DialogTitle>
            <div className="text-[10px] font-mono uppercase text-slate-500">
              {historyDoc?.amendments?.length || 0} amendment{(historyDoc?.amendments?.length || 0) === 1 ? "" : "s"} · Current revision {historyDoc?.version}
            </div>
          </DialogHeader>
          {historyDoc && (
            <div className="max-h-[60vh] overflow-y-auto space-y-3 pr-1">
              {historyDoc.amendments.slice().reverse().map((a, i) => (
                <div key={i} className="p-3 rounded border border-white/5 bg-white/[0.02]">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="text-cyan-400">{new Date(a.amended_at).toLocaleString()}</span>
                    <span className="text-slate-500">by {a.amended_by}</span>
                  </div>
                  {a.reason && <div className="text-sm text-slate-200 mt-2 italic">"{a.reason}"</div>}
                  <div className="mt-2 space-y-1">
                    {(a.changes || []).map((c, j) => (
                      <div key={j} className="text-xs font-mono">
                        <span className="text-slate-500">{c.field}: </span>
                        <span className="text-red-300 line-through">{String(c.from ?? "—")}</span>
                        <span className="text-slate-500 mx-1">→</span>
                        <span className="text-emerald-300">{String(c.to ?? "—")}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {historyDoc.amendments.length === 0 && (
                <div className="text-center py-6 text-slate-500 text-sm">No amendments yet.</div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setHistoryDoc(null)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------- Generate-from-shipment ---------- */}
      <Dialog open={genFromShip} onOpenChange={setGenFromShip}>
        <DialogContent className="bg-[#131821] border-cyan-500/30 max-w-lg" data-testid="gen-bol-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2">
              <Wand2 size={16} /> Generate BOL from existing shipment
            </DialogTitle>
            <div className="text-[10px] font-mono uppercase text-slate-500">Pre-fills all BOL fields from the shipment record. Land it in the archive, then amend as needed.</div>
          </DialogHeader>
          <div className="space-y-3">
            <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Pick a shipment</Label>
            <Select value={genShipId} onValueChange={setGenShipId}>
              <SelectTrigger className="bg-[#0B0E14] border-white/10" data-testid="gen-bol-shipment-select"><SelectValue placeholder={`${shipments.length} shipments available…`} /></SelectTrigger>
              <SelectContent className="max-h-72">
                {shipments.map((s) => (
                  <SelectItem key={s.shipment_id} value={s.shipment_id}>
                    {s.reference || s.shipment_id} · {s.carrier} · {s.origin?.city} → {s.destination?.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setGenFromShip(false)}>Cancel</Button>
            <Button onClick={generateFromShipment} data-testid="gen-bol-confirm" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" disabled={!genShipId}>
              Generate BOL
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
