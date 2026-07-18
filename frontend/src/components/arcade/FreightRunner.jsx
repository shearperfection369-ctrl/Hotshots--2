import React, { useEffect, useRef, useState } from "react";

const COLS = 24, ROWS = 16, CELL = 24;

export default function FreightRunner({ onScore }) {
  const canvasRef = useRef(null);
  const [status, setStatus] = useState("ready"); // ready | playing | over
  const [score, setScore] = useState(0);
  const stateRef = useRef(null);

  const start = () => {
    stateRef.current = {
      snake: [{ x: 6, y: 8 }, { x: 5, y: 8 }, { x: 4, y: 8 }],
      dir: { x: 1, y: 0 }, nextDir: { x: 1, y: 0 },
      cargo: { x: 15, y: 8 }, score: 0, speed: 140, dead: false,
    };
    setScore(0); setStatus("playing");
  };

  useEffect(() => {
    const onKey = (e) => {
      const map = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0], w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0] };
      const v = map[e.key];
      if (!v) return;
      e.preventDefault();
      const st = stateRef.current;
      if (!st || st.dead) return;
      if (v[0] === -st.dir.x && v[1] === -st.dir.y) return;
      st.nextDir = { x: v[0], y: v[1] };
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (status !== "playing") return;
    let timer;
    const tick = () => {
      const st = stateRef.current;
      st.dir = st.nextDir;
      const head = { x: st.snake[0].x + st.dir.x, y: st.snake[0].y + st.dir.y };
      const hitWall = head.x < 0 || head.x >= COLS || head.y < 0 || head.y >= ROWS;
      const hitSelf = st.snake.some((s) => s.x === head.x && s.y === head.y);
      if (hitWall || hitSelf) {
        st.dead = true; setStatus("over"); onScore?.(st.score); return;
      }
      st.snake.unshift(head);
      if (head.x === st.cargo.x && head.y === st.cargo.y) {
        st.score += 10; setScore(st.score);
        st.speed = Math.max(60, st.speed - 3);
        do {
          st.cargo = { x: Math.floor(Math.random() * COLS), y: Math.floor(Math.random() * ROWS) };
        } while (st.snake.some((s) => s.x === st.cargo.x && s.y === st.cargo.y));
      } else st.snake.pop();
      draw();
      timer = setTimeout(tick, st.speed);
    };
    const draw = () => {
      const ctx = canvasRef.current?.getContext("2d");
      if (!ctx) return;
      const st = stateRef.current;
      ctx.fillStyle = "#080B12"; ctx.fillRect(0, 0, COLS * CELL, ROWS * CELL);
      ctx.strokeStyle = "rgba(34,211,238,0.06)";
      for (let x = 0; x <= COLS; x++) { ctx.beginPath(); ctx.moveTo(x * CELL, 0); ctx.lineTo(x * CELL, ROWS * CELL); ctx.stroke(); }
      for (let y = 0; y <= ROWS; y++) { ctx.beginPath(); ctx.moveTo(0, y * CELL); ctx.lineTo(COLS * CELL, y * CELL); ctx.stroke(); }
      // cargo crate
      ctx.shadowBlur = 14; ctx.shadowColor = "#F59E0B"; ctx.fillStyle = "#F59E0B";
      ctx.fillRect(st.cargo.x * CELL + 4, st.cargo.y * CELL + 4, CELL - 8, CELL - 8);
      // trailer body
      st.snake.forEach((s, i) => {
        ctx.shadowBlur = i === 0 ? 16 : 8;
        ctx.shadowColor = i === 0 ? "#22D3EE" : "rgba(34,211,238,0.6)";
        ctx.fillStyle = i === 0 ? "#22D3EE" : `rgba(34,211,238,${Math.max(0.35, 1 - i * 0.05)})`;
        ctx.fillRect(s.x * CELL + 2, s.y * CELL + 2, CELL - 4, CELL - 4);
      });
      ctx.shadowBlur = 0;
    };
    draw();
    timer = setTimeout(tick, stateRef.current.speed);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <div className="flex flex-col items-center gap-3" data-testid="game-freight-runner">
      <div className="flex items-center gap-4 text-sm font-mono">
        <span className="text-cyan-300">SCORE <b className="text-white">{score}</b></span>
        <span className="text-slate-500 text-xs">Arrows / WASD to steer · pick up freight · don't jackknife</span>
      </div>
      <div className="relative rounded-xl overflow-hidden border border-cyan-500/30 shadow-lg shadow-cyan-500/10">
        <canvas ref={canvasRef} width={COLS * CELL} height={ROWS * CELL} className="block" />
        {status !== "playing" && (
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm grid place-items-center">
            <div className="text-center">
              {status === "over" && <div className="text-2xl font-black text-amber-400 mb-1">JACKKNIFED!</div>}
              {status === "over" && <div className="text-sm text-slate-300 mb-3 font-mono">Final haul: {score}</div>}
              <button onClick={start} data-testid="freight-runner-start-btn"
                      className="px-6 py-2.5 rounded-full bg-cyan-500 text-black font-black hover:bg-cyan-400">
                {status === "over" ? "Run it again" : "Start hauling"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
