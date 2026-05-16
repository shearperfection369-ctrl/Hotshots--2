import React, { createContext, useContext, useEffect, useState } from "react";

export const THEMES = [
  // ===== Orisei brand theme (default for Orisei tenants) =====
  { id: "calafia",  label: "Calafia · Orisei", desc: "Gold leaf on deep navy — Queen Calafia heraldic", swatch: "#C9A24A", bg: "#0A1830", dark: true },
  // ===== Existing 7 =====
  { id: "cyan",     label: "HUD Cyan",     desc: "Tennant default — electric cyan on navy",  swatch: "#00E5FF", bg: "#0B0E14", dark: true },
  { id: "forest",   label: "Forest Calm",  desc: "Calming evergreen — easier on the eyes",   swatch: "#34D399", bg: "#0B1410", dark: true },
  { id: "sunset",   label: "Sunset Warm",  desc: "Warm amber on deep maroon — late shift",   swatch: "#FBBF24", bg: "#14090C", dark: true },
  { id: "arctic",   label: "Arctic",       desc: "Cool ice blue — high focus",                swatch: "#93C5FD", bg: "#0A0F18", dark: true },
  { id: "lavender", label: "Lavender",     desc: "Soft violet — relaxed concentration",       swatch: "#C4B5FD", bg: "#0D0B14", dark: true },
  { id: "mocha",    label: "Mocha",        desc: "Espresso & cream — cozy warmth",            swatch: "#FCD9B6", bg: "#14100C", dark: true },
  { id: "solar",    label: "Solar Light",  desc: "Bright theme — daylight working",           swatch: "#B45309", bg: "#F8FAFC", dark: false },
  // ===== NEW v2.4 =====
  { id: "tennant",   label: "Tennant Brand", desc: "Official Tennant red on midnight",        swatch: "#E4002B", bg: "#0A0E18", dark: true },
  { id: "neon",      label: "Neon Tokyo",    desc: "Magenta-cyan synthwave · maximum HUD",    swatch: "#FF00C8", bg: "#080418", dark: true },
  { id: "matrix",    label: "Matrix Green",  desc: "Phosphor green on black — terminal mode", swatch: "#00FF66", bg: "#02060A", dark: true },
  { id: "amber",     label: "Amber CRT",     desc: "Vintage amber-monitor warmth",            swatch: "#FFB000", bg: "#0E0905", dark: true },
  { id: "midnight",  label: "Midnight Steel",desc: "Deep navy + steel blue · maritime feel",  swatch: "#60A5FA", bg: "#07101D", dark: true },
  { id: "rose",      label: "Rose Quartz",   desc: "Muted pink on charcoal · gentle accent",  swatch: "#F472B6", bg: "#120B11", dark: true },
  { id: "carbon",    label: "Carbon Fiber",  desc: "Slate-on-slate stealth · minimal accent", swatch: "#94A3B8", bg: "#0A0D12", dark: true },
  { id: "paper",     label: "Paper White",   desc: "High-contrast light mode for printouts",  swatch: "#0F172A", bg: "#FFFFFF", dark: false },
  { id: "highvis",   label: "High-Vis Safety",desc: "Safety yellow on charcoal · forklift OK",swatch: "#FACC15", bg: "#0F1316", dark: true },
];

const STORAGE_KEY = "tennant_tms_theme";
const ThemeCtx = createContext({ theme: "cyan", setTheme: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || "calafia"; } catch { return "calafia"; }
  });

  useEffect(() => {
    // Remove any existing theme-* class and add the new one
    const body = document.body;
    Array.from(body.classList).filter((c) => c.startsWith("theme-")).forEach((c) => body.classList.remove(c));
    body.classList.add(`theme-${theme}`);
    try { localStorage.setItem(STORAGE_KEY, theme); } catch {}
  }, [theme]);

  return <ThemeCtx.Provider value={{ theme, setTheme }}>{children}</ThemeCtx.Provider>;
}

export const useTheme = () => useContext(ThemeCtx);
