import React, { useEffect, useMemo, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Building2, Check } from "lucide-react";
import { api } from "@/lib/api";

/**
 * <CustomerCombobox value={name} onChange={fn} onSelect={(customer) => ...} />
 *
 * Smart customer picker. Pulls live customer directory from
 * `/api/autocomplete/customers/directory` (full customer records with
 * primary contact, AP email, payment terms, credit limit). On select, fires
 * `onSelect({customer_id, name, primary_contact_email, ap_email,
 * payment_terms, credit_limit_usd, billing_address, ...})` so the caller can
 * auto-fill billing fields.
 */
export function CustomerCombobox({
  value,
  onChange,
  onSelect,
  placeholder = "Start typing customer name…",
  testid = "customer-combobox",
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
        .get(`/autocomplete/customers/directory?q=${encodeURIComponent(value || "")}&limit=40`)
        .then((r) => setItems(r.data?.items || []))
        .catch(() => setItems([]));
    }, 200);
    return () => debounce.current && clearTimeout(debounce.current);
  }, [value]);

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
              key={c.customer_id || `c-${i}`}
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
              <Building2 size={13} className="text-cyan-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                  {c.name}
                  {c.payment_terms && (
                    <span className="ml-2 font-mono text-[10px] text-cyan-300">
                      {c.payment_terms}
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-slate-500 truncate font-mono">
                  {c.primary_contact_email || c.ap_email || "—"}
                  {c.credit_limit_usd ? ` · credit $${Number(c.credit_limit_usd).toLocaleString()}` : ""}
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
