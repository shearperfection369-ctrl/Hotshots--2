import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Play, Pause, Radio, Search, Globe, Headphones } from "lucide-react";
import { useMusic } from "../lib/music";

export default function Music() {
  const [genres, setGenres] = useState([]);
  const [genre, setGenre] = useState("lofi");
  const [stations, setStations] = useState([]);
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [loading, setLoading] = useState(false);
  const { current, playing, playStation } = useMusic();

  useEffect(() => { api.get("/music/genres").then(({ data }) => setGenres(data)); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (genre) params.set("genre", genre);
      if (q) params.set("q", q);
      if (country) params.set("country", country);
      params.set("limit", "60");
      const { data } = await api.get(`/music/stations?${params}`);
      setStations(data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [genre]);

  return (
    <>
      <Topbar title="Music · Focus Mode" subtitle="30,000+ free internet radio stations · royalty-free streaming via Radio Browser" />
      <div className="p-4 md:p-6 space-y-5">

        {/* Genre row */}
        <Card className="hud-surface p-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 px-1">Genres</div>
          <div className="flex gap-2 overflow-x-auto pb-1" data-testid="music-genres">
            {genres.map((g) => (
              <button
                key={g.id}
                onClick={() => setGenre(g.id)}
                data-testid={`genre-${g.id}`}
                className={`shrink-0 px-3 py-1.5 rounded-md text-xs font-mono uppercase tracking-wider transition-all border ${
                  genre === g.id ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan" : "bg-white/[0.02] text-slate-300 border-white/5 hover:border-cyan-500/40 hover:text-cyan-300"
                }`}
              >
                <span className="mr-1.5">{g.icon}</span>{g.label}
              </button>
            ))}
          </div>
        </Card>

        {/* Search */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div className="md:col-span-7 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="music-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              placeholder="Search by station name (e.g., 'KEXP', 'Radio Paradise')..."
              className="pl-9 bg-[#131821] border-white/10"
            />
          </div>
          <div className="md:col-span-3 relative">
            <Globe size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && load()}
              placeholder="Country code (US, DE, JP, UK...)"
              className="pl-9 bg-[#131821] border-white/10 font-mono uppercase"
            />
          </div>
          <Button onClick={load} className="md:col-span-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold">SEARCH</Button>
        </div>

        {/* Stations grid */}
        <Card className="hud-surface p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Stations</div>
              <h3 className="font-display text-lg font-bold flex items-center gap-2">
                <Headphones size={18} className="text-cyan-400" /> {stations.length} stations available
              </h3>
            </div>
            {loading && <Badge className="bg-cyan-500/10 text-cyan-300 border-cyan-500/30 font-mono text-[10px]">LOADING...</Badge>}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="station-grid">
            {stations.map((s) => {
              const active = current?.id === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => playStation(s)}
                  data-testid={`station-${s.id}`}
                  className={`text-left p-3.5 rounded-md border transition-all ${
                    active
                      ? "border-cyan-500 bg-cyan-500/10 hud-glow-cyan"
                      : "border-white/5 bg-white/[0.02] hover:border-cyan-500/30 hover:bg-cyan-500/[0.03]"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${active ? "bg-cyan-500 text-black" : "bg-cyan-500/10 text-cyan-400"}`}>
                      {active && playing ? <Pause size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-medium truncate" title={s.name}>{s.name}</div>
                      <div className="text-[10px] font-mono text-slate-500 mt-0.5">{s.country} · {s.codec || "?"} · {s.bitrate || "?"}kbps</div>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {s.tags.filter(Boolean).slice(0, 3).map((tag, i) => (
                          <span key={i} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] text-slate-400">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                  {active && (
                    <div className="mt-2 pt-2 border-t border-cyan-500/20 flex items-center gap-1.5">
                      <Radio size={10} className="text-cyan-400 blink-dot" />
                      <span className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{playing ? "Now Playing" : "Paused"}</span>
                    </div>
                  )}
                </button>
              );
            })}
            {!loading && stations.length === 0 && (
              <div className="col-span-full text-center py-12 text-slate-500">No stations found. Try a different genre or country.</div>
            )}
          </div>
        </Card>

        <div className="text-[10px] font-mono text-slate-500 text-center">
          Streaming via Radio Browser API · explicit/talk content filtered · audio played directly in browser
        </div>
      </div>
    </>
  );
}
