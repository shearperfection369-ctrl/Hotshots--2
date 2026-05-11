import React from "react";
import { useMusic } from "../lib/music";
import { Play, Pause, X, Volume2, Radio } from "lucide-react";

export default function MiniPlayer() {
  const { current, playing, volume, setVolume, togglePlay, stop } = useMusic();
  if (!current) return null;

  return (
    <div
      className="fixed bottom-3 right-3 z-50 w-[330px] hud-surface rounded-lg border border-cyan-500/30 hud-glow-cyan p-2.5 flex items-center gap-2.5 shadow-2xl"
      data-testid="music-mini-player"
    >
      <button
        onClick={togglePlay}
        data-testid="mini-player-toggle"
        className="w-10 h-10 rounded-full bg-cyan-500 hover:bg-cyan-400 text-black flex items-center justify-center shrink-0"
      >
        {playing ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <Radio size={11} className={`text-cyan-400 ${playing ? "blink-dot" : ""}`} />
          <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{playing ? "LIVE" : "PAUSED"}</span>
        </div>
        <div className="text-sm text-white truncate" title={current.name}>{current.name}</div>
        <div className="text-[10px] font-mono text-slate-500 truncate">
          {current.country} · {current.codec || "—"} {current.bitrate ? `· ${current.bitrate}kbps` : ""}
        </div>
      </div>
      <div className="flex flex-col gap-1 items-center">
        <Volume2 size={11} className="text-slate-400" />
        <input
          type="range" min={0} max={1} step={0.01}
          value={volume}
          onChange={(e) => setVolume(parseFloat(e.target.value))}
          data-testid="mini-player-volume"
          className="w-16 h-1 accent-cyan-400 cursor-pointer"
        />
      </div>
      <button
        onClick={stop}
        data-testid="mini-player-stop"
        className="w-7 h-7 rounded text-slate-500 hover:text-red-400 hover:bg-red-500/10 flex items-center justify-center"
        title="Stop"
      ><X size={13} /></button>
    </div>
  );
}
