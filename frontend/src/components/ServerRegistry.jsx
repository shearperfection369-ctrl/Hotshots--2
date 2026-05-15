import React, { useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "./ui/dialog";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "./ui/select";
import { Textarea } from "./ui/textarea";
import { Server, Plus, Activity, Trash2, Pencil, RefreshCw, CheckCircle2, AlertTriangle, Cpu, Database, Cloud, Globe, Boxes, ShieldCheck, Inbox } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * ServerRegistry — admin-only "CMDB lite" for every server attached to the
 * TMS. Auto-detects live system servers (this pod, MongoDB, LLM gateway,
 * ingress) and lets the admin register additional infrastructure with
 * one-click TCP / HTTP health probes.
 */
const ROLE_ICON = {
  api: Cpu,
  db: Database,
  cache: Boxes,
  llm: Cpu,
  edge: Globe,
  storage: Cloud,
  edi: Inbox,
  queue: Activity,
  reporting: ShieldCheck,
  other: Server,
};

const HEALTH_STYLE = {
  healthy:      "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  degraded:     "bg-amber-500/15 text-amber-300 border-amber-500/30",
  down:         "bg-red-500/15 text-red-300 border-red-500/30",
  unknown:      "bg-slate-500/15 text-slate-300 border-slate-500/30",
  unconfigured: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

const EMPTY_FORM = {
  name: "", role: "api", hostname: "", port: "", protocol: "https",
  region: "", environment: "production", owner_email: "", notes: "", health_url: "",
};

export default function ServerRegistry() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [pingingId, setPingingId] = useState(null);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/servers");
      setData(data);
    } catch {
      toast.error("Failed to load server registry");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => { setForm(EMPTY_FORM); setEditingId(null); setDialogOpen(true); };
  const openEdit = (s) => {
    setForm({
      name: s.name || "", role: s.role || "api", hostname: s.hostname || "",
      port: s.port || "", protocol: s.protocol || "https", region: s.region || "",
      environment: s.environment || "production", owner_email: s.owner_email || "",
      notes: s.notes || "", health_url: s.health_url || "",
    });
    setEditingId(s.id);
    setDialogOpen(true);
  };

  const submit = async () => {
    if (!form.name.trim() || !form.hostname.trim()) {
      toast.error("Name and hostname are required");
      return;
    }
    try {
      const payload = { ...form, port: form.port ? Number(form.port) : null };
      if (editingId) {
        await api.patch(`/admin/servers/${editingId}`, payload);
        toast.success("Server updated");
      } else {
        await api.post("/admin/servers", payload);
        toast.success("Server registered");
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const ping = async (id) => {
    setPingingId(id);
    try {
      const { data } = await api.post(`/admin/servers/${id}/ping`);
      if (data.last_health === "healthy") toast.success(`Healthy · ${data.last_ping_ms ?? "?"}ms`);
      else if (data.last_health === "degraded") toast.warning(`Degraded · ${data.last_detail || ""}`);
      else toast.error(`Down · ${data.last_detail || ""}`);
      load();
    } catch {
      toast.error("Ping failed");
    } finally { setPingingId(null); }
  };

  const remove = async (id, name) => {
    if (!window.confirm(`Remove server "${name}"?`)) return;
    try {
      await api.delete(`/admin/servers/${id}`);
      toast.success("Server removed");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const totals = data?.totals || {};
  const allRows = [...(data?.system || []), ...(data?.custom || [])];

  return (
    <Card className="hud-surface p-5" data-testid="server-registry">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Infrastructure</div>
          <h3 className="font-display text-lg font-bold flex items-center gap-2">
            <Server size={18} className="text-cyan-400" /> Server Registry
          </h3>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Every host and service attached to the TMS. Auto-discovered system servers stay
            live; custom servers can be registered, edited, ping-tested, and retired.
          </p>
        </div>
        <Button onClick={openCreate} data-testid="server-registry-add" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shrink-0">
          <Plus size={14} className="mr-1.5" /> Register Server
        </Button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Tile label="Total Servers"  value={totals.total ?? "—"}   accent="text-cyan-300" />
        <Tile label="Healthy"        value={totals.healthy ?? 0}   accent="text-emerald-300" />
        <Tile label="Down"           value={totals.down ?? 0}      accent={totals.down ? "text-red-300" : "text-slate-400"} />
        <Tile label="Roles"          value={Object.keys(totals.by_role || {}).length} accent="text-purple-300" />
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded border border-white/5">
        <table className="w-full text-sm">
          <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="text-left py-3 px-4">Server</th>
              <th className="text-left py-3 px-4">Role</th>
              <th className="text-left py-3 px-4">Hostname</th>
              <th className="text-left py-3 px-4">Region · Env</th>
              <th className="text-left py-3 px-4">Health</th>
              <th className="text-left py-3 px-4">Last Check</th>
              <th className="text-right py-3 px-4">Actions</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {loading && (
              <tr><td colSpan={7} className="text-center py-10 text-slate-500">Loading…</td></tr>
            )}
            {!loading && allRows.length === 0 && (
              <tr><td colSpan={7} className="text-center py-10 text-slate-500">No servers registered yet.</td></tr>
            )}
            {allRows.map((s) => {
              const Icon = ROLE_ICON[s.role] || Server;
              const health = s.health || s.last_health || "unknown";
              const isSys = s.system || s.id?.startsWith("system::");
              const lastCheck = s.last_check_at ? new Date(s.last_check_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—";
              return (
                <tr key={s.id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`server-row-${s.id}`}>
                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded bg-cyan-500/10 border border-cyan-500/20">
                        <Icon size={12} className="text-cyan-300" />
                      </div>
                      <div>
                        <div className="text-slate-200 font-bold flex items-center gap-1.5">
                          {s.name}
                          {isSys && <span className="text-[8px] font-mono uppercase tracking-wider text-cyan-400 px-1.5 py-0.5 rounded bg-cyan-500/10">SYSTEM</span>}
                        </div>
                        {s.notes && <div className="text-[10px] text-slate-500 mt-0.5 max-w-[280px] truncate">{s.notes}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="py-2.5 px-4 text-slate-300 uppercase text-[10px] tracking-wider">{s.role}</td>
                  <td className="py-2.5 px-4 text-slate-300">
                    <div className="text-cyan-300">{s.hostname}{s.port ? `:${s.port}` : ""}</div>
                    {s.ip && <div className="text-[10px] text-slate-500">{s.ip}</div>}
                    {s.protocol && <div className="text-[10px] text-slate-500">{s.protocol}</div>}
                  </td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">
                    {s.region || "—"}<br />
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">{s.environment || "—"}</span>
                  </td>
                  <td className="py-2.5 px-4">
                    <Badge className={`${HEALTH_STYLE[health] || HEALTH_STYLE.unknown} font-mono text-[10px] uppercase`}>
                      {health === "healthy" && <CheckCircle2 size={10} className="mr-1" />}
                      {health === "down" && <AlertTriangle size={10} className="mr-1" />}
                      {health}
                    </Badge>
                    {(s.ping_ms || s.last_ping_ms) && <div className="text-[10px] text-slate-500 mt-1">{s.ping_ms ?? s.last_ping_ms}ms</div>}
                    {s.version && <div className="text-[10px] text-slate-500 mt-0.5 truncate max-w-[180px]" title={s.version}>v{s.version}</div>}
                  </td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">{lastCheck}</td>
                  <td className="py-2.5 px-4 text-right">
                    <div className="inline-flex gap-1.5">
                      {!isSys && (
                        <Button size="sm" variant="ghost" onClick={() => ping(s.id)} disabled={pingingId === s.id}
                          data-testid={`server-ping-${s.id}`}
                          className="h-7 px-2 text-[10px] hover:bg-cyan-500/10 hover:text-cyan-300">
                          <RefreshCw size={11} className={pingingId === s.id ? "animate-spin" : ""} />
                        </Button>
                      )}
                      {!isSys && (
                        <Button size="sm" variant="ghost" onClick={() => openEdit(s)}
                          data-testid={`server-edit-${s.id}`}
                          className="h-7 px-2 text-[10px] hover:bg-cyan-500/10 hover:text-cyan-300">
                          <Pencil size={11} />
                        </Button>
                      )}
                      {!isSys && (
                        <Button size="sm" variant="ghost" onClick={() => remove(s.id, s.name)}
                          data-testid={`server-delete-${s.id}`}
                          className="h-7 px-2 text-[10px] hover:bg-red-500/10 hover:text-red-300">
                          <Trash2 size={11} />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Create / edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl bg-[#0B0E14] border-white/10">
          <DialogHeader>
            <DialogTitle className="font-display text-lg flex items-center gap-2">
              <Server size={16} className="text-cyan-400" />
              {editingId ? "Edit Server" : "Register a New Server"}
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400">
              Track any backing infrastructure — EDI gateways, reporting nodes, object stores,
              edge proxies, etc. Provide a <code className="text-cyan-300">health_url</code> for
              HTTP checks or <code className="text-cyan-300">port</code> for TCP probes.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name *" testid="server-form-name">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="EDI Gateway · Cleo" data-testid="server-form-name-input" />
            </Field>
            <Field label="Role *" testid="server-form-role">
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="server-form-role-trigger"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["api", "db", "cache", "llm", "edge", "storage", "edi", "queue", "reporting", "other"].map((r) => (
                    <SelectItem key={r} value={r}>{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Hostname *" testid="server-form-host">
              <Input value={form.hostname} onChange={(e) => setForm({ ...form, hostname: e.target.value })} placeholder="edi.tennantco.internal" data-testid="server-form-host-input" />
            </Field>
            <Field label="Port" testid="server-form-port">
              <Input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} placeholder="443" data-testid="server-form-port-input" />
            </Field>
            <Field label="Protocol">
              <Select value={form.protocol} onValueChange={(v) => setForm({ ...form, protocol: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["https", "http", "tcp", "grpc", "amqp", "sftp", "mongodb", "postgres"].map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Environment">
              <Select value={form.environment} onValueChange={(v) => setForm({ ...form, environment: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["production", "staging", "dr", "dev"].map((p) => (
                    <SelectItem key={p} value={p}>{p}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Region">
              <Input value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} placeholder="us-east-1" />
            </Field>
            <Field label="Owner Email">
              <Input value={form.owner_email} onChange={(e) => setForm({ ...form, owner_email: e.target.value })} placeholder="ops@tennantco.com" />
            </Field>
            <div className="col-span-2">
              <Field label="Health URL (optional · used for /ping)">
                <Input value={form.health_url} onChange={(e) => setForm({ ...form, health_url: e.target.value })} placeholder="https://edi.tennantco.internal/healthz" data-testid="server-form-healthurl-input" />
              </Field>
            </div>
            <div className="col-span-2">
              <Field label="Notes">
                <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Owner team, SLA tier, secrets vault path, etc." />
              </Field>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDialogOpen(false)} data-testid="server-form-cancel">Cancel</Button>
            <Button onClick={submit} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="server-form-submit">
              {editingId ? "Save Changes" : "Register"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function Tile({ label, value, accent = "text-cyan-300" }) {
  return (
    <div className="p-3 rounded bg-white/[0.02] border border-white/5">
      <div className="text-[9px] font-mono uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`text-2xl font-display font-bold tabular-nums ${accent} mt-1`}>{value}</div>
    </div>
  );
}

function Field({ label, children, testid }) {
  return (
    <div data-testid={testid}>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 block">{label}</Label>
      {children}
    </div>
  );
}
