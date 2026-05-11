import React, { useEffect, useState } from "react";
import { Activity, Wifi } from "lucide-react";
import ThemeSwitcher from "./ThemeSwitcher";

export default function Topbar({ title, subtitle }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="sticky top-0 z-30 px-4 md:px-6 py-3 border-b border-white/5 bg-[#0B0E14]/80 backdrop-blur-xl" data-testid="topbar">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl md:text-2xl font-bold tracking-tight text-white" data-testid="topbar-title">{title}</h1>
          {subtitle && <p className="text-xs text-slate-500 font-mono mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-emerald-400">All Systems Online</span>
          </div>
          <div className="hidden md:flex items-center gap-2 text-xs font-mono text-slate-400">
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
