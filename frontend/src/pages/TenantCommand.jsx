import React, { useCallback, useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Building2, Plus, ExternalLink, Copy, Loader2, Activity, Ban, Play, Trash2, HeartPulse, Eye } from "lucide-react";
import { toast } from "sonner";
import { api, BACKEND_URL } from "../lib/api";

const PLAN_BADGE = {
  starter: "bg-slate-500/15 text-slate-300 border-slate-500/40",
  growth: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  dwy: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40",
};
const EMPTY = { company_name: "", slug: "", plan: "growth", admin_email: "", admin_password: "", admin_name: "" };

export default function TenantCommand() {
  const [tenants, setTenants] = useState([]);
  const [activity, setActivity] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);

  const load = useCallback(async () => {
    try {
      const [t, a, s] = await Promise.all([
        api.get("/hotshot/tenants"), api.get("/hotshot/activity"),
        fetch(`${BACKEND_URL}/api/hotshot/status`).then((r) => r.json()),
      ]);
      setTenants(t.data.tenants); setActivity(a.data.activity); setStatus(s);
    } catch (_) {}
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 20000); return () => clearInterval(id); }, [load]);

  const provision = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/hotshot/tenants", { ...form, origin_url: window.location.origin });
      const w = data.welcome_email;
      if (w?.sent) toast.success(`Tenant live — welcome email sent to ${form.admin_email}`);
      else toast.success(`Tenant live at ${data.login_path}`, { description: w?.reason || "" });
      setOpen(false); setForm(EMPTY); load();
    } catch (e2) { toast.error(typeof e2?.response?.data?.detail === "string" ? e2.response.data.detail : "Provisioning failed"); }
    finally { setBusy(false); }
  };

  const setTenantStatus = async (slug, s) => {
    try { await api.post(`/hotshot/tenants/${slug}/status`, { status: s }); toast.success(`Tenant ${s}`); load(); }
    catch (_) { toast.error("Failed"); }
  };
  const del = async (slug) => {
    if (!window.confirm(`Delete tenant '${slug}' and DROP their entire database? This cannot be undone.`)) return;
    try { await api.delete(`/hotshot/tenants/${slug}`); toast.success("Tenant deleted"); load(); }
    catch (_) { toast.error("Failed"); }
  };
  const copyLink = (slug) => {
    navigator.clipboard.writeText(`${window.location.origin}/t/${slug}/login`);
    toast.success("Client login link copied");
  };
  const viewAsClient = async (slug) => {
    try {
      const { data } = await api.post(`/hotshot/tenants/${slug}/impersonate`);
      localStorage.setItem(`hs_token_${slug}`, data.token);
      window.open(data.portal_path, "_blank");
      toast.success("Opening client view — you'll see exactly what they see");
    } catch (_) { toast.error("Failed to open client view"); }
  };

  return (
    <>
      <Topbar title="Hot Shot TMS — Tenant Command" subtitle="Provision, monitor and support your white-label clients — each in a fully isolated database" />
      <div className="p-4 md:p-6 space-y-5" data-testid="tenant-command-page">
        {/* Platform status */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="p-4 bg-slate-950/60 border-emerald-500/30">
            <div className="text-[10px] font-mono uppercase text-slate-500 flex items-center gap-1.5"><HeartPulse size={11} className="text-emerald-400" /> Platform</div>
            <div className={`text-xl font-black ${status?.ok ? "text-emerald-400" : "text-red-400"}`} data-testid="tc-platform-status">{status?.ok ? "HEALTHY" : "DOWN"}</div>
            <div className="text-[10px] text-slate-500 font-mono">uptime {status ? Math.floor(status.uptime_seconds / 60) : 0}m · point UptimeRobot at /api/hotshot/status</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-[10px] font-mono uppercase text-slate-500">Tenants</div>
            <div className="text-xl font-black text-amber-400" data-testid="tc-tenant-count">{tenants.length}</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-[10px] font-mono uppercase text-slate-500">Paying (active subs)</div>
            <div className="text-xl font-black text-emerald-400">{tenants.filter((t) => t.billing?.status === "active").length}</div>
          </Card>
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-[10px] font-mono uppercase text-slate-500">MRR (founder rates)</div>
            <div className="text-xl font-black text-cyan-300">
              ${tenants.filter((t) => t.billing?.status === "active")
                .reduce((a, t) => a + ({ starter: 390, growth: 975, dwy: 2600 }[t.billing?.plan] || 0), 0).toLocaleString()}
            </div>
          </Card>
        </div>

        {/* Provision */}
        <Card className="p-4 bg-slate-950/60 border-amber-500/30" data-testid="tc-provision-card">
          <div className="flex items-center justify-between">
            <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2"><Building2 size={13} /> Client workspaces</div>
            <button onClick={() => setOpen(!open)} data-testid="tc-new-tenant-btn"
                    className="px-4 py-2 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5 hover:bg-amber-400">
              <Plus size={13} /> Provision Client
            </button>
          </div>
          {open && (
            <form onSubmit={provision} className="mt-4 grid sm:grid-cols-3 gap-3" data-testid="tc-provision-form">
              {[["company_name", "Client company name *"], ["slug", "URL slug (auto if blank)"], ["admin_name", "Client admin name"],
                ["admin_email", "Client admin email *"], ["admin_password", "Client admin password (8+) *"]].map(([k, ph]) => (
                <input key={k} required={ph.includes("*")} type={k === "admin_password" ? "password" : "text"}
                       value={form[k]} placeholder={ph} data-testid={`tc-${k}-input`}
                       onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                       className="h-10 rounded-lg bg-slate-950 border border-white/15 px-3 text-sm outline-none focus:border-amber-400" />
              ))}
              <select value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })} data-testid="tc-plan-select"
                      className="h-10 rounded-lg bg-slate-950 border border-white/15 px-3 text-sm">
                <option value="starter">Starter · $390/mo</option>
                <option value="growth">Growth · $975/mo</option>
                <option value="dwy">Done-With-You · $2,600/mo</option>
              </select>
              <div className="sm:col-span-3">
                <button type="submit" disabled={busy} data-testid="tc-provision-submit"
                        className="px-5 py-2 rounded-full bg-amber-500 text-black font-bold text-sm disabled:opacity-60 inline-flex items-center gap-2">
                  {busy && <Loader2 size={13} className="animate-spin" />} Create isolated workspace
                </button>
              </div>
            </form>
          )}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
                <th className="py-2 pr-3">Client</th><th className="py-2 pr-3">Plan</th><th className="py-2 pr-3">Billing</th>
                <th className="py-2 pr-3">Usage</th><th className="py-2 pr-3">Last login</th><th className="py-2 pr-3">Status</th><th className="py-2">Actions</th>
              </tr></thead>
              <tbody>
                {tenants.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-slate-500">No clients yet — provision your first workspace above.</td></tr>}
                {tenants.map((t) => (
                  <tr key={t.slug} className="border-b border-white/5" data-testid={`tc-tenant-row-${t.slug}`}>
                    <td className="py-2.5 pr-3"><div className="text-white font-semibold">{t.company_name}{t.source === "self_serve" && <span className="ml-2 text-[8px] font-mono uppercase px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/40">self-serve</span>}</div><div className="text-[10px] text-slate-500 font-mono">/t/{t.slug}</div></td>
                    <td className="py-2.5 pr-3"><Badge className={`${PLAN_BADGE[t.plan]} text-[9px] font-mono uppercase`}>{t.plan}</Badge></td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-[10px] font-mono uppercase ${t.billing?.status === "active" ? "text-emerald-400" : "text-orange-300"}`} data-testid={`tc-billing-${t.slug}`}>
                        {t.billing?.status || "trial"}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-[11px] text-slate-400 font-mono">{t.usage.users}u · {t.usage.loads}ld · {t.usage.invoices}inv</td>
                    <td className="py-2.5 pr-3 text-[10px] text-slate-500 font-mono">{t.usage.last_login_at ? new Date(t.usage.last_login_at).toLocaleDateString() : "—"}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-[10px] font-mono uppercase ${t.status === "active" ? "text-emerald-400" : "text-red-400"}`}>{t.status}</span>
                    </td>
                    <td className="py-2.5">
                      <div className="flex gap-2.5 items-center">
                        <a href={`/t/${t.slug}/login`} target="_blank" rel="noreferrer" title="Open portal" data-testid={`tc-open-${t.slug}`}
                           className="text-cyan-300 hover:text-cyan-200"><ExternalLink size={14} /></a>
                        <button onClick={() => viewAsClient(t.slug)} title="View as client — see exactly what they see" data-testid={`tc-impersonate-${t.slug}`}
                                className="text-purple-300 hover:text-purple-200"><Eye size={14} /></button>
                        <button onClick={() => copyLink(t.slug)} title="Copy client login link" className="text-slate-400 hover:text-white"><Copy size={14} /></button>
                        {t.status === "active" ? (
                          <button onClick={() => setTenantStatus(t.slug, "suspended")} title="Suspend" data-testid={`tc-suspend-${t.slug}`}
                                  className="text-orange-400 hover:text-orange-300"><Ban size={14} /></button>
                        ) : (
                          <button onClick={() => setTenantStatus(t.slug, "active")} title="Reactivate" data-testid={`tc-activate-${t.slug}`}
                                  className="text-emerald-400 hover:text-emerald-300"><Play size={14} /></button>
                        )}
                        <button onClick={() => del(t.slug)} title="Delete tenant + drop DB" data-testid={`tc-delete-${t.slug}`}
                                className="text-slate-600 hover:text-red-400"><Trash2 size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Activity feed */}
        <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="tc-activity-card">
          <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2 mb-3"><Activity size={13} /> Platform activity · logins, billing, errors</div>
          {activity.length === 0 ? (
            <div className="text-sm text-slate-500 py-4 text-center">No activity yet.</div>
          ) : (
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {activity.map((a, i) => (
                <div key={i} className="flex items-center gap-3 text-xs py-1.5 border-b border-white/5 last:border-0">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${a.level === "warn" ? "bg-orange-400" : "bg-emerald-400"}`} />
                  <span className="font-mono text-slate-500 w-24 shrink-0">{new Date(a.at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  <span className="font-mono text-amber-300 w-24 shrink-0 truncate">{a.slug}</span>
                  <span className="text-slate-300 truncate">{a.message}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
