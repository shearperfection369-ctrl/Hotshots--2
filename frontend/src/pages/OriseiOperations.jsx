import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Plus, Users, FileText, Send, Truck, Copy, Trash2, Mail,
  DollarSign, ExternalLink, Building2, ClipboardCheck,
} from "lucide-react";
import { authedDownload } from "@/lib/authedDownload";
import { CarrierCombobox } from "@/components/CarrierCombobox";
import { Autocomplete } from "@/components/Autocomplete";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// FastAPI returns validation errors as an array of objects; toast.error chokes on non-strings.
function errText(e, fallback) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return `${d[0].loc?.slice(-1)[0] || "field"}: ${d[0].msg}`;
  return fallback;
}

// Strip empty-string values so Pydantic Optional[EmailStr] / numbers don't 422.
function clean(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v === "" || v === undefined) continue;
    out[k] = v;
  }
  return out;
}

/** /orisei-operations — Customers · Quotes · Rate Cons · Portal Links */
export default function OriseiOperations() {
  const [tab, setTab] = useState("customers");
  return (
    <>
      <Topbar title="Orisei Operations" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <Card className="hud-surface p-5" data-testid="orisei-ops-header">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
            Real-world brokerage operations
          </div>
          <h1 className="font-display text-3xl font-black mt-1 flex items-center gap-3">
            <Building2 className="text-cyan-400" size={28} /> Orisei Operations
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Customers · Quotes · Rate Confirmations · Customer Portal Links.
            Everything between "I have a TMS" and "first paying load."
          </p>
          <div className="flex flex-wrap gap-2 mt-5 border-t border-white/5 pt-4">
            {[
              { id: "customers", label: "Customers", icon: Users },
              { id: "quotes", label: "Quotes", icon: FileText },
              { id: "ratecons", label: "Rate Cons", icon: ClipboardCheck },
            ].map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
                className={`px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition flex items-center gap-2 ${
                  tab === t.id ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "text-slate-400 hover:text-cyan-300 border border-transparent hover:bg-white/5"}`}>
                <t.icon size={13} /> {t.label}
              </button>
            ))}
          </div>
        </Card>

        {tab === "customers" && <CustomersTab />}
        {tab === "quotes" && <QuotesTab />}
        {tab === "ratecons" && <RateConsTab />}
      </div>
    </>
  );
}

