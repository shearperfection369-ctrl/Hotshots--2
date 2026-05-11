import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Sparkles } from "lucide-react";

/**
 * Subtle ambient quote ticker — fades quotes in/out every 12s.
 * Placed at the top of Command Center, intentionally low-contrast so it doesn't compete with KPIs.
 */
export default function QuotesTicker() {
  const [quotes, setQuotes] = useState([]);
  const [idx, setIdx] = useState(0);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    api.get("/quotes").then(({ data }) => {
      const arr = data.quotes || [];
      // Randomize order so two users don't see the same one at the same time
      const shuffled = [...arr].sort(() => Math.random() - 0.5);
      setQuotes(shuffled);
      setIdx(Math.floor(Math.random() * shuffled.length));
    });
  }, []);

  useEffect(() => {
    if (!quotes.length) return;
    const id = setInterval(() => {
      setFading(true);
      setTimeout(() => {
        setIdx((i) => (i + 1) % quotes.length);
        setFading(false);
      }, 800);
    }, 12000);
    return () => clearInterval(id);
  }, [quotes.length]);

  if (!quotes.length) return null;
  const q = quotes[idx];

  return (
    <div
      className="hud-surface px-5 py-3 rounded-lg border border-cyan-500/15 bg-gradient-to-r from-cyan-500/[0.02] via-cyan-500/[0.04] to-transparent flex items-center gap-3 group"
      data-testid="quotes-ticker"
    >
      <Sparkles size={13} className="text-cyan-400/60 shrink-0" />
      <div className={`flex-1 transition-opacity duration-700 ${fading ? "opacity-0" : "opacity-100"}`}>
        <span className="text-slate-300 text-sm italic font-light">"{q.text}"</span>
        <span className="text-cyan-400/70 text-xs font-mono ml-2">— {q.author}</span>
      </div>
      <span className="text-[9px] font-mono text-slate-600 shrink-0 hidden md:inline tabular-nums">{idx + 1}/{quotes.length}</span>
    </div>
  );
}
