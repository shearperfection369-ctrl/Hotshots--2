import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { TennantLogo } from "../components/TennantLogo";
import {
  Truck, Plane, Ship, Package, Train, Sparkles, ShieldCheck, Receipt,
  Smartphone, Database, MessagesSquare, Video, BarChart3, Globe2,
  FileWarning, Archive, Factory, Wrench, Gamepad2, Palette, Quote, Mail, UserPlus
} from "lucide-react";

const FEATURES = [
  { Icon: Truck, title: "All Modes, One Glass", text: "TL · LTL · Parcel · Ocean · Air · Rail in a single mission-control view." },
  { Icon: Receipt, title: "Freight Audit & Pay", text: "Auto-detect overcharges in accessorials. Approve, pay, or dispute in clicks." },
  { Icon: FileWarning, title: "Payments & Claims", text: "File damage / shortage / overcharge claims. Track recovery rate $ and %." },
  { Icon: ShieldCheck, title: "Carrier Onboarding", text: "MC/DOT/SCAC/CSA · W-9, COI, contracts. Send Tennant Onboarding Packet email in one click." },
  { Icon: UserPlus, title: "Carrier Invites + Scoped Portal", text: "Tokenized invites grant carriers read-mostly access to only their own loads — no admin help." },
  { Icon: Smartphone, title: "Driver Mobile Check-In", text: "GPS, fuel, odometer, and status — no login required. Auto-updates the dashboard." },
  { Icon: Database, title: "SAP S/4HANA OData", text: "Live SO/PO sync. Pull-from-SAP auto-fills Book Load reference, delivery, commodity." },
  { Icon: Archive, title: "Document Vault", text: "Insurance COIs · W-9 · MSDS · contracts — GridFS-backed with expiry tracking." },
  { Icon: Globe2, title: "Trade Compliance", text: "18 HTS codes · USMCA/KORUS/FTZ · Section 301/232 · Sanctions screening · ACE filings." },
  { Icon: Factory, title: "Supplier Sourcing", text: "20 suppliers tracked · risk scores · single-source alerts · annual spend by country." },
  { Icon: Wrench, title: "Machine Catalog", text: "17 current Tennant models with full-color photos, specs, NMFC codes, prices." },
  { Icon: Mail, title: "Email Composers", text: "One-click routing guides, carrier ETA/POD requests, KPI report emails — copy or open in mail client." },
  { Icon: Video, title: "Cisco Webex", text: "Post shipment alerts to Spaces. Schedule meetings without leaving the TMS." },
  { Icon: Sparkles, title: "HUDLINK AI Co-Pilot", text: "Claude Sonnet 4.5 trained on Tennant context — HS codes, carrier strategy, customs." },
  { Icon: BarChart3, title: "KPI Reports", text: "On-time rates, lane economics, weekly weights. Download PDF/XLSX or email instantly." },
  { Icon: Gamepad2, title: "Arcade · Tournaments", text: "Connect 4 with challenges, brackets, trophies, and a tiered leaderboard. Lunch-break friendly." },
  { Icon: Palette, title: "7 Visual Themes", text: "HUD Cyan, Forest, Sunset, Arctic, Lavender, Mocha, Solar Light — pick what fits your shift." },
  { Icon: Quote, title: "Quotes Ticker", text: "100 curated motivational quotes rotate ambiently at the top of the Command Center." },
];

const TECH_STACK = [
  { label: "Frontend", value: "React 19 · Tailwind · Shadcn UI · Recharts · Leaflet" },
  { label: "Backend", value: "FastAPI · MongoDB · WebSockets · ReportLab PDF" },
  { label: "Auth", value: "Emergent-managed Google OAuth · RBAC (admin/auditor/dispatcher/driver)" },
  { label: "AI", value: "Claude Sonnet 4.5 via Emergent Universal Key" },
  { label: "Video", value: "Sora 2 (this promo was AI-generated)" },
  { label: "Live Data", value: "Open-Meteo Weather · OSM Map Tiles · Real-time WebSocket Chat" },
  { label: "Capacity", value: "250 concurrent users · 3 manufacturing facilities" },
];

