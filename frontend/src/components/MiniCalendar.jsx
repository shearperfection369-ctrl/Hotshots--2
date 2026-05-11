import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";

/**
 * MiniCalendar — compact, HUD-styled month calendar designed to live in the
 * top-right of the Command Center. Renders a small 7-col grid with the
 * current day glowing cyan.
 *
 *   <MiniCalendar />
 *
 * Internal state only — month navigation is local. No backend hookup yet.
 */
export default function MiniCalendar() {
  const today = useMemo(() => new Date(), []);
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));

  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const monthLabel = cursor.toLocaleDateString("en-US", { month: "short", year: "numeric" }).toUpperCase();

  // Build a 6-week grid starting on Sunday.
  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const isToday = (d) =>
    d != null &&
    d === today.getDate() &&
    month === today.getMonth() &&
    year === today.getFullYear();

  return (
    <div
      className="hud-surface rounded-lg p-3 w-[240px] shrink-0 border border-cyan-500/10"
      data-testid="mini-calendar"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <CalendarDays size={11} className="text-cyan-400" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">
            {monthLabel}
          </span>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => setCursor(new Date(year, month - 1, 1))}
            data-testid="mini-cal-prev"
            aria-label="Previous month"
            className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10"
          >
            <ChevronLeft size={12} />
          </button>
          <button
            type="button"
            onClick={() => setCursor(new Date(today.getFullYear(), today.getMonth(), 1))}
            data-testid="mini-cal-today"
            className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider text-slate-500 hover:text-cyan-300"
            title="Jump to today"
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => setCursor(new Date(year, month + 1, 1))}
            data-testid="mini-cal-next"
            aria-label="Next month"
            className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10"
          >
            <ChevronRight size={12} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-[2px] text-center mb-1">
        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
          <div key={i} className="text-[9px] font-mono text-slate-500 uppercase">{d}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-[2px] text-center">
        {cells.map((d, i) => (
          <div
            key={i}
            data-testid={d ? `mini-cal-day-${d}` : undefined}
            className={[
              "h-6 flex items-center justify-center text-[10px] font-mono tabular-nums rounded",
              !d && "text-transparent",
              d && !isToday(d) && "text-slate-300 hover:bg-cyan-500/10 hover:text-cyan-300 cursor-default",
              isToday(d) && "bg-cyan-500/20 text-cyan-300 border border-cyan-400/60 font-bold",
            ].filter(Boolean).join(" ")}
          >
            {d || "·"}
          </div>
        ))}
      </div>
    </div>
  );
}
