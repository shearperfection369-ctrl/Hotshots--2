import React, { useEffect, useState } from "react";
import { Activity, Wifi } from "lucide-react";
import ThemeSwitcher from "./ThemeSwitcher";
import GlobalSearch from "./GlobalSearch";
import { useBranding } from "../lib/branding";

export default function Topbar({ title, subtitle }) {
  const [now, setNow] = useState(new Date());
  const { brand } = useBranding();
  const isDefault = !brand || brand.is_default || brand.brand_id === "orisei-freight";
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="sticky top-0 z-30 px-4 md:px-6 py-3 border-b border-white/5 bg-[#0B0E14]/80 backdrop-blur-xl" data-testid="topbar">
      <div className="flex items-center justify-between gap-4">
        <div className="shrink-0 min-w-0 flex items-center gap-3">
          <div className="hidden md:flex items-center gap-2 pr-3 border-r border-white/10">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center font-orisei text-xl shadow-[0_0_18px_rgba(224,184,92,0.4)]"
                 style={isDefault
                   ? { background: "linear-gradient(135deg,#E0B85C,#B08A36)", color: "#0A2D55" }
                   : { background: `linear-gradient(135deg,${brand.primary_color || "#3B82F6"},${brand.secondary_color || "#60A5FA"})`, color: "#0B0E14" }}>
              {isDefault ? "O" : (brand.logo_letter || (brand.short_name || "B")[0]).toUpperCase()}
            </div>
            <div className="font-orisei text-lg leading-none" data-testid="topbar-brand"
                 style={{ color: isDefault ? "#FCD34D" : (brand.primary_color || "#3B82F6") }}>
              {isDefault ? "Orisei" : (brand.short_name || brand.company_name)}
            </div>
          </div>
          <div className="min-w-0">
            <h1 className="font-display text-xl md:text-2xl font-bold tracking-tight text-white truncate" data-testid="topbar-title">{title}</h1>
            {subtitle && <p className="text-xs text-slate-500 font-mono mt-0.5 truncate">{subtitle}</p>}
          </div>
        </div>
        {/* Omni-search — searches every TMS reference + jumps into SAP S/4HANA */}
        <div className="hidden md:block flex-1 max-w-md">
          <GlobalSearch />
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-400">All Systems Online</span>
          </div>
          <div className="hidden xl:flex items-center gap-2 text-xs font-mono text-slate-400">
            <Wifi size={14} className="text-cyan-400" />
            <span>UPLINK</span>
          </div>
          <ThemeSwitcher />
          <div className="text-right">
            <div className="text-xs font-mono text-cyan-400 tabular-nums" data-testid="topbar-clock">
              {now.toLocaleTimeString("en-US", { hour12: false })}
            </div>
            <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              {now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
