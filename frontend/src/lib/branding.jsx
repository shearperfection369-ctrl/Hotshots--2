import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "./api";

const DEFAULT_BRAND = {
  brand_id: "tennant",
  company_name: "Tennant Companies",
  short_name: "Tennant",
  tagline: "Mission-control TMS · Built for the team's day",
  industry: "Industrial cleaning equipment manufacturer",
  headquarters: "Golden Valley, MN",
  primary_color: "#00E5FF",
  secondary_color: "#06B6D4",
  accent_color: "#10B981",
  logo_letter: "T",
  catalog_label: "Machine Catalog",
  is_default: true,
};

const BrandCtx = createContext({ brand: DEFAULT_BRAND, refresh: () => {} });

// Global event name fired whenever the active brand changes. Pages /
// components that consume brand-aware API data should subscribe via
// `useBrandRefresh()` so they re-fetch data on every theme switch.
export const BRAND_CHANGED_EVENT = "brand-changed";

/**
 * BrandingProvider — fetches the active company brand once at app boot
 * and re-applies CSS custom properties (--brand-*) on every change so the
 * whole UI re-themes instantly. Falls back to the hard-coded Tennant brand
 * if the API is unreachable.
 */
export function BrandingProvider({ children }) {
  const [brand, setBrand] = useState(DEFAULT_BRAND);

  const apply = (b) => {
    if (!b) return;
    const root = document.documentElement;
    root.style.setProperty("--brand-primary", b.primary_color || "#00E5FF");
    root.style.setProperty("--brand-secondary", b.secondary_color || "#06B6D4");
    root.style.setProperty("--brand-accent", b.accent_color || "#10B981");
    if (b.company_name) {
      document.title = `${b.short_name || b.company_name} · TMS`;
    }
  };

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/branding");
      const next = data.brand || DEFAULT_BRAND;
      // Fire a global event so any subscribed page re-fetches its data.
      // Compare by brand_id so we don't fire on cold-boot first fetch.
      setBrand((prev) => {
        if (prev?.brand_id !== next?.brand_id) {
          try { window.dispatchEvent(new CustomEvent(BRAND_CHANGED_EVENT, { detail: next })); } catch { /* noop */ }
        }
        return next;
      });
      apply(next);
    } catch {
      setBrand(DEFAULT_BRAND);
      apply(DEFAULT_BRAND);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return <BrandCtx.Provider value={{ brand, refresh }}>{children}</BrandCtx.Provider>;
}

export const useBranding = () => useContext(BrandCtx);

/**
 * useBrandRefresh — subscribe a callback that runs whenever the active
 * brand changes. Use in any page/component that displays brand-aware API
 * data so it re-fetches the moment the admin switches themes.
 *
 *   useBrandRefresh(() => loadData(), [loadData]);
 */
export function useBrandRefresh(callback, deps = []) {
  useEffect(() => {
    const handler = () => { try { callback(); } catch { /* noop */ } };
    window.addEventListener(BRAND_CHANGED_EVENT, handler);
    return () => window.removeEventListener(BRAND_CHANGED_EVENT, handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
