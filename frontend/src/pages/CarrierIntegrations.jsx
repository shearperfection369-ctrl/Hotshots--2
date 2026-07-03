import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Package, FileText, PlugZap, CheckCircle2, Loader2, DollarSign, Clock,
  Truck, Zap, Send, ArrowDownToLine, FileWarning, Receipt, ClipboardCheck,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

/**
 * CarrierIntegrations — FedEx/UPS parcel rating + SPS Commerce EDI console.
 * All flows work in SAMPLE mode without keys, light up LIVE when creds
 * are wired via the built-in Connect dialogs (admin-only).
 */
export default function CarrierIntegrations() {
  const [tab, setTab] = useState("rating");
  return (
    <div className="p-4 space-y-4 min-h-screen bg-slate-950" data-testid="carrier-integrations-root">
      <header className="flex items-end justify-between border-b border-white/10 pb-3">
        <div>
          <h1 className="text-2xl font-mono tracking-widest text-cyan-100 uppercase flex items-center gap-2">
            <Package size={20} className="text-cyan-400" /> Carrier · EDI Console
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            FedEx + UPS real-time rating · SPS Commerce EDI 204/210/214/990/856.
          </p>
        </div>
        <div className="flex gap-2">
          {[
            { id: "rating", label: "Parcel Rating", icon: DollarSign },
            { id: "edi204", label: "204 Tenders", icon: ArrowDownToLine },
            { id: "edi856", label: "856 ASN Inbox", icon: FileText },
            { id: "edi214", label: "214 · 210 Send", icon: Send },
            { id: "history", label: "Audit Log", icon: ClipboardCheck },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`ci-tab-${id}`}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded text-[11px] font-mono uppercase tracking-widest border transition ${
                tab === id
                  ? "bg-cyan-500/15 border-cyan-400 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.25)]"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-100"
              }`}
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
      </header>

      {tab === "rating" && <RatingView />}
      {tab === "edi204" && <TendersView />}
      {tab === "edi856" && <AsnView />}
      {tab === "edi214" && <StatusInvoiceView />}
      {tab === "history" && <HistoryView />}
    </div>
  );
}

// ============================================================
//                     PARCEL RATING
// ============================================================
function RatingView() {
  const [provider, setProvider] = useState(null);
  const [form, setForm] = useState({
    origin_zip: "30301", destination_zip: "85001",
    weight_lbs: 25, length_in: 18, width_in: 12, height_in: 10,
    package_count: 2, residential: false,
  });
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/parcel/provider").then(({ data }) => setProvider(data)).catch(() => {}); }, []);

  const quote = async () => {
    setBusy(true); setResult(null);
    try {
      const payload = { ...form,
        weight_lbs: Number(form.weight_lbs),
        length_in: Number(form.length_in),
        width_in: Number(form.width_in),
        height_in: Number(form.height_in),
        package_count: Number(form.package_count) };
      const { data } = await api.post("/parcel/quote", payload);
      setResult(data);
      toast.success(`${data.items.length} rates · cheapest $${data.cheapest?.total_charge}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Quote failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3">
      <div className="grid md:grid-cols-2 gap-3">
        <ConnectCarrierCard carrier="fedex" provider={provider} onDone={() => api.get("/parcel/provider").then(({data}) => setProvider(data))} />
        <ConnectCarrierCard carrier="ups"   provider={provider} onDone={() => api.get("/parcel/provider").then(({data}) => setProvider(data))} />
      </div>

      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Field label="Origin ZIP">
            <Input value={form.origin_zip} onChange={(e) => setForm({ ...form, origin_zip: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="rating-origin-zip" />
          </Field>
          <Field label="Destination ZIP">
            <Input value={form.destination_zip} onChange={(e) => setForm({ ...form, destination_zip: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="rating-dest-zip" />
          </Field>
          <Field label="Weight (lbs)">
            <Input type="number" value={form.weight_lbs} onChange={(e) => setForm({ ...form, weight_lbs: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="rating-weight" />
          </Field>
          <Field label="Packages">
            <Input type="number" min="1" value={form.package_count} onChange={(e) => setForm({ ...form, package_count: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" data-testid="rating-pkg-count" />
          </Field>
          <Field label="Length (in)">
            <Input type="number" value={form.length_in} onChange={(e) => setForm({ ...form, length_in: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </Field>
          <Field label="Width (in)">
            <Input type="number" value={form.width_in} onChange={(e) => setForm({ ...form, width_in: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </Field>
          <Field label="Height (in)">
            <Input type="number" value={form.height_in} onChange={(e) => setForm({ ...form, height_in: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </Field>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-xs text-slate-300 pb-1.5">
              <input type="checkbox" checked={form.residential} onChange={(e) => setForm({ ...form, residential: e.target.checked })}
                data-testid="rating-residential" />
              Residential
            </label>
          </div>
        </div>
        <div className="flex justify-end">
          <Button onClick={quote} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="rating-quote-btn">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <Zap size={13} className="mr-1" />}
            Get Rates
          </Button>
        </div>
      </Card>

      {result && (
        <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden" data-testid="rating-results">
          <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between text-[10px] font-mono uppercase tracking-widest">
            <span className="text-cyan-300">
              {result.items.length} rates · {result.distance_mi} mi ·
              FedEx: <span className={result.fedex_mode === "live" ? "text-emerald-300" : "text-slate-500"}> {result.fedex_mode}</span> ·
              UPS: <span className={result.ups_mode === "live" ? "text-emerald-300" : "text-slate-500"}> {result.ups_mode}</span>
            </span>
            <div className="flex gap-3">
              <span className="text-emerald-300">Cheapest: {result.cheapest?.service_name} · ${result.cheapest?.total_charge}</span>
              <span className="text-amber-300">Fastest: {result.fastest?.service_name} · {result.fastest?.transit_days}d</span>
            </div>
          </div>
          <table className="w-full text-xs" data-testid="rating-table">
            <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
              <tr>
                <th className="px-3 py-2 text-left">Carrier</th>
                <th className="px-3 py-2 text-left">Service</th>
                <th className="px-3 py-2 text-right">Rate</th>
                <th className="px-3 py-2 text-right">Transit</th>
                <th className="px-3 py-2 text-left">Est. Delivery</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map((r, i) => (
                <tr key={`${r.carrier}-${r.service_code}-${i}`} className="border-t border-white/5"
                  data-testid={`rating-row-${r.carrier}-${r.service_code}`}>
                  <td className="px-3 py-2">
                    <Badge className={r.carrier === "FEDEX"
                      ? "bg-purple-500/20 text-purple-200 border-purple-500/40"
                      : "bg-amber-500/20 text-amber-200 border-amber-500/40"}>
                      {r.carrier}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-slate-200">{r.service_name}</td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">
                    ${r.total_charge?.toFixed(2)} <span className="text-slate-500 text-[10px]">{r.currency}</span>
                  </td>
                  <td className="px-3 py-2 text-right text-amber-300 font-mono">{r.transit_days ?? "—"} d</td>
                  <td className="px-3 py-2 text-slate-400 font-mono text-[10px]">{r.delivery_date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function ConnectCarrierCard({ carrier, provider, onDone }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ client_id: "", client_secret: "", account_number: "" });
  const [busy, setBusy] = useState(false);
  const connected = provider?.[carrier]?.connected;
  const brand = carrier === "fedex"
    ? { name: "FedEx",  color: "#7C3AED" }
    : { name: "UPS",    color: "#F59E0B" };

  const submit = async () => {
    if (!form.client_id || !form.client_secret || !form.account_number) {
      toast.error("All 3 fields required"); return;
    }
    setBusy(true);
    try {
      await api.post(`/parcel/connect/${carrier}`, form);
      toast.success(`${brand.name} connected`); setOpen(false); onDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Connect failed");
    } finally { setBusy(false); }
  };

  return (
    <Card className={`p-3 bg-slate-900/60 border ${connected ? "border-emerald-500/40" : "border-white/10"}`}
      data-testid={`ci-carrier-card-${carrier}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Truck size={14} style={{ color: brand.color }} />
          <span className="text-sm font-mono uppercase tracking-widest text-slate-200">{brand.name}</span>
          <Badge variant="outline" className={connected
            ? "border-emerald-500/40 text-emerald-300"
            : "border-slate-500/40 text-slate-400"}>
            {connected ? "LIVE" : "SAMPLE"}
          </Badge>
        </div>
        <Button size="sm" variant={connected ? "ghost" : "default"}
          onClick={() => setOpen(!open)}
          className={connected ? "text-cyan-300 hover:text-cyan-100 h-7" : "bg-cyan-500 hover:bg-cyan-400 text-black h-7"}
          data-testid={`ci-connect-${carrier}-btn`}>
          <PlugZap size={12} className="mr-1" /> {connected ? "Rotate" : "Connect"}
        </Button>
      </div>
      {open && (
        <div className="mt-3 space-y-2" data-testid={`ci-connect-${carrier}-form`}>
          <Input placeholder="client_id" value={form.client_id}
            onChange={(e) => setForm({ ...form, client_id: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" />
          <Input type="password" placeholder="client_secret" value={form.client_secret}
            onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" />
          <Input placeholder={carrier === "fedex" ? "FedEx account #" : "UPS shipper #"}
            value={form.account_number}
            onChange={(e) => setForm({ ...form, account_number: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" />
          <Button onClick={submit} disabled={busy}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-black h-8"
            data-testid={`ci-connect-${carrier}-submit`}>
            {busy ? <Loader2 size={12} className="animate-spin mr-1" /> : <CheckCircle2 size={12} className="mr-1" />}
            Save & Connect
          </Button>
        </div>
      )}
    </Card>
  );
}

// ============================================================
//                     EDI 204 TENDER INBOX
// ============================================================
function TendersView() {
  const [items, setItems] = useState([]);
  const [mode, setMode] = useState("sample");
  const [busy, setBusy] = useState(false);
  const [decidingId, setDecidingId] = useState(null);
  const [decision, setDecision] = useState({ decision: "accept", notes: "" });

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/edi/inbound/204");
      setItems(data.items || []); setMode(data.mode || "sample");
    } catch (e) { toast.error("Failed to load tenders"); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitDecision = async (tender_id) => {
    try {
      await api.post("/edi/outbound/990", { tender_id, ...decision });
      toast.success(`Tender ${tender_id} · ${decision.decision.toUpperCase()} sent (EDI 990)`);
      setDecidingId(null); setDecision({ decision: "accept", notes: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to send 990"); }
  };

  const stColor = (s) => s === "accepted" ? "text-emerald-400"
    : s === "rejected" ? "text-red-400"
    : s === "countered" ? "text-amber-400"
    : "text-slate-400";

  return (
    <div className="space-y-3">
      <ProviderBanner label="SPS · 204" mode={mode} />
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 flex justify-between text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <span><ArrowDownToLine size={12} className="inline mr-1" /> {items.length} inbound tenders</span>
          <Button size="sm" variant="ghost" onClick={load} disabled={busy} className="h-6 text-cyan-300">
            {busy ? <Loader2 size={11} className="animate-spin" /> : "Refresh"}
          </Button>
        </div>
        <table className="w-full text-xs" data-testid="edi-204-table">
          <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">Tender</th>
              <th className="px-3 py-2 text-left">Shipper</th>
              <th className="px-3 py-2 text-left">Lane</th>
              <th className="px-3 py-2 text-left">Commodity</th>
              <th className="px-3 py-2 text-right">Amount</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <React.Fragment key={t.tender_id}>
                <tr className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`edi-204-row-${t.tender_id}`}>
                  <td className="px-3 py-2 text-slate-200 font-mono">{t.tender_id}
                    <div className="text-[9px] text-slate-500">{t.shipper_reference}</div></td>
                  <td className="px-3 py-2 text-slate-300">{t.shipper}</td>
                  <td className="px-3 py-2 text-slate-400 text-[11px]">
                    {t.origin?.city}, {t.origin?.state} → {t.destination?.city}, {t.destination?.state}
                    <div className="text-[9px] text-slate-500">{t.equipment_type} · {(t.weight_lbs || 0).toLocaleString()} lbs</div>
                  </td>
                  <td className="px-3 py-2 text-slate-300">{t.commodity}
                    {t.hazmat && <span className="ml-1 text-red-400 text-[9px]">
                      <AlertTriangle size={9} className="inline" /> HAZMAT</span>}</td>
                  <td className="px-3 py-2 text-right text-emerald-300 font-mono">${(t.tender_amount_usd || 0).toLocaleString()}</td>
                  <td className={`px-3 py-2 uppercase font-mono text-[10px] ${stColor(t.status)}`}>{t.status}</td>
                  <td className="px-3 py-2 text-right">
                    {t.status === "new" && (
                      <Button size="sm" onClick={() => setDecidingId(t.tender_id)}
                        className="bg-cyan-500 hover:bg-cyan-400 text-black h-7"
                        data-testid={`edi-204-decide-${t.tender_id}`}>
                        Respond (990)
                      </Button>
                    )}
                  </td>
                </tr>
                {decidingId === t.tender_id && (
                  <tr className="bg-cyan-500/5">
                    <td colSpan={7} className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <select value={decision.decision}
                          onChange={(e) => setDecision({ ...decision, decision: e.target.value })}
                          className="bg-black/40 border border-white/10 rounded px-2 py-1 text-xs text-slate-100"
                          data-testid={`edi-204-decision-select-${t.tender_id}`}>
                          <option value="accept">Accept</option>
                          <option value="reject">Reject</option>
                          <option value="counter">Counter-offer</option>
                        </select>
                        <Input placeholder="Notes (optional)" value={decision.notes}
                          onChange={(e) => setDecision({ ...decision, notes: e.target.value })}
                          className="flex-1 bg-black/40 border-white/10 h-8 text-xs" />
                        <Button size="sm" variant="ghost" onClick={() => setDecidingId(null)}>Cancel</Button>
                        <Button size="sm" onClick={() => submitDecision(t.tender_id)}
                          className="bg-emerald-500 hover:bg-emerald-400 text-black h-8"
                          data-testid={`edi-204-decide-submit-${t.tender_id}`}>
                          <Send size={11} className="mr-1" /> Send 990
                        </Button>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {!items.length && !busy && (
              <tr><td colSpan={7} className="p-8 text-center text-slate-500">No inbound tenders.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ============================================================
//                     EDI 856 ASN INBOX
// ============================================================
function AsnView() {
  const [items, setItems] = useState([]);
  const [mode, setMode] = useState("sample");
  useEffect(() => { api.get("/edi/inbound/856").then(({ data }) => { setItems(data.items || []); setMode(data.mode || "sample"); }).catch(() => {}); }, []);
  return (
    <div className="space-y-3">
      <ProviderBanner label="SPS · 856" mode={mode} />
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <FileText size={12} className="inline mr-1" /> {items.length} advance ship notices
        </div>
        <table className="w-full text-xs" data-testid="edi-856-table">
          <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">ASN</th>
              <th className="px-3 py-2 text-left">Ship / ETA</th>
              <th className="px-3 py-2 text-left">Shipper</th>
              <th className="px-3 py-2 text-right">Pallets · Cartons</th>
              <th className="px-3 py-2 text-left">SSCC</th>
              <th className="px-3 py-2 text-left">Notes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.asn_id} className="border-t border-white/5" data-testid={`edi-856-row-${a.asn_id}`}>
                <td className="px-3 py-2 text-slate-200 font-mono">{a.asn_id}
                  <div className="text-[9px] text-slate-500">{a.shipment_id} · {a.tender_id}</div></td>
                <td className="px-3 py-2 text-slate-400 text-[11px]">
                  {a.ship_date} → {a.expected_delivery_date}
                </td>
                <td className="px-3 py-2 text-slate-300">{a.shipper}</td>
                <td className="px-3 py-2 text-right text-cyan-300 font-mono">{a.pallet_count} · {a.carton_count}</td>
                <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{a.sscc}</td>
                <td className="px-3 py-2 text-slate-400 text-[11px]">{a.notes}</td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={6} className="p-8 text-center text-slate-500">No ASNs.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ============================================================
//                     214 STATUS + 210 INVOICE
// ============================================================
function StatusInvoiceView() {
  const [statusForm, setStatusForm] = useState({ tender_id: "", shipment_id: "", status_code: "in_transit", details: "" });
  const [invoiceForm, setInvoiceForm] = useState({ tender_id: "", invoice_number: "", amount: "", currency: "USD" });
  const [busy, setBusy] = useState({ s: false, i: false });

  const sendStatus = async () => {
    setBusy((b) => ({ ...b, s: true }));
    try {
      const r = await api.post("/edi/outbound/214", statusForm);
      toast.success(`214 sent · ${r.data.doc_id} (${r.data.mode})`);
      setStatusForm({ tender_id: "", shipment_id: "", status_code: "in_transit", details: "" });
    } catch (e) { toast.error(e?.response?.data?.detail || "214 send failed"); }
    finally { setBusy((b) => ({ ...b, s: false })); }
  };
  const sendInvoice = async () => {
    if (!invoiceForm.amount) { toast.error("Amount required"); return; }
    setBusy((b) => ({ ...b, i: true }));
    try {
      const r = await api.post("/edi/outbound/210", { ...invoiceForm, amount: Number(invoiceForm.amount) });
      toast.success(`210 sent · ${r.data.doc_id} (${r.data.mode})`);
      setInvoiceForm({ tender_id: "", invoice_number: "", amount: "", currency: "USD" });
    } catch (e) { toast.error(e?.response?.data?.detail || "210 send failed"); }
    finally { setBusy((b) => ({ ...b, i: false })); }
  };

  return (
    <div className="grid md:grid-cols-2 gap-3">
      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3" data-testid="edi-214-form">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-1">
          <Send size={12} /> Send 214 · Shipment Status
        </div>
        <Input placeholder="Tender ID (optional)" value={statusForm.tender_id}
          onChange={(e) => setStatusForm({ ...statusForm, tender_id: e.target.value })}
          className="bg-black/40 border-white/10 h-8 text-xs" data-testid="edi-214-tender" />
        <Input placeholder="Shipment ID (optional)" value={statusForm.shipment_id}
          onChange={(e) => setStatusForm({ ...statusForm, shipment_id: e.target.value })}
          className="bg-black/40 border-white/10 h-8 text-xs" />
        <select value={statusForm.status_code}
          onChange={(e) => setStatusForm({ ...statusForm, status_code: e.target.value })}
          className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
          data-testid="edi-214-status">
          <option value="picked_up">Picked up</option>
          <option value="in_transit">In transit</option>
          <option value="delayed">Delayed</option>
          <option value="delivered">Delivered</option>
        </select>
        <Textarea rows={2} placeholder="Details (optional)" value={statusForm.details}
          onChange={(e) => setStatusForm({ ...statusForm, details: e.target.value })}
          className="bg-black/40 border-white/10 text-xs" />
        <Button onClick={sendStatus} disabled={busy.s} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black"
          data-testid="edi-214-submit">
          {busy.s ? <Loader2 size={13} className="animate-spin mr-1" /> : <Send size={13} className="mr-1" />}
          Send 214
        </Button>
      </Card>

      <Card className="p-4 bg-slate-900/60 border-white/10 space-y-3" data-testid="edi-210-form">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-1">
          <Receipt size={12} /> Send 210 · Freight Invoice
        </div>
        <Input placeholder="Tender ID (optional)" value={invoiceForm.tender_id}
          onChange={(e) => setInvoiceForm({ ...invoiceForm, tender_id: e.target.value })}
          className="bg-black/40 border-white/10 h-8 text-xs" />
        <Input placeholder="Invoice Number *" value={invoiceForm.invoice_number}
          onChange={(e) => setInvoiceForm({ ...invoiceForm, invoice_number: e.target.value })}
          className="bg-black/40 border-white/10 h-8 text-xs" data-testid="edi-210-invoice-number" />
        <div className="grid grid-cols-2 gap-2">
          <Input type="number" placeholder="Amount *" value={invoiceForm.amount}
            onChange={(e) => setInvoiceForm({ ...invoiceForm, amount: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" data-testid="edi-210-amount" />
          <Input placeholder="Currency" value={invoiceForm.currency}
            onChange={(e) => setInvoiceForm({ ...invoiceForm, currency: e.target.value })}
            className="bg-black/40 border-white/10 h-8 text-xs" />
        </div>
        <Button onClick={sendInvoice} disabled={busy.i} className="w-full bg-emerald-500 hover:bg-emerald-400 text-black"
          data-testid="edi-210-submit">
          {busy.i ? <Loader2 size={13} className="animate-spin mr-1" /> : <Send size={13} className="mr-1" />}
          Send 210
        </Button>
      </Card>
    </div>
  );
}

// ============================================================
//                     OUTBOUND HISTORY
// ============================================================
function HistoryView() {
  const [rows, setRows] = useState([]);
  const [byKind, setByKind] = useState({});
  useEffect(() => { api.get("/edi/outbound/history").then(({ data }) => { setRows(data.items || []); setByKind(data.by_kind || {}); }).catch(() => {}); }, []);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        {["990", "214", "210"].map((k) => (
          <Card key={k} className="p-3 bg-slate-900/60 border-white/10">
            <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">EDI {k}</div>
            <div className="text-2xl font-mono text-cyan-300 mt-1">{byKind[k] || 0}</div>
          </Card>
        ))}
      </div>
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <ClipboardCheck size={12} className="inline mr-1" /> {rows.length} outbound documents
        </div>
        <table className="w-full text-xs" data-testid="edi-history-table">
          <thead className="bg-black/40 text-slate-500 font-mono uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">Sent</th>
              <th className="px-3 py-2 text-left">Doc ID</th>
              <th className="px-3 py-2 text-left">Kind</th>
              <th className="px-3 py-2 text-left">Mode</th>
              <th className="px-3 py-2 text-left">Payload preview</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.doc_id} className="border-t border-white/5" data-testid={`edi-history-row-${r.doc_id}`}>
                <td className="px-3 py-2 text-slate-500 font-mono text-[10px]">{r.sent_at?.slice(0, 19).replace("T", " ")}</td>
                <td className="px-3 py-2 text-slate-200 font-mono">{r.doc_id}</td>
                <td className="px-3 py-2">
                  <Badge className={r.kind === "990" ? "bg-cyan-500/20 text-cyan-200 border-cyan-500/40"
                    : r.kind === "214" ? "bg-amber-500/20 text-amber-200 border-amber-500/40"
                    : "bg-emerald-500/20 text-emerald-200 border-emerald-500/40"}>EDI {r.kind}</Badge>
                </td>
                <td className={`px-3 py-2 uppercase font-mono text-[10px] ${r.mode === "live" ? "text-emerald-400" : "text-slate-500"}`}>
                  {r.mode}
                </td>
                <td className="px-3 py-2 text-slate-400 text-[10px] font-mono truncate max-w-md">
                  {JSON.stringify(r.payload).slice(0, 120)}…
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No outbound documents yet.</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ============================================================
//                     SHARED PRIMS
// ============================================================
function ProviderBanner({ label, mode }) {
  const live = mode === "live";
  return (
    <div className={`px-3 py-2 rounded border flex items-center gap-2 text-xs ${
      live ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-100"
           : "border-slate-500/30 bg-slate-500/5 text-slate-300"
    }`} data-testid={`edi-banner-${label.replace(/\s+/g, "-").toLowerCase()}`}>
      {live ? <CheckCircle2 size={13} className="text-emerald-400" /> : <PlugZap size={13} className="text-slate-400" />}
      <span className="font-mono uppercase text-[10px] tracking-widest">{label}</span>
      <Badge variant="outline" className={live ? "border-emerald-500/40 text-emerald-300" : "border-slate-500/40 text-slate-400"}>
        {live ? "LIVE" : "SAMPLE"}
      </Badge>
      {!live && <span className="text-slate-400 ml-2 text-[11px]">
        Connect SPS Commerce via POST /api/edi/connect to switch to live inbound docs.
      </span>}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  );
}
