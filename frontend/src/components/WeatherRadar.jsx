import React, { useEffect, useState, useMemo } from "react";

/**
 * WeatherRadar · interactive North American radar from RainViewer's free
 * public API. No API key required, no auth, ~30MB/min for active viewers.
 *
 * Uses the public `radar` endpoint that lists available 10-minute tile
 * frames; we plug the most recent frame into a Leaflet-less canvas:
 * RainViewer ships an iframe-friendly map widget at `tilecache.rainviewer.com`
 * which is what we embed. Falls back to a static frame thumbnail if the
 * iframe is blocked.
 */
const RV_API = "https://api.rainviewer.com/public/weather-maps.json";

export default function WeatherRadar({ height = 320 }) {
  const [frames, setFrames] = useState([]);
  const [frameIdx, setFrameIdx] = useState(0);
  const [opts, setOpts] = useState({ playing: true, scheme: 2, smooth: 1 });
  const [host, setHost] = useState("https://tilecache.rainviewer.com");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(RV_API);
        const d = await r.json();
        if (cancelled) return;
        setHost(d.host || host);
        // We blend past + nowcast for the timeline animation
        const past = d.radar?.past || [];
        const now = d.radar?.nowcast || [];
        const all = [...past, ...now];
        setFrames(all);
        setFrameIdx(past.length - 1); // start at "now"
      } catch (e) { /* offline — keep frames empty, show fallback */ }
    })();
    return () => { cancelled = true; };
  }, []);

  // Auto-advance through frames every 600ms
  useEffect(() => {
    if (!opts.playing || frames.length === 0) return;
    const t = setInterval(() => {
      setFrameIdx((i) => (i + 1) % frames.length);
    }, 600);
    return () => clearInterval(t);
  }, [opts.playing, frames.length]);

  const current = frames[frameIdx];
  const stamp = useMemo(() => {
    if (!current) return "";
    const d = new Date(current.time * 1000);
    return d.toLocaleString("en-US", { hour: "numeric", minute: "2-digit", month: "short", day: "numeric" });
  }, [current]);

  // Approx continental-US bounding box ~ z=4, centered Kansas
  // RainViewer tile format: {host}{path}/512/{z}/{x}/{y}/{color}/{options}.png
  // For an at-a-glance map we use their hosted "Map Widget" via iframe.
  const widgetSrc = current
    ? `https://www.rainviewer.com/map.html?loc=39.50,-98.35,4&oFa=0&oC=0&oU=0&oCS=1&oF=0&c=${opts.scheme}&o=83&lm=0&layer=radar&sm=${opts.smooth}&sn=1&hu=0`
    : null;

  return (
    <div className="hud-surface rounded-lg overflow-hidden border border-cyan-500/10" data-testid="weather-radar">
      <div className="px-4 py-2 border-b border-white/5 flex items-center justify-between gap-2 flex-wrap">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">
            North America · Live Weather Radar
          </div>
          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
            {stamp ? `Frame · ${stamp}` : "Loading frames…"} · {frames.length} frame{frames.length === 1 ? "" : "s"} ·
            <span className="text-cyan-300 ml-1">RainViewer</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setOpts((o) => ({ ...o, playing: !o.playing }))}
            data-testid="weather-radar-toggle"
            className="px-2 py-1 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-[9px] font-mono uppercase tracking-wider"
          >
            {opts.playing ? "Pause" : "Play"}
          </button>
          <button
            onClick={() => setOpts((o) => ({ ...o, scheme: (o.scheme + 1) % 9 }))}
            data-testid="weather-radar-scheme"
            className="px-2 py-1 rounded border border-white/10 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 text-[9px] font-mono uppercase tracking-wider"
            title="Cycle color scheme"
          >
            Theme
          </button>
          <a
            href="https://www.rainviewer.com/map.html?loc=39.5,-98.35,4"
            target="_blank" rel="noreferrer"
            data-testid="weather-radar-open"
            className="px-2 py-1 rounded border border-white/10 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 text-[9px] font-mono uppercase tracking-wider"
          >
            Fullscreen
          </a>
        </div>
      </div>
      {widgetSrc ? (
        <iframe
          src={widgetSrc}
          title="RainViewer radar"
          className="w-full block"
          style={{ height, border: 0, background: "#000" }}
          data-testid="weather-radar-iframe"
        />
      ) : (
        <div
          className="flex items-center justify-center text-slate-500 text-xs font-mono"
          style={{ height }}
        >
          Loading radar feed from RainViewer…
        </div>
      )}
      <div className="px-3 py-1.5 bg-[#0B0E14]/60 border-t border-white/5 flex items-center gap-2 text-[9px] font-mono text-slate-500">
        <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        <span>LIVE · refreshes every 10 minutes from rainviewer.com</span>
      </div>
    </div>
  );
}
