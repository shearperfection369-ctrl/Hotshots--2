import React, { useEffect, useState, useId, useRef } from "react";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

/**
 * <Autocomplete kind="carriers" value={x} onChange={fn} ... />
 *
 * Wraps a normal text Input with an HTML <datalist> populated from the
 * /api/autocomplete/<kind> endpoint. Provides:
 *   - native browser autosuggest (HTML datalist)
 *   - debounced server fetch as the user types
 *   - spellCheck enabled by default
 *   - autoCapitalize / autoComplete tuned for each kind
 *   - optional onSelect(item) callback invoked when the user picks a
 *     suggestion (detected by exact match against the suggestion list).
 *
 * Supported `kind` values: carriers, customers, commodities, equipment,
 * modes, references, lanes, terms, hazmat_un, cities (cities renders a
 * client-side list from freightCities.js for instant feedback — no API).
 */

import { CITY_NAMES, lookupCity } from "@/lib/freightCities";

export function Autocomplete({
  kind,
  value,
  onChange,
  onSelect,
  placeholder,
  className,
  testid,
  ...rest
}) {
  const datalistId = useId();
  const [items, setItems] = useState([]);
  const debounce = useRef(null);

  // Cities are local; everything else hits the API
  useEffect(() => {
    if (kind === "cities") {
      setItems(CITY_NAMES);
      return;
    }
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      api.get(`/autocomplete/${kind}?q=${encodeURIComponent(value || "")}&limit=40`)
         .then(r => setItems(r.data?.suggestions || []))
         .catch(() => {});
    }, 250);
    return () => debounce.current && clearTimeout(debounce.current);
  }, [kind, value]);

  const handleChange = (e) => {
    const v = e.target.value;
    onChange?.(v);
    if (onSelect && items.includes(v)) onSelect(v);
    // Cities special — auto-fire onSelect for city lookups
    if (kind === "cities" && onSelect) {
      const m = lookupCity(v);
      if (m) onSelect(v, m);
    }
  };

  return (
    <>
      <Input
        list={datalistId}
        value={value || ""}
        onChange={handleChange}
        placeholder={placeholder}
        spellCheck="true"
        autoComplete="off"     // disable browser's own to favor datalist
        data-testid={testid}
        className={className}
        {...rest}
      />
      <datalist id={datalistId}>
        {items.map(it => <option key={it} value={it} />)}
      </datalist>
    </>
  );
}
