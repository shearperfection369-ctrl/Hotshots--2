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
  { Icon: Truck,         title: "Five-Board Aggregator",        text: "DAT One · Truckstop · Convoy/Flexport · Uber Freight · 123Loadboard — one ranked queue with margin forecasts." },
  { Icon: Stamp,         title: "Orisei BOLs · Beautiful PDFs", text: "Heraldic Calafia-stamped Bills of Lading rendered in seconds — every party, freight line, and charge structured cleanly." },
  { Icon: PackageCheck,  title: "Proof of Delivery + Photos",   text: "Capture up to 3 dock photos, mark delivered in one tap, email the signed POD to the customer instantly." },
  { Icon: Mail,          title: "Auto-Mail Automation",         text: "Toggle BOL-on-tender and POD-on-delivery — the customer rhythm runs without dispatcher clicks." },
  { Icon: Banknote,      title: "Factoring Hub",                text: "Triumph · Apex · OTR · TBS · RTS — live advance rates, fuel-card balances, NOA letters, and verified factor health pings." },
  { Icon: Calculator,    title: "Live Cost Analysis",           text: "30-day projected burn with tuners for headcount, factor fees, fuel, and tech. Sparkline trend in real time." },
  { Icon: Wallet,        title: "Brokerage Accounting",         text: "AR aging · margin per load · 1099 contractor ledger · QuickBooks Online OAuth sync (real, not mocked)." },
  { Icon: Building2,     title: "Investor Outreach",            text: "One-click LP pitch: business plan PDF, cap table, personalised note — delivered via Resend." },
  { Icon: UserPlus,      title: "Driver & Carrier Roster",      text: "MC/DOT/CDL/SCAC tracking · COI, W-9, contracts · scoped portal invites in a single click." },
  { Icon: BookOpen,      title: "Brokerage Business Plan",      text: "Live-rendered Orisei business plan tab, plus the Cost Analysis and Home-Office Setup playbooks built in." },
  { Icon: ShieldCheck,   title: "Forms Library · DOT-Ready",    text: "FMCSA · BOI · ELD · IFTA — every legal form generates as a clean PDF with the Calafia mark stamped on top." },
  { Icon: Plug,          title: "Connections Vault",            text: "Fernet-encrypted API key locker for DAT, Truckstop, Resend, QuickBooks, Stripe, and custom providers. One paste, everything wakes up." },
  { Icon: Sparkles,      title: "HUDLINK AI Co-Pilot",          text: "Claude Sonnet 4.5 trained on Orisei context — load scoring, carrier strategy, MC vetting, lane economics." },
  { Icon: Snowflake,     title: "Reefer · Temp Compliance",     text: "FSMA Sanitary Transport Rule guardrails, pre-cool checks, and continuous temperature logging baked in." },
  { Icon: Smartphone,    title: "Mobile-First Driver View",     text: "No-login GPS check-in, fuel/odometer capture, and POD photo capture — works on any smartphone." },
  { Icon: FileWarning,   title: "Claims & Damage Tracking",     text: "OS&D logging · 49 CFR §370 timers · concealed-damage 15-day rule alerts." },
  { Icon: BarChart3,     title: "KPI Reports",                  text: "Margin per lane, factor advance velocity, broker time-to-pay, on-time delivery — PDF or XLSX in two clicks." },
  { Icon: Palette,       title: "Multi-Tenant White-Label",     text: "Swap branding, logos, palette, and copy per tenant. Orisei is one of many — the platform speaks every brand." },
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
  { step: "1", title: "Connections Vault",     desc: "Operator pastes DAT, Truckstop, Convoy, Resend, QuickBooks keys into the encrypted vault. Nothing leaves the perimeter unencrypted." },
  { step: "2", title: "Five-Board Pull",       desc: "Adapters fan out concurrently to each load board. The board badge flips LIVE API FEED when a real key resolves, otherwise SYNTHETIC FALLBACK keeps the desk warm." },
  { step: "3", title: "Margin Scoring",        desc: "Each posting normalized into Orisei-shape: RPM, forecast margin $, carrier pay, age, and AI tags. Ranked queue surfaces highest-margin loads first." },
  { step: "4", title: "Book + Carrier Onboard",desc: "One-click book pulls MC, DOT, SCAC, CSA. Carrier packet emails on send. NOA assigned to the factor in the same step." },
  { step: "5", title: "BOL + Auto-Tender",     desc: "Calafia-stamped BOL renders on customer-attach. Auto-mail BOL toggle ships the PDF the moment customer email is captured." },
  { step: "6", title: "POD + Settlement",      desc: "Driver marks delivered → POD with embedded dock photos auto-mails to the customer. Settlement writes back to QuickBooks Online via OAuth." },
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
        title={`${shortName} · v3.0 Launch`}
        subtitle="A cinematic tour through the Orisei Freight Solutions command deck — five-board aggregator, Calafia BOLs, auto-mail POD, factoring hub, QuickBooks OAuth, and the encrypted Connections vault."
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
              {brandName} · Freight Brokerage Command Deck · v3.0 Launch
            </div>
            <h1 className="font-display text-4xl md:text-5xl font-black tracking-tighter leading-none">
              Five Boards.<br/>
              <span style={{ color: ORISEI_GOLD }}>One ranked queue.</span> Total command.
            </h1>
            <p className="mt-5 text-slate-300 text-lg max-w-3xl leading-relaxed">
              {founder} — and every operator who works a board for a living — meet the
              brokerage command deck we built from scratch. Five major load boards
              aggregated into a margin-aware queue, Queen-Calafia-stamped BOLs and PODs,
              automated customer mailing, a factoring hub for cash-flow visibility, real
              QuickBooks OAuth, and an encrypted Connections vault that turns the whole
              platform on the moment you paste a key.
            </p>
            <div className="mt-4 text-[10px] font-mono text-slate-500">
              {hasLocalMp4
                ? `Cinematic · 20-slide branded tour of ${shortName} v3.0 · AI narration + ambient music · self-hosted, plays on any network.`
                : <>Trailer · default freight footage. Drop a rendered <code style={{ color: ORISEI_GOLD }}>/promo.mp4</code> into <code style={{ color: ORISEI_GOLD }}>/app/frontend/public</code> to swap automatically.</>}
            </div>
          </div>
        </Card>

        {/* Features */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>What it delivers</div>
          <h2 className="font-display text-3xl font-bold mb-6">Features & Benefits</h2>
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
            <Server size={26} style={{ color: ORISEI_GOLD }} /> From key-paste to settled load
          </h2>
          <p className="text-slate-400 mb-6 max-w-3xl">
            The platform's day-one win: paste your DAT, Truckstop, Resend, and QuickBooks
            keys into the Connections vault and every downstream surface lights up at
            once — no rebuild, no redeploy. Here's the six-stage hand-off the platform runs
            for every load.
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

        {/* Technical Stack */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-2" style={{ color: ORISEI_GOLD }}>Under the Hood</div>
          <h2 className="font-display text-3xl font-bold mb-6">Technical Foundation</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TECH_STACK.map((s) => (
              <div
                key={s.label}
                className="p-4 rounded-md border bg-white/[0.02] flex items-start gap-4"
                style={{ borderColor: "rgba(255,255,255,0.05)" }}
              >
                <div className="text-[10px] font-mono uppercase tracking-wider w-28 shrink-0 pt-0.5" style={{ color: ORISEI_GOLD }}>{s.label}</div>
                <div className="text-sm text-slate-200 font-mono leading-relaxed">{s.value}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <Spec label="Deployment" value="Cloud-native · Kubernetes · zero-downtime rolling updates" />
            <Spec label="Security" value="Fernet-encrypted vault · OAuth 2.0 · server-side RBAC" />
            <Spec label="Mobile" value="PWA-ready · driver POD capture works on any modern smartphone" />
          </div>
        </Card>

        {/* Closing CTA */}
        <Card className="hud-surface p-8 md:p-12 text-center relative overflow-hidden">
          <div className="absolute inset-0 hud-scanline pointer-events-none"></div>
          <div className="flex justify-center">
            <TennantLogo size="lg" />
          </div>
          <h2 className="font-display text-3xl md:text-4xl font-black mt-6 tracking-tighter">
            Ready when you are, {founder}.
          </h2>
          <p className="text-slate-300 mt-3 max-w-xl mx-auto">
            Launch the dashboard, paste your API keys into Connections, and let the
            five-board queue, auto-mail rhythm, and Calafia-stamped paperwork run while
            you focus on the lanes that pay.
          </p>
          <div className="mt-6 inline-flex items-center gap-2 text-[10px] font-mono tracking-[0.2em] uppercase" style={{ color: ORISEI_GOLD }}>
            <span className="w-2 h-2 rounded-full blink-dot" style={{ background: ORISEI_GOLD }}></span>
            v3.0 · Orisei Launch · 5 boards · 4 factors · QB OAuth · Auto-Mail · 200+ endpoints · AI narration
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
