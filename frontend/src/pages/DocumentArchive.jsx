import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Archive, FileDown, Eye, RefreshCw, ShieldCheck, History, Search } from "lucide-react";
import { toast } from "sonner";
import { api, getStoredToken, BACKEND_URL } from "@/lib/api";

/**
 * /document-archive — immutable legal-hold archive of every generated PDF.
 *
 * Every BOL / Invoice / Rate-Confirmation / Quote PDF rendered by the system
 * is auto-pushed into MongoDB GridFS (`doc_vault` bucket) with a SHA256
 * fingerprint, monotonic version, and 7-year retention. This page surfaces
 * the archive with filters + inline preview + re-render shortcut.
 */

const DOC_TYPE_LABEL = {
  BOL: "Bill of Lading",
  COMMERCIAL_INVOICE: "Commercial Invoice",
  PACKING_SLIP: "Packing Slip",
  WEIGHT_CERT: "Weight Cert",
  COO: "Certificate of Origin",
  RATE_CONFIRMATION: "Rate Confirmation",
  QUOTE: "Freight Quote",
  OTHER: "Other",
};

const DOC_TYPE_COLOR = {
  BOL: "amber",
  COMMERCIAL_INVOICE: "emerald",
  PACKING_SLIP: "sky",
  WEIGHT_CERT: "violet",
  COO: "rose",
  RATE_CONFIRMATION: "cyan",
  QUOTE: "teal",
  OTHER: "slate",
};

