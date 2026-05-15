import React, { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Youtube, ExternalLink, Save, ListMusic, Plus, X } from "lucide-react";

/**
 * Extract a YouTube video ID from any common URL form, or accept a raw ID.
 *  - https://www.youtube.com/watch?v=ID
 *  - https://youtu.be/ID
 *  - https://www.youtube.com/embed/ID
 *  - https://www.youtube.com/shorts/ID
 *  - Plain 11-char ID
 */
function parseYouTubeId(input) {
  if (!input) return null;
  const trimmed = String(input).trim();
  // Already a bare 11-char ID
  if (/^[A-Za-z0-9_-]{11}$/.test(trimmed)) return trimmed;
  // URL forms
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
      // /embed/ID, /shorts/ID, /v/ID, /live/ID
      const i = parts.findIndex((p) => ["embed", "shorts", "v", "live"].includes(p));
      if (i >= 0 && parts[i + 1] && /^[A-Za-z0-9_-]{11}$/.test(parts[i + 1])) {
        return parts[i + 1];
      }
    }
  } catch (e) { /* not a URL */ }
  return null;
}

const DEFAULT_VIDEO = "mTxE3g7o4aY"; // Tennant Company official trailer
const STORAGE_KEY = "tms-dashboard-video";
const PLAYLIST_KEY = "tms-dashboard-playlist";

// Curated default playlist — replaced/extended by what the user pins.
const DEFAULT_PLAYLIST = [
  { id: "mTxE3g7o4aY", title: "Tennant · Is Everywhere Trailer" },
  { id: "5qap5aO4i9A", title: "Lofi Hip Hop · Study Stream" },
  { id: "jfKfPfyJRdk", title: "Lofi Hip Hop · Beats to Relax" },
  { id: "DWcJFNfaw9c", title: "Daily Stoic Reading" },
  { id: "rQ7yA5jb5_M", title: "FedEx · Operations Inside Look" },
  { id: "U2knUaP5kK0", title: "Supply Chain Dive · Weekly" },
];

export default function YouTubeVideoTile() {
  const [videoId, setVideoId] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && /^[A-Za-z0-9_-]{11}$/.test(saved)) return saved;
    } catch (e) { /* ignore */ }
    return DEFAULT_VIDEO;
  });
  const [draft, setDraft] = useState(videoId);
  const [error, setError] = useState("");
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

  const apply = () => {
    const id = parseYouTubeId(draft);
    if (!id) {
      setError("Couldn't read that — paste a youtube.com or youtu.be link.");
      return;
    }
    setError("");
    setVideoId(id);
    setDraft(id);
  };

  const pinCurrent = () => {
    if (playlist.some((p) => p.id === videoId)) return;
    const title = prompt("Title for this pinned video?", `Video · ${videoId.slice(0, 6)}`);
    if (!title) return;
    setPlaylist([{ id: videoId, title }, ...playlist].slice(0, 12));
  };

  const removePin = (id) => setPlaylist(playlist.filter((p) => p.id !== id));

  return (
    <Card className="hud-surface p-4" data-testid="video-player-tile">
      <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Youtube size={16} className="text-red-500" />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Video Screen</div>
            <h3 className="font-display text-base font-bold mt-0.5">YouTube Player</h3>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={pinCurrent}
            data-testid="video-pin-btn"
            disabled={playlist.some((p) => p.id === videoId)}
            className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-emerald-300 hover:text-emerald-200 disabled:opacity-40 disabled:cursor-not-allowed"
            title={playlist.some((p) => p.id === videoId) ? "Already pinned" : "Pin to playlist"}
          >
            <Plus size={11} /> Pin
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

      <div className="flex gap-2 mb-3">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") apply(); }}
          placeholder="Paste any YouTube URL or 11-char ID, then press Load…"
          data-testid="video-url-input"
          className="bg-[#0B0E14] border-white/10 font-mono text-xs"
        />
        <button
          onClick={apply}
          data-testid="video-load-btn"
          className="px-3 py-2 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-xs font-mono uppercase tracking-wider flex items-center gap-1.5 shrink-0"
        >
          <Save size={12} /> Load
        </button>
      </div>
      {error ? (
        <div className="text-[10px] font-mono text-red-400 mb-2" data-testid="video-error">{error}</div>
      ) : null}

      {/* Playlist · one-click switch */}
      {playlist.length > 0 && (
        <div className="mb-3" data-testid="video-playlist">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500 mb-1.5">
            <ListMusic size={10} /> Pinned Playlist
          </div>
          <div className="flex flex-wrap gap-1.5">
            {playlist.map((p) => (
              <div
                key={p.id}
                className={`group flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wider border transition ${
                  p.id === videoId
                    ? "bg-cyan-500 text-black border-cyan-400"
                    : "border-white/10 text-slate-300 hover:border-cyan-400/40 hover:text-cyan-200"
                }`}
              >
                <button
                  onClick={() => { setVideoId(p.id); setDraft(p.id); setError(""); }}
                  data-testid={`video-play-${p.id}`}
                  className="max-w-[180px] truncate text-left"
                  title={p.title}
                >
                  {p.title}
                </button>
                <button
                  onClick={() => removePin(p.id)}
                  data-testid={`video-unpin-${p.id}`}
                  className={`opacity-0 group-hover:opacity-100 ${p.id === videoId ? "hover:text-red-700" : "hover:text-red-400"}`}
                  title="Remove pin"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="relative w-full aspect-video bg-black rounded overflow-hidden border border-white/5">
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

      <div className="mt-2 text-[10px] font-mono text-slate-500">
        Tip: Paste any YouTube link · click <span className="text-emerald-300">Pin</span> to save it for one-click playback next time.
        Corporate networks may block youtube.com — use <span className="text-cyan-300">Open in YouTube</span> as a fallback.
      </div>
    </Card>
  );
}

