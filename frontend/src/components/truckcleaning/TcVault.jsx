import React, { useCallback, useEffect, useRef, useState } from "react";
import { Card } from "../ui/card";
import { FolderOpen, Upload, Download, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");

export const TcVault = ({ clients }) => {
  const [files, setFiles] = useState([]);
  const [cats, setCats] = useState([]);
  const [filter, setFilter] = useState("");
  const [form, setForm] = useState({ category: "Other", client_id: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const [f, c] = await Promise.all([
        api.get("/truck-cleaning/vault/files", { params: filter ? { category: filter } : {} }),
        api.get("/truck-cleaning/vault/categories"),
      ]);
      setFiles(f.data.files); setCats(c.data.categories);
    } catch (_) {}
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const upload = async (e) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.error("Choose a file first"); return; }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("category", form.category);
    fd.append("client_id", form.client_id);
    fd.append("notes", form.notes);
    setBusy(true);
    try {
      await api.post("/truck-cleaning/vault/upload", fd);
      toast.success("Document stored");
      fileRef.current.value = ""; setForm((f) => ({ ...f, notes: "" }));
      load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  const download = async (f) => {
    try {
      const r = await api.get(`/truck-cleaning/vault/files/${f.file_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = f.filename; a.click(); URL.revokeObjectURL(url);
    } catch (_) { toast.error("Download failed"); }
  };

  const del = async (f) => {
    try { await api.delete(`/truck-cleaning/vault/files/${f.file_id}`); toast.success("Deleted"); load(); }
    catch (e2) { toast.error(errTxt(e2)); }
  };

  return (
    <div className="space-y-4" data-testid="tc-vault">
      <form onSubmit={upload} className="p-4 rounded-xl border border-white/10 bg-slate-950/70 flex flex-wrap gap-2 items-center" data-testid="tc-vault-upload-form">
        <FolderOpen className="text-amber-400" size={18} />
        <input type="file" ref={fileRef} data-testid="tc-vault-file-input"
               className="text-xs text-slate-400 file:mr-2 file:px-3 file:py-1.5 file:rounded-full file:border-0 file:bg-amber-500 file:text-black file:font-bold file:text-xs" />
        <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} data-testid="tc-vault-category-select"
                className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs">
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} data-testid="tc-vault-client-select"
                className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2 text-xs">
          <option value="">General (no client)</option>
          {clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.company}</option>)}
        </select>
        <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Notes"
               data-testid="tc-vault-notes-input" className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs flex-1 min-w-[140px]" />
        <button type="submit" disabled={busy} data-testid="tc-vault-upload-btn"
                className="h-9 px-4 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5 disabled:opacity-60">
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />} Store
        </button>
      </form>
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => setFilter("")} className={`px-3 py-1 rounded-full text-[10px] font-mono border ${!filter ? "border-amber-400 text-amber-300" : "border-white/15 text-slate-500"}`}>ALL</button>
        {cats.map((c) => (
          <button key={c} onClick={() => setFilter(c)} data-testid={`tc-vault-filter-${c.replace(/[^a-z]/gi, "")}`}
                  className={`px-3 py-1 rounded-full text-[10px] font-mono border ${filter === c ? "border-amber-400 text-amber-300" : "border-white/15 text-slate-500"}`}>{c}</button>
        ))}
      </div>
      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Document</th><th className="p-3">Category</th><th className="p-3">Client</th><th className="p-3">Size</th><th className="p-3">Stored</th><th className="p-3" /></tr></thead>
          <tbody>
            {files.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-slate-600 text-xs font-mono">No documents yet — upload COIs, agreements, photos, receipts…</td></tr>}
            {files.map((f) => (
              <tr key={f.file_id} className="border-b border-white/5" data-testid={`tc-vault-row-${f.file_id}`}>
                <td className="p-3"><div className="font-semibold text-white text-xs">{f.filename}</div>{f.notes && <div className="text-[10px] text-slate-500">{f.notes}</div>}</td>
                <td className="p-3 text-[11px] text-cyan-300 font-mono">{f.category}</td>
                <td className="p-3 text-xs text-slate-400">{f.company || "—"}</td>
                <td className="p-3 text-[11px] text-slate-500 tabular-nums">{f.length ? `${(f.length / 1024).toFixed(0)} KB` : "—"}</td>
                <td className="p-3 text-[11px] text-slate-500">{(f.uploaded_at || "").slice(0, 10)}</td>
                <td className="p-3 flex gap-2">
                  <button onClick={() => download(f)} data-testid={`tc-vault-download-${f.file_id}`} className="text-amber-400 hover:text-amber-300"><Download size={14} /></button>
                  <button onClick={() => del(f)} data-testid={`tc-vault-delete-${f.file_id}`} className="text-slate-600 hover:text-red-400"><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};
