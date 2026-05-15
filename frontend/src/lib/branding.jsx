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
    // Update <title> + <meta name="application-name">
    if (b.company_name) {
      document.title = `${b.short_name || b.company_name} · TMS`;
    }
  };

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/branding");
      setBrand(data.brand || DEFAULT_BRAND);
      apply(data.brand || DEFAULT_BRAND);
    } catch {
      setBrand(DEFAULT_BRAND);
      apply(DEFAULT_BRAND);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return <BrandCtx.Provider value={{ brand, refresh }}>{children}</BrandCtx.Provider>;
}

export const useBranding = () => useContext(BrandCtx);
