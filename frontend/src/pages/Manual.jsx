import React, { useEffect, useState, useMemo, useCallback } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Download, ChevronLeft, ChevronRight, BookOpen, Sparkles, ArrowRight, ListChecks } from "lucide-react";

export default function Manual() {
  const [data, setData] = useState(null);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    api.get("/manual/content").then(({ data }) => setData(data));
  }, []);

  const slides = data?.slides || [];
  const slide = slides[idx];

  const go = useCallback((delta) => {
    setIdx((i) => Math.max(0, Math.min(slides.length - 1, i + delta)));
  }, [slides.length]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight") go(1);
      if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go]);

  const onDownload = () => {
    // open in new tab; browser will use cookie auth
    window.open(`${BACKEND_URL}/api/manual/download`, "_blank");
  };

  const sections = useMemo(() => {
    const out = [];
    slides.forEach((s, i) => {
      if (s.kind === "section" || s.kind === "cover" || s.kind === "toc" || s.kind === "closing") {
        out.push({ idx: i, label: s.title });
      }
    });
    return out;
  }, [slides]);

  if (!data) return (<><Topbar title="User Manual" /><div className="p-8 text-slate-400">Loading manual…</div></>);

  return (
    <>
      <Topbar
        title="User Manual"
        subtitle={`In-app walkthrough · ${slides.length} slides · keyboard arrows to navigate`}
      />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-5">
        {/* Section nav */}
        <Card className="hud-surface p-3 h-fit lg:sticky lg:top-4" data-testid="manual-sections">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 px-2 py-1">Chapters</div>
          <div className="space-y-1 mt-1">
            {sections.map((sec) => (
              <button
                key={sec.idx}
                onClick={() => setIdx(sec.idx)}
                data-testid={`manual-section-${sec.idx}`}
                className={`w-full text-left px-2.5 py-1.5 rounded text-xs transition-all ${
                  idx === sec.idx ? "bg-cyan-500/15 text-cyan-300 border-l-2 border-cyan-400" : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
                }`}
              >{sec.label}</button>
            ))}
          </div>
          <Button
            onClick={onDownload}
            data-testid="manual-download-btn"
            className="w-full mt-3 bg-cyan-500 hover:bg-cyan-600 text-black font-bold flex items-center gap-2"
          >
            <Download size={14} /> Download .PPTX
          </Button>
          <div className="text-[10px] font-mono text-slate-500 text-center mt-2">Tennant_TMS_User_Manual.pptx</div>
        </Card>

        {/* Slide viewer */}
        <Card className="hud-surface p-0 overflow-hidden" data-testid="manual-deck">
          <SlideView slide={slide} />
          <div className="border-t border-white/5 bg-[#0B0E14] flex items-center justify-between px-5 py-3">
            <button onClick={() => go(-1)} disabled={idx === 0} data-testid="manual-prev" className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-slate-400 hover:text-cyan-300 disabled:opacity-30">
              <ChevronLeft size={14} /> Prev
            </button>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
              Slide <span className="text-cyan-300">{idx + 1}</span> / {slides.length}
            </div>
            <button onClick={() => go(1)} disabled={idx === slides.length - 1} data-testid="manual-next" className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 disabled:opacity-30">
              Next <ChevronRight size={14} />
            </button>
          </div>
        </Card>
      </div>
    </>
  );
}