// ============================ CUSTOMERS ============================
function CustomersTab() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({
    name: "", primary_contact_name: "", primary_contact_email: "",
    primary_contact_phone: "", ap_email: "", payment_terms: "Net 30",
    credit_limit_usd: "", billing_address: "", notes: "",
  });
  const [creating, setCreating] = useState(false);

  const fetchList = async () => {
    try { const { data } = await api.get("/orisei/customers"); setList(data.items || []); }
    catch { toast.error("Failed to load customers"); }
  };
  useEffect(() => { fetchList(); }, []);

  const create = async () => {
    if (!form.name.trim()) return toast.error("Customer name required");
    setCreating(true);
    try {
      const payload = clean({ ...form,
        credit_limit_usd: form.credit_limit_usd ? parseFloat(form.credit_limit_usd) : null });
      await api.post("/orisei/customers", payload);
      toast.success(`Created · ${form.name}`);
      setForm({ name: "", primary_contact_name: "", primary_contact_email: "",
        primary_contact_phone: "", ap_email: "", payment_terms: "Net 30",
        credit_limit_usd: "", billing_address: "", notes: "" });
      fetchList();
    } catch (e) { toast.error(errText(e, "Create failed")); }
    finally { setCreating(false); }
  };

  const generatePortalLink = async (cust) => {
    try {
      const { data } = await api.post(`/orisei/customers/${cust.customer_id}/portal-link`,
        { customer_id: cust.customer_id, days_valid: 90 });
      try { await navigator.clipboard.writeText(data.share_url); } catch {}
      toast.success(`Portal link generated + copied · expires ${data.expires_at?.slice(0,10)}`);
    } catch (e) { toast.error(errText(e, "Failed")); }
  };

  const deactivate = async (cust) => {
    if (!window.confirm(`Deactivate ${cust.name}?`)) return;
    try { await api.delete(`/orisei/customers/${cust.customer_id}`); fetchList(); }
    catch { toast.error("Deactivate failed"); }
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="customers-form-card">
        <h2 className="font-display text-xl font-bold mb-3 flex items-center gap-2">
          <Plus size={18} className="text-cyan-400" /> New customer
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <F label="Name *" value={form.name} onChange={(v) => setForm({...form, name: v})} testId="cust-name" />
          <F label="Primary contact" value={form.primary_contact_name} onChange={(v) => setForm({...form, primary_contact_name: v})} testId="cust-contact" />
          <F label="Primary contact email" type="email" value={form.primary_contact_email} onChange={(v) => setForm({...form, primary_contact_email: v})} testId="cust-email" />
          <F label="Primary contact phone" value={form.primary_contact_phone} onChange={(v) => setForm({...form, primary_contact_phone: v})} testId="cust-phone" />
          <F label="AP email (invoices)" type="email" value={form.ap_email} onChange={(v) => setForm({...form, ap_email: v})} testId="cust-ap" />
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Payment terms</Label>
            <select value={form.payment_terms} onChange={(e) => setForm({...form, payment_terms: e.target.value})}
              className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10"
              data-testid="cust-terms">
              {["Net 15", "Net 30", "Net 45", "Net 60"].map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
          <F label="Credit limit (USD)" type="number" value={form.credit_limit_usd} onChange={(v) => setForm({...form, credit_limit_usd: v})} testId="cust-credit" />
          <F label="Billing address" value={form.billing_address} onChange={(v) => setForm({...form, billing_address: v})} testId="cust-addr" />
          <F label="Notes" value={form.notes} onChange={(v) => setForm({...form, notes: v})} testId="cust-notes" />
        </div>
        <Button onClick={create} disabled={creating} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-3" data-testid="cust-create">
          <Plus size={14} className="mr-2" /> {creating ? "Creating…" : "Add customer"}
        </Button>
      </Card>

      <Card className="hud-surface p-5" data-testid="customers-list-card">
        <h3 className="font-display text-lg font-bold mb-3">Customers · {list.length}</h3>
        {list.length === 0 ? (
          <div className="text-slate-400 text-sm italic py-8 text-center">No customers yet.</div>
        ) : (
          <div className="space-y-2">
            {list.map((c) => (
              <div key={c.customer_id} className="p-3 rounded border bg-white/[0.02] flex items-start justify-between flex-wrap gap-2"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={`cust-card-${c.customer_id}`}>
                <div>
                  <div className="font-bold">{c.name}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {c.customer_id} · {c.payment_terms}
                    {c.primary_contact_email && <> · {c.primary_contact_email}</>}
                  </div>
                  {c.primary_contact_name && <div className="text-xs text-slate-400 mt-0.5">{c.primary_contact_name}{c.primary_contact_phone && ` · ${c.primary_contact_phone}`}</div>}
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => generatePortalLink(c)}
                    className="text-cyan-300 hover:bg-cyan-500/10" data-testid={`portal-${c.customer_id}`}>
                    <Copy size={12} className="mr-1" /> Portal link
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deactivate(c)}
                    className="text-red-400 hover:bg-red-500/10" data-testid={`deact-${c.customer_id}`}>
                    <Trash2 size={12} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ QUOTES ============================
function QuotesTab() {
  const [list, setList] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [form, setForm] = useState({
    customer_id: "", origin: "", destination: "", pickup_date: "", delivery_date: "",
    equipment: "Dry Van", miles: "", weight_lbs: "", line_haul_usd: "", fuel_surcharge_usd: "0",
    valid_for_days: "7", notes: "",
  });

  const fetchAll = async () => {
    try {
      const [{ data: q }, { data: cust }] = await Promise.all([
        api.get("/orisei/quotes"), api.get("/orisei/customers"),
      ]);
      setList(q.items || []); setCustomers(cust.items || []);
    } catch { toast.error("Failed to load quotes"); }
  };
  useEffect(() => { fetchAll(); }, []);

  const create = async () => {
    if (!form.customer_id) return toast.error("Pick a customer");
    if (!form.origin || !form.destination || !form.line_haul_usd)
      return toast.error("Origin, destination, line-haul are required");
    try {
      const payload = clean({ ...form,
        miles: form.miles ? parseFloat(form.miles) : null,
        weight_lbs: form.weight_lbs ? parseFloat(form.weight_lbs) : null,
        line_haul_usd: parseFloat(form.line_haul_usd),
        fuel_surcharge_usd: parseFloat(form.fuel_surcharge_usd || 0),
        valid_for_days: parseInt(form.valid_for_days, 10),
      });
      const { data } = await api.post("/orisei/quotes", payload);
      toast.success(`Quote ${data.quote_id} · $${data.total_usd.toLocaleString()}`);
      setForm({ ...form, origin: "", destination: "", line_haul_usd: "", notes: "" });
      fetchAll();
    } catch (e) { toast.error(errText(e, "Create failed")); }
  };

  const downloadPdf = (qid) => {
    authedDownload(`/api/orisei/quotes/${qid}/pdf`, {
      filename: `Orisei_Quote_${qid}.pdf`,
      inline: true,
    });
  };
  const sendQuote = async (qid) => {
    if (!window.confirm("Email this quote to the customer's primary contact?")) return;
    try {
      const { data } = await api.post(`/orisei/quotes/${qid}/send`);
      toast.success(data.sent ? `Sent to ${data.to}` : `Drafted (no Resend creds in vault — to ${data.to})`);
      fetchAll();
    } catch (e) { toast.error(errText(e, "Send failed")); }
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="quotes-form-card">
        <h2 className="font-display text-xl font-bold mb-3 flex items-center gap-2">
          <Plus size={18} className="text-cyan-400" /> New quote
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Customer *</Label>
            <select value={form.customer_id} onChange={(e) => setForm({...form, customer_id: e.target.value})}
              data-testid="quote-customer"
              className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm border-white/10">
              <option value="">-- Select customer --</option>
              {customers.map((c) => <option key={c.customer_id} value={c.customer_id}>{c.name}</option>)}
            </select>
          </div>
          <F label="Origin *" value={form.origin} onChange={(v) => setForm({...form, origin: v})} testId="quote-origin" kind="cities" />
          <F label="Destination *" value={form.destination} onChange={(v) => setForm({...form, destination: v})} testId="quote-dest" kind="cities" />
          <F label="Pickup date" type="date" value={form.pickup_date} onChange={(v) => setForm({...form, pickup_date: v})} testId="quote-pickup" />
          <F label="Delivery date" type="date" value={form.delivery_date} onChange={(v) => setForm({...form, delivery_date: v})} testId="quote-delivery" />
          <F label="Equipment" value={form.equipment} onChange={(v) => setForm({...form, equipment: v})} testId="quote-equip" kind="equipment" />
          <F label="Miles" type="number" value={form.miles} onChange={(v) => setForm({...form, miles: v})} testId="quote-miles" />
          <F label="Weight (lbs)" type="number" value={form.weight_lbs} onChange={(v) => setForm({...form, weight_lbs: v})} testId="quote-weight" />
          <F label="Line haul $ *" type="number" value={form.line_haul_usd} onChange={(v) => setForm({...form, line_haul_usd: v})} testId="quote-linehaul" />
          <F label="Fuel surcharge $" type="number" value={form.fuel_surcharge_usd} onChange={(v) => setForm({...form, fuel_surcharge_usd: v})} testId="quote-fuel" />
          <F label="Valid for (days)" type="number" value={form.valid_for_days} onChange={(v) => setForm({...form, valid_for_days: v})} testId="quote-valid" />
          <F label="Notes" value={form.notes} onChange={(v) => setForm({...form, notes: v})} testId="quote-notes" />
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-3" data-testid="quote-create">
          <Plus size={14} className="mr-2" /> Generate quote
        </Button>
      </Card>

      <Card className="hud-surface p-5" data-testid="quotes-list-card">
        <h3 className="font-display text-lg font-bold mb-3">Quotes · {list.length}</h3>
        {list.length === 0 ? (
          <div className="text-slate-400 text-sm italic py-8 text-center">No quotes yet.</div>
        ) : (
          <div className="space-y-2">
            {list.map((q) => (
              <div key={q.quote_id} className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={`quote-card-${q.quote_id}`}>
                <div>
                  <div className="font-bold">{q.customer_name} · {q.origin} → {q.destination}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {q.quote_id} · ${q.total_usd?.toLocaleString()} · {q.status?.toUpperCase()}
                    {q.send_status && <> · {q.send_status}</>}
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => downloadPdf(q.quote_id)} className="text-cyan-300"
                          data-testid={`quote-pdf-${q.quote_id}`}>
                    <FileText size={12} className="mr-1" /> PDF
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => sendQuote(q.quote_id)} className="text-cyan-300"
                          data-testid={`quote-send-${q.quote_id}`}>
                    <Send size={12} className="mr-1" /> Email
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ============================ RATE CONS ============================
function RateConsTab() {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({
    booking_id: "", carrier_mc: "", carrier_name: "", carrier_contact_email: "",
    carrier_contact_phone: "", rate_usd: "", pickup_date: "", delivery_date: "",
    pickup_instructions: "", delivery_instructions: "", special_requirements: "",
    accessorial_notes: "", quickpay_offered: true, quickpay_fee_pct: "3.0",
  });

  const fetchList = async () => {
    try { const { data } = await api.get("/orisei/rate-confirmations"); setList(data.items || []); }
    catch { toast.error("Failed to load rate confirmations"); }
  };
  useEffect(() => { fetchList(); }, []);

  const create = async () => {
    if (!form.booking_id || !form.carrier_mc || !form.carrier_name || !form.rate_usd)
      return toast.error("Booking, carrier name, MC, and rate are required");
    try {
      const payload = clean({ ...form,
        rate_usd: parseFloat(form.rate_usd),
        quickpay_fee_pct: parseFloat(form.quickpay_fee_pct || 3) });
      const { data } = await api.post("/orisei/rate-confirmations", payload);
      toast.success(`Rate-con ${data.rc_id} generated`);
      fetchList();
    } catch (e) { toast.error(errText(e, "Create failed")); }
  };

  const downloadPdf = (rcid) => authedDownload(
    `/api/orisei/rate-confirmations/${rcid}/pdf`,
    { filename: `Orisei_RateCon_${rcid}.pdf`, inline: true }
  );
  const sendRc = async (rcid) => {
    if (!window.confirm("Email this rate confirmation to the carrier?")) return;
    try {
      const { data } = await api.post(`/orisei/rate-confirmations/${rcid}/send`);
      toast.success(data.sent ? `Sent to ${data.to}` : `Drafted (to ${data.to})`);
      fetchList();
    } catch (e) { toast.error(errText(e, "Send failed")); }
  };

  return (
    <>
      <Card className="hud-surface p-5" data-testid="ratecons-form-card">
        <h2 className="font-display text-xl font-bold mb-3 flex items-center gap-2">
          <Plus size={18} className="text-cyan-400" /> New Rate Confirmation
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <F label="Booking ID *" value={form.booking_id} onChange={(v) => setForm({...form, booking_id: v})} testId="rc-booking" />
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Carrier name * <span className="text-cyan-300 normal-case tracking-normal">· auto-fills MC #</span></Label>
            <CarrierCombobox
              value={form.carrier_name}
              onChange={(v) => setForm({ ...form, carrier_name: v })}
              onSelect={(rec) => setForm((f) => ({
                ...f,
                carrier_name: rec.name,
                carrier_mc: rec.mc || f.carrier_mc,
                carrier_contact_email: rec.contact_email || f.carrier_contact_email,
                carrier_contact_phone: rec.contact_phone || f.carrier_contact_phone,
              }))}
              testid="rc-name"
              className="bg-[#0B1320] border-white/10 text-white"
            />
          </div>
          <F label="Carrier MC *" value={form.carrier_mc} onChange={(v) => setForm({...form, carrier_mc: v})} testId="rc-mc" />
          <F label="Carrier email" type="email" value={form.carrier_contact_email} onChange={(v) => setForm({...form, carrier_contact_email: v})} testId="rc-email" />
          <F label="Carrier phone" value={form.carrier_contact_phone} onChange={(v) => setForm({...form, carrier_contact_phone: v})} testId="rc-phone" />
          <F label="All-in rate $ *" type="number" value={form.rate_usd} onChange={(v) => setForm({...form, rate_usd: v})} testId="rc-rate" />
          <F label="Pickup date" type="date" value={form.pickup_date} onChange={(v) => setForm({...form, pickup_date: v})} testId="rc-pickup" />
          <F label="Delivery date" type="date" value={form.delivery_date} onChange={(v) => setForm({...form, delivery_date: v})} testId="rc-delivery" />
          <F label="QuickPay fee %" type="number" value={form.quickpay_fee_pct} onChange={(v) => setForm({...form, quickpay_fee_pct: v})} testId="rc-qpfee" />
          <F label="Pickup instructions" value={form.pickup_instructions} onChange={(v) => setForm({...form, pickup_instructions: v})} testId="rc-pinstr" />
          <F label="Delivery instructions" value={form.delivery_instructions} onChange={(v) => setForm({...form, delivery_instructions: v})} testId="rc-dinstr" />
          <F label="Special requirements" value={form.special_requirements} onChange={(v) => setForm({...form, special_requirements: v})} testId="rc-special" />
        </div>
        <Button onClick={create} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-3" data-testid="rc-create">
          <Plus size={14} className="mr-2" /> Generate rate confirmation
        </Button>
      </Card>

      <Card className="hud-surface p-5" data-testid="ratecons-list-card">
        <h3 className="font-display text-lg font-bold mb-3">Rate confirmations · {list.length}</h3>
        {list.length === 0 ? (
          <div className="text-slate-400 text-sm italic py-8 text-center">No rate-cons yet.</div>
        ) : (
          <div className="space-y-2">
            {list.map((rc) => (
              <div key={rc.rc_id} className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
                   style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={`rc-card-${rc.rc_id}`}>
                <div>
                  <div className="font-bold">{rc.carrier_name} · MC {rc.carrier_mc}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {rc.rc_id} · Booking {rc.booking_id} · ${rc.rate_usd?.toLocaleString()}
                    {rc.send_status && <> · {rc.send_status}</>}
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => downloadPdf(rc.rc_id)} className="text-cyan-300"
                          data-testid={`rc-pdf-${rc.rc_id}`}>
                    <FileText size={12} className="mr-1" /> PDF
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => sendRc(rc.rc_id)} className="text-cyan-300"
                          data-testid={`rc-send-${rc.rc_id}`}>
                    <Send size={12} className="mr-1" /> Email
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

function F({ label, value, onChange, type = "text", testId, kind }) {
  // When `kind` is provided, render a typeahead-enabled <Autocomplete>
  // (cities / equipment / commodities / carriers / etc.). Otherwise a
  // plain <Input> — same as before so this stays a drop-in upgrade.
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{label}</Label>
      {kind ? (
        <Autocomplete
          kind={kind}
          value={value}
          onChange={onChange}
          testid={testId}
          className="bg-[#0B1320] border-white/10 text-white"
        />
      ) : (
        <Input type={type} value={value} onChange={(e) => onChange(e.target.value)}
          data-testid={testId} className="bg-[#0B1320] border-white/10 text-white" />
      )}
    </div>
  );
}
