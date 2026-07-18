import React, { useCallback, useEffect, useState } from "react";

const SIZE = 4;
const TILE_STYLE = {
  2: "bg-slate-700 text-slate-200", 4: "bg-slate-600 text-white",
  8: "bg-cyan-700 text-white", 16: "bg-cyan-600 text-white",
  32: "bg-cyan-500 text-black", 64: "bg-amber-600 text-white",
  128: "bg-amber-500 text-black", 256: "bg-orange-500 text-black",
  512: "bg-orange-400 text-black", 1024: "bg-fuchsia-500 text-white",
  2048: "bg-fuchsia-400 text-black shadow-lg shadow-fuchsia-500/40",
};

const emptyGrid = () => Array.from({ length: SIZE }, () => Array(SIZE).fill(0));
const addTile = (g) => {
  const empt = [];
  g.forEach((row, r) => row.forEach((v, c) => { if (!v) empt.push([r, c]); }));
  if (!empt.length) return g;
  const [r, c] = empt[Math.floor(Math.random() * empt.length)];
  g[r][c] = Math.random() < 0.9 ? 2 : 4;
  return g;
};

const slide = (row) => {
  const vals = row.filter(Boolean);
  let gained = 0;
  const out = [];
  for (let i = 0; i < vals.length; i++) {
    if (vals[i] === vals[i + 1]) { out.push(vals[i] * 2); gained += vals[i] * 2; i++; }
    else out.push(vals[i]);
  }
  while (out.length < SIZE) out.push(0);
  return [out, gained];
};

const move = (grid, dir) => {
  let g = grid.map((r) => [...r]);
  let gained = 0, moved = false;
  const rot = (m) => m[0].map((_, c) => m.map((row) => row[c]).reverse());
  let rots = { left: 0, up: 3, right: 2, down: 1 }[dir];
  for (let i = 0; i < rots; i++) g = rot(g);
  g = g.map((row) => { const [nr, pts] = slide(row); gained += pts; if (nr.join() !== row.join()) moved = true; return nr; });
  for (let i = 0; i < (4 - rots) % 4; i++) g = rot(g);
  return { g, gained, moved };
};

const canMove = (g) => {
  for (let r = 0; r < SIZE; r++) for (let c = 0; c < SIZE; c++) {
    if (!g[r][c]) return true;
    if (c < SIZE - 1 && g[r][c] === g[r][c + 1]) return true;
    if (r < SIZE - 1 && g[r][c] === g[r + 1][c]) return true;
  }
  return false;
};

export default function LoadStacker({ onScore }) {
  const [grid, setGrid] = useState(() => addTile(addTile(emptyGrid())));
  const [score, setScore] = useState(0);
  const [over, setOver] = useState(false);

  const restart = () => { setGrid(addTile(addTile(emptyGrid()))); setScore(0); setOver(false); };

  const handleMove = useCallback((dir) => {
    if (over) return;
    setGrid((prev) => {
      const { g, gained, moved } = move(prev, dir);
      if (!moved) return prev;
      addTile(g);
      setScore((s) => {
        const ns = s + gained;
        if (!canMove(g)) { setOver(true); onScore?.(ns); }
        return ns;
      });
      if (!canMove(g)) setOver(true);
      return g;
    });
  }, [over, onScore]);

  useEffect(() => {
    const onKey = (e) => {
      const map = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down", a: "left", d: "right", w: "up", s: "down" };
      if (!map[e.key]) return;
      e.preventDefault();
      handleMove(map[e.key]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleMove]);

  return (
    <div className="flex flex-col items-center gap-3" data-testid="game-load-stacker">
      <div className="flex items-center gap-4 text-sm font-mono">
        <span className="text-amber-300">SCORE <b className="text-white">{score}</b></span>
        <span className="text-slate-500 text-xs">Arrows / WASD to consolidate pallets · reach the 2048 mega-load</span>
      </div>
      <div className="relative p-2 rounded-xl bg-[#080B12] border border-amber-500/30 shadow-lg shadow-amber-500/10">
        <div className="grid grid-cols-4 gap-2">
          {grid.flat().map((v, i) => (
            <div key={i}
                 className={`w-20 h-20 rounded-lg grid place-items-center font-black transition-colors ${v ? TILE_STYLE[v] || "bg-fuchsia-300 text-black" : "bg-white/5"} ${v >= 128 ? "text-xl" : "text-2xl"}`}>
              {v ? v.toLocaleString() : ""}
            </div>
          ))}
        </div>
        {over && (
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm grid place-items-center rounded-xl">
            <div className="text-center">
              <div className="text-2xl font-black text-amber-400 mb-1">DOCK FULL!</div>
              <div className="text-sm text-slate-300 mb-3 font-mono">Total consolidated: {score}</div>
              <button onClick={restart} data-testid="load-stacker-restart-btn"
                      className="px-6 py-2.5 rounded-full bg-amber-500 text-black font-black hover:bg-amber-400">Stack again</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