function SlideView({ slide }) {
  if (!slide) return null;
  const kind = slide.kind;

  if (kind === "cover") {
    return (
      <div className="aspect-video bg-gradient-to-br from-[#0B0E14] via-[#0B0E14] to-[#101720] p-10 md:p-14 flex flex-col justify-center">
        <div className="text-[11px] font-mono uppercase tracking-[0.3em] text-cyan-400 flex items-center gap-2">
          <Sparkles size={14} /> {slide.eyebrow}
        </div>
        <div className="h-[3px] w-24 bg-cyan-400 mt-3 hud-glow-cyan" />
        <h1 className="font-display text-4xl md:text-6xl font-bold text-white mt-6 leading-tight">{slide.title}</h1>
        <p className="text-slate-400 text-lg md:text-2xl mt-4 font-light max-w-3xl">{slide.subtitle}</p>
        <div className="mt-auto pt-8 text-[10px] font-mono uppercase tracking-wider text-slate-500">{slide.footnote}</div>
      </div>
    );
  }

  if (kind === "toc") {
    const mid = Math.ceil(slide.sections.length / 2);
    return (
      <div className="aspect-video bg-[#0B0E14] p-10 md:p-14">
        <div className="text-[11px] font-mono uppercase tracking-[0.3em] text-cyan-400 flex items-center gap-2">
          <ListChecks size={14} /> Table of Contents
        </div>
        <div className="h-[3px] w-24 bg-cyan-400 mt-3 hud-glow-cyan" />
        <h1 className="font-display text-3xl md:text-5xl font-bold text-white mt-6">{slide.title}</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-2 mt-8">
          {slide.sections.map((s, i) => (
            <div key={i} className={`text-slate-300 text-sm md:text-base font-mono ${i >= mid ? "" : ""}`}>{s}</div>
          ))}
        </div>
      </div>
    );
  }

  if (kind === "section") {
    return (
      <div className="aspect-video bg-gradient-to-br from-[#0B0E14] to-[#0F1620] p-10 md:p-14 flex flex-col justify-center items-start">
        <div className="text-[11px] font-mono uppercase tracking-[0.3em] text-cyan-400">Chapter</div>
        <div className="h-[3px] w-32 bg-cyan-400 mt-3 hud-glow-cyan" />
        <h1 className="font-display text-4xl md:text-7xl font-bold mt-6 text-cyan-300 leading-tight">{slide.title}</h1>
        <p className="text-slate-400 text-lg md:text-2xl mt-4 font-light max-w-3xl">{slide.tagline}</p>
      </div>
    );
  }

  if (kind === "feature") {
    return (
      <div className="aspect-video bg-[#0B0E14] p-8 md:p-12 flex flex-col">
        <div className="text-[11px] font-mono uppercase tracking-[0.3em] text-cyan-400">{slide.subtitle || "Feature Walkthrough"}</div>
        <div className="h-[3px] w-20 bg-cyan-400 mt-2 hud-glow-cyan" />
        <h1 className="font-display text-2xl md:text-4xl font-bold text-white mt-4">{slide.title}</h1>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-6 mt-6 flex-1 overflow-hidden">
          <div className="space-y-2 overflow-y-auto pr-2">
            {(slide.steps || []).map((step, i) => (
              <div key={i} className="flex items-start gap-3 text-slate-200 text-sm md:text-base">
                <span className="font-mono font-bold text-cyan-400 text-xs md:text-sm shrink-0 mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
          {slide.tips?.length > 0 && (
            <div className="border border-cyan-500/30 bg-cyan-500/5 rounded p-4 h-fit">
              <div className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 mb-2">Tips</div>
              {slide.tips.map((t, i) => (
                <div key={i} className="text-slate-300 text-xs md:text-sm font-light mb-2">• {t}</div>
              ))}
            </div>
          )}
        </div>
        {slide.page_url && (
          <div className="mt-4 text-[11px] font-mono text-emerald-400 flex items-center gap-1.5">
            <ArrowRight size={12} /> {slide.page_url}
          </div>
        )}
      </div>
    );
  }

  if (kind === "closing") {
    return (
      <div className="aspect-video bg-gradient-to-br from-[#0B0E14] to-[#0F1620] p-10 md:p-14 flex flex-col justify-center items-start">
        <h1 className="font-display text-5xl md:text-7xl font-bold text-cyan-300 leading-tight">{slide.title}</h1>
        <div className="h-[3px] w-32 bg-cyan-400 mt-4 hud-glow-cyan" />
        <p className="text-slate-400 text-xl md:text-2xl mt-6 font-light">{slide.subtitle}</p>
        <div className="mt-auto pt-8 text-[10px] font-mono uppercase tracking-wider text-slate-500">{slide.footnote}</div>
      </div>
    );
  }

  return (
    <div className="aspect-video bg-[#0B0E14] p-10 flex items-center justify-center">
      <div className="text-slate-400 flex items-center gap-2"><BookOpen size={18} /> {slide.title}</div>
    </div>
  );
}
