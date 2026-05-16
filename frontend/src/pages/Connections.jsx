import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  Plug, KeyRound, ExternalLink, CheckCircle2, AlertCircle, Loader2,
  RefreshCw, Trash2, Save, Activity, Lock, ShieldCheck, Plus, X, GripVertical, SlidersHorizontal,
} from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * Connections · admin-managed third-party credential vault.
 *
 * Each provider card shows status + last update; clicking Configure opens a
 * dialog with the strict field schema served by the backend. Secret fields
 * are masked in the list and accept empty input on edit (keep existing).
 */
const STATUS_STYLES = {
  connected:    { bg: "bg-emerald-500/12 text-emerald-300 border-emerald-500/30",   label: "CONNECTED",   Icon: CheckCircle2 },
  configured:   { bg: "bg-cyan-500/12 text-cyan-300 border-cyan-500/30",            label: "CONFIGURED",  Icon: CheckCircle2 },
  disabled:     { bg: "bg-yellow-500/12 text-yellow-300 border-yellow-500/30",      label: "DISABLED",    Icon: AlertCircle },
  unconfigured: { bg: "bg-white/[0.04] text-slate-400 border-white/10",             label: "AVAILABLE",   Icon: KeyRound },
  error:        { bg: "bg-red-500/12 text-red-300 border-red-500/30",               label: "ERROR",       Icon: AlertCircle },
};

export default function Connections() {
  const [connections, setConnections] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeProvider, setActiveProvider] = useState(null);
  const [showAdd, setShowAdd] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/connections");
      setConnections(data.connections || []);
      setProviders(data.providers || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load connections");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  // Build merged view: provider def + current conn state
  const cards = useMemo(() => {
    return providers.map((prov) => {
      const conn = connections.find((c) => c.provider_id === prov.id) || {
        provider_id: prov.id,
        status: "unconfigured",
        enabled: false,
        fields: {},
      };
      return { ...prov, conn };
    });
  }, [providers, connections]);

  const grouped = useMemo(() => {
    const out = {};
    cards.forEach((c) => { (out[c.category] ||= []).push(c); });
    return out;
  }, [cards]);

  const configuredCount = connections.filter((c) => c.status !== "unconfigured").length;
  const enabledCount = connections.filter((c) => c.enabled).length;
  const customCount = providers.filter((p) => p.builtin === false).length;

  const deleteCustomProvider = async (id, name) => {
    if (!window.confirm(`Remove custom provider "${name}"? This deletes its stored credentials too.`)) return;
    try {
      await api.delete(`/connections/providers/custom/${id}`);
      toast.success(`Removed ${name}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Remove failed");
    }
  };

  return (
    <>
      <Topbar title="Connections · External Providers" subtitle="Admin-managed credentials · encrypted at rest" />
      <div className="p-4 md:p-6 space-y-5" data-testid="connections-page">
        {/* Header bar */}
        <Card className="hud-surface p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3" data-testid="connections-header">
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2">
              <Lock size={11} /> Encrypted Vault
            </div>
            <h3 className="font-display text-xl font-black flex items-center gap-2">
              <Plug size={18} className="text-cyan-400" /> {providers.length} Available Connectors
            </h3>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              {configuredCount} configured · {enabledCount} enabled · {customCount} custom · Secrets stored Fernet-encrypted, never returned in plaintext.
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => setShowAdd(true)}
              data-testid="connections-add-custom-btn"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase tracking-wider"
            >
              <Plus size={13} className="mr-1.5" /> Add Integration
            </Button>
            <Button
              onClick={() => { setLoading(true); load(); }}
              disabled={loading}
              className="bg-white/5 border border-white/10 hover:border-cyan-400/40 hover:text-cyan-200 text-slate-300 font-mono text-[11px] uppercase tracking-wider"
              data-testid="connections-refresh-btn"
            >
              {loading ? <Loader2 size={13} className="animate-spin mr-1.5" /> : <RefreshCw size={13} className="mr-1.5" />} Refresh
            </Button>
          </div>
        </Card>

        {loading && !cards.length ? (
          <div className="flex items-center justify-center p-12 text-slate-500"><Loader2 className="animate-spin mr-2" size={16} /> Loading connectors…</div>
        ) : (
          Object.entries(grouped).map(([category, list]) => (
            <Card key={category} className="hud-surface p-5" data-testid={`connections-group-${category.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">{category}</div>
              <h3 className="font-display text-lg font-bold mb-4">{category}</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {list.map((card) => (
                  <ProviderCard
                    key={card.id}
                    card={card}
                    onConfigure={() => setActiveProvider(card)}
                    onDeleteCustom={card.builtin === false ? () => deleteCustomProvider(card.id, card.name) : null}
                  />
                ))}
              </div>
            </Card>
          ))
        )}
      </div>

      <ConfigureDialog
        provider={activeProvider}
        onClose={() => setActiveProvider(null)}
        onSaved={() => { setActiveProvider(null); load(); }}
      />
      <AddCustomProviderDialog
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSaved={() => { setShowAdd(false); load(); }}
      />
    </>
  );
}

