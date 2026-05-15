import React, { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Youtube, ExternalLink, Save, ListMusic, Plus, X, Play, Pin } from "lucide-react";

/**
 * Extract a YouTube video ID from any common URL form, or accept a raw ID.
 */
function parseYouTubeId(input) {
  if (!input) return null;
  const trimmed = String(input).trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(trimmed)) return trimmed;
  try {
    const u = new URL(trimmed);
    const host = u.hostname.replace(/^www\./, "");
    if (host === "youtu.be") {
      const id = u.pathname.split("/").filter(Boolean)[0];
      return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
    }
    if (host === "youtube.com" || host === "m.youtube.com") {
      if (u.searchParams.get("v")) return u.searchParams.get("v");
      const parts = u.pathname.split("/").filter(Boolean);
      const i = parts.findIndex((p) => ["embed", "shorts", "v", "live"].includes(p));
      if (i >= 0 && parts[i + 1] && /^[A-Za-z0-9_-]{11}$/.test(parts[i + 1])) {
        return parts[i + 1];
      }
    }
  } catch (e) { /* not a URL */ }
  return null;
}

const DEFAULT_VIDEO = "mTxE3g7o4aY";
const STORAGE_KEY = "tms-dashboard-video";
const PLAYLIST_KEY = "tms-dashboard-playlist.v2";

const DEFAULT_PLAYLIST = [
  { id: "mTxE3g7o4aY", title: "Tennant · Is Everywhere Trailer" },
  { id: "5qap5aO4i9A", title: "Lofi Hip Hop · Study Stream" },
  { id: "jfKfPfyJRdk", title: "Lofi Hip Hop · Beats to Relax" },
  { id: "DWcJFNfaw9c", title: "Daily Stoic Reading" },
  { id: "rQ7yA5jb5_M", title: "FedEx · Operations Inside Look" },
  { id: "U2knUaP5kK0", title: "Supply Chain Dive · Weekly" },
];

const thumbUrl = (id) => `https://i.ytimg.com/vi/${id}/mqdefault.jpg`;

// Pull a real title from YouTube's oEmbed endpoint (no API key needed).
async function fetchTitle(id) {
  try {
    const r = await fetch(`https://www.youtube.com/oembed?url=https://youtube.com/watch?v=${id}&format=json`);
    if (!r.ok) return null;
    const j = await r.json();
    return j.title || null;
  } catch { return null; }
}

export default function YouTubeVideoTile() {
  const [videoId, setVideoId] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && /^[A-Za-z0-9_-]{11}$/.test(saved)) return saved;
    } catch (e) { /* ignore */ }
    return DEFAULT_VIDEO;
  });
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [playlist, setPlaylist] = useState(() => {
    try {
      const saved = localStorage.getItem(PLAYLIST_KEY);
      if (saved) return JSON.parse(saved);
    } catch (e) { /* ignore */ }
    return DEFAULT_PLAYLIST;
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, videoId); } catch (e) { /* ignore */ }
  }, [videoId]);

  useEffect(() => {
    try { localStorage.setItem(PLAYLIST_KEY, JSON.stringify(playlist)); } catch (e) { /* ignore */ }
  }, [playlist]);

  const addToPlaylist = async () => {
    const id = parseYouTubeId(draft);
    if (!id) {
      setError("Couldn't read that — paste a YouTube URL or 11-char ID.");
      return;
    }
    if (playlist.some((p) => p.id === id)) {
      setError("Already in your playlist.");
      setVideoId(id);
      setDraft("");
      return;
    }
    setError("");
    const title = await fetchTitle(id) || `Video · ${id.slice(0, 6)}`;
    setPlaylist([{ id, title }, ...playlist].slice(0, 24));
    setVideoId(id);
    setDraft("");
    setAdding(false);
  };

  const removeFromPlaylist = (id) => {
    setPlaylist(playlist.filter((p) => p.id !== id));
    if (id === videoId && playlist.length > 1) {
      const next = playlist.find((p) => p.id !== id);
      if (next) setVideoId(next.id);
    }
  };

  const active = playlist.find((p) => p.id === videoId);

  return (
    <Card className="hud-surface p-4" data-testid="video-player-tile">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Youtube size={16} className="text-red-500" />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Video Screen</div>
            <h3 className="font-display text-base font-bold mt-0.5">{active?.title || "YouTube Player"}</h3>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setAdding((v) => !v); setError(""); }}
            data-testid="video-add-toggle"
            className={`inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider ${adding ? "text-slate-400 hover:text-white" : "text-emerald-300 hover:text-emerald-200"}`}
          >
            {adding ? <><X size={11} /> Cancel</> : <><Plus size={11} /> Add Video</>}
          </button>
          <a
            href={`https://www.youtube.com/watch?v=${videoId}`}
            target="_blank" rel="noreferrer"
            data-testid="video-open-youtube"
            className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200"
          >
            Open in YouTube <ExternalLink size={10} />
          </a>
        </div>
      </div>

      {adding && (
        <div className="mb-3" data-testid="video-add-form">
          <div className="flex gap-2">
            <Input
              value={draft}
              autoFocus
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") addToPlaylist(); }}
              placeholder="Paste youtube.com/youtu.be URL or 11-char ID…"
              data-testid="video-url-input"
              className="bg-[#0B0E14] border-white/10 font-mono text-xs"
            />
            <button
              onClick={addToPlaylist}
              data-testid="video-load-btn"
              className="px-3 py-2 rounded border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0"
            >
              <Save size={12} /> Save
            </button>
          </div>
          {error && <div className="text-[10px] font-mono text-red-400 mt-2" data-testid="video-error">{error}</div>}
        </div>
      )}

      {/* Player */}
      <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-white/5 mb-3">
        <iframe
          key={videoId}
          src={`https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1`}
          title="YouTube player"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          data-testid="video-iframe"
          className="absolute inset-0 w-full h-full"
        />
      </div>

      {/* Thumbnail playlist */}
      {playlist.length > 0 && (
        <div data-testid="video-playlist">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500 mb-2">
            <ListMusic size={10} /> My Playlist · {playlist.length}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {playlist.map((p) => (
              <div
                key={p.id}
                data-testid={`video-card-${p.id}`}
                className={`group relative aspect-video rounded overflow-hidden border cursor-pointer transition ${
                  p.id === videoId
                    ? "border-cyan-400 ring-2 ring-cyan-400/40"
                    : "border-white/10 hover:border-cyan-400/40"
                }`}
                onClick={() => { setVideoId(p.id); setError(""); }}
                title={p.title}
              >
                <img src={thumbUrl(p.id)} alt="" className="w-full h-full object-cover" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent" />
                <div className="absolute inset-x-1.5 bottom-1 text-[10px] font-mono text-white truncate leading-tight" data-testid={`video-play-${p.id}`}>
                  {p.title}
                </div>
                {p.id === videoId && (
                  <div className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-cyan-500 text-black text-[8px] font-mono font-bold uppercase tracking-wider flex items-center gap-0.5">
                    <Play size={8} className="fill-current" /> Now
                  </div>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); removeFromPlaylist(p.id); }}
                  data-testid={`video-unpin-${p.id}`}
                  className="absolute top-1 right-1 p-0.5 rounded bg-black/60 backdrop-blur text-slate-300 opacity-0 group-hover:opacity-100 hover:bg-red-500 hover:text-white transition"
                  title="Remove from playlist"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 text-[10px] font-mono text-slate-500">
        Tip: <span className="text-emerald-300">+ Add Video</span> to paste a YouTube link · click a thumbnail to play · hover a tile to remove. Playlist saved per browser.
      </div>
    </Card>
  );
}
