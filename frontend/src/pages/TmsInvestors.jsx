import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";
import {
  Play, Pause, RotateCcw, Volume2, VolumeX, Download, ArrowRight, Plug, Palette, Sparkles,
  ShieldCheck, BarChart3, Truck, Cpu, Globe2, Zap, MapPin, Briefcase,
  Award, CheckCircle2, Mail, Send, Building2, Layers, FileText, Archive,
  Stamp,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const HSTMS_CYAN = "#22D3EE";
const HSTMS_BLUE = "#0EA5E9";

/**
 * Public-facing Hot Shot TMS investor pitch page at /tms-investors.
 * Polished, video-first VC pitch — separate from the Orisei brokerage pitch
 * at /investors.
 */
export default function TmsInvestors() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [brandIdx, setBrandIdx] = useState(0);
  const [hasLocalMp4, setHasLocalMp4] = useState(false);
  const [muted, setMuted] = useState(true);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "", email: "", firm: "", check_size_usd: "", linkedin: "", message: "", website: "",
  });
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token");
  const [inviteInfo, setInviteInfo] = useState(null);
  const [inviteError, setInviteError] = useState(null);
  const videoRef = React.useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasStarted, setHasStarted] = useState(false);

  useEffect(() => {
    document.title = "Hot Shot TMS · Investor Executive Summary";
    setMetaTags();
    (async () => {
      try {
        const { data: d } = await axios.get(`${REACT_APP_BACKEND_URL}/api/public/tms-pitch-summary`);
        setData(d);
      } catch (e) { /* graceful */ }
      finally { setLoading(false); }
    })();
    // Local MP4 probe
    fetch("/promo.mp4", { method: "HEAD" })
      .then((r) => {
        const ct = (r.headers.get("content-type") || "").toLowerCase();
        const len = parseInt(r.headers.get("content-length") || "0", 10);
        const isHtmlFallback = ct.includes("text/html") || ct.includes("application/json");
        setHasLocalMp4(r.ok && !isHtmlFallback && len > 100000);
      })
      .catch(() => setHasLocalMp4(false));
  }, []);

  // Token-gated visit handshake: validate token + log the first page view +
  // pre-fill the intro form. Runs once per token.
  useEffect(() => {
    if (!inviteToken) return;
    (async () => {
      try {
        const { data: info } = await axios.get(
          `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}`
        );
        setInviteInfo(info);
        setForm((f) => ({
          ...f,
          firm: info.firm_name || f.firm,
          name: info.contact_name || f.name,
        }));
        // Fire-and-forget visit log
        axios.post(
          `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}/visit`,
          { event: "page_view", referrer: document.referrer || null }
        ).catch(() => {});
      } catch (err) {
        const detail = err?.response?.data?.detail || "Invite link not found or expired.";
        setInviteError(detail);
      }
    })();
  }, [inviteToken]);

  // Track download events when the user clicks any download link
  const logDownload = (eventName) => {
    if (!inviteToken) return;
    axios.post(
      `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}/visit`,
      { event: eventName }
    ).catch(() => {});
  };

  // Brand reel auto-rotation
  useEffect(() => {
    if (!data?.rebranding?.brand_reel?.length) return;
    const t = setInterval(() => {
      setBrandIdx((i) => (i + 1) % data.rebranding.brand_reel.length);
    }, 1800);
    return () => clearInterval(t);
  }, [data]);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email) return;
    setSubmitting(true);
    try {
      await axios.post(`${REACT_APP_BACKEND_URL}/api/public/investor-intro`, {
        ...form,
        message: `[Hot Shot TMS pitch] ${form.message || ""}`.trim(),
      });
      setSubmitted(true);
    } catch (err) { /* inline state */ }
    finally { setSubmitting(false); }
  };

  const playVideo = () => {
    const v = videoRef.current; if (!v) return;
    v.muted = false; setMuted(false);
    v.play().then(() => { setIsPlaying(true); setHasStarted(true); })
      .catch(() => {  // autoplay blocked — fall back to muted play
        v.muted = true; setMuted(true);
        v.play().then(() => { setIsPlaying(true); setHasStarted(true); }).catch(() => {});
      });
  };
  const pauseVideo = () => {
    const v = videoRef.current; if (!v) return;
    v.pause(); setIsPlaying(false);
  };
  const replayVideo = () => {
    const v = videoRef.current; if (!v) return;
    v.currentTime = 0; playVideo();
  };
  const toggleMute = () => {
    const v = videoRef.current; if (!v) return;
    v.muted = !v.muted; setMuted(v.muted);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050A14] text-white flex items-center justify-center">
        <div className="text-slate-400 font-mono text-sm tracking-wider">Loading Hot Shot TMS pitch…</div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="min-h-screen bg-[#050A14] text-white flex items-center justify-center p-8 text-center">
        <div>
          <div className="text-slate-300 mb-3">Pitch summary failed to load.</div>
          <Link to="/about" className="text-cyan-300 hover:underline">← Back to overview</Link>
        </div>
      </div>
    );
  }

  const activeBrand = data.rebranding.brand_reel[brandIdx];
  // Token-aware download URLs: when an invite token is present and valid, use
  // the personalized endpoints so every PDF gets a "Prepared for [Firm]"
  // stamp + diagonal watermark.
  const downloadUrls = inviteToken && inviteInfo && !inviteError ? {
    deck:     `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}/deck.pdf`,
    onePager: `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}/one-pager.pdf`,
    zip:      `${REACT_APP_BACKEND_URL}/api/public/tms-link/${inviteToken}/data-room.zip`,
  } : {
    deck:     `${REACT_APP_BACKEND_URL}/api/public/tms-deck.pdf`,
    onePager: `${REACT_APP_BACKEND_URL}/api/public/tms-one-pager.pdf`,
    zip:      `${REACT_APP_BACKEND_URL}/api/public/tms-data-room.zip`,
  };

  return (
    <div className="min-h-screen bg-[#050A14] text-white overflow-x-hidden">
      {/* JadeOS family ribbon */}
      <div className="relative z-30 border-b border-white/5 bg-black/40 text-xs font-mono"
           data-testid="hstms-jadeos-ribbon">
        <div className="max-w-7xl mx-auto px-6 py-1.5 flex items-center justify-between flex-wrap gap-2">
          <span className="text-slate-400">
            Part of the <span style={{ color: HSTMS_CYAN }}>JadeOS</span> stack —
            three products, one cap table.
          </span>
          <a href="https://mpls-automation-hub.emergent.host/"
             target="_blank" rel="noopener noreferrer"
             data-testid="hstms-jadeos-ribbon-link"
             className="hover:underline tracking-wider uppercase"
             style={{ color: HSTMS_CYAN }}>
            See the full thesis →
          </a>
        </div>
      </div>
      {/* Background grid */}
      <div
        className="fixed inset-0 opacity-[0.05] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(${HSTMS_CYAN}33 1px,transparent 1px), linear-gradient(90deg,${HSTMS_CYAN}33 1px,transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />
      {/* Sticky public nav */}
      <header className="relative z-20 border-b border-white/5 bg-[#050A14]/85 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/about" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center font-black text-black text-lg shadow-lg"
                 style={{ background: `linear-gradient(135deg, ${HSTMS_CYAN}, ${HSTMS_BLUE})` }}>
              H
            </div>
            <div>
              <div className="font-display text-lg font-black tracking-tight">Hot Shot TMS</div>
              <div className="text-[9px] font-mono tracking-[0.25em] text-cyan-400/70 -mt-0.5">
                INVESTOR EXECUTIVE SUMMARY
              </div>
            </div>
          </Link>
          <nav className="flex items-center gap-5 text-sm font-mono uppercase tracking-wider text-slate-400">
            <a href="#video" className="hover:text-cyan-300 hidden md:inline">Demo</a>
            <a href="#changeability" className="hover:text-cyan-300 hidden md:inline">Re-Theme</a>
            <a href="#plug-and-play" className="hover:text-cyan-300 hidden md:inline">Plug & Play</a>
            <a href="#jadeos-stack" className="hover:text-cyan-300 hidden md:inline">The Stack</a>
            <a href="#founder" className="hover:text-cyan-300 hidden md:inline">Founder</a>
            <a href="#ask" className="hover:text-cyan-300 hidden md:inline">The Ask</a>
            <a href="#intro"
               className="px-3 py-1.5 text-black font-bold rounded text-xs"
               style={{ background: HSTMS_CYAN }}>
              Talk to Oliver →
            </a>
          </nav>
        </div>
      </header>

      {/* HERO + VIDEO */}
      <section id="video" className="relative z-10 max-w-7xl mx-auto px-6 pt-16 pb-20"
               data-testid="hstms-hero">

        {/* PERSONALIZED INVITE BANNER */}
        {(inviteInfo || inviteError) && (
          <div className="mb-8" data-testid="hstms-invite-banner">
            {inviteInfo && (
              <div className="rounded-xl border-2 p-5 flex items-start gap-4"
                   style={{ borderColor: HSTMS_CYAN, background: `${HSTMS_CYAN}11` }}>
                <div className="w-12 h-12 rounded-lg flex items-center justify-center font-black text-black text-2xl shrink-0"
                     style={{ background: HSTMS_CYAN }}>
                  {(inviteInfo.firm_name || "?")[0]}
                </div>
                <div className="flex-1">
                  <div className="text-[10px] font-mono uppercase tracking-[0.25em]" style={{ color: HSTMS_CYAN }}>
                    Personalized for · Confidential
                  </div>
                  <div className="font-display text-2xl md:text-3xl font-black mt-1" data-testid="invite-firm-name">
                    Welcome, <span style={{ color: HSTMS_CYAN }}>{inviteInfo.firm_name}</span>
                    {inviteInfo.contact_name && <span className="text-slate-400 text-lg"> · {inviteInfo.contact_name}</span>}
                  </div>
                  <div className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                    <Stamp size={12} style={{ color: HSTMS_CYAN }} />
                    Every PDF you download is stamped "Prepared for {inviteInfo.firm_name}" on every page.
                  </div>
                </div>
              </div>
            )}
            {inviteError && (
              <div className="rounded-xl border-2 p-5 flex items-center gap-4"
                   style={{ borderColor: "#FB923C", background: "rgba(251,146,60,0.10)" }}
                   data-testid="hstms-invite-error">
                <div className="text-amber-300 font-mono text-xs uppercase tracking-wider">Invite link issue</div>
                <div className="text-sm text-slate-200">{inviteError}</div>
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-5">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-[10px] font-mono uppercase tracking-[0.25em] mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              Series Seed · Open SAFE Round
            </div>
            <h1 className="font-display text-5xl md:text-7xl font-black leading-[0.95] tracking-tighter">
              One TMS.
              <br />
              <span className="inline-block transition-all duration-700"
                    style={{ color: activeBrand.color, textShadow: `0 0 40px ${activeBrand.color}55` }}
                    data-testid="hero-active-brand">
                {activeBrand.name}.
              </span>
              <br />
              <span className="text-slate-500">Any Company.</span>
            </h1>
            <p className="mt-7 text-lg text-slate-300 leading-relaxed max-w-xl">
              The first Transportation Management System that <strong className="text-white">re-themes
              itself for any company in 60 seconds</strong>. Type the company name. Watch the entire
              app — colors, sample data, ERP context, suppliers, lanes, documents — reshape around them.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href={downloadUrls.deck} target="_blank" rel="noopener noreferrer"
                 onClick={() => logDownload("deck")}
                 data-testid="hstms-download-deck"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold text-black"
                 style={{ background: HSTMS_CYAN }}>
                <Download size={16} /> Pitch Deck (PDF)
              </a>
              <a href={downloadUrls.onePager} target="_blank" rel="noopener noreferrer"
                 onClick={() => logDownload("one-pager")}
                 data-testid="hstms-download-one-pager"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold border-2 transition-colors"
                 style={{ borderColor: HSTMS_CYAN, color: HSTMS_CYAN }}>
                <FileText size={16} /> One-Pager
              </a>
              <a href={downloadUrls.zip}
                 onClick={() => logDownload("zip")}
                 data-testid="hstms-download-zip"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md text-sm text-slate-300 hover:text-white border border-white/10 transition">
                <Archive size={14} /> Full Data Room (ZIP)
              </a>
            </div>
            <div className="mt-7 flex flex-wrap items-center gap-4 text-xs font-mono text-slate-500">
              <span className="flex items-center gap-1.5"><CheckCircle2 size={12} style={{ color: HSTMS_CYAN }} /> {data.founder.name} · Founder</span>
              <span>•</span>
              <span className="flex items-center gap-1.5"><MapPin size={12} style={{ color: HSTMS_CYAN }} /> {data.founder.location}</span>
              <span>•</span>
              <span className="flex items-center gap-1.5"><Mail size={12} style={{ color: HSTMS_CYAN }} /> shearperfection369@gmail.com</span>
            </div>
          </div>

          {/* VIDEO PLAYER */}
          <div className="lg:col-span-7" data-testid="hstms-video-container">
            <div className="relative rounded-2xl overflow-hidden border-2 shadow-2xl"
                 style={{ borderColor: `${HSTMS_CYAN}55`, boxShadow: `0 0 60px ${HSTMS_CYAN}22` }}>
              {hasLocalMp4 ? (
                <div className="relative">
                  <video
                    ref={videoRef}
                    src="/promo.mp4"
                    preload="metadata"
                    playsInline
                    onPlay={() => { setIsPlaying(true); setHasStarted(true); }}
                    onPause={() => setIsPlaying(false)}
                    onEnded={() => setIsPlaying(false)}
                    className="w-full aspect-video object-cover bg-black"
                    data-testid="hstms-video"
                  />
                  {/* PRE-PLAY POSTER OVERLAY */}
                  {!hasStarted && (
                    <button onClick={playVideo}
                            data-testid="hstms-play-poster"
                            className="absolute inset-0 flex items-center justify-center bg-black/60 backdrop-blur-sm hover:bg-black/50 transition group">
                      <div className="text-center">
                        <div className="w-20 h-20 mx-auto rounded-full flex items-center justify-center mb-3 group-hover:scale-110 transition shadow-2xl"
                             style={{ background: HSTMS_CYAN, color: "#000" }}>
                          <Play size={32} className="ml-1" fill="currentColor" />
                        </div>
                        <div className="text-white font-bold tracking-wider">Play Investor Trailer</div>
                        <div className="text-xs text-slate-300 mt-1 font-mono">Hot Shot TMS · 90 seconds</div>
                      </div>
                    </button>
                  )}
                  {/* CONTROLS BAR (visible after first play) */}
                  {hasStarted && (
                    <div className="absolute bottom-0 inset-x-0 flex items-center gap-2 px-3 py-2 bg-gradient-to-t from-black/85 to-transparent"
                         data-testid="hstms-video-controls">
                      <button onClick={isPlaying ? pauseVideo : playVideo}
                              data-testid={isPlaying ? "hstms-pause" : "hstms-play"}
                              className="w-10 h-10 rounded-full flex items-center justify-center hover:scale-110 transition"
                              style={{ background: HSTMS_CYAN, color: "#000" }}
                              title={isPlaying ? "Pause" : "Play"}>
                        {isPlaying ? <Pause size={18} fill="currentColor"/> : <Play size={18} fill="currentColor" className="ml-0.5"/>}
                      </button>
                      <button onClick={replayVideo}
                              data-testid="hstms-replay"
                              className="w-9 h-9 rounded-full flex items-center justify-center bg-white/15 hover:bg-white/25 text-white transition"
                              title="Restart from beginning">
                        <RotateCcw size={15}/>
                      </button>
                      <button onClick={toggleMute}
                              data-testid="hstms-mute-toggle"
                              className="w-9 h-9 rounded-full flex items-center justify-center bg-white/15 hover:bg-white/25 text-white transition"
                              title={muted ? "Unmute" : "Mute"}>
                        {muted ? <VolumeX size={15}/> : <Volume2 size={15}/>}
                      </button>
                      <div className="flex-1"/>
                      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/60 mr-1">
                        {isPlaying ? "PLAYING" : "PAUSED"}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <iframe
                  src={`https://www.youtube.com/embed/${data.video.youtube_fallback_id}?modestbranding=1&rel=0`}
                  title="Hot Shot TMS · Investor Trailer"
                  className="w-full aspect-video"
                  allow="encrypted-media; picture-in-picture; fullscreen"
                  data-testid="hstms-video-iframe"
                />
              )}
            </div>
            <div className="mt-4 text-xs text-slate-400 leading-relaxed text-center max-w-2xl mx-auto">
              {data.video.caption}
            </div>
          </div>
        </div>
      </section>

      {/* STATS BAR */}
      <section className="relative z-10 border-y bg-cyan-500/[0.03]"
               style={{ borderColor: `${HSTMS_CYAN}33` }}
               data-testid="hstms-stats">
        <div className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-2 md:grid-cols-7 gap-6">
          <Stat v={data.platform_stats.modules + "+"} k="Modules" />
          <Stat v={data.platform_stats.api_endpoints + "+"} k="API Endpoints" />
          <Stat v={data.platform_stats.erp_connectors} k="ERP Connectors" />
          <Stat v={data.platform_stats.launch_day_integrations} k="Integrations" />
          <Stat v={data.platform_stats.visual_themes} k="Visual Themes" />
          <Stat v={data.platform_stats.brand_directory} k="Brand Directory" />
          <Stat v={data.platform_stats.scorecard_metrics} k="Scorecard Metrics" />
        </div>
      </section>

      {/* CHANGEABILITY · RE-THEME WEDGE */}
      <section id="changeability" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5"
               data-testid="hstms-changeability">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              The wedge that wins enterprise deals
            </div>
            <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter mb-6">
              60 seconds to a <span style={{ color: HSTMS_CYAN }}>fully-skinned</span> live demo.
            </h2>
            <p className="text-slate-300 text-lg leading-relaxed mb-6">
              Most TMS implementations take <strong className="text-white">6 to 18 months</strong>. Hot Shot TMS skins
              itself for the prospect's company <strong className="text-cyan-300">DURING the sales call</strong>. Type
              the company name → Claude Sonnet generates the brand profile → watch the entire app reshape in real time.
            </p>

            <div className="space-y-3 mt-8">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: HSTMS_CYAN }}>
                What re-themes instantly
              </div>
              <ul className="space-y-1.5">
                {data.rebranding.what_changes.map((line, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-200">
                    <Palette size={14} className="mt-0.5 shrink-0" style={{ color: HSTMS_CYAN }} />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="mt-6 space-y-3">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2 text-slate-500">
                What stays put (security · audit · data integrity)
              </div>
              <ul className="space-y-1.5">
                {data.rebranding.what_stays.map((line, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
                    <ShieldCheck size={14} className="mt-0.5 shrink-0 text-slate-500" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Brand reel grid */}
          <div className="lg:col-span-6">
            <div className="relative">
              <div className="absolute -inset-6 rounded-3xl blur-3xl opacity-25 transition-colors duration-700"
                   style={{ background: activeBrand.color }} />
              <div className="relative rounded-2xl border-2 p-8 backdrop-blur-sm transition-colors duration-700"
                   style={{ borderColor: `${activeBrand.color}77`, background: `${activeBrand.color}10` }}>
                <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-slate-400 mb-3">
                  Active Brand · Live Re-Theming · Powered by Claude Sonnet 4.5
                </div>
                <div className="flex items-center gap-5">
                  <div className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl font-black text-black transition-colors duration-700"
                       style={{ background: activeBrand.color }}>
                    {activeBrand.name[0]}
                  </div>
                  <div className="flex-1">
                    <div className="font-display text-4xl font-black tracking-tight transition-colors duration-700"
                         style={{ color: activeBrand.color }}>
                      {activeBrand.name}
                    </div>
                    <div className="text-xs font-mono text-slate-400 mt-1">
                      Skin {brandIdx + 1} of {data.rebranding.brand_reel.length} · {(activeBrand.color || "").toUpperCase()}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-5 gap-2 mt-6">
                  {data.rebranding.brand_reel.map((b, i) => (
                    <button key={b.name} onClick={() => setBrandIdx(i)}
                            className={`p-2 rounded border-2 transition cursor-pointer ${i === brandIdx ? "scale-105" : "opacity-60 hover:opacity-100"}`}
                            style={{
                              borderColor: i === brandIdx ? b.color : "rgba(255,255,255,0.08)",
                              background: i === brandIdx ? `${b.color}22` : "rgba(255,255,255,0.02)",
                            }}
                            data-testid={`brand-tile-${i}`}>
                      <div className="w-full h-5 rounded mb-1.5" style={{ background: b.color }} />
                      <div className="text-[9px] font-mono truncate text-slate-300">{b.name}</div>
                    </button>
                  ))}
                </div>
                <div className="mt-5 text-[11px] text-slate-400 leading-relaxed flex items-start gap-1.5">
                  <Sparkles size={12} className="shrink-0 mt-0.5" style={{ color: HSTMS_CYAN }} />
                  <span>Type any company name → AI writes the brand profile → entire app re-skins in 60 seconds. Zero implementation overhead.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* PLUG AND PLAY */}
      <section id="plug-and-play" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5"
               data-testid="hstms-plug-and-play">
        <div className="max-w-3xl mb-12">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
            Plug · Test · Activate
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter mb-5">
            Connect to any ERP. <span style={{ color: HSTMS_CYAN }}>Two clicks.</span>
          </h2>
          <p className="text-slate-300 text-lg leading-relaxed">
            Drop your endpoint URL, paste your service-user credentials, hit <strong className="text-white">Test
            Connection</strong> — done. Live orders, shipments, customers, and materials flow into the app
            immediately. <strong className="text-cyan-300">{data.plug_and_play.encryption}.</strong>
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          {/* ERPs */}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              {data.platform_stats.erp_connectors} ERP Connectors · Live
            </div>
            <div className="grid grid-cols-3 gap-2.5">
              {data.plug_and_play.erp_connectors.map((e) => (
                <div key={e.name} className="p-3 rounded-lg border bg-white/[0.02] hover:border-cyan-500/40 transition"
                     style={{ borderColor: "rgba(255,255,255,0.08)" }}
                     data-testid={`erp-${e.name.toLowerCase().replace(/\s+/g, "-")}`}>
                  <Plug size={13} style={{ color: HSTMS_CYAN }} className="mb-2" />
                  <div className="text-sm font-bold leading-tight">{e.name}</div>
                  <div className="text-[9px] font-mono text-slate-500 mt-1 uppercase tracking-wider">{e.category}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Launch-day providers */}
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              {data.platform_stats.launch_day_integrations} Launch-Day Integrations · Pre-Wired
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {data.plug_and_play.launch_day_providers.map((p) => (
                <div key={p.name} className="p-3 rounded-lg border bg-white/[0.02] hover:border-cyan-500/40 transition"
                     style={{ borderColor: "rgba(255,255,255,0.08)" }}>
                  <Layers size={13} style={{ color: HSTMS_CYAN }} className="mb-2" />
                  <div className="text-sm font-bold leading-tight">{p.name}</div>
                  <div className="text-[9px] font-mono text-slate-500 mt-1 uppercase tracking-wider">{p.category}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-10 p-6 rounded-xl border bg-cyan-500/5 max-w-3xl"
             style={{ borderColor: `${HSTMS_CYAN}44` }}>
          <div className="flex items-start gap-3">
            <ShieldCheck size={20} style={{ color: HSTMS_CYAN }} className="shrink-0 mt-0.5" />
            <div>
              <div className="font-display text-lg font-bold mb-1">Security by default</div>
              <p className="text-sm text-slate-300 leading-relaxed">
                Every credential in the Connections vault is Fernet-encrypted at rest. Secrets are
                never returned in plaintext API responses — only masked previews like
                <code className="font-mono text-cyan-300"> xxx•••yyy</code>. Multiple environments
                (PROD, QAS, DEV) live side-by-side per integration.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FEATURES GRID */}
      <section id="features" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5"
               data-testid="hstms-features">
        <div className="max-w-3xl mb-10">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
            What's already built
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter">
            Enterprise depth. <span style={{ color: HSTMS_CYAN }}>Mid-market price.</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.features.map((f, i) => (
            <div key={f.title}
                 className="p-5 rounded-xl border bg-white/[0.02] hover:border-cyan-500/40 transition"
                 style={{ borderColor: "rgba(255,255,255,0.06)" }}
                 data-testid={`feature-${i}`}>
              <div className="p-2 rounded-lg inline-block mb-3"
                   style={{ background: `${HSTMS_CYAN}1a`, border: `1px solid ${HSTMS_CYAN}33` }}>
                <FeatureIcon idx={i} />
              </div>
              <h3 className="font-display text-lg font-bold mb-1.5">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* FOUNDER */}
      <section id="founder" className="relative z-10 max-w-7xl mx-auto px-6 py-24 border-t border-white/5"
               data-testid="hstms-founder">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
          <div className="lg:col-span-4">
            <div className="aspect-square rounded-2xl bg-gradient-to-br from-cyan-500/20 to-slate-900 border-2 flex items-center justify-center"
                 style={{ borderColor: `${HSTMS_CYAN}44` }}>
              <div className="text-center">
                <div className="w-32 h-32 mx-auto rounded-full flex items-center justify-center text-6xl font-black text-black shadow-2xl"
                     style={{ background: HSTMS_CYAN }}>
                  OC
                </div>
                <div className="mt-4 font-display text-2xl font-bold">{data.founder.name}</div>
                <div className="text-xs font-mono mt-1" style={{ color: HSTMS_CYAN }}>{data.founder.title}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-2">{data.founder.location}</div>
              </div>
            </div>
          </div>
          <div className="lg:col-span-8">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              13 years on the desk
            </div>
            <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter mb-5">
              Built by someone who's <span style={{ color: HSTMS_CYAN }}>actually run the desk</span>.
            </h2>
            <p className="text-slate-300 text-lg leading-relaxed">
              {data.founder.bio}
            </p>

            <div className="mt-7 grid grid-cols-2 md:grid-cols-4 gap-3">
              <FounderStat v={data.founder.tenure_years} k="Years in Logistics" />
              <FounderStat v={data.founder.modes.length} k="Modes Mastered" />
              <FounderStat v="MN" k="HQ State" />
              <FounderStat v="13+" k="Years Operator" />
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <Pill Icon={MapPin} label={data.founder.location} />
              <Pill Icon={Briefcase} label={data.founder.current_role.split(" · ")[1] || "Tennant Companies"} />
              <Pill Icon={Globe2} label="International Specialist" />
              <Pill Icon={Award} label={`${data.founder.tenure_years}+ Years Operator`} />
            </div>
          </div>
        </div>
      </section>

      {/* THREE-PRODUCT STACK · JadeOS family */}
      <section id="jadeos-stack" className="relative z-10 max-w-7xl mx-auto px-6 py-20 border-t border-white/5"
               data-testid="hstms-jadeos-stack">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
          The Stack · Three products · One thesis
        </div>
        <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter mb-4">
          Hot Shot TMS is <span style={{ color: HSTMS_CYAN }}>1 of 3</span> products on one cap table.
        </h2>
        <p className="text-slate-300 max-w-3xl leading-relaxed mb-10">
          JadeOS Quantum AI is the flagship. JadeOS-Agent Suite is the
          freight-vertical productization. Hot Shot TMS is the operator-built
          system of record. Same builder. Same persistent-memory substrate.
          One investable thesis.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a href="https://onejades.com/investors#stats" target="_blank" rel="noopener noreferrer"
             data-testid="jadeos-stack-product-1"
             className="block p-5 rounded-md border bg-white/[0.02] hover:bg-white/[0.04] transition"
             style={{ borderColor: `${HSTMS_CYAN}33` }}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: HSTMS_CYAN }}>
              Product 01 · Flagship
            </div>
            <div className="font-display text-2xl font-black mb-2">JadeOS Quantum AI</div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              The AI command center for builders, founders, and lifelong learners.
              50+ modules, voice-first "Hey Jade", persistent memory across modules.
              128-qubit Qiskit Aer + Claude Haiku 4.5.
            </p>
            <div className="text-[10px] font-mono text-slate-500">
              50+ MODULES · 128 QUBITS · BETA
            </div>
          </a>
          <a href="https://mpls-automation-hub.emergent.host/#agents" target="_blank" rel="noopener noreferrer"
             data-testid="jadeos-stack-product-2"
             className="block p-5 rounded-md border bg-white/[0.02] hover:bg-white/[0.04] transition"
             style={{ borderColor: `${HSTMS_CYAN}33` }}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: HSTMS_CYAN }}>
              Product 02 · Freight-vertical agents
            </div>
            <div className="font-display text-2xl font-black mb-2">JadeOS-Agent Suite</div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Six AI agents that sit on top of any TMS — Hot Shot or Descartes
              / McLeod / TMW. Rate-floor guard, audit chain, workflow memory,
              active claims — all production-class.
            </p>
            <div className="text-[10px] font-mono text-slate-500">
              6 AGENTS · 1 LIVE PROD · 2 LIVE PARTIAL
            </div>
          </a>
          <div data-testid="jadeos-stack-product-3"
               className="block p-5 rounded-md border-2 bg-white/[0.04]"
               style={{ borderColor: HSTMS_CYAN }}>
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: HSTMS_CYAN }}>
              Product 03 · You are here
            </div>
            <div className="font-display text-2xl font-black mb-2" style={{ color: HSTMS_CYAN }}>
              Hot Shot TMS
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-3">
              Operator-built transportation management for the hot-shot
              small-to-mid carrier segment that incumbent TMS vendors don't
              serve well. Build complete · deployment-ready · zero customers
              yet by design.
            </p>
            <div className="text-[10px] font-mono text-slate-500">
              BUILD COMPLETE · 6 MODES · READY TO DEPLOY
            </div>
          </div>
        </div>
        <div className="mt-6 text-xs text-slate-500 font-mono">
          Full three-product thesis →
          <a href="https://mpls-automation-hub.emergent.host/" target="_blank" rel="noopener noreferrer"
             className="ml-1 underline hover:no-underline" style={{ color: HSTMS_CYAN }}>
            mpls-automation-hub.emergent.host
          </a>
        </div>
      </section>

      {/* THE ASK */}
      <section id="ask" className="relative z-10 border-t border-white/5"
               style={{ background: `${HSTMS_BLUE}11` }}
               data-testid="hstms-ask">
        <div className="max-w-7xl mx-auto px-6 py-20 grid grid-cols-1 md:grid-cols-12 gap-10">
          <div className="md:col-span-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              The Ask
            </div>
            <h2 className="font-display text-4xl md:text-5xl font-black leading-tight tracking-tighter">
              <span style={{ color: HSTMS_CYAN }}>${(data.ask.amount_usd / 1_000_000).toFixed(1)}M</span> seed SAFE at a <span style={{ color: HSTMS_CYAN }}>${(data.ask.valuation_cap_usd / 1_000_000).toFixed(0)}M cap</span>.
            </h2>
            <p className="mt-5 text-slate-300 leading-relaxed max-w-md">
              {data.ask.discount_pct}% discount. Founder operates company. Most-Favored-Nation
              for the lead investor. Operating control retained.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href={downloadUrls.deck} target="_blank" rel="noopener noreferrer"
                 onClick={() => logDownload("deck")}
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-bold text-black"
                 style={{ background: HSTMS_CYAN }}>
                Full Deck <ArrowRight size={14} />
              </a>
              <a href="#intro"
                 className="inline-flex items-center gap-2 px-5 py-3 rounded-md border-2 transition-colors"
                 style={{ borderColor: HSTMS_CYAN, color: HSTMS_CYAN }}>
                Request the data room
              </a>
            </div>
          </div>
          <div className="md:col-span-7">
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3" style={{ color: HSTMS_CYAN }}>
              Milestone schedule
            </div>
            <div className="space-y-3">
              <MilestoneCard year={1} text={data.ask.milestone_year1} accent={HSTMS_CYAN} />
              <MilestoneCard year={2} text={data.ask.milestone_year2} accent={HSTMS_CYAN} />
              <MilestoneCard year={3} text={data.ask.milestone_year3} accent={HSTMS_CYAN} />
            </div>
            <div className="mt-6 p-4 rounded-md border bg-white/[0.02] flex items-center justify-between"
                 style={{ borderColor: `${HSTMS_CYAN}33` }}>
              <div className="text-sm text-slate-300">Market opportunity</div>
              <div className="text-right">
                <span className="font-mono font-bold mr-3" style={{ color: HSTMS_CYAN }}>
                  ${data.market.tam_usd_billion}B TAM
                </span>
                <span className="font-mono text-slate-400 mr-3 text-sm">
                  ${data.market.sam_usd_billion}B SAM
                </span>
                <span className="font-mono text-slate-500 text-sm">
                  ${data.market.som_year3_usd_million}M Y3 SOM
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* INVESTOR INTRO FORM */}
      <section id="intro" className="border-t border-white/5"
               data-testid="hstms-intro-form-section">
        <div className="max-w-3xl mx-auto px-6 py-20">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] mb-3 text-center" style={{ color: HSTMS_CYAN }}>
            30-minute deep-dive
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-black tracking-tighter mb-4 text-center">
            Let's <span style={{ color: HSTMS_CYAN }}>talk</span>.
          </h2>
          <p className="text-center text-slate-400 mb-9 max-w-xl mx-auto">
            Drop your details. Oliver replies within 24 hours with the full data room and three
            time slots for a 30-minute deep-dive.
          </p>

          {submitted ? (
            <div className="rounded-xl p-8 border-2 text-center"
                 style={{ borderColor: HSTMS_CYAN, background: `${HSTMS_CYAN}11` }}
                 data-testid="hstms-thanks">
              <CheckCircle2 size={42} style={{ color: HSTMS_CYAN }} className="mx-auto mb-3" />
              <h3 className="font-display text-2xl font-bold mb-2">Got it — thank you.</h3>
              <p className="text-slate-300 max-w-md mx-auto">
                Oliver will email you within 24 hours with the full data room and three time slots
                for a 30-minute deep-dive.
              </p>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3" data-testid="hstms-intro-form">
              <input type="text" name="website" value={form.website}
                     onChange={(e) => setForm({ ...form, website: e.target.value })}
                     style={{ position: "absolute", left: "-9999px" }} tabIndex={-1} autoComplete="off" />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Field label="Your name" required value={form.name} testId="hstms-name"
                       onChange={(v) => setForm({ ...form, name: v })} accent={HSTMS_CYAN} />
                <Field label="Email" type="email" required value={form.email} testId="hstms-email"
                       onChange={(v) => setForm({ ...form, email: v })} accent={HSTMS_CYAN} />
                <Field label="Firm (optional)" value={form.firm} testId="hstms-firm"
                       onChange={(v) => setForm({ ...form, firm: v })} accent={HSTMS_CYAN} />
                <Field label="Typical check size (optional)" value={form.check_size_usd}
                       placeholder="e.g. $250K–$1M" testId="hstms-check"
                       onChange={(v) => setForm({ ...form, check_size_usd: v })} accent={HSTMS_CYAN} />
              </div>
              <Field label="LinkedIn (optional)" value={form.linkedin}
                     placeholder="https://linkedin.com/in/…" testId="hstms-linkedin"
                     onChange={(v) => setForm({ ...form, linkedin: v })} accent={HSTMS_CYAN} />
              <div>
                <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 block mb-1.5">
                  Message (optional)
                </label>
                <textarea rows={4} value={form.message}
                          onChange={(e) => setForm({ ...form, message: e.target.value })}
                          data-testid="hstms-message"
                          className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm"
                          style={{ borderColor: "rgba(255,255,255,0.1)" }}
                          placeholder="What grabbed your attention?" />
              </div>
              <button type="submit" disabled={submitting}
                      data-testid="hstms-intro-submit"
                      className="w-full mt-2 px-5 py-3 rounded-md font-bold text-black flex items-center justify-center gap-2 disabled:opacity-60"
                      style={{ background: HSTMS_CYAN }}>
                <Send size={14} /> {submitting ? "Sending…" : "Request the data room"}
              </button>
              <p className="text-[10px] text-slate-500 text-center mt-2">
                We'll only ever use your details to send the data room and schedule a single intro
                call. No mailing list. No third-party sharing.
              </p>
            </form>
          )}
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-white/5 text-xs font-mono text-slate-500"
              data-testid="hstms-footer">
        <div className="max-w-7xl mx-auto px-6 py-10 flex justify-between flex-wrap gap-3">
          <div>© 2026 Hot Shot TMS · Built by Oliver Cummins · Plymouth, MN</div>
          <div className="flex items-center gap-4">
            <Link to="/about" className="hover:text-cyan-300">Overview</Link>
            <Link to="/login" className="hover:text-cyan-300">Sign In</Link>
            <a href="mailto:shearperfection369@gmail.com" className="hover:text-cyan-300">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Stat({ v, k }) {
  return (
    <div>
      <div className="font-display text-3xl md:text-4xl font-black text-cyan-300 tabular-nums">{v}</div>
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-400 mt-1">{k}</div>
    </div>
  );
}

function FounderStat({ v, k }) {
  return (
    <div className="p-3 rounded border border-white/10 bg-white/[0.02]">
      <div className="font-display text-3xl font-black text-cyan-300 tabular-nums">{v}</div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mt-1">{k}</div>
    </div>
  );
}

function Pill({ Icon, label }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-white/10 bg-white/[0.02] text-xs text-slate-300">
      <Icon size={11} style={{ color: HSTMS_CYAN }} /> {label}
    </div>
  );
}

function MilestoneCard({ year, text, accent }) {
  return (
    <div className="flex items-center gap-4 p-4 rounded-lg border bg-white/[0.02]"
         style={{ borderColor: "rgba(255,255,255,0.08)" }}>
      <div className="w-12 h-12 rounded-lg flex items-center justify-center font-black text-black font-display text-2xl shrink-0"
           style={{ background: accent }}>
        Y{year}
      </div>
      <div className="text-sm text-slate-200 leading-relaxed">{text}</div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", required = false, placeholder, accent, testId }) {
  return (
    <div>
      <label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 block mb-1.5">
        {label} {required && <span style={{ color: accent }}>*</span>}
      </label>
      <input
        type={type} value={value} required={required}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="w-full px-3 py-2 rounded border bg-[#0B1320] text-white text-sm"
        style={{ borderColor: "rgba(255,255,255,0.1)" }}
      />
    </div>
  );
}

function FeatureIcon({ idx }) {
  const icons = [Sparkles, Plug, Layers, Truck, BarChart3, ShieldCheck, FileText, Cpu, Zap, Building2];
  const Icon = icons[idx % icons.length];
  return <Icon size={16} style={{ color: HSTMS_CYAN }} />;
}

function setMetaTags() {
  const title = "Hot Shot TMS · Investor Executive Summary";
  const description = "One TMS · Any Company · 60 seconds to skin. Series Seed · $1.5M SAFE @ $8M cap. The first re-themable Transportation Management System. Built by a 13-year logistics practitioner.";
  const setMeta = (selector, attrs) => {
    let el = document.head.querySelector(selector);
    if (!el) {
      el = document.createElement("meta");
      Object.entries(attrs).forEach(([k, v]) => k !== "content" && el.setAttribute(k, v));
      document.head.appendChild(el);
    }
    el.setAttribute("content", attrs.content);
  };
  setMeta('meta[property="og:title"]',       { property: "og:title", content: title });
  setMeta('meta[property="og:description"]', { property: "og:description", content: description });
  setMeta('meta[property="og:type"]',        { property: "og:type", content: "website" });
  setMeta('meta[name="twitter:card"]',       { name: "twitter:card", content: "summary_large_image" });
  setMeta('meta[name="twitter:title"]',      { name: "twitter:title", content: title });
  setMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description });
  setMeta('meta[name="description"]',        { name: "description", content: description });
}
