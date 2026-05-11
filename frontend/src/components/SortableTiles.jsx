import React, { useEffect, useState } from "react";
import { GripVertical, RotateCcw } from "lucide-react";

/**
 * SortableTiles — minimal HTML5 drag-and-drop list, vertical.
 *
 *  Props:
 *    storageKey       localStorage key for persisting order
 *    defaultOrder     initial array of tile ids
 *    tiles            { [id]: { label, render: () => JSX } }
 *
 *  Behavior:
 *    - Tiles render in current `order` state.
 *    - Drag a tile by its grip handle to reorder.
 *    - "Reset Layout" button restores `defaultOrder`.
 *    - Order persists across reloads via localStorage.
 *    - Hidden tile ids (ids in defaultOrder but missing from tiles map) are skipped gracefully.
 */
export default function SortableTiles({ storageKey, defaultOrder, tiles }) {
  const [order, setOrder] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (Array.isArray(saved) && saved.every((s) => typeof s === "string")) {
        // Merge: drop unknown ids, append any new ids missing from saved.
        const known = saved.filter((id) => defaultOrder.includes(id));
        const missing = defaultOrder.filter((id) => !known.includes(id));
        return [...known, ...missing];
      }
    } catch (e) { /* ignore */ }
    return defaultOrder;
  });
  const [dragId, setDragId] = useState(null);
  const [overId, setOverId] = useState(null);

  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(order)); } catch (e) { /* ignore */ }
  }, [order, storageKey]);

  const onDragStart = (id) => (e) => {
    e.dataTransfer.setData("text/plain", id);
    e.dataTransfer.effectAllowed = "move";
    setDragId(id);
  };
  const onDragOver = (id) => (e) => {
    e.preventDefault();
    if (id !== overId) setOverId(id);
  };
  const onDragLeave = () => setOverId(null);
  const onDrop = (targetId) => (e) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData("text/plain");
    setDragId(null); setOverId(null);
    if (!sourceId || sourceId === targetId) return;
    const next = [...order];
    const from = next.indexOf(sourceId);
    const to = next.indexOf(targetId);
    if (from === -1 || to === -1) return;
    next.splice(from, 1);
    next.splice(to, 0, sourceId);
    setOrder(next);
  };
  const onDragEnd = () => { setDragId(null); setOverId(null); };

  const reset = () => setOrder(defaultOrder);

  return (
    <div className="space-y-5" data-testid="sortable-tiles">
      <div className="flex items-center justify-end gap-2">
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
          Drag tiles to rearrange · order saves automatically
        </span>
        <button
          onClick={reset}
          data-testid="reset-tile-layout"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-cyan-500/30 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:bg-cyan-500/10"
        >
          <RotateCcw size={11} /> Reset Layout
        </button>
      </div>

      {order.map((id) => {
        const tile = tiles[id];
        if (!tile) return null;
        const isDragging = dragId === id;
        const isOver = overId === id && dragId && dragId !== id;
        return (
          <div
            key={id}
            data-testid={`tile-${id}`}
            draggable
            onDragStart={onDragStart(id)}
            onDragOver={onDragOver(id)}
            onDragLeave={onDragLeave}
            onDrop={onDrop(id)}
            onDragEnd={onDragEnd}
            className={`relative transition-all ${isDragging ? "opacity-40" : ""} ${isOver ? "ring-2 ring-cyan-400 ring-offset-2 ring-offset-[#0B0E14]" : ""}`}
          >
            {/* Grip handle overlay */}
            <button
              type="button"
              aria-label={`Drag ${tile.label}`}
              data-testid={`drag-${id}`}
              className="absolute top-2 right-2 z-10 p-1.5 rounded bg-black/40 backdrop-blur-sm border border-white/10 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/40 cursor-grab active:cursor-grabbing opacity-60 hover:opacity-100 transition"
            >
              <GripVertical size={14} />
            </button>
            {tile.render()}
          </div>
        );
      })}
    </div>
  );
}
