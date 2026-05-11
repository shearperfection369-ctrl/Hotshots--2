import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Upload, FileText, Trash2, Download, Search, AlertTriangle, Calendar } from "lucide-react";
import { useAuth } from "../lib/auth";

export default function Vault() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canUpload = ["admin", "dispatcher", "auditor"].includes(user?.role);
  const [files, setFiles] = useState([]);
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("ALL");
  const [q, setQ] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ file: null, category: "Insurance COI", related_to: "", expires_at: "", notes: "" });

  const load = async () => {
    const { data } = await api.get("/vault/files");
    setFiles(data);
  };
  useEffect(() => {
    api.get("/vault/categories").then(({ data }) => setCategories(data.categories || []));
    load();
  }, []);

  const filtered = files.filter((f) => {
    if (category !== "ALL" && f.category !== category) return false;
    if (q) {
      const ql = q.toLowerCase();
      const hay = [f.filename, f.related_to, f.notes, f.category, f.uploaded_by_name].filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(ql)) return false;
    }
    return true;
  });

  const onUpload = async () => {
    if (!form.file) { toast.error("Pick a file first"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", form.file);
      fd.append("category", form.category);
      fd.append("related_to", form.related_to);
      if (form.expires_at) fd.append("expires_at", form.expires_at);
      fd.append("notes", form.notes);
      await api.post("/vault/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Uploaded ${form.file.name}`);
      setUploadOpen(false);
      setForm({ file: null, category: form.category, related_to: "", expires_at: "", notes: "" });
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (file_id, filename) => {
    if (!window.confirm(`Delete ${filename}? This cannot be undone.`)) return;
    try {
      await api.delete(`/vault/files/${file_id}`);
      toast.success(`Deleted ${filename}`);
      load();
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  const onDownload = (file_id, filename) => {
    const a = document.createElement("a");
    a.href = `${BACKEND_URL}/api/vault/files/${file_id}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const expiringSoon = (iso) => {
    if (!iso) return false;
    const d = new Date(iso); const today = new Date(); const diff = (d - today) / 86400000;
    return diff < 60 && diff > -3650;
  };
  const expired = (iso) => iso && new Date(iso) < new Date();

  const counts = {
    all: files.length,
    expiring: files.filter((f) => expiringSoon(f.expires_at) && !expired(f.expires_at)).length,
    expired: files.filter((f) => expired(f.expires_at)).length,
  };

  return (
    <>
      <Topbar title="Document Vault" subtitle={`${files.length} files · ${counts.expiring} expiring soon · ${counts.expired} expired`} />
      <div className="p-4 md:p-6 space-y-4">
        <Card className="hud-surface p-4 flex flex-wrap items-center gap-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Categories</div>
          <button onClick={() => setCategory("ALL")} className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${category === "ALL" ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>All ({counts.all})</button>
          {categories.map((c) => (
            <button key={c} onClick={() => setCategory(c)} data-testid={`vault-cat-${c}`}
              className={`px-3 py-1.5 rounded text-xs font-mono uppercase border ${category === c ? "bg-cyan-500 text-black border-cyan-400" : "border-white/10 text-slate-300 hover:border-cyan-400/40"}`}>{c}</button>
          ))}
          <div className="ml-auto relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search vault..." className="pl-9 w-72 bg-[#131821] border-white/10" data-testid="vault-search" />
          </div>
          {canUpload && (
            <Button onClick={() => setUploadOpen(true)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="vault-upload-btn">
              <Upload size={14} className="mr-2" /> Upload File
            </Button>
          )}
        </Card>

        <Card className="hud-surface overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider">
              <tr>
                <th className="text-left py-3 px-4">File</th>
                <th className="text-left py-3 px-4">Category</th>
                <th className="text-left py-3 px-4">Related To</th>
                <th className="text-left py-3 px-4">Uploaded</th>
                <th className="text-left py-3 px-4">Expires</th>
                <th className="text-right py-3 px-4">Size</th>
                <th className="text-center py-3 px-4 w-24">Actions</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {filtered.map((f) => (
                <tr key={f.file_id} className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`vault-row-${f.file_id}`}>
                  <td className="py-2.5 px-4 text-slate-200 flex items-center gap-2"><FileText size={13} className="text-cyan-400 shrink-0" /> <span className="truncate max-w-[280px]" title={f.filename}>{f.filename}</span></td>
                  <td className="py-2.5 px-4 text-cyan-300">{f.category}</td>
                  <td className="py-2.5 px-4 text-slate-400">{f.related_to || "—"}</td>
                  <td className="py-2.5 px-4 text-slate-400 text-xs">{(f.upload_date || "").slice(0, 10)}<div className="text-[10px] text-slate-600">{f.uploaded_by_name}</div></td>
                  <td className="py-2.5 px-4">
                    {f.expires_at ? (
                      <span className={`inline-flex items-center gap-1 text-xs ${expired(f.expires_at) ? "text-red-400" : expiringSoon(f.expires_at) ? "text-yellow-400" : "text-slate-400"}`}>
                        <Calendar size={11} /> {f.expires_at.slice(0, 10)}
                        {expired(f.expires_at) && <AlertTriangle size={11} className="text-red-400" />}
                      </span>
                    ) : <span className="text-slate-600">—</span>}
                  </td>
                  <td className="py-2.5 px-4 text-right text-slate-400 text-xs">{f.length ? (f.length / 1024).toFixed(1) + " KB" : "—"}</td>
                  <td className="py-2.5 px-4 text-center">
                    <div className="inline-flex gap-1">
                      <button onClick={() => onDownload(f.file_id, f.filename)} className="p-1.5 rounded text-cyan-300 hover:bg-cyan-500/10" data-testid={`vault-download-${f.file_id}`}><Download size={13} /></button>
                      {isAdmin && <button onClick={() => onDelete(f.file_id, f.filename)} className="p-1.5 rounded text-red-400 hover:bg-red-500/10" data-testid={`vault-delete-${f.file_id}`}><Trash2 size={13} /></button>}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (<tr><td colSpan={7} className="text-center py-12 text-slate-500">No files. {canUpload && "Click Upload File to add one."}</td></tr>)}
            </tbody>
          </table>
        </Card>
      </div>

      <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-lg" data-testid="vault-upload-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2"><Upload size={16} /> Upload to Vault</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">File</label>
              <input type="file" onChange={(e) => setForm({ ...form, file: e.target.files?.[0] || null })} className="block w-full mt-1 text-sm text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:bg-cyan-500 file:text-black file:font-bold file:cursor-pointer" data-testid="vault-file-input" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Category</label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10" data-testid="vault-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Related To (Carrier / Vendor / Shipment)</label>
              <Input value={form.related_to} onChange={(e) => setForm({ ...form, related_to: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" placeholder="XPO Logistics / SHP-12345 / Penn Battery" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Expires (optional)</label>
                <Input type="date" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Notes</label>
                <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" placeholder="Optional" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadOpen(false)}>Cancel</Button>
            <Button onClick={onUpload} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="vault-upload-confirm">
              {busy ? "Uploading..." : "Upload File"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
