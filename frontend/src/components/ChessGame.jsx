import React, { useMemo, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { RotateCcw, Bot } from "lucide-react";

/**
 * ChessGame — play vs a deliberately-weak random/heuristic engine.
 * Uses chess.js (logic) + react-chessboard (UI). Player is white by default;
 * Hit "Flip" to swap sides, "New Game" to reset.
 *
 * Engine strategy: prefer captures and check, otherwise random move. Plenty
 * of fun for a lunch-break match without dragging in a real chess engine.
 */
export default function ChessGame() {
  const [game, setGame] = useState(() => new Chess());
  const [orientation, setOrientation] = useState("white");
  const [thinking, setThinking] = useState(false);
  const [moves, setMoves] = useState([]);

  const fen = game.fen();
  const status = useMemo(() => {
    if (game.isCheckmate()) return `Checkmate — ${game.turn() === "w" ? "Black" : "White"} wins`;
    if (game.isDraw()) return "Draw";
    if (game.isCheck()) return `Check — ${game.turn() === "w" ? "White" : "Black"} to move`;
    return `${game.turn() === "w" ? "White" : "Black"} to move`;
  }, [fen, game]);

  const replaceGame = (g) => {
    setGame(g);
    setMoves(g.history());
  };

  const engineMove = (g) => {
    setThinking(true);
    setTimeout(() => {
      const possible = g.moves({ verbose: true });
      if (possible.length === 0) { setThinking(false); return; }
      // Heuristic: prefer captures, then checks, otherwise random
      const captures = possible.filter((m) => m.captured);
      const checks = possible.filter((m) => m.san.includes("+"));
      const pool = captures.length ? captures : checks.length ? checks : possible;
      const pick = pool[Math.floor(Math.random() * pool.length)];
      const next = new Chess(g.fen());
      next.move(pick);
      replaceGame(next);
      setThinking(false);
    }, 350);
  };

  const onDrop = (from, to) => {
    if (thinking) return false;
    const next = new Chess(game.fen());
    let result;
    try { result = next.move({ from, to, promotion: "q" }); } catch { return false; }
    if (!result) return false;
    replaceGame(next);
    if (!next.isGameOver()) setTimeout(() => engineMove(next), 250);
    return true;
  };

  const reset = () => { const g = new Chess(); replaceGame(g); };
  const flip = () => setOrientation((o) => (o === "white" ? "black" : "white"));

  return (
    <Card className="hud-surface p-5" data-testid="chess-game">
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2">
            <Bot size={11} /> Chess · vs HUDLINK engine
          </div>
          <h3 className="font-display text-lg font-bold">{status}</h3>
        </div>
        <div className="flex items-center gap-1.5">
          <Button onClick={flip} variant="outline" data-testid="chess-flip" className="border-cyan-500/30 text-cyan-300">
            Flip
          </Button>
          <Button onClick={reset} variant="outline" data-testid="chess-reset" className="border-white/10 text-slate-300">
            <RotateCcw size={12} className="mr-1" /> New Game
          </Button>
        </div>
      </div>
      <div className="flex gap-4 items-start flex-wrap">
        <div className="w-full md:w-[480px]" data-testid="chess-board-wrap">
          <Chessboard
            position={fen}
            onPieceDrop={onDrop}
            boardOrientation={orientation}
            customDarkSquareStyle={{ backgroundColor: "#0F1B2D" }}
            customLightSquareStyle={{ backgroundColor: "#1F2A40" }}
            customBoardStyle={{ borderRadius: 6, boxShadow: "0 0 0 1px rgba(0,229,255,0.2)" }}
          />
        </div>
        <div className="flex-1 min-w-[180px]" data-testid="chess-moves">
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2">Move history</div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 max-h-[420px] overflow-y-auto text-xs font-mono">
            {moves.length === 0 && <div className="col-span-2 text-slate-500">No moves yet. You play white.</div>}
            {moves.reduce((acc, m, i) => {
              const turn = Math.floor(i / 2) + 1;
              if (i % 2 === 0) acc.push({ turn, w: m, b: "" });
              else acc[acc.length - 1].b = m;
              return acc;
            }, []).map((row) => (
              <React.Fragment key={row.turn}>
                <div className="text-slate-500">{row.turn}. <span className="text-cyan-200">{row.w}</span></div>
                <div className="text-slate-300">{row.b}</div>
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
