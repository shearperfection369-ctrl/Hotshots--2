import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Sparkles } from "lucide-react";

/**
 * Streaming quote ticker — quotes flicker IN and OUT of reality every ~5s
 * with a sci-fi static + glitch transition. Replaces the older 12s fade.
 *
 * Animation uses two CSS keyframes (`quoteIn` / `quoteOut`) defined in
 * /app/frontend/src/index.css.
 */
export default function QuotesTicker() {
  const [quotes, setQuotes] = useState([]);
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState("in"); // 'in' | 'out'

  useEffect(() => {
    api.get("/quotes").then(({ data }) => {
      const arr = data.quotes || [];
      const shuffled = [...arr].sort(() => Math.random() - 0.5);
      setQuotes(shuffled);
      setIdx(Math.floor(Math.random() * shuffled.length));
    });
  }, []);

  useEffect(() => {
    if (!quotes.length) return;
    // Cadence: 4500ms total — 800ms out, 200ms gap, advance, 3500ms in
    const id = setInterval(() => {
      setPhase("out");
      setTimeout(() => {
        setIdx((i) => (i + 1) % quotes.length);
        setPhase("in");
      }, 800);
    }, 5000);
    return () => clearInterval(id);
  }, [quotes.length]);

  if (!quotes.length) return null;
  const q = quotes[idx];
  const cls = phase === "in" ? "quote-streaming-in" : "quote-streaming-out";

  return (
    <div
      className="hud-surface px-5 py-3 rounded-lg border border-cyan-500/20 bg-gradient-to-r from-cyan-500/[0.03] via-cyan-500/[0.06] to-transparent flex items-center gap-3 relative overflow-hidden"
      data-testid="quotes-ticker"
    >
      {/* Faint scanline overlay — adds the "streaming through the matrix" feel */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          background:
            "repeating-linear-gradient(0deg, rgba(0,229,255,0.04) 0 1px, transparent 1px 4px)",
        }}
      />
      <Sparkles size={13} className="text-cyan-400 shrink-0 relative z-10" />
      <div className={`flex-1 relative z-10 ${cls}`} key={idx /* re-trigger animation */}>
        <span className="text-slate-200 text-sm italic font-light tracking-wide">"{q.text}"</span>
        <span className="text-cyan-400 text-xs font-mono ml-2">— {q.author}</span>
      </div>
      <span className="text-[9px] font-mono text-cyan-500/60 shrink-0 hidden md:inline tabular-nums relative z-10">
        {idx + 1}/{quotes.length}
      </span>
    </div>
  );
}
