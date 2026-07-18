import React, { useEffect, useRef, useState } from "react";

const W = 576, H = 400, PW = 96, PH = 12, BR = 7;
const ROWS = 5, COLS = 10, BW = W / COLS - 6, BH = 18;
const COLORS = ["#F59E0B", "#FB923C", "#22D3EE", "#A78BFA", "#34D399"];

export default function DockBreaker({ onScore }) {
  const canvasRef = useRef(null);
  const [status, setStatus] = useState("ready");
  const [score, setScore] = useState(0);
  const [lives, setLives] = useState(3);
  const stRef = useRef(null);

  const buildBricks = () =>
    Array.from({ length: ROWS }, (_, r) => Array.from({ length: COLS }, (_, c) => ({ r, c, alive: true }))).flat();

  const start = () => {
    stRef.current = {
      px: W / 2 - PW / 2, bx: W / 2, by: H - 60, vx: 3.4, vy: -3.4,
      bricks: buildBricks(), score: 0, lives: 3, level: 1, keys: {},
    };
    setScore(0); setLives(3); setStatus("playing");
  };

  useEffect(() => {
    const kd = (e) => { if (stRef.current && ["ArrowLeft", "ArrowRight"].includes(e.key)) { e.preventDefault(); stRef.current.keys[e.key] = true; } };
    const ku = (e) => { if (stRef.current) stRef.current.keys[e.key] = false; };
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
    return () => { window.removeEventListener("keydown", kd); window.removeEventListener("keyup", ku); };
  }, []);

  useEffect(() => {
    if (status !== "playing") return;
    let raf;
    const cv = canvasRef.current;
    const onMouse = (e) => {
      const rect = cv.getBoundingClientRect();
      stRef.current.px = Math.min(W - PW, Math.max(0, e.clientX - rect.left - PW / 2));
    };
    cv.addEventListener("mousemove", onMouse);
    const loop = () => {
      const st = stRef.current;
      if (st.keys.ArrowLeft) st.px = Math.max(0, st.px - 7);
      if (st.keys.ArrowRight) st.px = Math.min(W - PW, st.px + 7);
      st.bx += st.vx; st.by += st.vy;
      if (st.bx < BR || st.bx > W - BR) st.vx *= -1;
      if (st.by < BR) st.vy *= -1;
      if (st.by > H - 40 - PH && st.by < H - 40 && st.bx > st.px - BR && st.bx < st.px + PW + BR && st.vy > 0) {
        st.vy *= -1;
        st.vx += ((st.bx - (st.px + PW / 2)) / (PW / 2)) * 1.4;
        st.vx = Math.max(-6, Math.min(6, st.vx));
      }
      st.bricks.forEach((b) => {
        if (!b.alive) return;
        const x = b.c * (W / COLS) + 3, y = 40 + b.r * (BH + 6);
        if (st.bx > x - BR && st.bx < x + BW + BR && st.by > y - BR && st.by < y + BH + BR) {
          b.alive = false; st.vy *= -1; st.score += 15;
          setScore(st.score);
        }
      });
      if (st.bricks.every((b) => !b.alive)) {
        st.level += 1; st.bricks = buildBricks();
        st.bx = W / 2; st.by = H - 60; st.vy = -(3.4 + st.level * 0.6); st.vx = 3.4;
        st.score += 100; setScore(st.score);
      }
      if (st.by > H + BR) {
        st.lives -= 1; setLives(st.lives);
        if (st.lives <= 0) { setStatus("over"); onScore?.(st.score); return; }
        st.bx = W / 2; st.by = H - 60; st.vy = -3.4; st.vx = 3.4;
      }
      const ctx = cv.getContext("2d");
      ctx.fillStyle = "#080B12"; ctx.fillRect(0, 0, W, H);
      st.bricks.forEach((b) => {
        if (!b.alive) return;
        ctx.shadowBlur = 8; ctx.shadowColor = COLORS[b.r];
        ctx.fillStyle = COLORS[b.r];
        ctx.fillRect(b.c * (W / COLS) + 3, 40 + b.r * (BH + 6), BW, BH);
      });
      ctx.shadowBlur = 14; ctx.shadowColor = "#22D3EE"; ctx.fillStyle = "#22D3EE";
      ctx.fillRect(st.px, H - 40, PW, PH);
      ctx.beginPath(); ctx.arc(st.bx, st.by, BR, 0, Math.PI * 2);
      ctx.shadowColor = "#F59E0B"; ctx.fillStyle = "#F59E0B"; ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "rgba(148,163,184,0.6)"; ctx.font = "11px monospace";
      ctx.fillText(`LVL ${st.level}`, 10, 20);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); cv.removeEventListener("mousemove", onMouse); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <div className="flex flex-col items-center gap-3" data-testid="game-dock-breaker">
      <div className="flex items-center gap-4 text-sm font-mono">
        <span className="text-orange-300">SCORE <b className="text-white">{score}</b></span>
        <span className="text-red-400">{"❤".repeat(Math.max(0, lives))}</span>
        <span className="text-slate-500 text-xs">Mouse or ← → to move the dock plate · clear every crate</span>
      </div>
      <div className="relative rounded-xl overflow-hidden border border-orange-500/30 shadow-lg shadow-orange-500/10">
        <canvas ref={canvasRef} width={W} height={H} className="block" />
        {status !== "playing" && (
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm grid place-items-center">
            <div className="text-center">
              {status === "over" && <div className="text-2xl font-black text-orange-400 mb-1">DOCK CLOSED!</div>}
              {status === "over" && <div className="text-sm text-slate-300 mb-3 font-mono">Crates cleared: {score}</div>}
              <button onClick={start} data-testid="dock-breaker-start-btn"
                      className="px-6 py-2.5 rounded-full bg-orange-500 text-black font-black hover:bg-orange-400">
                {status === "over" ? "Reopen the dock" : "Open the dock"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
