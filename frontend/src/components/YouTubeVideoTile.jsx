import React, { useState, useEffect } from "react";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { Youtube, ExternalLink, Save } from "lucide-react";

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

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, videoId); } catch (e) { /* ignore */ }
  }, [videoId]);

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
        <a
          href={`https://www.youtube.com/watch?v=${videoId}`}
          target="_blank" rel="noreferrer"
          data-testid="video-open-youtube"
          className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200"
        >
          Open in YouTube <ExternalLink size={10} />
        </a>
      </div>

      <div className="flex gap-2 mb-3">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") apply(); }}
          placeholder="Paste YouTube URL or video ID…"
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
        Tip: Tennant corporate network may block youtube.com. If the player is blank,
        click <span className="text-cyan-300">Open in YouTube</span> to launch in a new tab.
      </div>
    </Card>
  );
}
