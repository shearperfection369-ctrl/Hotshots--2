import React, { useEffect, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Truck, Check, History } from "lucide-react";
import { api } from "@/lib/api";

/**
 * <CarrierCombobox value={name} onChange={fn} onSelect={(carrier) => ...} />
 *
 * Smart carrier picker that pulls the live carrier directory from
 * `/api/autocomplete/carriers/directory` (booked carriers + curated big-board
 * list). When the user selects a known carrier, `onSelect` fires with the full
 * record `{ name, mc, dot, contact_email, contact_phone, ... }` so callers can
 * auto-populate adjacent fields (MC #, contact email).
 *
 * Props:
 *   - value       : current text value (string)
 *   - onChange    : (text) => void
 *   - onSelect    : (record) => void   // optional, fires when user picks a row
 *   - placeholder : string
 *   - testid      : data-testid for the input
 *   - className   : extra classes on input
 */
export function CarrierCombobox({
  value,
  onChange,
  onSelect,
  placeholder = "Start typing carrier name…",
  testid = "carrier-combobox",
  className = "",
}) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);
  const wrap = useRef(null);
  const debounce = useRef(null);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      api
        .get(`/autocomplete/carriers/directory?q=${encodeURIComponent(value || "")}&limit=40`)
        .then((r) => setItems(r.data?.items || []))
        .catch(() => setItems([]));
    }, 200);
    return () => debounce.current && clearTimeout(debounce.current);
  }, [value]);

  // Close on outside click
  useEffect(() => {
    const onDoc = (e) => {
      if (wrap.current && !wrap.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const filtered = useMemo(() => items.slice(0, 12), [items]);

  const choose = (rec) => {
    onChange?.(rec.name);
    onSelect?.(rec);
    setOpen(false);
  };

  const onKey = (e) => {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi((h) => Math.min(filtered.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter" && hi >= 0 && filtered[hi]) {
      e.preventDefault();
      choose(filtered[hi]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={wrap} className="relative" data-testid={`${testid}-wrap`}>
      <Input
        value={value || ""}
        onChange={(e) => {
          onChange?.(e.target.value);
          setOpen(true);
          setHi(-1);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        placeholder={placeholder}
        data-testid={testid}
        autoComplete="off"
        className={className}
      />
      {open && filtered.length > 0 && (
        <div
          className="absolute z-50 left-0 right-0 mt-1 max-h-72 overflow-y-auto rounded-md border border-cyan-500/30 bg-[#0B0E14] shadow-xl"
          data-testid={`${testid}-dropdown`}
        >
          {filtered.map((c, i) => (
            <button
              key={`${c.name}-${i}`}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(c)}
              onMouseEnter={() => setHi(i)}
              data-testid={`${testid}-item-${i}`}
              className={`w-full text-left px-3 py-2 flex items-start gap-2.5 border-b border-white/5 last:border-b-0 transition-colors ${
                hi === i
                  ? "bg-cyan-500/10 text-cyan-100"
                  : "hover:bg-cyan-500/5 text-slate-200"
              }`}
            >
              <Truck size={13} className="text-cyan-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {c.name}
                  {c.mc && (
                    <span className="ml-2 font-mono text-[10px] text-cyan-300">
                      {c.mc}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-slate-500 font-mono uppercase tracking-wider flex items-center gap-2 mt-0.5">
                  {c.source === "booking" && (
                    <span className="text-emerald-400 inline-flex items-center gap-1">
                      <History size={9} /> {c.use_count} loads
                    </span>
                  )}
                  {c.source === "rate-con" && (
                    <span className="text-amber-400">rate-con only</span>
                  )}
                  {c.source === "curated" && (
                    <span className="text-slate-500">big board</span>
                  )}
                  {c.contact_email && (
                    <span className="text-slate-400 normal-case tracking-normal">
                      · {c.contact_email}
                    </span>
                  )}
                </div>
              </div>
              {value && value.toLowerCase() === (c.name || "").toLowerCase() && (
                <Check size={13} className="text-cyan-300 mt-1" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
