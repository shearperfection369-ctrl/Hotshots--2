import React, { useEffect, useState, useCallback } from "react";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { authedDownload } from "@/lib/authedDownload";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Mail, Globe, FileText, Copy, Plus, Edit3, Trash2, Save,
  Eye, Send, Sparkles, Shield, ExternalLink, Receipt,
} from "lucide-react";
import { toast } from "sonner";

/**
 * /broker-settings — Orisei admin hub for:
 *  • Editable carrier/shipper invite templates
 *  • Domain config (apex + site URL + support email + legal name)
 *  • Doc Override editor (edit any field on BOL/RC/Invoice/Quote PDFs)
 */

const TABS = [
  { id: "invites",   label: "Invite Templates", icon: Mail },
  { id: "domain",    label: "Domain",           icon: Globe },
  { id: "doc-edit",  label: "Document Editor",  icon: FileText },
  { id: "invoices",  label: "Invoices",         icon: Receipt },
];

export default function BrokerSettings() {
  const [tab, setTab] = useState("invites");
  return (
    <>
      <Topbar title="Brokerage Settings" subtitle="Invites · Domain · Editable Documents · Invoices" />
      <div className="p-4 md:p-6">
        <div className="flex gap-2 flex-wrap mb-4" data-testid="broker-settings-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              data-testid={`tab-${id}`}
              onClick={() => setTab(id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono uppercase tracking-wider transition border ${
                tab === id
                  ? "bg-cyan-500 text-black border-cyan-400 shadow-[0_0_18px_rgba(34,211,238,0.4)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>

        {tab === "invites"  && <InviteTemplatesTab />}
        {tab === "domain"   && <DomainTab />}
        {tab === "doc-edit" && <DocEditorTab />}
        {tab === "invoices" && <InvoicesTab />}
      </div>
    </>
  );
}

// ============================================================
// INVITE TEMPLATES
// ============================================================
function InviteTemplatesTab() {
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const [preview, setPreview] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/orisei/workflow/invites/templates");
      setItems(data.items || []);
    } catch (e) { toast.error("Could not load templates"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const startNew = (kind) => setEditing({
    template_id: null, kind, name: `New ${kind} invite`,
    subject: "", from_name: "Orisei Freight", body_html: "<p>Write your invite here...</p>",
  });

  const save = async () => {
    if (!editing) return;
    if (!editing.subject || !editing.body_html) {
      toast.error("Subject and body are required"); return;
    }
    try {
      const payload = {
        kind: editing.kind, name: editing.name,
        subject: editing.subject, from_name: editing.from_name,
        body_html: editing.body_html,
      };
      if (editing.template_id) {
        await api.put(`/orisei/workflow/invites/templates/${editing.template_id}`, payload);
        toast.success("Template updated");
      } else {
        await api.post("/orisei/workflow/invites/templates", payload);
        toast.success("Template created");
      }
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    }
  };

  const remove = async (t) => {
    if (!window.confirm(`Delete "${t.name}"?`)) return;
    try {
      await api.delete(`/orisei/workflow/invites/templates/${t.template_id}`);
      toast.success("Deleted"); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Could not delete"); }
  };

  const showPreview = async (t) => {
    try {
      const { data } = await api.post("/orisei/workflow/invites/preview", {
        template_id: t.template_id,
      });
      setPreview(data);
    } catch (e) { toast.error("Could not render preview"); }
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      <Card className="col-span-12 lg:col-span-5 p-4 bg-slate-950/60 border-white/10">
        <div className="flex justify-between items-center mb-3">
          <div className="text-xs font-mono uppercase tracking-widest text-cyan-300">Templates</div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => startNew("carrier")} data-testid="new-carrier-tpl" className="bg-cyan-500 text-black hover:bg-cyan-400">
              <Plus size={12} className="mr-1" /> Carrier
            </Button>
            <Button size="sm" onClick={() => startNew("shipper")} data-testid="new-shipper-tpl" className="bg-amber-500 text-black hover:bg-amber-400">
              <Plus size={12} className="mr-1" /> Shipper
            </Button>
          </div>
        </div>
        <div className="space-y-2">
          {items.map(t => (
            <div key={t.template_id}
                 data-testid={`tpl-${t.template_id}`}
                 className="p-3 rounded-lg bg-slate-900/60 border border-white/5 hover:border-cyan-400/30 transition">
              <div className="flex justify-between items-start gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge className={t.kind === "carrier"
                      ? "bg-cyan-500/15 text-cyan-200 border-cyan-400/30 text-[9px]"
                      : "bg-amber-500/15 text-amber-200 border-amber-400/30 text-[9px]"}>
                      {t.kind.toUpperCase()}
                    </Badge>
                    {t.is_default && <Badge variant="outline" className="border-white/10 text-slate-400 text-[9px]">DEFAULT</Badge>}
                  </div>
                  <div className="text-sm text-white mt-1 truncate">{t.name}</div>
                  <div className="text-[11px] text-slate-400 mt-0.5 truncate">{t.subject}</div>
                </div>
                <div className="flex flex-col gap-1 items-end">
                  <Button size="sm" variant="outline" onClick={() => showPreview(t)} className="h-7 bg-slate-900 border-white/10 text-xs">
                    <Eye size={11} className="mr-1" />Preview
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditing(t)} className="h-7 bg-slate-900 border-white/10 text-xs">
                    <Edit3 size={11} className="mr-1" />Edit
                  </Button>
                  {!t.is_default && (
                    <Button size="sm" variant="outline" onClick={() => remove(t)} className="h-7 bg-red-950/40 border-red-400/30 text-red-200 text-xs">
                      <Trash2 size={11} />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="col-span-12 lg:col-span-7 p-4 bg-slate-950/60 border-white/10">
        {!editing && (
          <div className="text-center text-slate-500 py-12">
            <Mail size={36} className="mx-auto mb-3 opacity-40" />
            Select a template to edit or create a new one.
            <div className="mt-3 text-xs text-slate-400">
              Use <code className="text-amber-300">{`{{token}}`}</code> placeholders.
              Available defaults: <span className="text-cyan-200">carrier_name, carrier_mc, shipper_name, lane_focus, onboard_url, portal_url, expires_days, site_url</span>
            </div>
          </div>
        )}
        {editing && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm text-white">
                {editing.template_id ? "Edit template" : "New template"}
                <Badge className="ml-2 text-[9px]">{editing.kind.toUpperCase()}</Badge>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEditing(null)} className="bg-slate-900 border-white/10 h-8 text-xs">
                  Cancel
                </Button>
                <Button onClick={save} data-testid="save-tpl-btn" className="bg-emerald-500 text-black hover:bg-emerald-400 h-8 text-xs">
                  <Save size={12} className="mr-1" /> Save
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Name</Label>
                <Input
                  data-testid="tpl-name"
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  className="bg-slate-900 border-white/10"
                />
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">From name</Label>
                <Input
                  value={editing.from_name || ""}
                  onChange={(e) => setEditing({ ...editing, from_name: e.target.value })}
                  className="bg-slate-900 border-white/10"
                />
              </div>
            </div>

            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Subject</Label>
              <Input
                data-testid="tpl-subject"
                value={editing.subject}
                onChange={(e) => setEditing({ ...editing, subject: e.target.value })}
                className="bg-slate-900 border-white/10"
              />
            </div>

            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Body (HTML)</Label>
              <Textarea
                data-testid="tpl-body"
                value={editing.body_html}
                onChange={(e) => setEditing({ ...editing, body_html: e.target.value })}
                className="bg-slate-900 border-white/10 font-mono text-xs min-h-[280px]"
              />
            </div>

            <div className="text-[11px] text-slate-400">
              <Sparkles size={11} className="inline text-amber-300" /> Tokens: {`{{carrier_name}} {{carrier_mc}} {{shipper_name}} {{lane_focus}} {{onboard_url}} {{portal_url}} {{expires_days}} {{site_url}}`}
            </div>
          </div>
        )}
      </Card>

      <Dialog open={!!preview} onOpenChange={() => setPreview(null)}>
        <DialogContent className="max-w-3xl bg-white text-slate-900">
          <DialogHeader>
            <DialogTitle>Email Preview</DialogTitle>
          </DialogHeader>
          {preview && (
            <div className="border rounded">
              <div className="p-3 bg-slate-100 border-b">
                <div className="text-xs text-slate-500">FROM</div>
                <div className="font-semibold">{preview.from_name}</div>
                <div className="text-xs text-slate-500 mt-2">SUBJECT</div>
                <div className="font-semibold">{preview.subject}</div>
              </div>
              <div className="p-5 prose max-w-none" dangerouslySetInnerHTML={{ __html: preview.body_html }} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================
// DOMAIN CONFIG
// ============================================================
function DomainTab() {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/orisei/workflow/domain-config");
      setCfg(data);
    } catch (e) { toast.error("Could not load domain config"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!cfg?.primary_domain) { toast.error("Primary domain required"); return; }
    setSaving(true);
    try {
      const { data } = await api.post("/orisei/workflow/domain-config", {
        primary_domain: cfg.primary_domain,
        site_url: cfg.site_url || undefined,
        apex_url: cfg.apex_url || undefined,
        support_email: cfg.support_email || undefined,
        legal_name: cfg.legal_name || undefined,
        propagate_to_static_site: cfg.propagate_to_static_site !== false,
      });
      setCfg(data);
      toast.success(`Domain saved${data.propagated_to_static_site ? " · static site updated" : ""}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    } finally { setSaving(false); }
  };

  if (!cfg) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="grid grid-cols-12 gap-4">
      <Card className="col-span-12 lg:col-span-7 p-5 bg-slate-950/60 border-white/10">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="text-cyan-300" size={18} />
          <div className="text-sm font-semibold text-white">Primary Domain</div>
        </div>
        <div className="space-y-3">
          <div>
            <Label className="text-[10px] uppercase tracking-widest text-slate-400">Primary domain</Label>
            <Input
              data-testid="domain-primary"
              value={cfg.primary_domain || ""}
              onChange={(e) => setCfg({ ...cfg, primary_domain: e.target.value })}
              placeholder="oriseifreight.com"
              className="bg-slate-900 border-white/10"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Site URL</Label>
              <Input
                value={cfg.site_url || ""}
                onChange={(e) => setCfg({ ...cfg, site_url: e.target.value })}
                placeholder={`https://${cfg.primary_domain}`}
                className="bg-slate-900 border-white/10"
              />
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Apex URL</Label>
              <Input
                value={cfg.apex_url || ""}
                onChange={(e) => setCfg({ ...cfg, apex_url: e.target.value })}
                placeholder={`https://${cfg.primary_domain}`}
                className="bg-slate-900 border-white/10"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Support email</Label>
              <Input
                value={cfg.support_email || ""}
                onChange={(e) => setCfg({ ...cfg, support_email: e.target.value })}
                placeholder={`hello@${cfg.primary_domain}`}
                className="bg-slate-900 border-white/10"
              />
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Legal name</Label>
              <Input
                value={cfg.legal_name || ""}
                onChange={(e) => setCfg({ ...cfg, legal_name: e.target.value })}
                className="bg-slate-900 border-white/10"
              />
            </div>
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 mt-2">
            <input
              type="checkbox"
              checked={cfg.propagate_to_static_site !== false}
              onChange={(e) => setCfg({ ...cfg, propagate_to_static_site: e.target.checked })}
              data-testid="domain-propagate"
            />
            Also rewrite domain across static marketing site HTML files
          </label>
          <Button
            onClick={save}
            disabled={saving}
            data-testid="domain-save-btn"
            className="bg-cyan-500 text-black hover:bg-cyan-400 font-semibold"
          >
            {saving ? "Saving…" : <><Save size={14} className="mr-1.5" /> Save & Propagate</>}
          </Button>
        </div>
      </Card>

      <Card className="col-span-12 lg:col-span-5 p-5 bg-slate-950/60 border-amber-400/20">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="text-amber-300" size={16} />
          <div className="text-xs font-mono uppercase tracking-widest text-amber-300">How this propagates</div>
        </div>
        <ul className="text-xs text-slate-300 space-y-2 list-disc pl-4">
          <li>All <code className="text-cyan-200">{`{{site_url}}`}</code> tokens in invite emails resolve to your new domain instantly.</li>
          <li>Customer Portal & Carrier Onboarding share-links use the new domain.</li>
          <li>If &ldquo;rewrite static site&rdquo; is on, every HTML file under <code className="text-cyan-200">/orisei-marketing</code> is rewritten — old hardcoded <code>oriseifreight.com</code> references update.</li>
          <li>Footer / legal name in generated PDFs respects <b>legal_name</b>.</li>
        </ul>
      </Card>
    </div>
  );
}

// ============================================================
// DOC EDITOR (BOL / RateCon / Invoice / Quote field overrides)
// ============================================================
const DOC_KINDS = [
  { id: "bol",      label: "Bill of Lading" },
  { id: "rate_con", label: "Rate Confirmation" },
  { id: "invoice",  label: "Invoice" },
  { id: "quote",    label: "Quote" },
];

function DocEditorTab() {
  const [docKind, setDocKind] = useState("invoice");
  const [docId, setDocId] = useState("");
  const [overrides, setOverrides] = useState({});
  const [rawText, setRawText] = useState("");

  const load = async () => {
    if (!docId) { toast.error("Enter a document ID"); return; }
    try {
      const { data } = await api.get(`/orisei/workflow/doc-overrides/${docKind}/${docId}`);
      const ov = data.overrides || {};
      setOverrides(ov);
      setRawText(JSON.stringify(ov, null, 2));
      toast.success(Object.keys(ov).length ? `Loaded ${Object.keys(ov).length} override(s)` : "No overrides yet — start editing");
    } catch (e) { toast.error("Could not load"); }
  };

  const save = async () => {
    let parsed;
    try { parsed = JSON.parse(rawText); }
    catch { toast.error("Invalid JSON in override body"); return; }
    try {
      await api.post("/orisei/workflow/doc-overrides", {
        doc_kind: docKind, doc_id: docId, overrides: parsed,
      });
      toast.success("Saved — PDF will re-render with overrides");
      setOverrides(parsed);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not save");
    }
  };

  const clear = async () => {
    if (!window.confirm("Clear all overrides for this doc?")) return;
    try {
      await api.delete(`/orisei/workflow/doc-overrides/${docKind}/${docId}`);
      setOverrides({}); setRawText("{}"); toast.success("Cleared");
    } catch (e) { toast.error("Could not clear"); }
  };

  const addField = (key) => {
    const next = { ...overrides, [key]: "" };
    setOverrides(next);
    setRawText(JSON.stringify(next, null, 2));
  };

  return (
    <Card className="p-5 bg-slate-950/60 border-white/10">
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 md:col-span-4">
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Doc kind</Label>
          <div className="flex gap-1.5 mt-1 flex-wrap">
            {DOC_KINDS.map(k => (
              <button
                key={k.id}
                data-testid={`doc-kind-${k.id}`}
                onClick={() => setDocKind(k.id)}
                className={`px-3 py-1.5 rounded-md text-xs border transition ${
                  docKind === k.id
                    ? "bg-cyan-500/20 border-cyan-400/60 text-cyan-200"
                    : "bg-slate-900/60 border-white/10 text-slate-400 hover:border-cyan-400/30"
                }`}
              >{k.label}</button>
            ))}
          </div>
        </div>
        <div className="col-span-12 md:col-span-5">
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Doc ID</Label>
          <Input
            data-testid="doc-id"
            value={docId} onChange={(e) => setDocId(e.target.value)}
            placeholder="INV-ABC123 / RC-... / BOL-..."
            className="bg-slate-900 border-white/10"
          />
        </div>
        <div className="col-span-12 md:col-span-3 flex items-end gap-2">
          <Button onClick={load} className="bg-slate-700 hover:bg-slate-600 h-9 text-xs flex-1" data-testid="doc-load">Load</Button>
          <Button onClick={save} className="bg-cyan-500 text-black hover:bg-cyan-400 h-9 text-xs flex-1" data-testid="doc-save">Save</Button>
          <Button onClick={clear} variant="outline" className="bg-red-950/40 border-red-400/30 text-red-200 h-9 text-xs">Clear</Button>
        </div>

        <div className="col-span-12 md:col-span-8">
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Overrides (JSON)</Label>
          <Textarea
            data-testid="doc-overrides-json"
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            className="bg-slate-900 border-white/10 font-mono text-xs min-h-[320px]"
            placeholder='{"shipper_name": "Acme Inc.", "weight_lbs": 12500, "notes": "Handle with care"}'
          />
          <div className="text-[11px] text-slate-400 mt-1">
            Any key on the doc can be overridden. Re-download the PDF to see overrides applied.
          </div>
        </div>

        <div className="col-span-12 md:col-span-4">
          <Label className="text-[10px] uppercase tracking-widest text-slate-400">Quick add field</Label>
          <div className="flex gap-1.5 flex-wrap mt-1">
            {{
              bol:      ["shipper_name", "shipper_address", "consignee_name", "consignee_address", "carrier_name", "carrier_mc", "weight_lbs", "pieces", "nmfc_class", "freight_charges", "special_instructions"],
              rate_con: ["carrier_name", "carrier_mc", "rate_usd", "pickup_date", "delivery_date", "fuel_surcharge_usd", "quickpay_offered", "quickpay_fee_pct", "notes"],
              invoice:  ["customer_name", "customer_billing_address", "due_at", "payment_terms", "notes", "tax_usd", "total_usd"],
              quote:    ["customer_name", "origin", "destination", "line_haul_usd", "fuel_surcharge_usd", "valid_for_days", "notes"],
            }[docKind].map(f => (
              <button
                key={f}
                onClick={() => addField(f)}
                className="px-2 py-1 rounded bg-slate-900 border border-white/10 text-[10px] text-slate-300 hover:border-cyan-400/30"
                data-testid={`add-field-${f}`}
              >
                + {f}
              </button>
            ))}
          </div>
          {docId && (
            <div className="mt-4 space-y-1.5">
              <button
                type="button"
                onClick={() => authedDownload(
                  `/api/orisei/workflow/invoices/${docId}/pdf`,
                  { filename: `${docKind}_${docId}.pdf`, inline: true }
                )}
                className="inline-flex items-center gap-1 text-cyan-300 text-xs hover:underline cursor-pointer"
                data-testid="doc-download-pdf"
              >
                <ExternalLink size={11} /> Download {docKind} PDF
              </button>
              <a
                href={`/document-archive?doc_id=${docId}`}
                className="block text-amber-300 text-[11px] hover:underline"
                data-testid="doc-history-link"
              >
                ↳ View immutable version history for <span className="font-mono">{docId}</span>
              </a>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

// ============================================================
// INVOICES
// ============================================================
export function InvoicesTab() {
  const [invoices, setInvoices] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ customer_id: "", booking_ids: [], notes: "", due_in_days: 30 });
  const [edit, setEdit] = useState(null);

  const load = useCallback(async () => {
    try {
      const [inv, cust, bk] = await Promise.all([
        api.get("/orisei/workflow/invoices"),
        api.get("/orisei/customers"),
        api.get("/brokerage/margins"),
      ]);
      setInvoices(inv.data.items || []);
      setCustomers(cust.data.items || []);
      setBookings((bk.data?.bookings || []).filter(b => b.booked_id));
    } catch (e) { toast.error("Could not load invoices"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!draft.customer_id) { toast.error("Pick a customer"); return; }
    if (!draft.booking_ids.length) { toast.error("Pick at least one booking"); return; }
    try {
      const { data } = await api.post("/orisei/workflow/invoices", draft);
      toast.success(`Invoice ${data.invoice_id} created`);
      setOpen(false);
      setDraft({ customer_id: "", booking_ids: [], notes: "", due_in_days: 30 });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not create");
    }
  };

  const saveEdit = async () => {
    if (!edit) return;
    try {
      await api.put(`/orisei/workflow/invoices/${edit.invoice_id}`, {
        line_items: edit.line_items,
        notes: edit.notes,
        payment_terms: edit.payment_terms,
        tax_usd: parseFloat(edit.tax_usd || 0),
        status: edit.status,
      });
      toast.success("Invoice updated");
      setEdit(null); load();
    } catch (e) { toast.error("Could not update"); }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-300">
          Invoices · {invoices.length}
        </div>
        <Button onClick={() => setOpen(true)} data-testid="new-invoice-btn" className="bg-cyan-500 text-black hover:bg-cyan-400">
          <Plus size={14} className="mr-1" /> New Branded Invoice
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {invoices.map(inv => (
          <Card key={inv.invoice_id} className="p-4 bg-slate-950/60 border-white/10 hover:border-cyan-400/30 transition" data-testid={`invoice-${inv.invoice_id}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="font-mono text-cyan-200 text-sm">{inv.invoice_id}</div>
                <div className="text-xs text-white mt-1">{inv.customer_name}</div>
              </div>
              <Badge className="bg-amber-500/20 text-amber-200 border-amber-400/40 text-[9px]">
                {(inv.status || "issued").toUpperCase()}
              </Badge>
            </div>
            <div className="text-2xl font-mono text-white mt-3 tabular-nums">
              ${(inv.total_usd || 0).toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-400 mt-1">
              Due {inv.due_at?.slice(0,10) || "—"} · {inv.payment_terms || "Net 30"}
            </div>
            <div className="flex gap-2 mt-3">
              <button type="button"
                 onClick={() => authedDownload(
                   `/api/orisei/workflow/invoices/${inv.invoice_id}/pdf`,
                   { filename: `Invoice_${inv.invoice_id}.pdf`, inline: true }
                 )}
                 data-testid={`invoice-pdf-${inv.invoice_id}`}
                 className="flex-1 inline-flex items-center justify-center gap-1 text-[11px] text-cyan-300 hover:underline cursor-pointer">
                <ExternalLink size={11} /> PDF
              </button>
              <Button size="sm" variant="outline" onClick={() => setEdit({
                ...inv,
                tax_usd: inv.tax_usd || 0,
              })} className="bg-slate-900 border-white/10 text-xs flex-1 h-7">
                <Edit3 size={11} className="mr-1" /> Edit
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-slate-950 border-white/10 text-white max-w-xl">
          <DialogHeader>
            <DialogTitle>New Branded Invoice</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Customer</Label>
              <select
                data-testid="invoice-customer"
                value={draft.customer_id}
                onChange={(e) => setDraft({ ...draft, customer_id: e.target.value })}
                className="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-sm"
              >
                <option value="">— pick a customer —</option>
                {customers.map(c => (
                  <option key={c.customer_id} value={c.customer_id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">
                Bookings to invoice
              </Label>
              <div className="max-h-48 overflow-y-auto border border-white/10 rounded p-2 space-y-1 bg-slate-900">
                {bookings.map(b => (
                  <label key={b.booked_id} className="flex items-center gap-2 text-xs">
                    <input
                      type="checkbox"
                      checked={draft.booking_ids.includes(b.booked_id)}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? [...draft.booking_ids, b.booked_id]
                          : draft.booking_ids.filter(x => x !== b.booked_id);
                        setDraft({ ...draft, booking_ids: next });
                      }}
                    />
                    <span className="font-mono text-cyan-200">{b.booked_id}</span>
                    <span className="text-slate-400">{b.origin} → {b.destination}</span>
                    <span className="ml-auto text-amber-300">
                      ${(b.settled_rate_usd || b.forecast_rate_usd || 0).toLocaleString()}
                    </span>
                  </label>
                ))}
                {!bookings.length && <div className="text-slate-500 text-xs">No bookings yet.</div>}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Due in (days)</Label>
                <Input type="number" min="1" max="120"
                       value={draft.due_in_days}
                       onChange={(e) => setDraft({ ...draft, due_in_days: parseInt(e.target.value) || 30 })}
                       className="bg-slate-900 border-white/10" />
              </div>
            </div>
            <div>
              <Label className="text-[10px] uppercase tracking-widest text-slate-400">Notes</Label>
              <Textarea value={draft.notes}
                        onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                        placeholder="Optional reference / PO / comments"
                        className="bg-slate-900 border-white/10" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)} className="bg-slate-900 border-white/10">Cancel</Button>
            <Button onClick={create} data-testid="invoice-create-btn" className="bg-cyan-500 text-black hover:bg-cyan-400">
              <Receipt size={14} className="mr-1.5" /> Generate Invoice
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!edit} onOpenChange={() => setEdit(null)}>
        <DialogContent className="bg-slate-950 border-white/10 text-white max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Invoice {edit?.invoice_id}</DialogTitle>
          </DialogHeader>
          {edit && (
            <div className="space-y-3">
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Line items</Label>
                <div className="space-y-1">
                  {(edit.line_items || []).map((li, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <Input
                        value={li.label}
                        onChange={(e) => {
                          const next = [...edit.line_items];
                          next[i] = { ...li, label: e.target.value };
                          setEdit({ ...edit, line_items: next });
                        }}
                        className="bg-slate-900 border-white/10 flex-1"
                      />
                      <Input
                        type="number" min="0" step="0.01"
                        value={li.amount_usd}
                        onChange={(e) => {
                          const next = [...edit.line_items];
                          next[i] = { ...li, amount_usd: parseFloat(e.target.value) || 0 };
                          setEdit({ ...edit, line_items: next });
                        }}
                        className="bg-slate-900 border-white/10 w-32"
                      />
                      <Button variant="outline" size="sm"
                              onClick={() => {
                                const next = edit.line_items.filter((_, idx) => idx !== i);
                                setEdit({ ...edit, line_items: next });
                              }}
                              className="bg-red-950/40 border-red-400/30 text-red-200">
                        <Trash2 size={11} />
                      </Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm"
                          onClick={() => setEdit({
                            ...edit,
                            line_items: [...(edit.line_items || []), { label: "", amount_usd: 0 }],
                          })}
                          className="bg-slate-900 border-white/10 text-xs mt-1">
                    <Plus size={11} className="mr-1" /> Add line
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-slate-400">Tax</Label>
                  <Input type="number" min="0" step="0.01"
                         value={edit.tax_usd}
                         onChange={(e) => setEdit({ ...edit, tax_usd: e.target.value })}
                         className="bg-slate-900 border-white/10" />
                </div>
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-slate-400">Terms</Label>
                  <Input value={edit.payment_terms || ""}
                         onChange={(e) => setEdit({ ...edit, payment_terms: e.target.value })}
                         className="bg-slate-900 border-white/10" />
                </div>
                <div>
                  <Label className="text-[10px] uppercase tracking-widest text-slate-400">Status</Label>
                  <select value={edit.status || "issued"}
                          onChange={(e) => setEdit({ ...edit, status: e.target.value })}
                          className="w-full bg-slate-900 border border-white/10 rounded px-2 py-2 text-sm">
                    <option value="issued">Issued</option>
                    <option value="sent">Sent</option>
                    <option value="paid">Paid</option>
                    <option value="overdue">Overdue</option>
                    <option value="void">Void</option>
                  </select>
                </div>
              </div>
              <div>
                <Label className="text-[10px] uppercase tracking-widest text-slate-400">Notes</Label>
                <Textarea value={edit.notes || ""}
                          onChange={(e) => setEdit({ ...edit, notes: e.target.value })}
                          className="bg-slate-900 border-white/10" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)} className="bg-slate-900 border-white/10">Cancel</Button>
            <Button onClick={saveEdit} className="bg-emerald-500 text-black hover:bg-emerald-400">
              <Save size={14} className="mr-1.5" /> Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
