import React, { useState } from "react";
import { Send, Loader2, CheckCircle2 } from "lucide-react";

const ORISEI_GOLD = "#C9A24A";
const ORISEI_NAVY = "#0E3A6B";

/**
 * QuoteForm — public, no-auth quote-request form.
 * Posts to /api/public/quote which writes to db.quote_requests + emails Oliver.
 * Honeypot field blocks bots silently.
 *
 * Backend URL is sourced from REACT_APP_BACKEND_URL — works for both preview
 * and production (livecleans.com) without any code change.
 */
export default function QuoteForm({ compact = false, onSubmitted, dataTestId = "public-quote-form" }) {
  const [f, setF] = useState({
    company_name: "", contact_name: "", email: "", phone: "",
    origin: "", destination: "", pickup_date: "",
    equipment: "Van", weight_lbs: "", pieces: "",
    commodity: "", target_rate: "", notes: "",
    website: "", // honeypot
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!f.company_name?.trim() || !f.contact_name?.trim() || !f.email?.trim()) return;
    setBusy(true);
    try {
      const url = `${process.env.REACT_APP_BACKEND_URL}/api/public/quote`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(f),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || "Submission failed");
      setDone(data.id);
      if (onSubmitted) onSubmitted(data);
    } catch (err) {
      setDone({ error: err.message || "Submission failed" });
    } finally {
      setBusy(false);
    }
  };

  if (done && !done.error) {
    return (
      <div
        className="rounded-xl border p-8 text-center"
        style={{ background: "rgba(201,162,74,0.08)", borderColor: "rgba(201,162,74,0.45)" }}
        data-testid="public-quote-success"
      >
        <CheckCircle2 size={36} style={{ color: ORISEI_GOLD }} className="mx-auto mb-3" />
        <h3 className="text-2xl font-bold" style={{ color: ORISEI_GOLD }}>We have your load.</h3>
        <p className="text-slate-200 mt-2 max-w-md mx-auto">
          Reference <span className="font-mono text-amber-300">{done}</span>. A named broker will email
          back within the hour with a firm rate. Tap <em>Reply</em> to that email and we'll get rolling.
        </p>
      </div>
    );
  }

  const inputCls = "w-full rounded border bg-slate-950/60 text-slate-100 placeholder-slate-600 px-3 py-2 text-sm focus:outline-none focus:ring-1";
  const inputStyle = { borderColor: "rgba(201,162,74,0.25)" };

  return (
    <form
      onSubmit={submit}
      data-testid={dataTestId}
      className="space-y-3"
      style={{ "--tw-ring-color": ORISEI_GOLD }}
    >
      {/* Honeypot */}
      <input
        type="text"
        tabIndex={-1}
        autoComplete="off"
        value={f.website}
        onChange={set("website")}
        style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }}
        aria-hidden="true"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Company *" testid="quote-company"
          ><input required value={f.company_name} onChange={set("company_name")} className={inputCls} style={inputStyle} placeholder="Your company" /></Field>
        <Field label="Contact name *" testid="quote-contact"
          ><input required value={f.contact_name} onChange={set("contact_name")} className={inputCls} style={inputStyle} placeholder="Who should we call back?" /></Field>
        <Field label="Email *" testid="quote-email"
          ><input required type="email" value={f.email} onChange={set("email")} className={inputCls} style={inputStyle} placeholder="you@company.com" /></Field>
        <Field label="Phone" testid="quote-phone"
          ><input value={f.phone} onChange={set("phone")} className={inputCls} style={inputStyle} placeholder="(555) 555-5555" /></Field>
        <Field label="Origin (city, ST)" testid="quote-origin"
          ><input value={f.origin} onChange={set("origin")} className={inputCls} style={inputStyle} placeholder="Saint Paul, MN" /></Field>
        <Field label="Destination (city, ST)" testid="quote-destination"
          ><input value={f.destination} onChange={set("destination")} className={inputCls} style={inputStyle} placeholder="Atlanta, GA" /></Field>
        <Field label="Pickup date" testid="quote-pickup"
          ><input type="date" value={f.pickup_date} onChange={set("pickup_date")} className={inputCls} style={inputStyle} /></Field>
        <Field label="Equipment" testid="quote-equipment">
          <select value={f.equipment} onChange={set("equipment")} className={inputCls} style={inputStyle}>
            {["Van", "Reefer", "Flatbed", "Step-Deck", "Power-Only", "LTL", "Hot-Shot", "Specialty"].map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
        </Field>
        {!compact && (
          <>
            <Field label="Weight (lbs)" testid="quote-weight"
              ><input value={f.weight_lbs} onChange={set("weight_lbs")} className={inputCls} style={inputStyle} placeholder="44,000" /></Field>
            <Field label="Pieces" testid="quote-pieces"
              ><input value={f.pieces} onChange={set("pieces")} className={inputCls} style={inputStyle} placeholder="24 pallets" /></Field>
            <Field label="Commodity" testid="quote-commodity"
              ><input value={f.commodity} onChange={set("commodity")} className={inputCls} style={inputStyle} placeholder="What's the freight?" /></Field>
            <Field label="Target rate (USD)" testid="quote-target"
              ><input value={f.target_rate} onChange={set("target_rate")} className={inputCls} style={inputStyle} placeholder="$2,400 — optional" /></Field>
          </>
        )}
      </div>

      <Field label="Anything we should know?" testid="quote-notes">
        <textarea
          value={f.notes} onChange={set("notes")}
          rows={3}
          className={inputCls + " resize-y"}
          style={inputStyle}
          placeholder="Receivers, hours, hazmat, fragile, dock vs. lift-gate, repeat lane?"
        />
      </Field>

      {done?.error && (
        <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">
          {done.error}
        </div>
      )}

      <button
        type="submit"
        disabled={busy}
        data-testid="quote-submit"
        className="w-full rounded font-bold uppercase tracking-wider text-sm py-3 transition flex items-center justify-center gap-2 disabled:opacity-60"
        style={{ background: ORISEI_GOLD, color: ORISEI_NAVY }}
      >
        {busy ? <Loader2 className="animate-spin" size={16} /> : <Send size={14} />}
        {busy ? "Sending…" : "Send Quote Request"}
      </button>
      <p className="text-[11px] text-slate-500 text-center">
        Reply within 60 minutes during business hours. After-hours requests answered by 7 a.m. CT.
      </p>
    </form>
  );
}

function Field({ label, children, testid }) {
  return (
    <label className="block text-sm" data-testid={`field-${testid}`}>
      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mb-1 inline-block">
        {label}
      </span>
      {children}
    </label>
  );
}
