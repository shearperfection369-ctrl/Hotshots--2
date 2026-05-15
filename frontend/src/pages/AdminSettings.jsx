import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Settings, Save, Bell, Mail, Database, Globe, Shield, Zap } from "lucide-react";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Navigate } from "react-router-dom";
import CompanyTheme from "../components/CompanyTheme";

/**
 * AdminSettings · single page for admin-tunable knobs. Persists to
 * /api/admin/settings (single doc). Non-admins are redirected away.
 */
const SECTIONS = [
  {
    key: "notifications",
    icon: Bell,
    title: "Notifications",
    fields: [
      { key: "wellness_nudges_enabled", label: "Wellness nudges in app", type: "switch", default: true, hint: "Friendly stretch/hydrate/breath reminders throughout the day." },
      { key: "weather_alerts_enabled", label: "Auto weather alerts banner", type: "switch", default: true, hint: "Surface NWS-style alerts in a sticky top banner." },
      { key: "wellness_interval_minutes", label: "Wellness nudge interval (minutes)", type: "number", default: 22 },
      { key: "weather_poll_seconds", label: "Weather alert poll (seconds)", type: "number", default: 60 },
    ],
  },
  {
    key: "email",
    icon: Mail,
    title: "Email",
    fields: [
      { key: "email_from", label: "Default \"from\" address", type: "text", default: "transportation@tennantco.com" },
      { key: "email_cs_quality", label: "CS · Quality team", type: "text", default: "CS-Quality@tennantco.com" },
      { key: "email_cs_parts", label: "CS · Parts team", type: "text", default: "CS-Parts@tennantco.com" },
      { key: "email_cs_distribution", label: "CS · Distribution team", type: "text", default: "CS-Distribution@tennantco.com" },
      { key: "email_cs_strategic", label: "CS · Strategic Accounts", type: "text", default: "CS-StrategicAccounts@tennantco.com" },
    ],
  },
  {
    key: "integrations",
    icon: Database,
    title: "Integrations",
    fields: [
      { key: "sap_s4_base", label: "SAP S/4HANA base URL", type: "text", default: "https://my-s4.tennantco.com" },
      { key: "sharepoint_tenant_url", label: "SharePoint tenant URL", type: "text", default: "https://tennantco.sharepoint.com" },
      { key: "powerbi_workspace_url", label: "Power BI workspace URL", type: "text", default: "https://app.powerbi.com/groups/me" },
    ],
  },
  {
    key: "operations",
    icon: Zap,
    title: "Operations",
    fields: [
      { key: "default_routing_mode", label: "Default routing mode for new shipments", type: "select", options: ["TL", "LTL", "Parcel", "Ocean", "Air", "Rail"], default: "TL" },
      { key: "tlb_auto_onboard_new_carriers", label: "Auto-onboard new carrier names on booking", type: "switch", default: true },
      { key: "yard_stale_threshold_days", label: "Stale trailer alert threshold (days)", type: "number", default: 5 },
      { key: "map_refresh_seconds", label: "Tracking map auto-refresh (seconds)", type: "number", default: 30 },
    ],
  },
  {
    key: "security",
    icon: Shield,
    title: "Security",
    fields: [
      { key: "session_timeout_minutes", label: "Session timeout (minutes)", type: "number", default: 480 },
      { key: "require_mfa_admins", label: "Require MFA for admin role", type: "switch", default: true },
      { key: "audit_log_retention_days", label: "Audit log retention (days)", type: "number", default: 365 },
    ],
  },
];

export default function AdminSettings() {
  const { user } = useAuth();
  const [values, setValues] = useState({});
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/admin/settings").then(({ data }) => {
      const merged = {};
      SECTIONS.forEach((s) => s.fields.forEach((f) => {
        merged[f.key] = data?.[f.key] !== undefined ? data[f.key] : f.default;
      }));
      setValues(merged);
      setLoaded(true);
    }).catch(() => {
      const def = {};
      SECTIONS.forEach((s) => s.fields.forEach((f) => { def[f.key] = f.default; }));
      setValues(def);
      setLoaded(true);
    });
  }, []);

  if (user && user.role !== "admin") return <Navigate to="/dashboard" replace />;

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/admin/settings", values);
      toast.success("Settings saved");
    } catch (e) {
      toast.error("Save failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };
  const set = (k, v) => setValues((x) => ({ ...x, [k]: v }));

  return (
    <>
      <Topbar title="Admin Settings" subtitle="Tune notifications, integrations, operations & security across the TMS" />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-12 flex items-center justify-end">
          <Button
            onClick={save}
            disabled={saving || !loaded}
            data-testid="admin-settings-save"
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
          >
            <Save size={14} className="mr-1.5" /> {saving ? "Saving…" : "Save all changes"}
          </Button>
        </div>

        {/* Company Theme switcher — full-width, top of the grid so it sets
            the context (the brand) before any of the other knobs. */}
        <CompanyTheme />

        {SECTIONS.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.key} className="hud-surface p-5 lg:col-span-6" data-testid={`admin-section-${s.key}`}>
              <div className="flex items-center gap-2 mb-4">
                <Icon size={14} className="text-cyan-400" />
                <h3 className="font-display text-base font-bold text-white">{s.title}</h3>
              </div>
              <div className="space-y-3">
                {s.fields.map((f) => (
                  <div key={f.key} className="grid grid-cols-1 md:grid-cols-3 gap-2 items-start">
                    <div className="md:col-span-2">
                      <Label className="text-xs text-slate-300">{f.label}</Label>
                      {f.hint && <div className="text-[10px] text-slate-500 mt-0.5">{f.hint}</div>}
                    </div>
                    <div>
                      {f.type === "switch" ? (
                        <Switch
                          checked={!!values[f.key]}
                          onCheckedChange={(v) => set(f.key, v)}
                          data-testid={`admin-${f.key}`}
                        />
                      ) : f.type === "select" ? (
                        <select
                          value={values[f.key] || ""}
                          onChange={(e) => set(f.key, e.target.value)}
                          data-testid={`admin-${f.key}`}
                          className="w-full bg-[#11151F] border border-white/10 rounded px-2 py-1 text-xs font-mono text-white"
                        >
                          {f.options.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      ) : (
                        <Input
                          type={f.type === "number" ? "number" : "text"}
                          value={values[f.key] ?? ""}
                          onChange={(e) => set(f.key, f.type === "number" ? Number(e.target.value) : e.target.value)}
                          data-testid={`admin-${f.key}`}
                          className="bg-[#11151F] border-white/10"
                        />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
