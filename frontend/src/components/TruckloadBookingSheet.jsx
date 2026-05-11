import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { toast } from "sonner";
import { Plus, Trash2, Search, Save, RadioTower, GripVertical } from "lucide-react";

const POLL_INTERVAL_MS = 3500; // background poll cadence for real-time updates

/**
 * Truckload Booking Sheet — fully editable spreadsheet view.
 *
 *   - Click any cell to edit. Tab/Enter saves and moves to the next cell.
 *   - Auto-saves to backend on blur. Toast appears only on errors to avoid noise.
 *   - Polls /version every 3.5s; refetches the full list only when the
 *     server-side revision counter changes (a colleague's edit committed).
 *   - Adding a row instantly inserts a blank row at the top and persists it.
 *   - Deleting a row prompts for confirm.
 *   - Free-text search filters across all visible cells.
 *
 * Column order is driven by the backend's TRUCKLOAD_BOOKING_COLUMNS list, but
 * we still respect the same per-tab drag-reorder localStorage map used by
 * other Workbook tabs (passed in via `orderedColumns`).
 */
export default function TruckloadBookingSheet({
  orderedColumns,
  reorderCol,
  dragColKey, setDragColKey,
  overColKey, setOverColKey,
}) {
  const [rows, setRows] = useState([]);
  const [columns, setColumns] = useState([]);
  const [version, setVersion] = useState(0);
  const [lastEditor, setLastEditor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState(null); // { rowId, key }
  const [busyRows, setBusyRows] = useState(new Set());
  const pollRef = useRef(null);
  const editValueRef = useRef("");

  const cols = useMemo(() => {
    // If the caller passed a reordered list (from the drag-drop layer), use it.
    if (!orderedColumns?.length) return columns;
    const byKey = Object.fromEntries(columns.map((c) => [c.key, c]));
    return orderedColumns.map((c) => byKey[c.key] || c).filter(Boolean);
  }, [orderedColumns, columns]);

  // ---- Load + poll ----
  const fetchAll = async () => {
    try {
      const { data } = await api.get("/workbook/truckload-bookings");
      setRows(data.rows || []);
      setColumns(data.columns || []);
      setVersion(data.version || 0);
      setLastEditor(data.last_editor || null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  useEffect(() => {
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.get("/workbook/truckload-bookings/version");
        if ((data.version || 0) > version) {
          await fetchAll();
        }
      } catch (e) { /* network blip, try again */ }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(pollRef.current);
  }, [version]);

  // ---- Filtered rows for free-text search ----
  const filtered = useMemo(() => {
    if (!q) return rows;
    const ql = q.toLowerCase();
    return rows.filter((r) =>
      Object.values(r).some((v) => v != null && String(v).toLowerCase().includes(ql))
    );
  }, [rows, q]);

  // ---- Mutations ----
  const startEdit = (rowId, key, current) => {
    setEditing({ rowId, key });
    editValueRef.current = current == null ? "" : String(current);
  };

  const commitEdit = async () => {
    if (!editing) return;
    const { rowId, key } = editing;
    const newVal = editValueRef.current;
    const prev = rows.find((r) => r.id === rowId)?.[key] ?? null;
    setEditing(null);
    if (String(prev ?? "") === newVal) return; // nothing changed
    // Optimistic update
    setRows((rs) => rs.map((r) => (r.id === rowId ? { ...r, [key]: newVal || null } : r)));
    setBusyRows((s) => new Set(s).add(rowId));
    try {
      const { data } = await api.patch(`/workbook/truckload-bookings/${rowId}`, { data: { [key]: newVal } });
      if (data.row) setRows((rs) => rs.map((r) => (r.id === rowId ? data.row : r)));
      if (data.version) setVersion(data.version);
      if (data.auto_onboarding_id) {
        toast.success(`New carrier sent to onboarding`, {
          description: `${data.auto_onboarding_id} · status: in_review · compliance team will gather W-9 + COI`,
        });
      }
    } catch (e) {
      toast.error("Save failed — reverting");
      fetchAll();
    } finally {
      setBusyRows((s) => { const ns = new Set(s); ns.delete(rowId); return ns; });
    }
  };

  const addRow = async () => {
    try {
      const { data } = await api.post("/workbook/truckload-bookings", {
        data: { date: new Date().toISOString().slice(0, 10), status: "Quoted" },
      });
      setRows((rs) => [data.row, ...rs]);
      if (data.version) setVersion(data.version);
      toast.success(`Booked ${data.row.id}`);
    } catch (e) {
      toast.error("Could not add row");
    }
  };

  const deleteRow = async (rowId) => {
    if (!window.confirm(`Delete booking ${rowId}? This cannot be undone.`)) return;
    setRows((rs) => rs.filter((r) => r.id !== rowId));
    try {
      const { data } = await api.delete(`/workbook/truckload-bookings/${rowId}`);
      if (data.version) setVersion(data.version);
      toast.success("Booking deleted");
    } catch (e) {
      toast.error("Delete failed — reloading");
      fetchAll();
    }
  };

  return (
    <Card className="hud-surface overflow-hidden" data-testid="truckload-booking-sheet">
      {/* Toolbar */}
      <div className="px-4 py-3 border-b border-white/5 flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-[220px] relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <Input
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search by BOL #, PO #, carrier, status…"
            data-testid="tlb-search"
            className="pl-9 bg-[#0B0E14] border-white/10 font-mono text-xs"
          />
        </div>
        <Badge className="bg-white/[0.02] text-slate-300 border border-white/5 font-mono text-[10px]">
          {filtered.length} of {rows.length} loads
        </Badge>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-emerald-500/30 text-[10px] font-mono uppercase tracking-wider text-emerald-300" data-testid="tlb-live-indicator">
          <RadioTower size={10} className="animate-pulse" />
          Live · rev {version}
          {lastEditor ? <span className="text-slate-500"> · last by {lastEditor}</span> : null}
        </div>
        <Button onClick={addRow} data-testid="tlb-add-row" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
          <Plus size={14} className="mr-1" /> ADD LOAD
        </Button>
      </div>

      {/* Editable spreadsheet */}
      <div className="overflow-x-auto max-h-[68vh] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0B0E14] text-[10px] font-mono text-cyan-400 uppercase tracking-wider sticky top-0 z-10">
            <tr>
              <th className="text-left py-3 px-3 w-10 text-slate-500">#</th>
              {cols.map((c) => {
                const isDragging = dragColKey === c.key;
                const isOver = overColKey === c.key && dragColKey && dragColKey !== c.key;
                return (
                  <th
                    key={c.key}
                    data-testid={`tlb-col-header-${c.key}`}
                    className={`text-left py-3 px-3 whitespace-nowrap transition-colors ${isOver ? "bg-cyan-500/15" : ""} ${isDragging ? "opacity-50" : ""}`}
                    onDragOver={(e) => { if (!dragColKey) return; e.preventDefault(); if (overColKey !== c.key) setOverColKey(c.key); }}
                    onDragLeave={() => { if (overColKey === c.key) setOverColKey(null); }}
                    onDrop={(e) => { e.preventDefault(); reorderCol(e.dataTransfer.getData("text/plain"), c.key); setDragColKey(null); setOverColKey(null); }}
                  >
                    <span
                      draggable
                      onDragStart={(e) => { e.dataTransfer.setData("text/plain", c.key); e.dataTransfer.effectAllowed = "move"; setDragColKey(c.key); }}
                      onDragEnd={() => { setDragColKey(null); setOverColKey(null); }}
                      data-testid={`tlb-col-drag-${c.key}`}
                      className="inline-flex items-center gap-1 cursor-grab active:cursor-grabbing select-none hover:text-cyan-300"
                      title="Drag to reorder"
                    ><GripVertical size={10} className="opacity-30" /> {c.label}</span>
                  </th>
                );
              })}
              <th className="text-center py-3 px-3 w-10 text-slate-500">⋯</th>
            </tr>
          </thead>
          <tbody className="font-mono">
            {filtered.map((r, idx) => (
              <tr
                key={r.id}
                data-testid={`tlb-row-${r.id}`}
                className={`border-t border-white/5 hover:bg-white/[0.02] ${busyRows.has(r.id) ? "bg-cyan-500/[0.03]" : ""}`}
              >
                <td className="py-2 px-3 text-slate-600">{idx + 1}</td>
                {cols.map((c) => (
                  <EditableCell
                    key={c.key}
                    rowId={r.id}
                    column={c}
                    value={r[c.key]}
                    isEditing={editing?.rowId === r.id && editing?.key === c.key}
                    onStart={() => startEdit(r.id, c.key, r[c.key])}
                    onCommit={commitEdit}
                    onCancel={() => setEditing(null)}
                    onChange={(v) => { editValueRef.current = v; }}
                  />
                ))}
                <td className="py-1 px-2 text-center">
                  <button
                    onClick={() => deleteRow(r.id)}
                    data-testid={`tlb-delete-${r.id}`}
                    title="Delete row"
                    className="p-1 rounded text-red-400 hover:bg-red-500/10 opacity-40 hover:opacity-100 transition"
                  ><Trash2 size={12} /></button>
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={cols.length + 2} className="text-center py-12 text-slate-500">
                  <div className="mb-2">No truckload bookings yet.</div>
                  <Button onClick={addRow} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
                    <Plus size={14} className="mr-1" /> ADD YOUR FIRST LOAD
                  </Button>
                </td>
              </tr>
            )}
            {loading && (
              <tr><td colSpan={cols.length + 2} className="text-center py-10 text-slate-500">Loading bookings…</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="text-[10px] font-mono text-slate-500 px-4 py-2 border-t border-white/5">
        <span className="text-cyan-400">TIP:</span> Click any cell to edit · Tab/Enter saves · auto-syncs every {Math.round(POLL_INTERVAL_MS / 1000)}s for the team
      </div>
    </Card>
  );
}

function EditableCell({ rowId, column, value, isEditing, onStart, onCommit, onCancel, onChange }) {
  const inputRef = useRef(null);
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      try { inputRef.current.select?.(); } catch (e) { /* select() not on all input types */ }
    }
  }, [isEditing]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onCommit(); }
    else if (e.key === "Tab") { onCommit(); } // let browser handle moving focus
    else if (e.key === "Escape") { e.preventDefault(); onCancel(); }
  };

  const renderEditor = () => {
    const common = {
      ref: inputRef,
      defaultValue: value == null ? "" : value,
      onChange: (e) => onChange(e.target.value),
      onBlur: onCommit,
      onKeyDown: handleKey,
      "data-testid": `tlb-input-${column.key}-${rowId}`,
      className: "w-full bg-[#0B0E14] border border-cyan-500 rounded px-2 py-1 text-xs font-mono text-white outline-none",
    };
    if (column.type === "select") {
      return (
        <select {...common}>
          {(column.options || []).map((opt) => <option key={opt} value={opt}>{opt || "—"}</option>)}
        </select>
      );
    }
    if (column.type === "combo") {
      // Datalist combobox: free-text typing + dropdown suggestions of
      // currently-onboarded carriers. Dispatchers can pick an approved
      // carrier OR type a brand-new name (then onboard them later).
      const listId = `tlb-list-${column.key}-${rowId}`;
      return (
        <>
          <input {...common} type="text" list={listId} placeholder="Pick or type carrier…" autoComplete="off" />
          <datalist id={listId}>
            {(column.options || []).filter(Boolean).map((opt) => (
              <option key={opt} value={opt} />
            ))}
          </datalist>
        </>
      );
    }
    if (column.type === "textarea") {
      return <textarea {...common} rows={2} />;
    }
    if (column.type === "date") {
      return <input {...common} type="date" />;
    }
    if (column.type === "number") {
      return <input {...common} type="number" step="any" />;
    }
    return <input {...common} type="text" />;
  };

  const displayValue = () => {
    if (value == null || value === "") return <span className="text-slate-700">—</span>;
    if (column.type === "number" && typeof value === "number") {
      return <span className="text-white">{Number(value).toLocaleString()}</span>;
    }
    return <span className={column.key === "carrier" || column.key === "bol_no" ? "text-cyan-300" : "text-slate-200"}>{value}</span>;
  };

  return (
    <td
      onClick={!isEditing ? onStart : undefined}
      data-testid={`tlb-cell-${column.key}-${rowId}`}
      className={`py-1.5 px-3 whitespace-nowrap cursor-text min-w-[120px] ${isEditing ? "p-0.5" : "hover:bg-white/[0.03]"}`}
    >
      {isEditing ? renderEditor() : displayValue()}
    </td>
  );
}
