import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Zap, Loader2 } from "lucide-react";
import { errText } from "./tenantApi";

export default function TenantLogin() {
  const { slug } = useParams();
  const nav = useNavigate();
  const [brand, setBrand] = useState(null);
  const [form, setForm] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/t/${slug}/branding/public`)
      .then((r) => setBrand(r.data)).catch(() => setBrand({ company_name: slug, primary_color: "#F59E0B", accent_color: "#22D3EE" }));
  }, [slug]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/t/${slug}/auth/login`, form);
      localStorage.setItem(`hs_token_${slug}`, data.token);
      nav(`/t/${slug}/app`);
    } catch (e2) { setErr(errText(e2)); } finally { setBusy(false); }
  };

  const p = brand?.primary_color || "#F59E0B";
  return (
    <div className="min-h-screen bg-[#0D1117] text-slate-100 grid place-items-center px-4" data-testid="tenant-login-page">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          {brand?.logo_b64 ? (
            <img src={brand.logo_b64} alt="logo" className="h-16 mx-auto mb-3 object-contain" data-testid="tenant-login-logo" />
          ) : (
            <div className="w-14 h-14 rounded-2xl mx-auto mb-3 grid place-items-center" style={{ background: p }}>
              <Zap className="text-black" size={26} />
            </div>
          )}
          <div className="text-2xl font-black tracking-tight" data-testid="tenant-login-company">{brand?.company_name || "…"}</div>
          <div className="text-[11px] font-mono uppercase tracking-widest text-slate-500 mt-1">{brand?.tagline || "Powered by Hot Shot TMS"}</div>
        </div>
        <form onSubmit={submit} className="space-y-3 p-6 rounded-2xl border border-white/10 bg-white/[0.02]" data-testid="tenant-login-form">
          <input type="email" required placeholder="Email" value={form.email} data-testid="tenant-login-email"
                 onChange={(e) => setForm({ ...form, email: e.target.value })}
                 className="w-full h-11 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none focus:border-white/40" />
          <input type="password" required placeholder="Password" value={form.password} data-testid="tenant-login-password"
                 onChange={(e) => setForm({ ...form, password: e.target.value })}
                 className="w-full h-11 rounded-lg bg-[#0D1117] border border-white/15 px-3 text-sm outline-none focus:border-white/40" />
          {err && <div className="text-xs text-red-400" data-testid="tenant-login-error">{err}</div>}
          <button type="submit" disabled={busy} data-testid="tenant-login-submit"
                  className="w-full py-3 rounded-full font-black text-black disabled:opacity-60 inline-flex items-center justify-center gap-2"
                  style={{ background: p }}>
            {busy && <Loader2 size={15} className="animate-spin" />} Sign in
          </button>
        </form>
        <div className="text-center text-[10px] text-slate-600 font-mono mt-6">HOT SHOT TMS · isolated workspace · {slug}</div>
      </div>
    </div>
  );
}
