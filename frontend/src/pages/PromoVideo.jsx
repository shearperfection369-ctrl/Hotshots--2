import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { TennantLogo } from "../components/TennantLogo";
import { useBranding } from "../lib/branding";
import {
  Truck, ShieldCheck, Receipt, Smartphone, Database, MessagesSquare,
  Video, BarChart3, Sparkles, FileWarning, Archive, Wrench, Palette, Quote,
  Mail, UserPlus, Volume2, Banknote, PackageCheck, Stamp, Plug, Server,
  Snowflake, Building2, Wallet, Calculator, BookOpen,
} from "lucide-react";

// Orisei brokerage-focused launch promo
const ORISEI_GOLD = "#C9A24A";
const ORISEI_NAVY = "#0E3A6B";

const FEATURES = [
  { Icon: PackageCheck,  title: "Named-Broker Accountability",   text: "One human owns your load from tender to POD. No call-center roulette. Direct cell, direct text." },
  { Icon: Stamp,         title: "Calafia-Stamped BOLs",          text: "Every Bill of Lading carries our heraldic seal. Professional paperwork, every time, no exceptions." },
  { Icon: Mail,          title: "POD in Your Inbox",             text: "Signed Proof of Delivery — with up to 3 dock photos — emailed the moment your freight is unloaded." },
  { Icon: Truck,         title: "Five Major Load Boards",        text: "DAT One · Truckstop · Convoy/Flexport · Uber Freight · 123Loadboard. Aggregated, ranked, and bid the same hour." },
  { Icon: Snowflake,     title: "Reefer · Cold Chain",           text: "FSMA-compliant pre-cool checks and continuous temperature logging on every reefer load." },
  { Icon: ShieldCheck,   title: "Carrier Vetting · Done Twice",  text: "MC, DOT, CSA, insurance, and CSA scores re-verified before every booking. No shadow trucks, no surprises." },
  { Icon: Sparkles,      title: "Margin-Aware Routing",          text: "Loads ranked by forecast margin and operator history before a quote ever leaves the desk." },
  { Icon: Banknote,      title: "Same-Day Carrier Pay",          text: "Built-in factoring hub keeps trusted carriers happy and prioritizing your freight first." },
  { Icon: BarChart3,     title: "Lane Economics",                text: "Margin per lane, RPM, dwell, and on-time history reported to you weekly. Numbers don't lie — and we don't hide them." },
];

const TECH_STACK = [
  { label: "Frontend",   value: "React 19 · Tailwind · Shadcn UI · Recharts · Leaflet" },
  { label: "Backend",    value: "FastAPI · MongoDB · WebSockets · ReportLab PDF" },
  { label: "Auth",       value: "Emergent-managed Google OAuth · RBAC (admin · auditor · dispatcher · driver)" },
  { label: "AI",         value: "Claude Sonnet 4.5 · Gemini 3 Nano-Banana imagery — via Emergent Universal Key" },
  { label: "Email",      value: "Resend · Orisei BOL + POD outbound" },
  { label: "Accounting", value: "QuickBooks Online · Intuit OAuth 2.0 token exchange" },
  { label: "Live Data",  value: "DAT One · Truckstop · Convoy/Flexport adapters with synthetic fallback" },
  { label: "Security",   value: "Fernet-encrypted Connections vault · httpOnly cookies · server-side RBAC" },
];

const PIPELINE = [
  { step: "1", title: "You Tender",       desc: "Send the load — email, phone, text, EDI. Within minutes a named broker has the lane, your rate floor, and the receiver's window in front of them." },
  { step: "2", title: "We Vet",           desc: "Carriers screened against MC/DOT, CSA, insurance, and our internal blacklist before a single dispatcher hits 'book'. No shadow trucks." },
  { step: "3", title: "We Cover",         desc: "Five aggregated load boards, ranked by margin and on-time history. Best truck for the job, not the cheapest one with a heartbeat." },
  { step: "4", title: "BOL on Tender",    desc: "The moment we book, the Calafia-stamped Bill of Lading lands in your inbox. No phone tag. No PDF surprises at midnight." },
  { step: "5", title: "We Watch",         desc: "Live GPS, dwell timers, weather alerts, dock photos. If something moves off-script, you hear from us — not the other way around." },
  { step: "6", title: "POD in Inbox",     desc: "Driver marks delivered → POD with up to 3 dock photos → emailed to your team in seconds. Cash flow starts the same day." },
];