function fmtBytes(b) {
  if (!b) return "0 B";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export default function DocumentArchive() {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get("doc_id") || "";
  const initialRefId = searchParams.get("ref_id") || "";
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState("ALL");
  const [filterDocId, setFilterDocId] = useState(initialDocId);
  const [filterRefId, setFilterRefId] = useState(initialRefId);
  const [search, setSearch] = useState("");
  const [previewing, setPreviewing] = useState(null); // { url, filename }
  const [meta, setMeta] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (filterType !== "ALL") params.set("doc_type", filterType);
      if (filterDocId) params.set("doc_id", filterDocId);
      if (filterRefId) params.set("ref_id", filterRefId);
      const [listRes, statsRes] = await Promise.all([
        api.get(`/doc-vault?${params.toString()}`),
        api.get(`/doc-vault/stats`),
      ]);
      setItems(listRes.data.items || []);
      setStats(statsRes.data);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load document archive");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filterType, filterDocId, filterRefId]);

  const filtered = useMemo(() => {
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(i =>
      (i.doc_id || "").toLowerCase().includes(q) ||
      (i.archive_id || "").toLowerCase().includes(q) ||
      (i.ref_id || "").toLowerCase().includes(q) ||
      (i.filename || "").toLowerCase().includes(q) ||
      (i.sha256 || "").toLowerCase().includes(q));
  }, [items, search]);

  const preview = async (a) => {
    try {
      const r = await api.get(`/doc-vault/${a.archive_id}/file`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      setPreviewing({ url, filename: a.filename, archive_id: a.archive_id });
      const m = await api.get(`/doc-vault/${a.archive_id}`);
      setMeta(m.data);
    } catch (e) {
      toast.error("Preview failed");
    }
  };

  const reRender = async (a) => {
    try {
      const r = await api.post(`/doc-vault/${a.archive_id}/re-render`);
      const nextUrl = r.data.next_url;
      const full = `${BACKEND_URL}${nextUrl}`;
      // Hit the source generator — that endpoint will archive a new version
      const token = getStoredToken();
      const res = await fetch(full, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = a.filename.replace(".pdf", "_reissued.pdf");
      link.click();
      toast.success("Re-rendered & re-archived as new version");
      load();
    } catch (e) {
      toast.error("Re-render failed: " + e.message);
    }
  };

  const totalDocs = stats?.total_documents ?? 0;
  const totalBytes = (stats?.by_type || []).reduce((s, x) => s + (x.bytes || 0), 0);
  const oldest = stats?.oldest_at;

  return (
    <>
      <Topbar
        title="Document Archive"
        subtitle="Immutable legal-hold · every generated PDF auto-versioned · SHA256 fingerprinted · 7-year retention"
      />
      <div className="p-4 md:p-6 space-y-5">
        {/* Compliance banner */}
        <Card className="p-4 bg-gradient-to-br from-emerald-950/40 via-slate-950 to-slate-950 border-emerald-400/30">
          <div className="flex items-start gap-3">
            <ShieldCheck className="text-emerald-300 shrink-0" size={28} />
            <div className="flex-1">
              <div className="text-sm font-semibold text-emerald-200">
                FMCSA / DOT Document Retention — Compliant
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Every BOL, Rate Confirmation, Commercial Invoice, Packing Slip,
                Weight Certificate, COO and Freight Quote rendered by this TMS
                is automatically captured to an immutable MongoDB GridFS vault
                with a SHA256 fingerprint and a 7-year auto-expiry tag — exceeds
                49 CFR §379 (broker records, 3 yrs) and §390.31 (driver/vehicle
                records, 6 mo–3 yrs) by a comfortable margin.
              </div>
            </div>
          </div>
        </Card>

        {/* Stats strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Documents Archived" value={totalDocs.toLocaleString()} icon={Archive} accent="amber" testid="stat-total" />
          <StatCard label="Total Bytes" value={fmtBytes(totalBytes)} icon={FileDown} accent="cyan" testid="stat-bytes" />
          <StatCard label="Oldest Entry" value={oldest ? new Date(oldest).toLocaleDateString() : "—"} icon={History} accent="emerald" testid="stat-oldest" />
          <StatCard label="Retention Window" value={`${stats?.retention_years ?? 7} years`} icon={ShieldCheck} accent="violet" testid="stat-retention" />
        </div>

        {/* By-type breakdown */}
        {(stats?.by_type || []).length > 0 && (
          <Card className="p-4 bg-slate-950/60 border-white/10">
            <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-3">
              By document type
            </div>
            <div className="flex flex-wrap gap-2">
              {(stats.by_type || []).map(t => (
                <button key={t.doc_type}
                        type="button"
                        data-testid={`type-chip-${t.doc_type}`}
                        onClick={() => setFilterType(filterType === t.doc_type ? "ALL" : t.doc_type)}
                        className={`px-3 py-1.5 rounded-full text-xs font-mono uppercase tracking-widest border transition ${
                          filterType === t.doc_type
                            ? "bg-amber-500 text-slate-950 border-amber-300"
                            : "bg-slate-900 text-slate-300 border-white/10 hover:border-amber-400/40"
                        }`}>
                  {DOC_TYPE_LABEL[t.doc_type] || t.doc_type} · {t.count}
                </button>
              ))}
            </div>
          </Card>
        )}

        {/* Filters */}
        <Card className="p-3 bg-slate-950/60 border-white/10">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 flex-1 min-w-[260px]">
              <Search size={14} className="text-slate-500 ml-1" />
              <Input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search by doc id, archive id, sha256, filename, shipment ref…"
                data-testid="search-input"
                className="bg-slate-900 border-white/10 text-sm h-9"
              />
            </div>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-[200px] bg-slate-900 border-white/10 h-9 text-xs" data-testid="filter-type">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All types</SelectItem>
                {Object.entries(DOC_TYPE_LABEL).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              value={filterDocId}
              onChange={e => setFilterDocId(e.target.value)}
              placeholder="Doc ID filter…"
              data-testid="filter-doc-id"
              className="w-[200px] bg-slate-900 border-white/10 h-9 text-xs"
            />
            <Button size="sm" variant="outline" data-testid="refresh-btn"
                    onClick={load}
                    className="h-9 bg-slate-900 border-white/10 text-xs">
              <RefreshCw size={12} className="mr-1" /> Refresh
            </Button>
          </div>
        </Card>

        {/* Table */}
        <Card className="bg-slate-950/60 border-white/10 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 border-b border-white/5">
                <tr className="text-left text-[10px] text-slate-400 font-mono uppercase tracking-widest">
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Doc ID</th>
                  <th className="px-4 py-2">Version</th>
                  <th className="px-4 py-2">Ref / Shipment</th>
                  <th className="px-4 py-2">Captured</th>
                  <th className="px-4 py-2">Size</th>
                  <th className="px-4 py-2">SHA256</th>
                  <th className="px-4 py-2">By</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody data-testid="archive-table-body">
                {loading && (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-500 text-xs">Loading…</td></tr>
                )}
                {!loading && filtered.length === 0 && (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-500 text-xs">
                    No archived documents yet. Generate a BOL, Invoice, or Rate Confirmation — it will appear here automatically.
                  </td></tr>
                )}
                {filtered.map(a => {
                  const color = DOC_TYPE_COLOR[a.doc_type] || "slate";
                  return (
                    <tr key={a.archive_id}
                        data-testid={`row-${a.archive_id}`}
                        className="border-b border-white/5 hover:bg-slate-900/40">
                      <td className="px-4 py-3">
                        <Badge className={`bg-${color}-500/15 text-${color}-300 border border-${color}-400/40 text-[10px]`}>
                          {DOC_TYPE_LABEL[a.doc_type] || a.doc_type}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-200">{a.doc_id}</td>
                      <td className="px-4 py-3 font-mono text-xs text-amber-300">v{a.version}</td>
                      <td className="px-4 py-3 font-mono text-[11px] text-slate-400">{a.ref_id || "—"}</td>
                      <td className="px-4 py-3 text-xs text-slate-300">{fmtDate(a.created_at)}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{fmtBytes(a.size_bytes)}</td>
                      <td className="px-4 py-3 font-mono text-[10px] text-slate-500" title={a.sha256}>
                        {a.sha256 ? a.sha256.slice(0, 10) + "…" : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{a.created_by_name || "system"}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex gap-1">
                          <Button size="sm" variant="outline"
                                  data-testid={`preview-${a.archive_id}`}
                                  onClick={() => preview(a)}
                                  className="h-7 bg-slate-900 border-white/10 text-[11px]">
                            <Eye size={11} className="mr-1" /> View
                          </Button>
                          <a href={`${BACKEND_URL}/api/doc-vault/${a.archive_id}/file?download=true`}
                             data-testid={`download-${a.archive_id}`}
                             onClick={e => {
                               e.preventDefault();
                               const token = getStoredToken();
                               fetch(`${BACKEND_URL}/api/doc-vault/${a.archive_id}/file?download=true`, {
                                 headers: { Authorization: `Bearer ${token}` }
                               }).then(r => r.blob()).then(b => {
                                 const link = document.createElement("a");
                                 link.href = URL.createObjectURL(b);
                                 link.download = a.filename;
                                 link.click();
                               });
                             }}
                             className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-slate-300 bg-slate-900 border border-white/10 hover:border-amber-400/40 cursor-pointer">
                            <FileDown size={11} /> PDF
                          </a>
                          <Button size="sm"
                                  data-testid={`rerender-${a.archive_id}`}
                                  onClick={() => reRender(a)}
                                  className="h-7 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px]">
                            <RefreshCw size={11} className="mr-1" /> Re-issue
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Preview modal */}
      {previewing && (
        <div className="fixed inset-0 z-50 bg-black/90 grid place-items-center p-4"
             onClick={() => { URL.revokeObjectURL(previewing.url); setPreviewing(null); setMeta(null); }}
             data-testid="archive-preview-modal">
          <div className="relative w-full max-w-5xl h-[92vh] bg-slate-950 rounded shadow-2xl border border-amber-400/30 flex flex-col"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/10">
              <div className="text-xs font-mono text-amber-300 truncate">
                {previewing.filename}
                {meta && <span className="text-slate-500 ml-2">· v{meta.version} · sha256 {meta.sha256?.slice(0,12)}…</span>}
              </div>
              <button onClick={() => { URL.revokeObjectURL(previewing.url); setPreviewing(null); setMeta(null); }}
                      className="text-slate-400 hover:text-white text-xs font-mono">CLOSE ✕</button>
            </div>
            <iframe src={previewing.url} className="flex-1 w-full bg-white" title="archive preview" />
          </div>
        </div>
      )}
    </>
  );
}

const ACCENT_TXT = { amber: "text-amber-300", cyan: "text-cyan-300", emerald: "text-emerald-300", violet: "text-violet-300", slate: "text-slate-300" };
const ACCENT_BORDER = { amber: "border-amber-400/30", cyan: "border-cyan-400/30", emerald: "border-emerald-400/30", violet: "border-violet-400/30", slate: "border-white/10" };

function StatCard({ label, value, icon: Icon, accent = "amber", testid }) {
  return (
    <Card className={`p-4 bg-slate-950/60 border-2 ${ACCENT_BORDER[accent]}`} data-testid={testid}>
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400">{label}</div>
        <Icon className={ACCENT_TXT[accent]} size={16} />
      </div>
      <div className={`text-2xl font-semibold ${ACCENT_TXT[accent]} font-mono`}>{value}</div>
    </Card>
  );
}
