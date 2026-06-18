import React, { useState } from "react";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, Image as ImageIcon, FileText, ExternalLink, Copy } from "lucide-react";
import { toast } from "sonner";

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
    dim: "2400 × 1339 px",
    sizeLabel: "~4.1 MB · PNG",
    badges: ["BROCHURE COVER", "LANDING HERO"],
    accent: "amber",
  },
  {
    id: "califia-watermark",
    title: "Subtle Corner Watermark",
    description: "Queen Califia with an elegant gold ORISEI monogram + wordmark in the bottom-right corner. Use as a presentation background, internal report cover, or social hero.",
    src: "/orisei-marketing/brand-assets/califia/califia-watermark.png",
    dim: "2400 × 1339 px",
    sizeLabel: "~4.7 MB · PNG",
    badges: ["PRESENTATION", "REPORT COVER"],
    accent: "cyan",
  },
  {
    id: "califia-social",
    title: "Social Share Card",
    description: "Optimized 1200 × 630 crop with a refined brand band — the exact aspect for LinkedIn, X / Twitter, and OpenGraph previews.",
    src: "/orisei-marketing/brand-assets/califia/califia-social.png",
    dim: "1200 × 630 px",
    sizeLabel: "~1.3 MB · PNG",
    badges: ["LINKEDIN", "OPENGRAPH", "TWITTER"],
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

const ACCENT_CLASS = {
  amber:   { border: "border-amber-400/50", text: "text-amber-300", bg: "bg-amber-500/15" },
  cyan:    { border: "border-cyan-400/40",  text: "text-cyan-300",  bg: "bg-cyan-500/15" },
  emerald: { border: "border-emerald-400/40",text:"text-emerald-300",bg: "bg-emerald-500/15" },
  red:     { border: "border-red-400/40",   text: "text-red-300",   bg: "bg-red-500/15" },
};

export default function BrandKit() {
  const [preview, setPreview] = useState(null);

  const copyLink = (src) => {
    const url = `${window.location.origin}${src}`;
    navigator.clipboard.writeText(url);
    toast.success("Asset URL copied to clipboard");
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
        </Card>

        {/* Asset cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {BRAND_ASSETS.map(a => {
            const acc = ACCENT_CLASS[a.accent];
            return (
              <Card key={a.id}
                    data-testid={`brand-${a.id}`}
                    className={`overflow-hidden bg-slate-950/60 border-2 ${acc.border} hover:scale-[1.005] transition`}>
                {/* Thumbnail */}
                <div className="relative aspect-video bg-slate-900 overflow-hidden group">
                  {a.isPdf ? (
                    <div className="absolute inset-0 grid place-items-center bg-gradient-to-br from-red-950/40 to-slate-950">
                      <FileText className="text-red-300" size={64} />
                    </div>
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
                      <a href={a.src} download
                         data-testid={`download-${a.id}`}
                         className={`inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-500 text-slate-950 hover:bg-amber-400 transition`}>
                        <Download size={12} /> Download
                      </a>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
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
          <img src={preview.src} alt={preview.title}
               className="max-w-[95vw] max-h-[90vh] rounded shadow-2xl" />
        </div>
      )}
    </>
  );
}
