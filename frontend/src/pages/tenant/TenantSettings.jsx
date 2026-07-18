import React, { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader2, UploadCloud, CreditCard, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { useTenant } from "./TenantPortal";
import { errText } from "./tenantApi";

export default function TenantSettings() {
  const { api, brand, primary, refreshBrand } = useTenant();
  const [params, setParams] = useSearchParams();
  const [bform, setBform] = useState({ company_name: brand.company_name, primary_color: brand.primary_color, accent_color: brand.accent_color, tagline: brand.tagline || "" });
  const [billing, setBilling] = useState(null);
  const [busy, setBusy] = useState(false);
  const [paying, setPaying] = useState(false);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const fileRef = useRef(null);

  const loadBilling = useCallback(() => api.get("/billing").then((r) => setBilling(r.data)).catch(() => {}), [api]);
  useEffect(() => { loadBilling(); }, [loadBilling]);

  // Stripe return polling
  useEffect(() => {
    const sid = params.get("session_id");
    if (!sid) return;
    let tries = 0;
    setPaying(true);
    const poll = async () => {
      tries += 1;
      try {
        const r = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/payments/status/${sid}`);
        const d = await r.json();
        if (d.payment_status === "paid") {
          toast.success("Subscription active — welcome aboard!");
          setPaying(false); setParams({}); loadBilling(); return;
        }
        if (d.status === "expired") { toast.error("Checkout expired — try again"); setPaying(false); setParams({}); return; }
      } catch (_) {}
      if (tries < 8) setTimeout(poll, 2000);
      else { toast.info("Payment still processing — check back shortly"); setPaying(false); setParams({}); }
    };
    poll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveBrand = async (extra = {}) => {
    setBusy(true);
    try { await api.put("/branding", { ...bform, ...extra }); toast.success("Branding updated"); refreshBrand(); }
    catch (e2) { toast.error(errText(e2)); } finally { setBusy(false); }
  };

  const onLogo = (file) => {
    if (!file) return;
    if (file.size > 380_000) { toast.error("Logo must be under 380KB"); return; }
    const reader = new FileReader();
    reader.onload = () => saveBrand({ logo_b64: reader.result });
    reader.readAsDataURL(file);
  };

  const checkout = async (lookup_key) => {
    try {
      const { data } = await api.post("/billing/checkout", { lookup_key, origin_url: window.location.origin });
      window.location.href = data.checkout_url;
    } catch (e2) { toast.error(errText(e2)); }
  };

  const changePw = async (e) => {
    e.preventDefault();
    try { await api.post("/auth/change-password", pw); toast.success("Password changed"); setPw({ current_password: "", new_password: "" }); }
    catch (e2) { toast.error(errText(e2)); }
  };

  const bstatus = billing?.billing?.status || "trial";

  return (
    <div className="space-y-8 max-w-4xl" data-testid="tenant-settings">
      <div><h1 className="text-2xl font-black tracking-tight">Settings</h1><p className="text-slate-500 text-sm">Branding, billing, and your account.</p></div>

      {/* Branding */}
      <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02]" data-testid="tenant-branding-card">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-4">White-label branding</div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-3">
            <input value={bform.company_name} onChange={(e) => setBform({ ...bform, company_name: e.target.value })}
                   placeholder="Company name" data-testid="tenant-brand-name-input"
                   className="w-full h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none" />
            <input value={bform.tagline} onChange={(e) => setBform({ ...bform, tagline: e.target.value })}
                   placeholder="Tagline" data-testid="tenant-brand-tagline-input"
                   className="w-full h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none" />
            <div className="flex gap-4">
              {[["primary_color", "Primary"], ["accent_color", "Accent"]].map(([k, label]) => (
                <label key={k} className="flex items-center gap-2 text-xs text-slate-400">
                  {label}
                  <input type="color" value={bform[k]} onChange={(e) => setBform({ ...bform, [k]: e.target.value })}
                         data-testid={`tenant-brand-${k}-input`} className="w-10 h-8 rounded cursor-pointer bg-transparent" />
                </label>
              ))}
            </div>
            <button onClick={() => saveBrand()} disabled={busy} data-testid="tenant-brand-save-btn"
                    className="px-5 py-2 rounded-full font-bold text-black text-sm disabled:opacity-60 inline-flex items-center gap-2" style={{ background: primary }}>
              {busy && <Loader2 size={13} className="animate-spin" />} Save branding
            </button>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-2">Logo (PNG/SVG, &lt;380KB)</div>
            {brand.logo_b64 ? (
              <div className="flex items-center gap-3">
                <img src={brand.logo_b64} alt="logo" className="h-16 rounded-lg bg-white/5 p-1 object-contain" />
                <button onClick={async () => { await api.delete("/branding/logo"); refreshBrand(); }} className="text-xs text-red-400 hover:text-red-300">Remove</button>
              </div>
            ) : (
              <button onClick={() => fileRef.current?.click()} data-testid="tenant-logo-upload-btn"
                      className="w-full py-6 rounded-lg border-2 border-dashed border-white/15 hover:border-white/40 text-sm text-slate-400 flex flex-col items-center gap-1">
                <UploadCloud size={18} /> Upload logo
              </button>
            )}
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => onLogo(e.target.files?.[0])} />
          </div>
        </div>
      </section>

      {/* Billing */}
      <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02]" data-testid="tenant-billing-card">
        <div className="flex items-center justify-between mb-4">
          <div className="text-xs font-mono uppercase tracking-widest text-slate-400">Billing · Stripe</div>
          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${bstatus === "active" ? "text-emerald-300 border-emerald-500/40 bg-emerald-500/10" : "text-orange-300 border-orange-500/40 bg-orange-500/10"}`}
                data-testid="tenant-billing-status">{bstatus}</span>
        </div>
        {paying && <div className="mb-4 flex items-center gap-2 text-sm text-slate-300"><Loader2 size={14} className="animate-spin" /> Confirming your payment with Stripe…</div>}
        {billing && (
          <div className="grid sm:grid-cols-3 gap-3">
            {Object.entries(billing.plans).map(([key, p]) => {
              const current = billing.billing?.plan === key && bstatus === "active";
              return (
                <div key={key} className={`p-4 rounded-xl border ${current ? "border-emerald-500/50 bg-emerald-500/5" : "border-white/10"}`}>
                  <div className="font-black">{p.name}</div>
                  <div className="text-xl font-black tabular-nums mt-1" style={{ color: primary }}>${p.monthly.toLocaleString()}<span className="text-xs text-slate-500 font-semibold">/mo</span></div>
                  {current ? (
                    <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-400 font-semibold"><CheckCircle2 size={13} /> Current plan</div>
                  ) : (
                    <button onClick={() => checkout(p.lookup_key)} data-testid={`tenant-checkout-${key}`}
                            className="mt-3 w-full py-2 rounded-full border border-white/15 hover:border-white/40 text-xs font-bold inline-flex items-center justify-center gap-1.5">
                      <CreditCard size={12} /> Subscribe
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
        <div className="text-[10px] text-slate-500 mt-3">Test card: 4242 4242 4242 4242 · any future expiry · any CVC</div>
      </section>

      {/* Password */}
      <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02]" data-testid="tenant-password-card">
        <div className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-4">Change password</div>
        <form onSubmit={changePw} className="flex flex-wrap gap-3">
          <input required type="password" placeholder="Current password" value={pw.current_password} data-testid="tenant-pw-current"
                 onChange={(e) => setPw({ ...pw, current_password: e.target.value })}
                 className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none flex-1 min-w-[180px]" />
          <input required type="password" placeholder="New password (8+ chars)" value={pw.new_password} data-testid="tenant-pw-new"
                 onChange={(e) => setPw({ ...pw, new_password: e.target.value })}
                 className="h-10 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none flex-1 min-w-[180px]" />
          <button type="submit" data-testid="tenant-pw-submit" className="px-5 py-2 rounded-full font-bold text-black text-sm" style={{ background: primary }}>Update</button>
        </form>
      </section>
    </div>
  );
}
