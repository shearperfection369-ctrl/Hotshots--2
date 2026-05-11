import React, { useState } from "react";
import { Palette, Check } from "lucide-react";
import { useTheme, THEMES } from "../lib/theme";

export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const current = THEMES.find((t) => t.id === theme) || THEMES[0];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="theme-switcher-btn"
        title="Change theme"
        className="px-3 py-1.5 rounded-md border border-white/10 bg-white/[0.02] hover:border-cyan-400/40 hover:bg-cyan-500/10 transition flex items-center gap-2 text-xs font-mono uppercase tracking-wider"
      >
        <Palette size={13} className="text-cyan-400" />
        <span className="hidden md:inline">{current.label}</span>
        <span className="w-3 h-3 rounded-full border border-white/20" style={{ background: current.swatch }} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-2 w-72 z-50 hud-surface rounded-lg border border-cyan-500/30 shadow-2xl p-2" data-testid="theme-switcher-panel">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 px-2 py-1.5">Visual Theme</div>
            {THEMES.map((t) => {
              const active = t.id === theme;
              return (
                <button
                  key={t.id}
                  onClick={() => { setTheme(t.id); setOpen(false); }}
                  data-testid={`theme-option-${t.id}`}
                  className={`w-full text-left p-2 rounded transition flex items-center gap-3 ${active ? "bg-cyan-500/10 border-l-2 border-cyan-400" : "hover:bg-white/[0.04]"}`}
                >
                  <div className="relative w-9 h-9 rounded border border-white/10 overflow-hidden shrink-0" style={{ background: t.bg }}>
                    <div className="absolute inset-1 rounded" style={{ background: `linear-gradient(135deg, ${t.swatch} 0%, ${t.swatch}55 100%)` }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-mono text-white flex items-center gap-1.5">
                      {t.label}
                      {!t.dark && <span className="text-[8px] px-1 py-0.5 rounded bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 font-mono">LIGHT</span>}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate">{t.desc}</div>
                  </div>
                  {active && <Check size={14} className="text-cyan-400 shrink-0" />}
                </button>
              );
            })}
            <div className="text-[9px] font-mono text-slate-500 px-2 py-1 mt-1 border-t border-white/5 pt-2">
              Theme persists across sessions · Affects all pages
            </div>
          </div>
        </>
      )}
    </div>
  );
}
