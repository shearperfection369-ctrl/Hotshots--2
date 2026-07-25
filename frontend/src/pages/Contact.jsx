/* eslint-disable */
import React, { useEffect, useState } from "react";
import { Mail, Phone, MapPin, Send, Loader2, CheckCircle2, ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import PublicNav from "../components/PublicNav";
import PublicFooter from "../components/PublicFooter";
import QuoteForm from "../components/QuoteForm";

const GOLD = "#C9A24A";
const NAVY = "#0E3A6B";

function ContactForm() {
  const [f, setF] = useState({
    name: "", email: "", phone: "", company: "", subject: "", message: "", website: "",
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/public/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(f),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || "Submission failed");
      setDone(data.id);
    } catch (err) {
      setDone({ error: err.message || "Submission failed" });
    } finally { setBusy(false); }
  };

  if (done && !done.error) {
    return (
      <div className="rounded-xl border p-8 text-center"
           style={{ background: "rgba(201,162,74,0.08)", borderColor: "rgba(201,162,74,0.45)" }}
           data-testid="contact-success">
        <CheckCircle2 size={36} style={{ color: GOLD }} className="mx-auto mb-3" />
        <h3 className="text-2xl font-bold" style={{ color: GOLD }}>Got it — we'll be in touch.</h3>
        <p className="text-slate-200 mt-2">Reference <span className="font-mono text-amber-300">{done}</span>.</p>
      </div>
    );
  }

  const inputCls = "w-full rounded border bg-slate-950/60 text-slate-100 placeholder-slate-600 px-3 py-2 text-sm focus:outline-none";
  const inputStyle = { borderColor: "rgba(201,162,74,0.25)" };

  return (
    <form onSubmit={submit} data-testid="contact-form" className="space-y-3">
      <input type="text" tabIndex={-1} autoComplete="off" value={f.website} onChange={set("website")}
             style={{ position: "absolute", left: "-9999px", width: 1, height: 1, opacity: 0 }} aria-hidden="true" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Name *"><input required value={f.name} onChange={set("name")} className={inputCls} style={inputStyle} /></Field>
        <Field label="Email *"><input required type="email" value={f.email} onChange={set("email")} className={inputCls} style={inputStyle} /></Field>
        <Field label="Phone"><input value={f.phone} onChange={set("phone")} className={inputCls} style={inputStyle} /></Field>
        <Field label="Company"><input value={f.company} onChange={set("company")} className={inputCls} style={inputStyle} /></Field>
      </div>
      <Field label="Subject"><input value={f.subject} onChange={set("subject")} className={inputCls} style={inputStyle} /></Field>
      <Field label="Message *">
        <textarea required value={f.message} onChange={set("message")} rows={5} className={inputCls + " resize-y"} style={inputStyle} />
      </Field>
      {done?.error && (
        <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">{done.error}</div>
      )}
      <button type="submit" disabled={busy} data-testid="contact-submit"
              className="w-full rounded font-bold uppercase tracking-wider text-sm py-3 transition flex items-center justify-center gap-2 disabled:opacity-60"
              style={{ background: GOLD, color: NAVY }}>
        {busy ? <Loader2 className="animate-spin" size={16} /> : <Send size={14} />}
        {busy ? "Sending…" : "Send Message"}
      </button>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mb-1 inline-block">{label}</span>
      {children}
    </label>
  );
}

export default function Contact() {
  const [brand, setBrand] = useState({});
  useEffect(() => { api.get("/branding").then(({ data }) => setBrand(data || {})).catch(() => {}); }, []);
  return (
    <div className="min-h-screen bg-[#0B1320] text-slate-100" data-testid="contact-page">
      <PublicNav brand={brand} />

      <section className="max-w-7xl mx-auto px-6 pt-16 pb-10">
        <div className="text-[10px] font-mono uppercase tracking-[0.3em]" style={{ color: GOLD }}>Get in touch</div>
        <h1 className="font-display font-black text-4xl md:text-5xl mt-3 leading-tight">
          Let's talk freight.
        </h1>
        <p className="text-slate-300 max-w-3xl mt-5 leading-relaxed">
          Need a fast quote? Use the <a href="/home#quote" className="underline" style={{ color: GOLD }}>quote form</a> on the
          home page. Anything else — partnership, RFP, carrier setup, vendor
          questions — send it through here and a real human will reply.
        </p>
      </section>

      <section className="max-w-7xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="rounded-xl border p-6 bg-white/[0.02]" style={{ borderColor: `${GOLD}33` }}>
              <h3 className="font-display font-bold text-xl">Direct contact</h3>
              <div className="mt-4 space-y-3 text-sm">
                <a href="mailto:oliver@oriseifreightsolutions.com" data-testid="contact-email" className="flex items-center gap-3 hover:text-amber-300 transition">
                  <Mail size={16} style={{ color: GOLD }} />
                  <span>oliver@oriseifreightsolutions.com</span>
                </a>
                <a href="tel:+16125550117" data-testid="contact-phone" className="flex items-center gap-3 hover:text-amber-300 transition">
                  <Phone size={16} style={{ color: GOLD }} />
                  <span>(612) 555-0117</span>
                </a>
                <div className="flex items-center gap-3 text-slate-300">
                  <MapPin size={16} style={{ color: GOLD }} />
                  <span>Saint Paul, Minnesota · 48-state coverage</span>
                </div>
              </div>
              <div className="mt-5 pt-5 border-t border-white/10 text-xs text-slate-400">
                Response window: <span style={{ color: GOLD }}>within 60 minutes</span> during
                business hours · after-hours requests answered by 7 a.m. CT.
              </div>
            </div>

            <div className="rounded-xl border p-6 bg-white/[0.02]" style={{ borderColor: `${GOLD}33` }}>
              <h3 className="font-display font-bold text-lg">Carriers + Drivers</h3>
              <p className="text-sm text-slate-300 mt-2 leading-relaxed">
                Want to run for Orisei? We're building a vetted carrier pool — quick-pay
                via factor of your choice, no shadow trucks. Email <a href="mailto:oliver@oriseifreightsolutions.com" style={{ color: GOLD }}>oliver@oriseifreightsolutions.com</a> with your MC#, COI, and dispatch contact.
              </p>
            </div>
          </div>

          <div className="rounded-xl border p-6" style={{ borderColor: `${GOLD}55`, background: `linear-gradient(135deg, ${NAVY}cc, ${NAVY}66)` }}>
            <h3 className="font-display font-bold text-xl mb-4">Send a message</h3>
            <ContactForm />
          </div>
        </div>
      </section>

      <PublicFooter brand={brand} />
    </div>
  );
}
