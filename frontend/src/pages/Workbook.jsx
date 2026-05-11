import React, { useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import {
  Plus, FileSpreadsheet, Download, Pencil, Trash2, Search
} from "lucide-react";

const KIND_OPTIONS = [
  { value: "shipments_tl", label: "Shipments — TL" },
  { value: "shipments_ltl", label: "Shipments — LTL" },
  { value: "shipments_expedites", label: "Shipments — Expedites/Air" },
  { value: "shipments_crates", label: "Shipments — Crates/Flatbed" },
  { value: "shipments_seafreight", label: "Shipments — Seafreight/Ocean" },
  { value: "shipments_import", label: "Shipments — Imports" },
  { value: "quotes", label: "Quotes" },
  { value: "plant_hubs", label: "Plant Hubs" },
  { value: "carriers_primary", label: "Primary Carriers" },
  { value: "contacts_suppliers", label: "Supplier Contacts" },
  { value: "contacts_carriers", label: "Carrier Contacts" },
  { value: "info", label: "Info (Key-Value)" },
  { value: "volume_overview", label: "Volume Overview" },
];

export default function Workbook() {
  const [tabs, setTabs] = useState([]);
  const [activeTab, setActiveTab] = useState(null);
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [newTabName, setNewTabName] = useState("");
  const [newTabKind, setNewTabKind] = useState("info");
  const renameInputRef = useRef(null);

  const loadTabs = async () => {
    const { data } = await api.get("/workbook/tabs");
    setTabs(data);
    if (data.length && !activeTab) setActiveTab(data[0].tab_id);
  };

  const loadRows = async (tabId) => {
    if (!tabId) return;
    const { data } = await api.get(`/workbook/tabs/${tabId}/rows`);
    setData(data);
  };

  useEffect(() => { loadTabs(); }, []);
  useEffect(() => { if (activeTab) loadRows(activeTab); }, [activeTab]);

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const submitRename = async () => {
    if (!renamingId) return;
    const newName = renameValue.trim();
    if (!newName) { setRenamingId(null); return; }
    const oldTab = tabs.find((t) => t.tab_id === renamingId);
    if (oldTab && newName === oldTab.name) { setRenamingId(null); return; }
    try {
      await api.patch(`/workbook/tabs/${renamingId}`, { name: newName });
      toast.success(`Tab renamed to "${newName}"`);
      setRenamingId(null);
      await loadTabs();
    } catch { toast.error("Rename failed"); }
  };

  const deleteTab = async (tabId) => {
    if (!window.confirm("Delete this tab? This cannot be undone (default tabs will reappear on refresh if all are deleted).")) return;
    try {
      await api.delete(`/workbook/tabs/${tabId}`);
      toast.success("Tab deleted");
      if (activeTab === tabId) setActiveTab(null);
      await loadTabs();
    } catch { toast.error("Delete failed"); }
  };

  const addTab = async () => {
    if (!newTabName.trim()) { toast.error("Tab name required"); return; }
    try {
      const { data } = await api.post("/workbook/tabs", { name: newTabName.trim(), kind: newTabKind });
      toast.success(`Tab "${data.name}" created`);
      setAddOpen(false); setNewTabName(""); setNewTabKind("info");
      await loadTabs();
      setActiveTab(data.tab_id);
    } catch { toast.error("Failed to create tab"); }
  };

  const downloadTab = (tabId, name) => {
    const url = `${BACKEND_URL}/api/workbook/tabs/${tabId}/export.xlsx`;
    window.open(url, "_blank");
    toast.success(`Exporting "${name}"...`);
  };

  const downloadAll = () => {
    window.open(`${BACKEND_URL}/api/workbook/export-all.xlsx`, "_blank");
    toast.success("Exporting full workbook (all tabs)...");
  };

  const filteredRows = (data?.rows || []).filter((r) => {
    if (!q) return true;
    const ql = q.toLowerCase();
    return Object.values(r).some((v) => v != null && String(v).toLowerCase().includes(ql));
  });

  return (
    <>
      <Topbar
        title="Workbook"
        subtitle={`${tabs.length} tabs · Excel-style tracking · drop-in replacement for the legacy XLSX`}
      />
      <div className="p-4 md:p-6 space-y-4">

        {/* Tab strip + Add + Export-all */}
        <Card className="hud-surface p-3" data-testid="workbook-tabs">
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-1 overflow-x-auto pb-1">
              {tabs.map((t) => (
                <div key={t.tab_id} className="shrink-0 relative group">
                  {renamingId === t.tab_id ? (
                    <input
                      ref={renameInputRef}
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={submitRename}
                      onKeyDown={(e) => { if (e.key === "Enter") submitRename(); if (e.key === "Escape") setRenamingId(null); }}
                      data-testid={`rename-input-${t.tab_id}`}
                      className="bg-cyan-500/10 border border-cyan-500 text-cyan-300 rounded px-3 py-1.5 text-xs font-mono uppercase tracking-wider outline-none w-44"
                    />
                  ) : (
                    <button
                      onClick={() => setActiveTab(t.tab_id)}
                      onDoubleClick={() => { setRenamingId(t.tab_id); setRenameValue(t.name); }}
                      data-testid={`tab-${t.tab_id}`}
                      className={`px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition-all border ${
                        activeTab === t.tab_id
                          ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan"
                          : "bg-white/[0.02] text-slate-300 border-white/5 hover:border-cyan-500/40 hover:text-cyan-300"
                      }`}
                    >
                      {t.name}
                    </button>
                  )}
                  {activeTab === t.tab_id && renamingId !== t.tab_id && (
                    <div className="absolute -top-2 -right-2 hidden group-hover:flex gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); setRenamingId(t.tab_id); setRenameValue(t.name); }}
                        data-testid={`rename-btn-${t.tab_id}`}
                        className="w-5 h-5 rounded-full bg-cyan-500 text-black flex items-center justify-center hover:bg-cyan-400"
                        title="Rename"
                      ><Pencil size={9} /></button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteTab(t.tab_id); }}
                        className="w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-400"
                        title="Delete"
                      ><Trash2 size={9} /></button>
                    </div>
                  )}
                </div>
              ))}
              <Button
                onClick={() => setAddOpen(true)}
                data-testid="add-tab-btn"
                className="shrink-0 bg-white/5 hover:bg-white/10 text-slate-300 border border-white/10 px-2 py-1 h-auto text-xs"
              >
                <Plus size={12} className="mr-1" /> ADD TAB
              </Button>
            </div>
            <Button
              onClick={downloadAll}
              data-testid="export-all-btn"
              className="shrink-0 bg-emerald-500 hover:bg-emerald-400 text-black font-bold"
            >
              <FileSpreadsheet size={14} className="mr-1.5" /> EXPORT ALL → XLSX
            </Button>
          </div>
          <div className="text-[10px] font-mono text-slate-500 mt-2 px-1">
            <span className="text-cyan-400">TIP:</span> Double-click a tab to rename. Hover the active tab to delete.
          </div>
        </Card>

        {/* Active tab toolbar */}
        {data && (
          <Card className="hud-surface p-3">
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input
                  data-testid="workbook-search"
                  value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder={`Search in "${data.tab.name}"...`}
                  className="pl-9 bg-[#0B0E14] border-white/10"
                />
              </div>
              <Badge className="bg-white/[0.02] text-slate-300 border border-white/5 font-mono text-[10px]">
                {filteredRows.length} of {data.rows.length} rows
              </Badge>
              <Button
                onClick={() => downloadTab(data.tab.tab_id, data.tab.name)}
                data-testid="export-tab-btn"
                className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
              >
                <Download size={14} className="mr-1.5" /> EXPORT THIS TAB
              </Button>
            </div>
          </Card>
        )}

        {/* Data table */}
        <Card className="hud-surface overflow-hidden" data-testid="workbook-table">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider sticky top-0">
                <tr>
                  <th className="text-left py-3 px-3 w-12 text-slate-500">#</th>
                  {(data?.columns || []).map((c) => (
                    <th key={c.key} className="text-left py-3 px-3 whitespace-nowrap">{c.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {filteredRows.map((r, i) => (
                  <tr key={i} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-3 text-slate-600">{i + 1}</td>
                    {(data?.columns || []).map((c) => {
                      let v = r[c.key];
                      if (v == null) v = "—";
                      else if (typeof v === "number") v = Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
                      else if (typeof v === "string" && v.length > 22 && (v.match(/^\d{4}-\d{2}-\d{2}T/) || v.match(/^\d{4}-\d{2}-\d{2}/))) {
                        // shorten ISO timestamps to date only
                        try { v = new Date(v).toLocaleDateString(); } catch (_) {}
                      }
                      return (
                        <td key={c.key} className={`py-2.5 px-3 ${c.key === "carrier" || c.key === "name" ? "text-white" : "text-slate-300"} whitespace-nowrap`}>
                          {String(v)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {data && filteredRows.length === 0 && (
                  <tr><td colSpan={(data?.columns?.length || 0) + 1} className="text-center py-12 text-slate-500">No rows match your search.</td></tr>
                )}
                {!data && (
                  <tr><td colSpan={2} className="text-center py-12 text-slate-500">Select a tab above.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Add tab dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="bg-[#131821] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Add New Tab</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Tab Name</label>
              <Input
                data-testid="new-tab-name"
                value={newTabName} onChange={(e) => setNewTabName(e.target.value)}
                placeholder="e.g., 26 Quotes, Reefer Only, Mexico Routes..."
                className="mt-1 bg-[#0B0E14] border-white/10"
                autoFocus
              />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Tab Type</label>
              <Select value={newTabKind} onValueChange={setNewTabKind}>
                <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {KIND_OPTIONS.map((k) => <SelectItem key={k.value} value={k.value}>{k.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="text-[10px] font-mono text-slate-500 mt-1">Determines which columns appear.</div>
            </div>
            <Button data-testid="submit-new-tab" onClick={addTab} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">CREATE TAB</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