function ProviderCard({ card, onConfigure, onDeleteCustom }) {
  const conn = card.conn;
  const styles = STATUS_STYLES[conn.status] || STATUS_STYLES.unconfigured;
  return (
    <div
      data-testid={`connection-card-${card.id}`}
      className="rounded-md border border-white/5 bg-white/[0.02] p-4 hover:border-cyan-500/30 transition-colors flex flex-col"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center font-mono text-[11px] font-bold text-cyan-300 shrink-0">
            {card.logo}
          </div>
          <div className="min-w-0">
            <div className="font-display font-semibold text-white truncate flex items-center gap-1.5">
              {card.name}
              {card.builtin === false && (
                <span className="text-[8px] font-mono uppercase px-1 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">custom</span>
              )}
            </div>
            <div className="text-[10px] font-mono text-slate-500 truncate">{card.fields.length} field{card.fields.length === 1 ? "" : "s"}</div>
          </div>
        </div>
        <Badge className={`${styles.bg} font-mono text-[9px] uppercase whitespace-nowrap`}>
          <styles.Icon size={10} className="mr-1" /> {styles.label}
        </Badge>
      </div>
      <p className="text-xs text-slate-400 mt-3 line-clamp-2 min-h-[2.4em]">{card.description}</p>
      <div className="mt-3 pt-3 border-t border-white/5 flex items-center justify-between gap-2">
        <div className="text-[10px] font-mono text-slate-500 truncate">
          {conn.updated_at ? `Updated ${new Date(conn.updated_at).toLocaleDateString()}` : "Not yet configured"}
        </div>
        <div className="flex items-center gap-1.5">
          {onDeleteCustom && (
            <button
              onClick={onDeleteCustom}
              data-testid={`connection-remove-custom-${card.id}`}
              title="Remove this custom integration"
              className="text-slate-500 hover:text-red-400 p-1"
            >
              <X size={12} />
            </button>
          )}
          <Button
            onClick={onConfigure}
            data-testid={`connection-configure-${card.id}`}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[10px] uppercase tracking-wider px-2.5 py-1 h-auto"
          >
            <KeyRound size={11} className="mr-1" /> Configure
          </Button>
        </div>
      </div>
    </div>
  );
}

