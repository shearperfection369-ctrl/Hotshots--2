import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, CalendarDays, Truck, Package, ArrowRight } from "lucide-react";

/**
 * MiniCalendar — compact, HUD-styled month calendar with live event badges.
 *
 * Pulls events from `GET /api/calendar/events?start=…&end=…` for the visible
 * month and renders:
 *   - A cyan ring + count badge on every date with at least one event
 *   - Today highlighted with a filled cyan tile
 *   - Click any date to pop the day's events in a small panel under the grid
 *     (label · sublabel · type icon · click-through to /shipments or /workbook)
 *
 * Designed for the Command Center top-right slot — 240px wide.
 */

function pad(n) { return String(n).padStart(2, "0"); }
function iso(y, m, d) { return `${y}-${pad(m + 1)}-${pad(d)}`; }

const TYPE_ICON = { pickup: Truck, delivery: Package, eta: ArrowRight };
const TYPE_COLOR = { pickup: "text-yellow-300", delivery: "text-emerald-300", eta: "text-cyan-300" };

export default function MiniCalendar() {
  const today = useMemo(() => new Date(), []);
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [events, setEvents] = useState([]);
  const [counts, setCounts] = useState({});
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);

  const year = cursor.getFullYear();
  const month = cursor.getMonth();
  const monthLabel = cursor.toLocaleDateString("en-US", { month: "short", year: "numeric" }).toUpperCase();

  // Fetch events covering the entire grid: from the Sunday of week 1
  // through the Saturday of the last week — small overlap is fine.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const firstDow = new Date(year, month, 1).getDay();
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const lastTail = 7 - ((firstDow + daysInMonth) % 7);
      const start = new Date(year, month, 1 - firstDow);
      const end = new Date(year, month, daysInMonth + (lastTail === 7 ? 0 : lastTail));
      const startISO = iso(start.getFullYear(), start.getMonth(), start.getDate());
      const endISO = iso(end.getFullYear(), end.getMonth(), end.getDate());
      try {
        const { data } = await api.get(`/calendar/events?start=${startISO}&end=${endISO}`);
        if (cancelled) return;
        setEvents(data.events || []);
        setCounts(data.counts_by_date || {});
      } catch (e) {
        if (!cancelled) { setEvents([]); setCounts({}); }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [year, month]);

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

  const dateKey = (d) => (d ? iso(year, month, d) : null);
  const selectedEvents = useMemo(
    () => (selected ? events.filter((e) => e.date === selected) : []),
    [selected, events]
  );

  return (
    <div
      className="hud-surface rounded-lg p-3 w-[260px] shrink-0 border border-cyan-500/10"
      data-testid="mini-calendar"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <CalendarDays size={11} className="text-cyan-400" />
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">
            {monthLabel}
          </span>
          {loading && <span className="ml-1 w-1 h-1 rounded-full bg-cyan-400 animate-pulse" />}
        </div>
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => { setCursor(new Date(year, month - 1, 1)); setSelected(null); }}
            data-testid="mini-cal-prev"
            aria-label="Previous month"
            className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10"
          >
            <ChevronLeft size={12} />
          </button>
          <button
            type="button"
            onClick={() => { setCursor(new Date(today.getFullYear(), today.getMonth(), 1)); setSelected(null); }}
            data-testid="mini-cal-today"
            className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider text-slate-500 hover:text-cyan-300"
            title="Jump to today"
          >
            Today
          </button>
          <button
            type="button"
            onClick={() => { setCursor(new Date(year, month + 1, 1)); setSelected(null); }}
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
        {cells.map((d, i) => {
          const key = dateKey(d);
          const evCount = key ? (counts[key] || 0) : 0;
          const hasEvents = evCount > 0;
          const isSel = key && selected === key;
          return (
            <button
              key={i}
              type="button"
              disabled={!d}
              onClick={() => key && setSelected(isSel ? null : key)}
              data-testid={d ? `mini-cal-day-${d}` : undefined}
              className={[
                "relative h-7 flex items-center justify-center text-[10px] font-mono tabular-nums rounded transition",
                !d && "text-transparent cursor-default",
                d && !isToday(d) && !isSel && "text-slate-300 hover:bg-cyan-500/10 hover:text-cyan-300",
                hasEvents && !isToday(d) && !isSel && "ring-1 ring-cyan-500/40",
                isToday(d) && !isSel && "bg-cyan-500/20 text-cyan-300 border border-cyan-400/60 font-bold",
                isSel && "bg-cyan-500/40 text-white border border-cyan-300 font-bold",
              ].filter(Boolean).join(" ")}
            >
              {d || "·"}
              {hasEvents && (
                <span
                  className="absolute -top-0.5 -right-0.5 text-[7px] font-bold font-mono bg-cyan-500 text-black rounded-full px-1 leading-tight"
                  data-testid={`mini-cal-badge-${d}`}
                >
                  {evCount > 9 ? "9+" : evCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Selected-day events panel */}
      {selected && (
        <div className="mt-3 pt-3 border-t border-white/10" data-testid="mini-cal-events-panel">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[9px] font-mono uppercase tracking-wider text-cyan-400">
              {new Date(selected + "T12:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
              {" "}· {selectedEvents.length} event{selectedEvents.length === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className="text-[9px] font-mono text-slate-500 hover:text-slate-300"
            >Close</button>
          </div>
          <div className="space-y-1.5 max-h-[180px] overflow-y-auto pr-1">
            {selectedEvents.length === 0 && (
              <div className="text-[10px] font-mono text-slate-500 text-center py-2">
                No events on this day.
              </div>
            )}
            {selectedEvents.slice(0, 12).map((e, i) => {
              const Icon = TYPE_ICON[e.type] || Truck;
              const color = TYPE_COLOR[e.type] || "text-cyan-300";
              return (
                <Link
                  key={i}
                  to={e.link || "/shipments"}
                  data-testid={`mini-cal-event-${i}`}
                  className="block px-2 py-1.5 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/40 hover:bg-cyan-500/[0.04] transition-colors"
                >
                  <div className="flex items-center gap-1.5">
                    <Icon size={9} className={`${color} shrink-0`} />
                    <span className="text-[10px] font-mono text-slate-100 truncate">{e.label}</span>
                  </div>
                  <div className="text-[9px] font-mono text-slate-500 truncate ml-3.5">{e.sublabel}</div>
                </Link>
              );
            })}
            {selectedEvents.length > 12 && (
              <div className="text-[9px] font-mono text-slate-500 text-center pt-1">
                +{selectedEvents.length - 12} more
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
