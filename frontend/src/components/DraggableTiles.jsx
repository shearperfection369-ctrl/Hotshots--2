import React, { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { GripVertical, RotateCcw } from "lucide-react";

/**
 * useUserLayout — persistent per-user tile ordering for any page.
 *
 *   const { order, setOrder, reset, ready } = useUserLayout("dashboard", DEFAULT);
 *
 *   - On mount: fetches GET /api/user/layouts/{page_key}. If empty (new user),
 *     falls back to localStorage (for offline / pre-existing users), then to
 *     the supplied `defaultOrder`.
 *   - On every `setOrder` call: debounces a PUT to the same endpoint AND
 *     mirrors to localStorage as fast-path cache.
 *   - `reset()` deletes the server-side record and reverts to defaultOrder.
 *   - Reconciles unknown / missing ids on each load so schema changes don't
 *     break a user's saved layout.
 */
export function useUserLayout(pageKey, defaultOrder) {
  const storageKey = `tms-layout-${pageKey}`;
  const [order, setOrderState] = useState(defaultOrder);
  const [ready, setReady] = useState(false);
  const saveTimer = useRef(null);

  // Reconcile any saved array against the current defaultOrder — drop stale
  // ids, append any newly-added ids the user has never seen before.
  const reconcile = (candidate) => {
    if (!Array.isArray(candidate) || !candidate.length) return defaultOrder;
    const known = candidate.filter((id) => defaultOrder.includes(id));
    const missing = defaultOrder.filter((id) => !known.includes(id));
    return [...known, ...missing];
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // 1. Optimistic local cache (instant render, no flash of default)
      try {
        const cached = JSON.parse(localStorage.getItem(storageKey) || "null");
        if (Array.isArray(cached) && cached.length) {
          setOrderState(reconcile(cached));
        }
      } catch (e) { /* ignore */ }
      // 2. Authoritative server fetch
      try {
        const { data } = await api.get(`/user/layouts/${pageKey}`);
        if (cancelled) return;
        if (Array.isArray(data.order) && data.order.length) {
          const next = reconcile(data.order);
          setOrderState(next);
          try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch (e) { /* ignore */ }
        }
      } catch (e) { /* unauthenticated / network — local cache will do */ }
      finally { if (!cancelled) setReady(true); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey]);

  const setOrder = (next) => {
    const resolved = typeof next === "function" ? next(order) : next;
    setOrderState(resolved);
    try { localStorage.setItem(storageKey, JSON.stringify(resolved)); } catch (e) { /* ignore */ }
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      api.put(`/user/layouts/${pageKey}`, { order: resolved }).catch(() => { /* offline; localStorage retains */ });
    }, 400);
  };

  const reset = async () => {
    setOrderState(defaultOrder);
    try { localStorage.removeItem(storageKey); } catch (e) { /* ignore */ }
    try { await api.delete(`/user/layouts/${pageKey}`); } catch (e) { /* ignore */ }
  };

  return { order, setOrder, reset, ready };
}


/**
 * DraggableTiles — render a list of tiles in user-controlled order.
 *
 *   <DraggableTiles
 *     pageKey="trade-compliance"
 *     defaultOrder={["summary","incoterms","tariffs", ...]}
 *     tiles={{
 *       summary:   { label: "Overview",  render: () => <SummaryCard /> },
 *       incoterms: { label: "Incoterms", render: () => <IncotermsCard /> },
 *       ...
 *     }}
 *     gap="gap-5"
 *   />
 *
 *  - Each tile gets a small grip handle in the top-right that becomes visible
 *    on hover. Drag to reorder. Drop on any other tile to insert there.
 *  - Persists per-user via /api/user/layouts.
 *  - Renders a tiny "Reset Layout" pill at the very top of the list.
 */
export default function DraggableTiles({ pageKey, defaultOrder, tiles, gap = "gap-5", className = "" }) {
  const { order, setOrder, reset } = useUserLayout(pageKey, defaultOrder);
  const [dragId, setDragId] = useState(null);
  const [overId, setOverId] = useState(null);

  const reorder = (src, target) => {
    if (!src || src === target) return;
    setOrder((arr) => {
      const next = [...arr];
      const from = next.indexOf(src);
      const to = next.indexOf(target);
      if (from === -1 || to === -1) return arr;
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  const items = useMemo(
    () => order.map((id) => ({ id, ...(tiles[id] || {}) })).filter((t) => !!t.render),
    [order, tiles]
  );

  return (
    <div className={`flex flex-col ${gap} ${className}`} data-testid={`draggable-${pageKey}`}>
      <div className="flex items-center justify-end gap-2 -mb-2">
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">
          Drag any tile by its grip · layout saved per user
        </span>
        <button
          onClick={reset}
          data-testid={`reset-layout-${pageKey}`}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-cyan-500/30 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:bg-cyan-500/10"
        >
          <RotateCcw size={11} /> Reset Layout
        </button>
      </div>

      {items.map(({ id, label, render }) => {
        const isDragging = dragId === id;
        const isOver = overId === id && dragId && dragId !== id;
        return (
          <div
            key={id}
            data-testid={`tile-${pageKey}-${id}`}
            data-tile-id={id}
            onDragOver={(e) => { if (!dragId) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; if (overId !== id) setOverId(id); }}
            onDragLeave={() => { if (overId === id) setOverId(null); }}
            onDrop={(e) => {
              e.preventDefault();
              reorder(e.dataTransfer.getData("text/plain"), id);
              setDragId(null); setOverId(null);
            }}
            className={`relative group transition ${isDragging ? "opacity-50" : ""} ${isOver ? "ring-2 ring-cyan-400 rounded-lg" : ""}`}
          >
            <button
              type="button"
              draggable
              onDragStart={(e) => { e.dataTransfer.setData("text/plain", id); e.dataTransfer.effectAllowed = "move"; setDragId(id); }}
              onDragEnd={() => { setDragId(null); setOverId(null); }}
              data-testid={`drag-${pageKey}-${id}`}
              aria-label={`Drag ${label}`}
              className="absolute top-1.5 right-1.5 z-20 p-1.5 rounded bg-black/50 backdrop-blur border border-white/10 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/40 cursor-grab active:cursor-grabbing opacity-30 group-hover:opacity-100 transition"
            >
              <GripVertical size={12} />
            </button>
            {render()}
          </div>
        );
      })}
    </div>
  );
}
