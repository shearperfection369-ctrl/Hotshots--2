import React, { createContext, useContext, useEffect, useState } from "react";

export const THEMES = [
  { id: "cyan", label: "HUD Cyan", desc: "Tennant default — electric cyan on navy", swatch: "#00E5FF", bg: "#0B0E14", dark: true },
  { id: "forest", label: "Forest Calm", desc: "Calming evergreen — easier on the eyes", swatch: "#34D399", bg: "#0B1410", dark: true },
  { id: "sunset", label: "Sunset Warm", desc: "Warm amber on deep maroon — late shift mood", swatch: "#FBBF24", bg: "#14090C", dark: true },
  { id: "arctic", label: "Arctic", desc: "Cool ice blue — high focus", swatch: "#93C5FD", bg: "#0A0F18", dark: true },
  { id: "lavender", label: "Lavender", desc: "Soft violet — relaxed concentration", swatch: "#C4B5FD", bg: "#0D0B14", dark: true },
  { id: "mocha", label: "Mocha", desc: "Espresso & cream — cozy warmth", swatch: "#FCD9B6", bg: "#14100C", dark: true },
  { id: "solar", label: "Solar Light", desc: "Bright theme — daylight working", swatch: "#B45309", bg: "#F8FAFC", dark: false },
];

const STORAGE_KEY = "tennant_tms_theme";
const ThemeCtx = createContext({ theme: "cyan", setTheme: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) || "cyan"; } catch { return "cyan"; }
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
