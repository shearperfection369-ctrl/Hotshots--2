import React, { useEffect, useMemo, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import {
  Plug, Plus, CheckCircle2, XCircle, Loader2, Trash2, Power, RefreshCw, Settings as Cog
} from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * ERPManager — admin connector hub. Lets the admin link the TMS to whatever
 * ERP the company runs (SAP, Oracle, Dynamics, NetSuite, Infor, Sage, Epicor,
 * IFS, or a custom REST API). Stores credentials server-side; secrets are
 * masked on read. Includes a live "Test Connection" probe.
 */
export default function ERPManager({ active, onChange }) {
  const [templates, setTemplates] = useState([]);
  const [connections, setConnections] = useState([]);
  const [open, setOpen] = useState(false);
  const [tpl, setTpl] = useState(null);
  const [label, setLabel] = useState("");
  const [authMode, setAuthMode] = useState("");
  const [cfg, setCfg] = useState({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);

  const loadAll = async () => {
    try {
      const [t, c] = await Promise.all([api.get("/admin/erp/templates"), api.get("/admin/erp")]);
      setTemplates(t.data.templates || []);
      setConnections(c.data.connections || []);
    } catch { toast.error("Failed to load ERP data"); }
  };
  useEffect(() => { loadAll(); }, []);

  const openFor = (template, existing = null) => {
    setTpl(template);
    setAuthMode((existing && existing.auth_mode) || template.auth_modes[0]);
    setLabel(existing?.label || `${template.name} · Default`);
    setCfg(existing?.config || {});
    setTestResult(null);
    setOpen(true);
  };

  const test = async () => {
    if (!tpl) return;
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post("/admin/erp/test", { erp_key: tpl.key, config: cfg });
      setTestResult(data);
      if (data.ok) toast.success(`Connection OK · ${data.elapsed_ms}ms · HTTP ${data.status_code}`);
      else toast.error(`Test failed · ${data.status_code || "ERR"} · ${data.error || data.preview?.slice(0, 80) || ""}`);
    } catch (e) { toast.error("Test request failed"); }
    finally { setTesting(false); }
  };

  const save = async (activate = false) => {
    if (!tpl) return;
    if (!label.trim()) { toast.error("Label is required"); return; }
    // Required fields check on the client too — for snappier UX
    for (const f of tpl.fields) {
      if (f.optional) continue;
      if (!cfg[f.key]) { toast.error(`Missing required: ${f.label}`); return; }
    }
    setSaving(true);
    try {
      await api.post("/admin/erp", { erp_key: tpl.key, label, auth_mode: authMode, config: cfg, activate });
      toast.success(activate ? "Saved & activated" : "Saved");
      setOpen(false);
      await loadAll();
      onChange?.();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    finally { setSaving(false); }
  };

  const activate = async (connection_id) => {
    try {
      await api.post("/admin/erp/activate", { connection_id });
      toast.success("Connection activated");
      await loadAll();
      onChange?.();
    } catch (e) { toast.error("Activate failed"); }
  };

  const remove = async (connection_id, label) => {
    if (!window.confirm(`Delete connection "${label}"?`)) return;
    try {
      await api.delete(`/admin/erp/${connection_id}`);
      toast.success("Connection removed");
      await loadAll();
      onChange?.();
    } catch (e) { toast.error("Delete failed"); }
  };

  return (
    <Card className="hud-surface p-5" data-testid="admin-erp-manager">
      <div className="flex items-center justify-between mb-1 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Plug size={14} className="text-cyan-400" />
          <h3 className="font-display text-base font-bold text-white">ERP Integration Hub</h3>
          <Badge className="text-[9px] font-mono uppercase bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">{templates.length} systems</Badge>
        </div>
        {active && (
          <Badge className="text-[9px] font-mono uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            Active · {active.erp_name} · {active.label}
          </Badge>
        )}
      </div>
      <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
        Connect the TMS to your company's ERP so live orders, shipments, customers and materials flow
        straight into the app. Pick a template, paste in your credentials, click <strong>Test</strong>, then activate.
      </p>

      {/* Saved connections */}
      {connections.length > 0 && (
        <>
          <div className="mt-4 text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">Saved Connections</div>
          <div className="mt-2 space-y-2" data-testid="erp-connections-list">
            {connections.map((c) => (
              <div key={c.connection_id} data-testid={`erp-conn-${c.connection_id}`}
                   className={`p-3 rounded-md border flex items-center gap-3 transition ${
                     c.is_active ? "border-emerald-500/50 bg-emerald-500/10" : "border-white/10 bg-white/[0.02] hover:border-cyan-500/30"
                   }`}>
                <Plug size={14} className="text-cyan-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-white truncate">{c.label}</div>
                  <div className="text-[10px] font-mono text-slate-500 truncate">{c.erp_name} · {c.auth_mode} · {c.config?.base_url}</div>
                </div>
                {c.is_active ? (
                  <Badge className="text-[9px] font-mono uppercase bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                    <CheckCircle2 size={9} className="mr-1" /> Active
                  </Badge>
                ) : (
                  <Button size="sm" onClick={() => activate(c.connection_id)} data-testid={`erp-activate-${c.connection_id}`}
                          className="h-7 text-[10px] font-mono uppercase tracking-wider bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    <Power size={10} className="mr-1" /> Activate
                  </Button>
                )}
                <button onClick={() => openFor(templates.find((t) => t.key === c.erp_key), c)} title="Edit" className="p-1.5 text-slate-400 hover:text-cyan-300" data-testid={`erp-edit-${c.connection_id}`}>
                  <Cog size={12} />
                </button>
                <button onClick={() => remove(c.connection_id, c.label)} title="Delete" className="p-1.5 text-slate-400 hover:text-red-400" data-testid={`erp-delete-${c.connection_id}`}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Templates grid */}
      <div className="mt-5 text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">Add a Connection</div>
      <div className="mt-2 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2" data-testid="erp-templates-grid">
        {templates.map((t) => (
          <button key={t.key} onClick={() => openFor(t)} data-testid={`erp-template-${t.key}`}
                  className="text-left p-3 rounded-md border border-white/10 bg-white/[0.02] hover:border-cyan-500/40 hover:bg-cyan-500/[0.04] transition group">
            <div className="flex items-center justify-between">
              <div className="text-sm font-bold text-white">{t.name}</div>
              <Plus size={13} className="text-slate-500 group-hover:text-cyan-300" />
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 truncate">
              {t.auth_modes.join(" · ")}
            </div>
          </button>
        ))}
      </div>

      {/* Connection dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-2xl" data-testid="erp-dialog">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Plug size={14} className="text-cyan-400" /> {tpl?.name} · Connection
            </DialogTitle>
          </DialogHeader>
          {tpl && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="md:col-span-2">
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Connection Label</Label>
                <Input value={label} onChange={(e) => setLabel(e.target.value)}
                       data-testid="erp-label" className="bg-[#11151F] border-white/10 mt-1"
                       placeholder='e.g. "SAP-PROD" or "Dynamics-Sandbox"' />
              </div>
              <div className="md:col-span-2">
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Authentication Mode</Label>
                <select value={authMode} onChange={(e) => setAuthMode(e.target.value)} data-testid="erp-auth-mode"
                        className="w-full bg-[#11151F] border border-white/10 rounded px-2 py-2 text-xs font-mono text-white mt-1">
                  {tpl.auth_modes.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              {tpl.fields.map((f) => (
                <div key={f.key} className={f.key === "base_url" ? "md:col-span-2" : ""}>
                  <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    {f.label}{f.optional && <span className="text-slate-600 ml-1">(optional)</span>}
                  </Label>
                  <Input
                    type={f.secret ? "password" : "text"}
                    value={cfg[f.key] || ""}
                    onChange={(e) => setCfg({ ...cfg, [f.key]: e.target.value })}
                    placeholder={f.placeholder || ""}
                    data-testid={`erp-field-${f.key}`}
                    className="bg-[#11151F] border-white/10 mt-1 font-mono text-xs"
                  />
                </div>
              ))}
              {testResult && (
                <div className={`md:col-span-2 p-2.5 rounded border text-[11px] font-mono ${
                  testResult.ok ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-300"
                                : "border-red-500/30 bg-red-500/5 text-red-300"
                }`} data-testid="erp-test-result">
                  <div className="flex items-center gap-1.5">
                    {testResult.ok ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
                    HTTP {testResult.status_code || "—"} · {testResult.elapsed_ms} ms
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1 truncate">{testResult.url}</div>
                  {testResult.error && <div className="text-[10px] mt-1">{testResult.error}</div>}
                  {testResult.preview && !testResult.error && (
                    <div className="text-[10px] mt-1 text-slate-400 line-clamp-2">{testResult.preview}</div>
                  )}
                </div>
              )}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpen(false)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={test} disabled={testing} data-testid="erp-test-btn"
                    className="bg-white/5 hover:bg-white/10 text-cyan-300 border border-cyan-500/30">
              {testing ? <><Loader2 size={13} className="mr-1.5 animate-spin" /> Testing…</> : <><RefreshCw size={13} className="mr-1.5" /> Test Connection</>}
            </Button>
            <Button onClick={() => save(false)} disabled={saving} data-testid="erp-save-btn"
                    className="bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30">
              {saving ? <><Loader2 size={13} className="mr-1.5 animate-spin" /> Saving…</> : "Save"}
            </Button>
            <Button onClick={() => save(true)} disabled={saving} data-testid="erp-save-activate-btn"
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              Save & Activate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