const SAP_FLOW = [
  { step: "1", title: "Authentication", desc: "OAuth 2.0 SAML Bearer Assertion against SAP IdP — service account TMS_SVC_ACCT, client 100." },
  { step: "2", title: "OData Pull", desc: "API_SALES_ORDER_SRV for SO data, API_PURCHASEORDER_PROCESS_SRV for PO data — filtered by plant code." },
  { step: "3", title: "Plant Mapping", desc: "1010 → Golden Valley MN · 1020 → Holland MI · 1030 → Louisville KY. Auto-routed to nearest carrier lane." },
  { step: "4", title: "Trigger Booking", desc: "SO with status 'Released to Shipping' → auto-create TMS shipment with matching origin facility & Incoterms." },
  { step: "5", title: "PO Inbound", desc: "Imports from Kuehne+Nagel pulled via PO API; container tracking auto-linked to inbound shipments." },
  { step: "6", title: "Write-Back", desc: "Delivery confirmation & POD posted back to SAP via OData PATCH on the linked PO/SO." },
];

export default function PromoVideo() {
  // Tennant Company official trailer — embedded so it launches reliably
  // without depending on Sora 2 generation or local /promo.mp4 asset.
  const TENNANT_TRAILER_ID = "mTxE3g7o4aY"; // "Tennant is Everywhere | Company Trailer"
  const [hasLocalMp4, setHasLocalMp4] = useState(false);

  useEffect(() => {
    // SPA serves index.html for unknown paths (text/html), which we MUST
    // exclude. But production CDN sometimes labels static .mp4 files as
    // 'application/octet-stream' instead of 'video/mp4' — that's still a
    // real video, so we accept anything that ISN'T html/json and that has
    // a non-trivial Content-Length (the real promo is ~1 MB).
    fetch("/promo.mp4", { method: "HEAD" })
      .then((r) => {
        const ct = (r.headers.get("content-type") || "").toLowerCase();
        const len = parseInt(r.headers.get("content-length") || "0", 10);
        const isHtmlFallback = ct.includes("text/html") || ct.includes("application/json");
        setHasLocalMp4(r.ok && !isHtmlFallback && len > 100000);
      })
      .catch(() => setHasLocalMp4(false));
  }, []);

  return (
    <>
      <Topbar title="TMS Launch · 2026 Update" subtitle="A cinematic tour through TMS v1.9 — Truckload Booking Sheet, Equipment Yard Analytics, drag-drop Command, Documents, AI Co-Pilot & more" />
      <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">

        {/* Hero with video — YouTube iframe is the most reliable embed */}
        <Card className="hud-surface overflow-hidden relative" data-testid="promo-hero">
          <div className="relative aspect-video bg-black">
            {hasLocalMp4 ? (
              <video
                src="/promo.mp4"
                controls
                autoPlay
                muted
                loop
                playsInline
                data-testid="promo-video"
                className="w-full h-full object-cover"
              />
            ) : (
              <iframe
                src={`https://www.youtube.com/embed/${TENNANT_TRAILER_ID}?rel=0&modestbranding=1&playsinline=1`}
                title="Tennant is Everywhere — Company Trailer"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
                data-testid="promo-video-iframe"
                className="absolute inset-0 w-full h-full"
              />
            )}
          </div>
          <div className="p-6 md:p-8">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Tennant Companies · Transportation Management System</div>
            <h1 className="font-display text-4xl md:text-5xl font-black tracking-tighter leading-none">
              One Glass.<br/>
              <span className="text-cyan-400">Every Mode.</span> Total Command.
            </h1>
            <p className="mt-5 text-slate-300 text-lg max-w-3xl leading-relaxed">
              Kirk — and the entire Tennant transportation team — meet the mission-control TMS we&apos;ve built for you. From Golden Valley to Holland to Louisville, every truck, container, pallet, and parcel now reports to a single command center, in real time.
            </p>
            <div className="mt-4 text-[10px] font-mono text-slate-500">
              {hasLocalMp4
                ? "Cinematic · 13-slide branded tour of Tennant TMS v1.9 · 39s · self-hosted, plays on any network."
                : <>Trailer · Tennant Equipment Insights (official YouTube). Drop a Sora 2-rendered <code className="text-cyan-300">/promo.mp4</code> into <code className="text-cyan-300">/app/frontend/public</code> to swap automatically.</>}
            </div>
          </div>
        </Card>

        {/* Features */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">What it delivers</div>
          <h2 className="font-display text-3xl font-bold mb-6">Features & Benefits</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map(({ Icon, title, text }) => (
              <div key={title} className="p-5 rounded-lg border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 hover:bg-cyan-500/[0.04] transition-all">
                <Icon size={22} className="text-cyan-400" strokeWidth={1.5} />
                <div className="mt-3 font-display font-semibold text-white">{title}</div>
                <div className="text-sm text-slate-400 mt-1.5 leading-relaxed">{text}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* SAP Integration deep-dive */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Integration Architecture</div>
          <h2 className="font-display text-3xl font-bold mb-3 flex items-center gap-3"><Database size={26} className="text-cyan-400" /> SAP S/4HANA Connection</h2>
          <p className="text-slate-400 mb-6 max-w-3xl">
            The TMS speaks native OData to your existing S/4HANA instance — no middleware bus, no flat-file batches. Sales orders and purchase orders flow continuously into the dispatcher&apos;s view; delivery confirmations write back the moment a load is delivered.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {SAP_FLOW.map((s) => (
              <div key={s.step} className="p-5 rounded-lg border border-cyan-500/15 bg-gradient-to-br from-cyan-500/[0.03] to-transparent">
                <div className="font-mono text-3xl font-bold text-cyan-400 leading-none">{s.step}</div>
                <div className="font-display font-semibold text-white mt-2">{s.title}</div>
                <div className="text-xs text-slate-400 mt-1.5 leading-relaxed">{s.desc}</div>
              </div>
            ))}
          </div>
        </Card>

        {/* Technical stack */}
        <Card className="hud-surface p-6 md:p-8">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Under the Hood</div>
          <h2 className="font-display text-3xl font-bold mb-6">Technical Requirements</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {TECH_STACK.map((s) => (
              <div key={s.label} className="p-4 rounded-md border border-white/5 bg-white/[0.02] flex items-start gap-4">
                <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 w-28 shrink-0 pt-0.5">{s.label}</div>
                <div className="text-sm text-slate-200 font-mono leading-relaxed">{s.value}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            <Spec label="Deployment" value="Cloud-native · Kubernetes · zero-downtime rolling updates" />
            <Spec label="Security" value="OAuth 2.0 · httpOnly cookies · RBAC enforced server-side" />
            <Spec label="Mobile" value="PWA-ready · driver console runs on any modern smartphone, no app store" />
          </div>
        </Card>

        {/* Closing CTA */}
        <Card className="hud-surface p-8 md:p-12 text-center relative overflow-hidden">
          <div className="absolute inset-0 hud-scanline pointer-events-none"></div>
          <TennantLogo size="lg" />
          <h2 className="font-display text-3xl md:text-4xl font-black mt-6 tracking-tighter">Ready when you are, Kirk.</h2>
          <p className="text-slate-300 mt-3 max-w-xl mx-auto">
            Launch the dashboard, share driver links with your fleet, and let HUDLINK answer the hard questions while you focus on lanes that matter.
          </p>
          <div className="mt-6 inline-flex items-center gap-2 text-[10px] font-mono text-cyan-400 tracking-[0.2em] uppercase">
            <span className="w-2 h-2 rounded-full bg-cyan-400 blink-dot"></span>
            v1.9 · 2026 Update · Live for 250 users · 30+ modules · 100+ API endpoints
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