export default function PromoVideo() {
  const { brand } = useBranding();
  const brandName = brand?.company_name || "Orisei Freight Solutions";
  const shortName = brand?.short_name || "Orisei";
  const founder = brand?.founder_first_name || "Oliver";

  // Brand-aware YouTube playlist: an admin can paste 2–3 video IDs into the brand
  // template field `promo_video_ids`. Falls back to a single curated freight trailer.
  const DEFAULT_TRAILER = "BvIfgEW2NQE"; // generic freight America trailer
  const brandVideoIds = (brand?.promo_video_ids || []).filter(Boolean);
  const playlist = brandVideoIds.length > 0 ? brandVideoIds : [DEFAULT_TRAILER];
  const [activeIdx, setActiveIdx] = useState(0);
  const activeVideoId = playlist[activeIdx] || playlist[0];
  const [hasLocalMp4, setHasLocalMp4] = useState(false);
  const [muted, setMuted] = useState(true);
  const videoRef = React.useRef(null);

  useEffect(() => { setActiveIdx(0); }, [brand?.brand_id]);

  useEffect(() => {
    fetch("/promo.mp4", { method: "HEAD" })
      .then((r) => {
        const ct = (r.headers.get("content-type") || "").toLowerCase();
        const len = parseInt(r.headers.get("content-length") || "0", 10);
        const isHtmlFallback = ct.includes("text/html") || ct.includes("application/json");
        setHasLocalMp4(r.ok && !isHtmlFallback && len > 100000);
      })
      .catch(() => setHasLocalMp4(false));
  }, []);

  const unmuteAndPlay = () => {
    setMuted(false);
    const v = videoRef.current;
    if (v) { v.muted = false; v.currentTime = 0; v.play().catch(() => {}); }
  };

  return (
    <>
      <Topbar
        title={`${shortName} · Launch Reel`}
        subtitle="Thirteen years of freight discipline, distilled into twelve seconds. Watch how a customer's load is handled from the moment it's tendered until the signed POD lands in their inbox."
      />
      <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">

        {/* Hero video */}
        <Card className="hud-surface overflow-hidden relative" data-testid="promo-hero">
          <div className="relative aspect-video bg-black">
            {hasLocalMp4 ? (
              <>
                <video
                  ref={videoRef}
                  src="/promo.mp4"
                  controls
                  autoPlay
                  muted={muted}
                  loop
                  playsInline
                  data-testid="promo-video"
                  className="w-full h-full object-cover"
                />
                {muted && (
                  <button
                    onClick={unmuteAndPlay}
                    data-testid="promo-unmute-btn"
                    className="absolute top-4 right-4 z-10 px-3.5 py-2 rounded-full font-mono text-xs font-bold uppercase tracking-wider shadow-lg transition flex items-center gap-2 animate-pulse"
                    style={{ background: ORISEI_GOLD, color: ORISEI_NAVY, boxShadow: "0 6px 20px -4px rgba(201,162,74,0.45)" }}
                    title="Click for narration + music"
                  >
                    <Volume2 size={14} /> Tap for sound
                  </button>
                )}
              </>
            ) : (
              <iframe
                key={activeVideoId}
                src={`https://www.youtube.com/embed/${activeVideoId}?rel=0&modestbranding=1&playsinline=1`}
                title={`${shortName} · Launch Promo`}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
                data-testid="promo-video-iframe"
                className="absolute inset-0 w-full h-full"
              />
            )}
          </div>

          {playlist.length > 1 && (
            <div className="px-6 pt-4 flex flex-wrap gap-2" data-testid="promo-playlist">
              {playlist.map((id, i) => (
                <button
                  key={id}
                  onClick={() => setActiveIdx(i)}
                  data-testid={`promo-playlist-${i}`}
                  className="px-3 py-1.5 rounded text-[11px] font-mono uppercase tracking-wider border transition"
                  style={
                    i === activeIdx
                      ? { background: ORISEI_GOLD, color: ORISEI_NAVY, borderColor: ORISEI_GOLD }
                      : { borderColor: "rgba(255,255,255,0.1)", color: "#94a3b8" }
                  }
                >
                  Video {i + 1}
                </button>
              ))}
            </div>
          )}

          <div className="p-6 md:p-8">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>
              {brandName} · 13 Years · Operator-Grade Freight
            </div>
            <h1 className="font-display text-4xl md:text-5xl font-black tracking-tighter leading-none">
              Thirteen years on the desk.<br/>
              <span style={{ color: ORISEI_GOLD }}>One mission:</span> move it right.
            </h1>
            <p className="mt-5 text-slate-300 text-lg max-w-3xl leading-relaxed">
              I'm {founder}, founder of {brandName}. After more than a decade booking,
              brokering, and babysitting freight for some of the toughest shippers in
              the country, I built this brokerage on one principle: <em
              style={{ color: ORISEI_GOLD }}>operator-grade discipline</em>.
              Every load runs through a margin-aware queue, every BOL carries
              the Calafia seal, every delivery is photographed and emailed before
              the customer has to ask. No silence. No surprises. No "let me check on it."
            </p>
            <p className="mt-3 text-slate-400 text-sm max-w-3xl leading-relaxed">
              When you tender a load to {brandName}, you get a named human accountable
              from pickup to POD — backed by a command deck most brokerages can't even
              afford to imagine. That's the deal.
            </p>
            <div className="mt-4 text-[10px] font-mono text-slate-500">
              {hasLocalMp4
                ? `Cinematic 12-second presentation · self-hosted · plays on any network.`
                : <>Trailer · default freight footage. Drop a rendered <code style={{ color: ORISEI_GOLD }}>/promo.mp4</code> into <code style={{ color: ORISEI_GOLD }}>/app/frontend/public</code> to swap automatically.</>}
            </div>
          </div>
        </Card>

        {/* Features */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>What you get</div>
          <h2 className="font-display text-3xl font-bold mb-6">Nine promises, kept on every load</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map(({ Icon, title, text }) => (
              <div
                key={title}
                className="p-5 rounded-lg border bg-white/[0.02] transition-all"
                style={{ borderColor: "rgba(201,162,74,0.15)" }}
                data-testid={`promo-feature-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              >
                <Icon size={22} strokeWidth={1.5} style={{ color: ORISEI_GOLD }} />
                <div className="mt-3 font-display font-semibold text-white">{title}</div>
                <div className="text-sm text-slate-400 mt-1.5 leading-relaxed">{text}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Operational Pipeline (replaces Tennant SAP flow) */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>Operational Architecture</div>
          <h2 className="font-display text-3xl font-bold mb-3 flex items-center gap-3">
            <Server size={26} style={{ color: ORISEI_GOLD }} /> What it looks like to ship with Orisei
          </h2>
          <p className="text-slate-400 mb-6 max-w-3xl">
            Six steps. Six promises. Every load — whether it's a one-off rescue
            cover at 11&nbsp;p.m. or a 200-load weekly program — runs through the
            same disciplined sequence. This is how thirteen years of freight
            instinct gets baked into every shipment we touch.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {PIPELINE.map((s) => (
              <div
                key={s.step}
                className="p-5 rounded-lg border bg-gradient-to-br from-amber-500/[0.04] to-transparent"
                style={{ borderColor: "rgba(201,162,74,0.18)" }}
                data-testid={`promo-pipeline-${s.step}`}
              >
                <div className="font-mono text-3xl font-bold leading-none" style={{ color: ORISEI_GOLD }}>{s.step}</div>
                <div className="font-display font-semibold text-white mt-2">{s.title}</div>
                <div className="text-xs text-slate-400 mt-1.5 leading-relaxed">{s.desc}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Owner credentials + trust signals */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>Why us</div>
          <h2 className="font-display text-3xl font-bold mb-6">Built by a 13-year freight veteran</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-slate-300 leading-relaxed">
                Before {brandName} existed, {founder} spent more than a decade
                booking, brokering, and babysitting freight for some of the
                toughest shippers in the country. He's covered hot loads at
                2&nbsp;a.m., chased lumper checks across three states, and re-routed
                a reefer around an interstate closure with a customer's CFO on
                speakerphone. That experience is why every promise on this page
                is a promise we actually keep.
              </p>
              <p className="text-slate-400 leading-relaxed mt-4">
                {brandName} was founded in Saint Paul, MN to bring that
                hard-won discipline to a brokerage that's small enough to care
                about your load and equipped enough to execute on it.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Spec label="Tenure" value="13+ years on dispatch desks before founding Orisei" />
              <Spec label="Coverage" value="48-state TL · LTL · Reefer · Flatbed · Step-Deck" />
              <Spec label="Authority" value="MC pending · BMC-84 surety bond · Contingent Cargo · E&O" />
              <Spec label="Carrier Pool" value="Vetted against MC/DOT/CSA before every booking" />
              <Spec label="Communication" value="Named broker with direct cell — answer in minutes, not hours" />
              <Spec label="Documentation" value="Calafia-stamped BOL + POD with photos in your inbox" />
            </div>
          </div>
        </Card>

        {/* Closing CTA */}
        <Card className="hud-surface p-8 md:p-12 text-center relative overflow-hidden">
          <div className="absolute inset-0 hud-scanline pointer-events-none"></div>
          <div className="flex justify-center">
            <TennantLogo size="lg" />
          </div>
          <h2 className="font-display text-3xl md:text-4xl font-black mt-6 tracking-tighter">
            Tender us your hardest load.
          </h2>
          <p className="text-slate-300 mt-3 max-w-xl mx-auto">
            One named broker. One signed BOL. One POD with photos in your inbox before
            the receiver hands the keys back. {brandName} runs freight the way
            it should have always been run.
          </p>
          <div className="mt-6 inline-flex items-center gap-2 text-[10px] font-mono tracking-[0.2em] uppercase" style={{ color: ORISEI_GOLD }}>
            <span className="w-2 h-2 rounded-full blink-dot" style={{ background: ORISEI_GOLD }}></span>
            13 years on the desk · MN-based · operator-grade discipline · proof in every POD
          </div>
        </Card>
      </div>
    </>
  );
}

function Spec({ label, value }) {
  return (
    <div className="p-3 rounded-md border border-white/5 bg-white/[0.02]">
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-slate-300 mt-1 text-xs leading-relaxed">{value}</div>
    </div>
  );
}
