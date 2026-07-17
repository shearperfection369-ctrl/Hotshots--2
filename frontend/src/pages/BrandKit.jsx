import React, { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, Image as ImageIcon, FileText, ExternalLink, Copy, Play, Film, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

/**
 * /brand-kit — Orisei downloadable brand assets.
 *
 * Currently hosts the Queen Califia heritage image in three watermark variants
 * plus a single-page brochure PDF. Add new asset families by appending to
 * BRAND_ASSETS below.
 */

const BRAND_ASSETS = [
  {
    id: "califia-hero",
    title: "Hero Brochure Cover",
    description: "Queen Califia with full ORISEI title block + tagline. Perfect for the front page of a sales deck, landing-page hero, or print brochure cover.",
    src: "/orisei-marketing/brand-assets/califia/califia-hero.png",
    videoSrc: "/orisei-marketing/brand-assets/califia/califia-hero.mp4",
    videoSizeLabel: "~1.1 MB · MP4 · 4 s",
    dim: "2400 × 1339 px",
    sizeLabel: "~4.1 MB · PNG",
    badges: ["BROCHURE COVER", "LANDING HERO", "ANIMATED"],
    accent: "amber",
  },
  {
    id: "califia-watermark",
    title: "Subtle Corner Watermark",
    description: "Queen Califia with an elegant gold ORISEI monogram + wordmark in the bottom-right corner. Use as a presentation background, internal report cover, or social hero.",
    src: "/orisei-marketing/brand-assets/califia/califia-watermark.png",
    videoSrc: "/orisei-marketing/brand-assets/califia/califia-watermark.mp4",
    videoSizeLabel: "~515 KB · MP4 · 4 s",
    dim: "2400 × 1339 px",
    sizeLabel: "~4.7 MB · PNG",
    badges: ["PRESENTATION", "REPORT COVER", "ANIMATED"],
    accent: "cyan",
  },
  {
    id: "califia-social",
    title: "Social Share Card",
    description: "Optimized 1200 × 630 crop with a refined brand band — the exact aspect for LinkedIn, X / Twitter, and OpenGraph previews.",
    src: "/orisei-marketing/brand-assets/califia/califia-social.png",
    videoSrc: "/orisei-marketing/brand-assets/califia/califia-social.mp4",
    videoSizeLabel: "~412 KB · MP4 · 4 s",
    dim: "1200 × 630 px",
    sizeLabel: "~1.3 MB · PNG",
    badges: ["LINKEDIN", "OPENGRAPH", "TWITTER", "ANIMATED"],
    accent: "emerald",
  },
  {
    id: "califia-brochure-pdf",
    title: "Brochure PDF (print-ready)",
    description: "Single-page print-ready PDF rendered from the hero cover, sized for 11×8.5 landscape spreads. Drop straight into a sales handout.",
    src: "/orisei-marketing/brand-assets/califia/orisei-califia-brochure.pdf",
    dim: "11 × 8.5 in · 150 DPI",
    sizeLabel: "~375 KB · PDF",
    badges: ["PRINT-READY", "BROCHURE"],
    isPdf: true,
    accent: "red",
  },
];

const LOGO_PACK_ASSETS = [
  {
    id: "logo-pack-pdf",
    title: "Official Logo Pack PDF (print-ready)",
    description: "Six-page launch pack: Queen Califia seal story, seal variations, wordmark + palette, and the full hoodie & headwear merch program with production specs. Send straight to your printer or embroiderer.",
    apiSrc: "/brokerage/logo-pack.pdf",
    fileName: "Orisei_Logo_Brand_Pack.pdf",
    src: "/brand/pack/seal_gold_light.png",
    dim: "8.5 × 11 in · 6 pages",
    sizeLabel: "PDF · Launch Edition",
    badges: ["PRINT-READY", "LAUNCH PACK", "MERCH SPECS"],
    isPdf: true,
    accent: "red",
  },
  {
    id: "launch-card-wide",
    title: "Launch Announcement — Wide",
    description: "\u201cWE'RE LIVE.\u201d launch-day card with the glowing Califia seal — sized for LinkedIn, X / Twitter, and OpenGraph link previews. Post it the day you go live.",
    src: "/brand/pack/launch_card_wide.png",
    dim: "1264 × 848 px",
    sizeLabel: "~1.3 MB · PNG",
    badges: ["LAUNCH DAY", "LINKEDIN", "TWITTER"],
    accent: "amber",
  },
  {
    id: "launch-card-square",
    title: "Launch Announcement — Square",
    description: "\u201cLAUNCH DAY\u201d square variant with corner ornaments — the exact aspect for Instagram, Facebook, and WhatsApp status posts.",
    src: "/brand/pack/launch_card_square.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.4 MB · PNG",
    badges: ["LAUNCH DAY", "INSTAGRAM", "SQUARE"],
    accent: "amber",
  },
  {
    id: "seal-gold-light",
    title: "Queen Califia Seal — Gold on Light",
    description: "Gold linework seal with curved ORISEI FREIGHT SOLUTIONS lettering, for letterhead, invoices, and light-background decks.",
    src: "/brand/pack/seal_gold_light.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.3 MB · PNG",
    badges: ["SEAL", "LETTERHEAD", "LIGHT BG"],
    accent: "amber",
  },
  {
    id: "seal-navy-mono",
    title: "Queen Califia Seal — Navy Official Stamp",
    description: "Single-color navy notary-style stamp version for contracts, BOLs, rate confirmations, and embossing dies.",
    src: "/brand/pack/seal_navy_mono.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.3 MB · PNG",
    badges: ["OFFICIAL STAMP", "CONTRACTS", "MONO"],
    accent: "cyan",
  },
  {
    id: "hoodie-front",
    title: "Hoodie Mockup — Front",
    description: "Navy pullover with the large gold Califia seal chest print. Spec: 9–10 in print, Califia Gold on Navy fleece.",
    src: "/brand/pack/hoodie_front.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.6 MB · PNG",
    badges: ["MERCH", "HOODIE", "MOCKUP"],
    accent: "emerald",
  },
  {
    id: "hoodie-back",
    title: "Hoodie Mockup — Back",
    description: "Zip hoodie back-print: ORISEI wordmark across the shoulders anchored by the seal. Spec: 11 in wide back print.",
    src: "/brand/pack/hoodie_back.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.6 MB · PNG",
    badges: ["MERCH", "HOODIE", "MOCKUP"],
    accent: "emerald",
  },
  {
    id: "hat-cap",
    title: "Structured Cap Mockup",
    description: "Navy structured cap with gold embroidered seal (2.5 in, metallic thread). The core carrier-partner giveaway.",
    src: "/brand/pack/hat_cap.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.4 MB · PNG",
    badges: ["MERCH", "CAP", "EMBROIDERY"],
    accent: "amber",
  },
  {
    id: "beanie-trucker",
    title: "Trucker + Beanie Mockup",
    description: "Trucker snapback with seal patch plus navy knit beanie with woven gold label — the onboarding kit bundle.",
    src: "/brand/pack/beanie_trucker.png",
    dim: "1024 × 1024 px",
    sizeLabel: "~1.5 MB · PNG",
    badges: ["MERCH", "BUNDLE", "MOCKUP"],
    accent: "cyan",
  },
];

const ACCENT_CLASS = {
  amber:   { border: "border-amber-400/50", text: "text-amber-300", bg: "bg-amber-500/15" },
  cyan:    { border: "border-cyan-400/40",  text: "text-cyan-300",  bg: "bg-cyan-500/15" },
  emerald: { border: "border-emerald-400/40",text:"text-emerald-300",bg: "bg-emerald-500/15" },
  red:     { border: "border-red-400/40",   text: "text-red-300",   bg: "bg-red-500/15" },
};

export default function BrandKit() {
  const [preview, setPreview] = useState(null);
  const [playingId, setPlayingId] = useState(null); // which card is showing its MP4
  const [downloadingId, setDownloadingId] = useState(null);

  const copyLink = (src) => {
    const url = `${window.location.origin}${src}`;
    navigator.clipboard.writeText(url);
    toast.success("Asset URL copied to clipboard");
  };

  const downloadApiPdf = async (a) => {
    setDownloadingId(a.id);
    try {
      const r = await api.get(a.apiSrc, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = a.fileName;
      link.click();
      URL.revokeObjectURL(url);
      toast.success("Logo pack PDF downloaded");
    } catch {
      toast.error("Failed to generate the logo pack PDF");
    } finally {
      setDownloadingId(null);
    }
  };

  const renderCard = (a) => {
    const acc = ACCENT_CLASS[a.accent];
    return (
      <Card key={a.id}
            data-testid={`brand-${a.id}`}
            className={`overflow-hidden bg-slate-950/60 border-2 ${acc.border} hover:scale-[1.005] transition`}>
        {/* Thumbnail */}
        <div className="relative aspect-video bg-slate-900 overflow-hidden group">
          {a.isPdf && !a.apiSrc ? (
            <div className="absolute inset-0 grid place-items-center bg-gradient-to-br from-red-950/40 to-slate-950">
              <FileText className="text-red-300" size={64} />
            </div>
          ) : playingId === a.id && a.videoSrc ? (
            <video src={a.videoSrc}
                   data-testid={`video-${a.id}`}
                   autoPlay loop muted playsInline
                   onClick={() => setPreview(a)}
                   className="absolute inset-0 w-full h-full object-cover cursor-zoom-in" />
          ) : (
            <img src={a.src} alt={a.title}
                 loading="lazy"
                 onClick={() => setPreview(a)}
                 className="absolute inset-0 w-full h-full object-cover cursor-zoom-in group-hover:scale-105 transition-transform duration-700" />
          )}
          <div className={`absolute top-2 left-2 flex gap-1 flex-wrap`}>
            {a.badges.map(b => (
              <Badge key={b} className={`${acc.bg} ${acc.text} ${acc.border} text-[9px]`}>{b}</Badge>
            ))}
          </div>
          {a.videoSrc && (
            <button
              type="button"
              data-testid={`toggle-anim-${a.id}`}
              onClick={() => setPlayingId(playingId === a.id ? null : a.id)}
              className="absolute bottom-2 right-2 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono uppercase tracking-widest bg-slate-950/80 border border-amber-400/40 text-amber-200 hover:bg-amber-500 hover:text-slate-950 transition">
              {playingId === a.id ? (<><ImageIcon size={11} /> Static</>) : (<><Play size={11} /> Play 4 s</>)}
            </button>
          )}
        </div>

        {/* Meta */}
        <div className="p-4 space-y-2">
          <div className="flex items-baseline justify-between gap-2">
            <div className="text-sm font-semibold text-white">{a.title}</div>
            <div className="text-[10px] text-slate-500 font-mono">{a.dim}</div>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{a.description}</p>
          <div className="flex items-center justify-between pt-2 border-t border-white/5">
            <span className="text-[10px] text-slate-500 font-mono">{a.sizeLabel}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="outline"
                      data-testid={`copy-${a.id}`}
                      onClick={() => copyLink(a.src)}
                      className="bg-slate-900 border-white/10 h-8 text-xs">
                <Copy size={11} className="mr-1" /> Link
              </Button>
              {!a.isPdf && (
                <a href={a.src} target="_blank" rel="noreferrer"
                   className="inline-flex items-center gap-1 px-2 py-1.5 rounded-md text-xs text-slate-300 bg-slate-900 border border-white/10 hover:border-cyan-400/40">
                  <ExternalLink size={11} /> Preview
                </a>
              )}
              {a.apiSrc ? (
                <button type="button"
                        data-testid={`download-${a.id}`}
                        disabled={downloadingId === a.id}
                        onClick={() => downloadApiPdf(a)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition disabled:opacity-60">
                  {downloadingId === a.id ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} PDF
                </button>
              ) : (
                <a href={a.src} download
                   data-testid={`download-${a.id}`}
                   className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition`}>
                  <Download size={12} /> {a.isPdf ? "PDF" : "PNG"}
                </a>
              )}
              {a.videoSrc && (
                <a href={a.videoSrc} download
                   data-testid={`download-video-${a.id}`}
                   title={`Download animated MP4 — ${a.videoSizeLabel}`}
                   className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-slate-900 text-amber-200 border border-amber-400/40 hover:bg-amber-500 hover:text-slate-950 transition">
                  <Film size={12} /> MP4
                </a>
              )}
            </div>
          </div>
        </div>
      </Card>
    );
  };

  return (
    <>
      <Topbar
        title="Brand Kit"
        subtitle="Queen Califia heritage assets · watermarked + ready to ship"
      />
      <div className="p-4 md:p-6 space-y-5">
        {/* Hero summary */}
        <Card className="p-5 bg-gradient-to-br from-slate-950 via-amber-950/20 to-slate-950 border-amber-400/30">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-11 h-11 rounded-lg grid place-items-center font-orisei text-xl"
                 style={{ background: "linear-gradient(135deg,#E0B85C,#B08A36)", color: "#0A2D55" }}>
              O
            </div>
            <div>
              <div className="font-orisei text-2xl text-amber-300">Orisei Brand Kit</div>
              <div className="text-xs text-slate-400 font-mono uppercase tracking-widest">
                Queen Califia · Spirit of the West · 2026
              </div>
            </div>
          </div>
          <p className="text-sm text-slate-300 max-w-3xl">
            Every asset below carries the official ORISEI wordmark in Cormorant-style serif
            with the gold-on-navy palette. Use the <b className="text-amber-300">Hero Brochure</b> for
            landing pages and decks, the <b className="text-cyan-300">Subtle Watermark</b> for internal
            reports, and the <b className="text-emerald-300">Social Card</b> for LinkedIn / Twitter
            previews. Print-ready PDF lives at the bottom.
          </p>
          <p className="text-xs text-amber-200/80 mt-2 font-mono uppercase tracking-widest">
            New · 4-second animated MP4 variants — tap <span className="text-amber-300">Play 4 s</span> on any card to preview the wordmark fade-in.
          </p>
        </Card>

        {/* Asset cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {BRAND_ASSETS.map(a => renderCard(a))}
        </div>

        {/* Logo Pack — launch edition */}
        <Card className="p-5 bg-gradient-to-br from-slate-950 via-blue-950/30 to-slate-950 border-amber-400/30" data-testid="logo-pack-section">
          <div className="font-orisei text-2xl text-amber-300">Official Logo Pack · Launch Edition</div>
          <div className="text-xs text-slate-400 font-mono uppercase tracking-widest mt-1 mb-2">
            Queen Califia Seal · Variations · Hoodie & Hat Merch Program
          </div>
          <p className="text-sm text-slate-300 max-w-3xl">
            Everything you need to launch: the print-ready <b className="text-amber-300">6-page Logo Pack PDF</b> with
            seal usage rules, palette, and production specs — plus every seal variation and apparel mockup
            as individual high-res PNGs for your printer, embroiderer, or web team.
          </p>
        </Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {LOGO_PACK_ASSETS.map(a => renderCard(a))}
        </div>

        {/* Usage guidelines */}
        <Card className="p-5 bg-slate-950/60 border-white/10">
          <div className="text-xs font-mono uppercase tracking-widest text-amber-300 mb-3">
            Usage Guidelines
          </div>
          <ul className="text-sm text-slate-300 space-y-1.5 list-disc pl-5">
            <li>Wordmark <b className="text-amber-300">ORISEI</b> is set in Liberation/Cormorant Garamond — never substitute a sans-serif.</li>
            <li>Brand colors: <span className="text-amber-300">Gold #E0B85C → #B08A36</span> · <span className="text-cyan-300">Navy #0A2D55</span> · <span className="text-slate-200">Off-white #F8FAFC</span>.</li>
            <li>Do not crop the Queen Califia & griffin figure out of the frame in any brand placement — the spirit is the brand.</li>
            <li>For darker backgrounds, prefer the watermark variant; for light decks, prefer the hero.</li>
            <li>Need a custom size or format (SVG, EPS, square 1080)? Ping the design team.</li>
          </ul>
        </Card>
      </div>

      {/* Lightbox */}
      {preview && (
        <div onClick={() => setPreview(null)}
             className="fixed inset-0 z-50 bg-black/90 grid place-items-center p-6 cursor-zoom-out"
             data-testid="brand-lightbox">
          {playingId === preview.id && preview.videoSrc ? (
            <video src={preview.videoSrc} autoPlay loop muted playsInline controls
                   className="max-w-[95vw] max-h-[90vh] rounded shadow-2xl" />
          ) : (
            <img src={preview.src} alt={preview.title}
                 className="max-w-[95vw] max-h-[90vh] rounded shadow-2xl" />
          )}
        </div>
      )}
    </>
  );
}