function ConfigureDialog({ provider, onClose, onSaved }) {
  const [values, setValues] = useState({});
  const [enabled, setEnabled] = useState(true);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (!provider) return;
    const conn = provider.conn || {};
    const initial = {};
    provider.fields.forEach((f) => {
      const cell = conn.fields?.[f.key] || {};
      // For secret fields, always start blank (user types only if changing).
      // For non-secret fields, prefill from server-stored value.
      initial[f.key] = f.secret ? "" : (cell.value || f.default || "");
    });
    setValues(initial);
    setEnabled(conn.enabled !== undefined ? conn.enabled : true);
    setNotes(conn.notes || "");
  }, [provider]);

  if (!provider) return null;

  const save = async () => {
    setBusy(true);
    try {
      await api.put(`/connections/${provider.id}`, { fields: values, enabled, notes: notes || null });
      toast.success(`${provider.name} saved`);
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const { data } = await api.post(`/connections/${provider.id}/test`);
      if (data.ok) toast.success(data.message || "Connection OK");
      else toast.error(data.message || "Connection test failed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm(`Disconnect ${provider.name}? This deletes the stored credentials.`)) return;
    setBusy(true);
    try {
      await api.delete(`/connections/${provider.id}`);
      toast.success(`${provider.name} disconnected`);
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Disconnect failed");
    } finally {
      setBusy(false);
    }
  };

  const isConfigured = provider.conn?.status && provider.conn.status !== "unconfigured";

  return (
    <Dialog open={!!provider} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-xl bg-slate-900 border-cyan-500/20" data-testid={`connections-dialog-${provider.id}`}>
        <DialogHeader>
          <DialogTitle className="font-display text-xl flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center font-mono text-[10px] font-bold text-cyan-300">{provider.logo}</div>
            Configure {provider.name}
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            {provider.description}
            {provider.docs_url && (
              <a href={provider.docs_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 ml-1.5">
                docs <ExternalLink size={10} />
              </a>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {provider.fields.map((f) => {
            const cellPreview = provider.conn?.fields?.[f.key]?.preview;
            const wasSet = provider.conn?.fields?.[f.key]?.set;
            return (
              <div key={f.key} className="space-y-1">
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  {f.tuner ? <SlidersHorizontal size={9} className="text-yellow-400" /> : f.secret && <Lock size={9} className="text-cyan-400" />}
                  {f.label}
                  {f.required && <span className="text-red-400">*</span>}
                </Label>
                {f.options ? (
                  <select
                    value={values[f.key] || ""}
                    onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    data-testid={`connections-field-${provider.id}-${f.key}`}
                    className="w-full bg-slate-950 border border-white/10 rounded px-3 py-2 text-sm text-slate-200 focus:border-cyan-500/50 focus:outline-none"
                  >
                    {f.options.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                ) : (
                  <Input
                    type={f.secret ? "password" : "text"}
                    value={values[f.key] || ""}
                    onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    placeholder={f.secret && wasSet ? `••• existing value kept (${cellPreview || "set"})` : f.placeholder || ""}
                    data-testid={`connections-field-${provider.id}-${f.key}`}
                    className={`bg-slate-950 border-white/10 ${f.tuner ? "border-yellow-500/30 focus:border-yellow-400/60" : ""}`}
                  />
                )}
                {f.hint && (
                  <div className="text-[10px] font-mono text-slate-500 pl-3 border-l border-yellow-500/30">{f.hint}</div>
                )}
              </div>
            );
          })}

          <div className="pt-2 space-y-2">
            <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Notes (optional)</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              data-testid={`connections-notes-${provider.id}`}
              placeholder="Account name, billing contact, renewal date…"
              className="bg-slate-950 border-white/10 text-sm"
            />
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <div className="flex items-center gap-2">
              <Switch
                checked={enabled}
                onCheckedChange={setEnabled}
                data-testid={`connections-enabled-${provider.id}`}
              />
              <Label className="text-xs text-slate-300">{enabled ? "Enabled" : "Disabled"}</Label>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
              <ShieldCheck size={11} className="text-emerald-400" /> Fernet-encrypted at rest
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2 flex-wrap">
          {isConfigured && (
            <Button
              onClick={disconnect}
              disabled={busy}
              data-testid={`connections-disconnect-${provider.id}`}
              className="bg-red-500/10 border border-red-500/40 text-red-300 hover:bg-red-500/20 font-mono text-[11px] uppercase mr-auto"
            >
              <Trash2 size={12} className="mr-1.5" /> Disconnect
            </Button>
          )}
          <Button
            onClick={test}
            disabled={testing || busy}
            data-testid={`connections-test-${provider.id}`}
            className="bg-white/5 border border-white/10 text-slate-300 hover:border-cyan-400/40 font-mono text-[11px] uppercase"
          >
            {testing ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <Activity size={12} className="mr-1.5" />} Test
          </Button>
          <Button
            onClick={save}
            disabled={busy}
            data-testid={`connections-save-${provider.id}`}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase"
          >
            {busy ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <Save size={12} className="mr-1.5" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ============================================================
//                ADD CUSTOM PROVIDER DIALOG
// ============================================================
function AddCustomProviderDialog({ open, onClose, onSaved }) {
  const blankField = () => ({ key: "", label: "", secret: false, required: true, placeholder: "" });
  const [name, setName] = useState("");
  const [pid, setPid] = useState("");
  const [category, setCategory] = useState("Other");
  const [description, setDescription] = useState("");
  const [logo, setLogo] = useState("");
  const [docsUrl, setDocsUrl] = useState("");
  const [fields, setFields] = useState([blankField()]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(""); setPid(""); setCategory("Other"); setDescription("");
    setLogo(""); setDocsUrl(""); setFields([blankField()]); setBusy(false);
  }, [open]);

  useEffect(() => {
    if (!name || pid) return;
    setPid(name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40));
  }, [name]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateField = (i, patch) => setFields((arr) => arr.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  const addField = () => setFields((arr) => [...arr, blankField()]);
  const removeField = (i) => setFields((arr) => arr.filter((_, j) => j !== i));

  const save = async () => {
    if (!name.trim() || !pid.trim() || !category.trim()) {
      toast.error("Name, ID, and category are required");
      return;
    }
    const cleaned = fields
      .map((f) => ({ ...f, key: (f.key || "").trim(), label: (f.label || "").trim() }))
      .filter((f) => f.key && f.label);
    if (!cleaned.length) {
      toast.error("Add at least one credential field");
      return;
    }
    for (const f of cleaned) {
      if (!/^[a-z0-9_]+$/.test(f.key)) {
        toast.error(`Field key "${f.key}" must be lowercase letters, numbers, or underscores`);
        return;
      }
    }
    setBusy(true);
    try {
      await api.post("/connections/providers/custom", {
        id: pid.trim(),
        name: name.trim(),
        category: category.trim(),
        description: description.trim() || null,
        logo: (logo || name.slice(0, 2)).toUpperCase().slice(0, 4),
        docs_url: docsUrl.trim() || null,
        fields: cleaned,
      });
      toast.success(`${name} added — configure it now`);
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to add provider");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-2xl bg-slate-900 border-cyan-500/20 max-h-[90vh] overflow-y-auto" data-testid="connections-add-custom-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-xl flex items-center gap-2">
            <Plus size={18} className="text-cyan-400" /> Add Custom Integration
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Define a brand-new provider and its credential fields. No code change required — the new card will appear immediately, and credentials will be encrypted at rest like every other connector.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Display Name <span className="text-red-400">*</span></Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acme Cargo API" data-testid="custom-provider-name" className="bg-slate-950 border-white/10" />
            </div>
            <div className="space-y-1">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Provider ID <span className="text-red-400">*</span></Label>
              <Input value={pid} onChange={(e) => setPid(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))} placeholder="acme-cargo" data-testid="custom-provider-id" className="bg-slate-950 border-white/10 font-mono text-xs" />
            </div>
            <div className="space-y-1">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Category <span className="text-red-400">*</span></Label>
              <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Load Board · Payments · Email · …" data-testid="custom-provider-category" className="bg-slate-950 border-white/10" />
            </div>
            <div className="space-y-1">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Logo Letters (2–4)</Label>
              <Input value={logo} onChange={(e) => setLogo(e.target.value.toUpperCase().slice(0, 4))} placeholder="AC" data-testid="custom-provider-logo" className="bg-slate-950 border-white/10 font-mono" />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Description (optional)</Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="One-line summary of what this integration does" data-testid="custom-provider-description" className="bg-slate-950 border-white/10" />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Docs URL (optional)</Label>
              <Input value={docsUrl} onChange={(e) => setDocsUrl(e.target.value)} placeholder="https://api.example.com/docs" data-testid="custom-provider-docs" className="bg-slate-950 border-white/10" />
            </div>
          </div>

          <div className="pt-2 border-t border-white/5">
            <div className="flex items-center justify-between mb-2">
              <Label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Credential Fields</Label>
              <button onClick={addField} data-testid="custom-provider-add-field" className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 flex items-center gap-1">
                <Plus size={11} /> Add field
              </button>
            </div>
            <div className="space-y-2">
              {fields.map((f, i) => (
                <div key={i} data-testid={`custom-provider-field-row-${i}`} className="grid grid-cols-12 gap-2 items-center p-2 rounded bg-white/[0.02] border border-white/5">
                  <GripVertical size={12} className="col-span-1 text-slate-600 mx-auto" />
                  <Input value={f.label} onChange={(e) => updateField(i, { label: e.target.value })} placeholder="Label (e.g. API Key)" data-testid={`custom-provider-field-label-${i}`} className="col-span-4 bg-slate-950 border-white/10 text-xs h-8" />
                  <Input value={f.key} onChange={(e) => updateField(i, { key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") })} placeholder="key (snake_case)" data-testid={`custom-provider-field-key-${i}`} className="col-span-3 bg-slate-950 border-white/10 text-xs h-8 font-mono" />
                  <label className="col-span-2 flex items-center gap-1.5 text-[10px] font-mono uppercase text-slate-400 cursor-pointer">
                    <input type="checkbox" checked={f.secret} onChange={(e) => updateField(i, { secret: e.target.checked })} data-testid={`custom-provider-field-secret-${i}`} className="accent-cyan-500" />
                    Secret
                  </label>
                  <label className="col-span-1 flex items-center gap-1.5 text-[10px] font-mono uppercase text-slate-400 cursor-pointer">
                    <input type="checkbox" checked={f.required} onChange={(e) => updateField(i, { required: e.target.checked })} data-testid={`custom-provider-field-required-${i}`} className="accent-cyan-500" />
                    Req
                  </label>
                  <button onClick={() => removeField(i)} disabled={fields.length === 1} data-testid={`custom-provider-field-remove-${i}`} className="col-span-1 text-slate-500 hover:text-red-400 disabled:opacity-30 mx-auto">
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-2 flex items-center gap-1.5">
              <ShieldCheck size={11} className="text-emerald-400" /> Secret fields are Fernet-encrypted at rest and never returned in plaintext.
            </div>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button onClick={onClose} disabled={busy} className="bg-white/5 border border-white/10 text-slate-300 hover:border-white/20 font-mono text-[11px] uppercase">Cancel</Button>
          <Button onClick={save} disabled={busy} data-testid="custom-provider-save-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold font-mono text-[11px] uppercase">
            {busy ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <Save size={12} className="mr-1.5" />} Add Integration
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
