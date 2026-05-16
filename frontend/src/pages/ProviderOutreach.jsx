import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  Send, CheckCircle2, AlertCircle, Loader2, Eye, Mail, ExternalLink,
  RefreshCw, ListChecks, Filter, KeyRound,
} from "lucide-react";

const ORISEI_GOLD = "#C9A24A";
const ORISEI_NAVY = "#0E3A6B";

/**
 * Provider Outreach — launch-day automation.
 *
 * Lets the operator pick which providers (DAT, Truckstop, Resend, QB, factors,
 * insurance, FMCSA, etc.) need an intro email, customizes the recipient if the
 * canonical address is wrong, optionally appends a personal note, and bulk-
 * sends them through Resend in one click. Tracks sent/replied/closed status
 * so the launch checklist is one glance.
 */
export default function ProviderOutreach() {
  const [providers, setProviders] = useState([]);
  const [history, setHistory] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [overrides, setOverrides] = useState({});
  const [note, setNote] = useState(
    "We're targeting a v3.0 platform launch in the next 14 days. The faster you can send onboarding paperwork the better — happy to jump on a call.",
  );
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(null);

  const load = async () => {
    try {
      const [{ data: cat }, { data: hist }] = await Promise.all([
        api.get("/provider-outreach/catalog"),
        api.get("/provider-outreach/history"),
      ]);
      setProviders(cat.providers || []);
      setHistory(hist.items || []);
    } catch (e) {
      toast.error("Failed to load provider catalog");
    }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    if (filter === "all") return providers;
    if (filter === "missing-keys") return providers.filter((p) => !p.has_credentials);
    if (filter === "not-contacted") return providers.filter((p) => !p.last_sent_at);
    return providers.filter((p) => p.category === filter);
  }, [providers, filter]);

  const categories = useMemo(() => {
    const s = new Set(providers.map((p) => p.category));
    return Array.from(s);
  }, [providers]);

  const toggle = (id) => setSelected((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const selectAllVisible = () => setSelected(new Set(filtered.map((p) => p.id)));
  const selectMissingKeys = () =>
    setSelected(new Set(providers.filter((p) => !p.has_credentials).map((p) => p.id)));
  const clearSelection = () => setSelected(new Set());

  const send = async (dryRun = false) => {
    if (selected.size === 0) { toast.error("Select at least one provider"); return; }
    setBusy(true);
    try {
      const payload = {
        provider_ids: Array.from(selected),
        to_email_overrides: overrides,
        note_appendix: note || null,
        dry_run: dryRun,
      };
      const { data } = await api.post("/provider-outreach/send", payload);
      if (dryRun) {
        toast.success(`Dry-run rendered ${data.dry_run_count} email(s)`);
        if (data.results?.length) setPreview(data.results[0]);
      } else if (data.errors > 0) {
        toast.error(`Sent ${data.sent}/${data.total} · ${data.errors} error(s)`);
      } else {
        toast.success(`Sent ${data.sent}/${data.total} provider emails`);
        clearSelection();
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Send failed");
    } finally { setBusy(false); }
  };

  const updateStatus = async (outreachId, status) => {
    try {
      await api.put(`/provider-outreach/${outreachId}/status`, { status });
      toast.success(`Marked ${status}`);
      load();
    } catch (e) { toast.error("Status update failed"); }
  };

  const stats = useMemo(() => {
    const total = providers.length;
    const contacted = providers.filter((p) => !!p.last_sent_at).length;
    const withKeys = providers.filter((p) => p.has_credentials).length;
    const ready = providers.filter((p) => p.has_credentials && p.last_sent_at).length;
    return { total, contacted, withKeys, ready };
  }, [providers]);

  return (
    <>
      <Topbar
        title="Provider Outreach · Launch Day"
        subtitle="Bulk-email every API provider, factor, insurer, and regulator we need to fully operate the platform — track status in one glance."
      />
      <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="provider-outreach-stats">
          <StatCard label="Providers in catalog" value={stats.total} />
          <StatCard label="Already contacted" value={stats.contacted} accent="text-cyan-300" />
          <StatCard label="Have credentials" value={stats.withKeys} accent="text-amber-300" gold />
          <StatCard label="Launch-ready" value={stats.ready} accent="text-emerald-300" />
        </div>

        {/* Toolbar */}
        <Card className="hud-surface p-4">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Filter size={14} style={{ color: ORISEI_GOLD }} />
            <FilterPill active={filter === "all"} onClick={() => setFilter("all")} tid="filter-all">All</FilterPill>
            <FilterPill active={filter === "missing-keys"} onClick={() => setFilter("missing-keys")} tid="filter-missing">Missing keys</FilterPill>
            <FilterPill active={filter === "not-contacted"} onClick={() => setFilter("not-contacted")} tid="filter-uncontacted">Not contacted</FilterPill>
            {categories.map((c) => (
              <FilterPill key={c} active={filter === c} onClick={() => setFilter(c)} tid={`filter-${c.toLowerCase().replace(/\s+/g,'-')}`}>{c}</FilterPill>
            ))}
            <button onClick={load} className="ml-auto text-[11px] font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-300 inline-flex items-center gap-1">
              <RefreshCw size={11} /> Refresh
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono uppercase tracking-wider">
            <span className="text-slate-500">Quick selection:</span>
            <button onClick={selectAllVisible} className="text-slate-300 hover:text-amber-300" data-testid="select-visible">all visible</button>
            <span className="text-slate-700">·</span>
            <button onClick={selectMissingKeys} className="text-slate-300 hover:text-amber-300" data-testid="select-missing">missing keys</button>
            <span className="text-slate-700">·</span>
            <button onClick={clearSelection} className="text-slate-300 hover:text-red-300" data-testid="select-clear">clear</button>
            <span className="ml-auto text-slate-400">{selected.size} selected</span>
          </div>
        </Card>

        {/* Provider table */}
        <Card className="hud-surface p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-500 bg-white/[0.02]">
                <tr>
                  <th className="text-left px-3 py-2 w-8"></th>
                  <th className="text-left px-3 py-2">Provider</th>
                  <th className="text-left px-3 py-2">Category</th>
                  <th className="text-left px-3 py-2">What we need</th>
                  <th className="text-left px-3 py-2">Email</th>
                  <th className="text-left px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => {
                  const isSelected = selected.has(p.id);
                  const overrideEmail = overrides[p.id] ?? "";
                  return (
                    <tr key={p.id} className="border-t border-white/5 hover:bg-white/[0.03]"
                        data-testid={`provider-row-${p.id}`}>
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggle(p.id)}
                          className="accent-amber-400"
                          data-testid={`provider-select-${p.id}`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-200">{p.name}</div>
                        <a
                          href={p.signup_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[10px] font-mono text-slate-500 hover:text-cyan-300 inline-flex items-center gap-1"
                        >{p.signup_url} <ExternalLink size={9} /></a>
                      </td>
                      <td className="px-3 py-3 text-[11px] font-mono text-slate-400">{p.category}</td>
                      <td className="px-3 py-3 text-xs text-slate-300 max-w-md leading-snug">{p.what_we_need}</td>
                      <td className="px-3 py-3">
                        <Input
                          value={overrideEmail || p.default_email}
                          onChange={(e) =>
                            setOverrides((prev) => ({ ...prev, [p.id]: e.target.value }))
                          }
                          className="text-xs h-8 font-mono bg-slate-950 border-white/10"
                          data-testid={`provider-email-${p.id}`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-col gap-1">
                          {p.has_credentials ? (
                            <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30 text-[10px]">
                              <KeyRound size={9} className="mr-1" /> KEYS PRESENT
                            </Badge>
                          ) : (
                            <Badge className="bg-amber-500/15 text-amber-300 border-amber-500/30 text-[10px]">
                              <AlertCircle size={9} className="mr-1" /> NEED KEYS
                            </Badge>
                          )}
                          {p.last_sent_at ? (
                            <span className="text-[9px] font-mono text-slate-500">
                              {p.last_status?.toUpperCase()} · {new Date(p.last_sent_at).toLocaleDateString()}
                            </span>
                          ) : (
                            <span className="text-[9px] font-mono text-slate-600">— not contacted —</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">No providers match this filter.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Compose + Send */}
        <Card className="hud-surface p-5" data-testid="outreach-compose">
          <h3 className="font-display text-lg font-bold flex items-center gap-2 mb-3">
            <Mail size={16} style={{ color: ORISEI_GOLD }} /> Compose & Send
          </h3>
          <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Personal note appended to every email (optional)</Label>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className="bg-slate-950 border-white/10 text-sm mt-1"
            data-testid="outreach-note"
          />
          <div className="flex flex-wrap gap-2 mt-4">
            <Button
              onClick={() => send(true)}
              disabled={busy || selected.size === 0}
              className="bg-white/5 border border-white/10 text-slate-200"
              data-testid="outreach-dry-run"
            >
              {busy ? <Loader2 className="animate-spin" size={14} /> : <Eye size={13} className="mr-1.5" />}
              Dry Run · Preview
            </Button>
            <Button
              onClick={() => send(false)}
              disabled={busy || selected.size === 0}
              className="font-bold"
              style={{ background: ORISEI_GOLD, color: ORISEI_NAVY }}
              data-testid="outreach-send"
            >
              {busy ? <Loader2 className="animate-spin" size={14} /> : <Send size={13} className="mr-1.5" />}
              Send to {selected.size || "—"} provider{selected.size === 1 ? "" : "s"}
            </Button>
          </div>
        </Card>

        {/* History */}
        <Card className="hud-surface p-5" data-testid="outreach-history">
          <h3 className="font-display text-lg font-bold flex items-center gap-2 mb-3">
            <ListChecks size={16} style={{ color: ORISEI_GOLD }} /> Outreach History
          </h3>
          {history.length === 0 && (
            <div className="text-sm text-slate-500">No outreach sent yet.</div>
          )}
          <div className="space-y-2">
            {history.slice(0, 30).map((h) => (
              <div key={h.id} className="flex flex-wrap items-center gap-3 p-2.5 rounded border border-white/5 hover:border-white/15 text-xs" data-testid={`history-${h.id}`}>
                <div className="font-mono text-slate-500 w-24">{h.id.slice(0, 14)}</div>
                <div className="font-medium text-slate-200 min-w-[160px]">{h.provider_name}</div>
                <div className="text-slate-400">{h.to_email}</div>
                <div className="ml-auto flex items-center gap-2">
                  <span className="text-[10px] font-mono text-slate-500">{new Date(h.sent_at).toLocaleString()}</span>
                  <StatusPill status={h.status} />
                  {h.status === "sent" && (
                    <button
                      onClick={() => updateStatus(h.id, "replied")}
                      className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200"
                      data-testid={`mark-replied-${h.id}`}
                    >mark replied</button>
                  )}
                  {h.status === "replied" && (
                    <button
                      onClick={() => updateStatus(h.id, "closed")}
                      className="text-[10px] font-mono uppercase tracking-wider text-emerald-300 hover:text-emerald-200"
                      data-testid={`mark-closed-${h.id}`}
                    >mark closed</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Preview modal */}
        {preview && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setPreview(null)}>
            <div className="bg-[#0B0E14] border border-amber-500/40 rounded max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()} data-testid="preview-modal">
              <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-amber-400">Email preview · {preview.provider_name}</div>
                  <div className="font-mono text-xs text-slate-300 mt-0.5">to {preview.to_email}</div>
                </div>
                <button onClick={() => setPreview(null)} className="text-slate-400 hover:text-white">×</button>
              </div>
              <div className="overflow-y-auto p-4">
                {preview.html_preview ? (
                  <iframe srcDoc={preview.html_preview} className="w-full h-[70vh] bg-white rounded" title="email preview" />
                ) : (
                  <div className="text-sm text-slate-400">No preview body.</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function StatCard({ label, value, accent = "text-slate-100", gold = false }) {
  return (
    <Card className="hud-surface p-4" style={gold ? { borderColor: "rgba(201,162,74,0.25)" } : {}}>
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`font-display text-3xl font-black mt-1 ${accent}`}>{value}</div>
    </Card>
  );
}

function FilterPill({ active, onClick, children, tid }) {
  return (
    <button
      onClick={onClick}
      data-testid={tid}
      className="px-2.5 py-1 rounded text-[10px] font-mono uppercase tracking-wider border transition"
      style={
        active
          ? { background: ORISEI_GOLD, color: ORISEI_NAVY, borderColor: ORISEI_GOLD }
          : { borderColor: "rgba(255,255,255,0.1)", color: "#94a3b8" }
      }
    >
      {children}
    </button>
  );
}

function StatusPill({ status }) {
  const map = {
    sent: ["bg-cyan-500/20 text-cyan-300", CheckCircle2],
    replied: ["bg-amber-500/20 text-amber-300", CheckCircle2],
    closed: ["bg-emerald-500/20 text-emerald-300", CheckCircle2],
    error: ["bg-red-500/20 text-red-300", AlertCircle],
    dry_run: ["bg-slate-500/20 text-slate-300", Eye],
  };
  const [cls, Icon] = map[status] || ["bg-slate-500/20 text-slate-300", AlertCircle];
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono uppercase ${cls}`}>
      <Icon size={9} /> {status?.replace("_", " ")}
    </span>
  );
}
