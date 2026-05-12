import React, { useEffect, useState, useRef, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Search, X, Loader2 } from "lucide-react";
import { api } from "../lib/api";

/**
 * GlobalSearch · omni-search bar that lives in the Topbar.
 *
 * Hits both:
 *   GET /api/search/global?q=…  — internal TMS records (shipments, bookings,
 *                                 BOLs, machines)
 *   GET /api/s4/search?q=…      — mocked S/4HANA cross-document search
 *                                 (POs, SOs, deliveries, invoices, materials)
 *
 * Press `/` anywhere to focus the box. Esc to close. Up/Down/Enter to navigate.
 */

const useDebounced = (value, delay) => {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return v;
};

export default function GlobalSearch() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState({ internal: [], s4: [] });
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const debouncedQ = useDebounced(q, 220);

  // Press "/" anywhere → focus search
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" &&
          document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Fire the searches
  useEffect(() => {
    if (debouncedQ.trim().length < 2) {
      setResults({ internal: [], s4: [] });
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.get(`/search/global?q=${encodeURIComponent(debouncedQ)}`),
      api.get(`/s4/search?q=${encodeURIComponent(debouncedQ)}`),
    ]).then(([a, b]) => {
      if (cancelled) return;
      setResults({
        internal: a.data.results || [],
        s4: b.data.results || [],
      });
    }).catch(() => {
      if (!cancelled) setResults({ internal: [], s4: [] });
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [debouncedQ]);

  const close = useCallback(() => setOpen(false), []);
  const totalCount = results.internal.length + results.s4.length;

  return (
    <div className="relative w-full max-w-md" data-testid="global-search">
      <div className="relative">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Search PO, BOL, invoice, part, SO… ( / )"
          data-testid="global-search-input"
          className="w-full pl-9 pr-9 py-1.5 rounded-lg bg-[#0B0E14]/80 border border-white/10 focus:border-cyan-500/50 text-xs font-mono text-slate-100 placeholder:text-slate-500 outline-none transition-colors"
        />
        {q && (
          <button
            onClick={() => { setQ(""); inputRef.current?.focus(); }}
            data-testid="global-search-clear"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-slate-500 hover:text-slate-200"
          >
            <X size={12} />
          </button>
        )}
        {loading && <Loader2 size={11} className="absolute right-8 top-1/2 -translate-y-1/2 text-cyan-400 animate-spin" />}
      </div>

      {open && q.trim().length >= 2 && (
        <>
          <div className="fixed inset-0 z-30" onClick={close} />
          <div
            data-testid="global-search-results"
            className="absolute z-40 left-0 right-0 mt-1.5 max-h-[480px] overflow-y-auto rounded-lg border border-cyan-500/20 bg-[#0B0E14] shadow-2xl shadow-cyan-500/10"
          >
            {/* Internal */}
            {results.internal.length > 0 && (
              <>
                <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-wider text-cyan-400 border-b border-white/5 sticky top-0 bg-[#0B0E14]">
                  TMS · {results.internal.length} result{results.internal.length === 1 ? "" : "s"}
                </div>
                {results.internal.map((r, i) => (
                  <Link
                    key={`int-${i}`}
                    to={r.link || "/"}
                    onClick={close}
                    data-testid={`global-search-result-${i}`}
                    className="block px-3 py-2 hover:bg-cyan-500/[0.07] border-b border-white/5"
                  >
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-mono uppercase bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shrink-0">
                        {r.badge || r.type}
                      </span>
                      <span className="text-xs font-mono text-cyan-100 truncate flex-1">{r.title}</span>
                      {r.status && (
                        <span className="text-[9px] font-mono text-slate-500 uppercase tracking-wider shrink-0">
                          {r.status}
                        </span>
                      )}
                    </div>
                    {r.subtitle && (
                      <div className="text-[10px] font-mono text-slate-400 mt-0.5 ml-12 truncate">{r.subtitle}</div>
                    )}
                  </Link>
                ))}
              </>
            )}
            {/* S/4 */}
            {results.s4.length > 0 && (
              <>
                <div className="px-3 py-1.5 text-[9px] font-mono uppercase tracking-wider text-orange-300 border-b border-white/5 sticky top-0 bg-[#0B0E14]">
                  SAP S/4HANA · {results.s4.length} result{results.s4.length === 1 ? "" : "s"} (opens in new tab)
                </div>
                {results.s4.map((r, i) => (
                  <a
                    key={`s4-${i}`}
                    href={r.url}
                    target="_blank" rel="noreferrer"
                    onClick={close}
                    data-testid={`s4-search-result-${i}`}
                    className="block px-3 py-2 hover:bg-orange-500/[0.07] border-b border-white/5"
                  >
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded text-[8px] font-mono uppercase bg-orange-500/15 text-orange-300 border border-orange-500/30 shrink-0">
                        {r.badge}
                      </span>
                      <span className="text-xs font-mono text-orange-100 truncate flex-1">{r.doc_number}</span>
                      <span className="text-[9px] font-mono text-slate-500 uppercase tracking-wider shrink-0">
                        {r.label}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-slate-400 mt-0.5 ml-12 truncate">{r.description}</div>
                  </a>
                ))}
              </>
            )}
            {totalCount === 0 && !loading && (
              <div className="p-6 text-center text-xs font-mono text-slate-500">
                No matches for <span className="text-cyan-300">"{q}"</span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
