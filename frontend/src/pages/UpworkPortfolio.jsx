import React, { useEffect, useState } from "react";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Copy, Download, Trophy, Sparkles, Briefcase, GraduationCap, FileText,
  CheckCircle2, ExternalLink, DollarSign, Clock, Target,
} from "lucide-react";
import { toast } from "sonner";
import { api, BACKEND_URL, getStoredToken } from "@/lib/api";

/**
 * /upwork-portfolio — polished, ready-to-paste Upwork profile + service catalog.
 *
 * Two surfaces:
 *   1. Live preview — how the profile will look (hero, tiers, portfolio)
 *   2. Copy-paste blocks — every section with a "Copy" button so the user
 *      can drop content directly into Upwork's profile editor.
 *
 * One-click PDF export ships the entire portfolio as a branded PDF the
 * user can attach to Upwork proposals.
 */
export default function UpworkPortfolio() {
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("preview");
  const [busy, setBusy] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);

  useEffect(() => {
    api.get("/upwork-portfolio")
       .then(r => setData(r.data))
       .catch(() => toast.error("Couldn't load portfolio"));
  }, []);

  const copy = (txt, label) => {
    navigator.clipboard.writeText(txt);
    toast.success(`${label} copied`);
  };

  const downloadPdf = async () => {
    setBusy(true);
    try {
      const token = getStoredToken();
      const res = await fetch(`${BACKEND_URL}/api/upwork-portfolio/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ include_pricing: true, include_awards: true }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Upwork_Portfolio.pdf";
      a.click();
      toast.success("Portfolio PDF downloaded · auto-archived to legal vault");
    } catch (e) {
      toast.error("PDF generation failed: " + e.message);
    } finally { setBusy(false); }
  };

  if (!data) {
    return (
      <>
        <Topbar title="Upwork Portfolio" subtitle="Loading…" />
        <div className="p-8 text-slate-500 text-sm">Loading…</div>
      </>
    );
  }

  return (
    <>
      <Topbar
        title="Upwork Portfolio"
        subtitle="Polished, ready-to-paste profile + three-tier service catalog · Stone Arch credentials baked in"
      />
      <div className="p-4 md:p-6 space-y-5">
        {/* Top toolbar */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex gap-1.5" data-testid="upwork-tabs">
            {[
              { id: "preview", label: "Live Preview", icon: Trophy },
              { id: "copy",    label: "Copy-Paste Blocks", icon: Copy },
              { id: "tiers",   label: "Service Catalog", icon: Briefcase },
            ].map(t => {
              const Icon = t.icon;
              const active = tab === t.id;
              return (
                <button key={t.id}
                        data-testid={`up-tab-${t.id}`}
                        onClick={() => setTab(t.id)}
                        className={`px-3.5 py-1.5 rounded-lg text-xs font-mono uppercase tracking-widest border transition flex items-center gap-1.5 ${
                          active
                            ? "bg-amber-500 text-slate-950 border-amber-300"
                            : "bg-slate-900 text-slate-300 border-white/10 hover:border-amber-400/40"
                        }`}>
                  <Icon size={13} /> {t.label}
                </button>
              );
            })}
          </div>
          <Button
            data-testid="download-portfolio-pdf"
            onClick={downloadPdf}
            disabled={busy}
            className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold"
          >
            <Download size={14} className="mr-1.5" />
            {busy ? "Generating…" : "Download Portfolio PDF"}
          </Button>
        </div>

        {tab === "preview" && <Preview data={data} />}
        {tab === "copy"    && <CopyBlocks data={data} copy={copy} />}
        {tab === "tiers"   && <ServiceCatalog data={data} copy={copy} />}

        {pdfUrl && (
          <Card className="p-3 bg-slate-950/60 border-amber-400/30 mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">Last generated PDF</div>
              <a href={pdfUrl} download="Upwork_Portfolio.pdf" className="text-xs text-amber-200 hover:underline inline-flex items-center gap-1">
                <Download size={11} /> Re-download
              </a>
            </div>
            <iframe src={pdfUrl} className="w-full h-[60vh] bg-white rounded border border-white/10" title="portfolio pdf" />
          </Card>
        )}
      </div>
    </>
  );
}

// ============================================================
//  LIVE PREVIEW
// ============================================================
function Preview({ data }) {
  return (
    <div className="space-y-4">
      {/* Hero */}
      <Card className="p-6 bg-gradient-to-br from-amber-950/40 via-slate-950 to-slate-950 border-amber-400/40">
        <div className="flex items-start gap-4 flex-wrap">
          <div className="w-16 h-16 rounded-full bg-amber-500/20 border-2 border-amber-400/60 grid place-items-center shrink-0">
            <Sparkles className="text-amber-300" size={28} />
          </div>
          <div className="flex-1 min-w-[260px]">
            <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-1">Upwork headline</div>
            <h1 className="text-xl md:text-2xl font-bold text-white leading-tight">{data.headline}</h1>
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-2 flex-wrap font-mono">
              <span className="text-emerald-300">${data.hourly_rate_usd} / hr</span>
              <span>·</span>
              <span>Min project ${data.min_project_budget}</span>
              <span>·</span>
              <span>Minneapolis, MN</span>
              <span>·</span>
              <span className="text-amber-300">100% Job Success target</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Overview */}
      <Card className="p-6 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-3">Profile overview</div>
        <div className="text-sm text-slate-200 whitespace-pre-line leading-relaxed" data-testid="preview-overview">
          {data.overview}
        </div>
      </Card>

      {/* Awards strip */}
      <Card className="p-5 bg-slate-950/60 border-emerald-400/30">
        <div className="text-[10px] font-mono uppercase tracking-widest text-emerald-300 mb-3 inline-flex items-center gap-1.5">
          <Trophy size={12} /> Awards & Recognition
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {data.certifications.map((c, i) => (
            <div key={i} className="p-3 rounded bg-emerald-500/5 border border-emerald-400/20">
              <div className="text-[10px] font-mono text-emerald-300">{c.year}</div>
              <div className="text-xs text-white font-semibold mt-0.5">{c.name}</div>
              <div className="text-[10px] text-slate-400 mt-1">{c.issuer}</div>
              <div className="text-[10px] text-slate-500 mt-1.5">{c.context}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2">
          <img src="/founder-bio/sba_award_team.jpg" alt="SBA Award" className="w-full h-32 object-cover rounded border border-emerald-400/20"/>
          <img src="/founder-bio/joc_top_100.png"    alt="JOC Top 100" className="w-full h-32 object-cover rounded border border-emerald-400/20"/>
          <img src="/founder-bio/cp_transload_award.jpg" alt="CP Transload" className="w-full h-32 object-cover rounded border border-emerald-400/20"/>
        </div>
      </Card>

      {/* Specialties */}
      <Card className="p-5 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-3">Specialties</div>
        <div className="flex flex-wrap gap-1.5" data-testid="preview-specialties">
          {data.specialties.map(s => (
            <Badge key={s} className="bg-cyan-500/15 text-cyan-200 border border-cyan-400/30 text-[10px] font-mono">{s}</Badge>
          ))}
        </div>
      </Card>

      {/* Portfolio items */}
      <Card className="p-5 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-violet-300 mb-3">Selected portfolio</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {data.portfolio_items.map((p, i) => (
            <div key={i} className="p-4 rounded bg-violet-500/5 border border-violet-400/20">
              <div className="text-[9px] font-mono uppercase tracking-widest text-violet-300">{p.category}</div>
              <div className="text-sm text-white font-semibold mt-1">{p.title}</div>
              <div className="text-[11px] text-slate-300 mt-2 leading-relaxed">{p.description}</div>
              <div className="text-[10px] text-emerald-300 mt-2"><b>Result:</b> {p.result}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Employment */}
      <Card className="p-5 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-3 inline-flex items-center gap-1.5">
          <Briefcase size={12} /> Employment history
        </div>
        <div className="space-y-3">
          {data.employment.map((e, i) => (
            <div key={i} className="pb-3 border-b border-white/5 last:border-0">
              <div className="flex items-baseline justify-between flex-wrap gap-2">
                <div className="text-sm font-semibold text-white">{e.title} — <span className="text-amber-200">{e.company}</span></div>
                <div className="text-[10px] font-mono text-slate-500">{e.location} · {e.start} – {e.end}</div>
              </div>
              <div className="text-xs text-slate-300 mt-1 leading-relaxed">{e.summary}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Skills */}
      <Card className="p-5 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-400 mb-3 inline-flex items-center gap-1.5">
          <GraduationCap size={12} /> Skills
        </div>
        <div className="flex flex-wrap gap-1">
          {data.skills.map(s => (
            <span key={s} className="px-2 py-0.5 rounded bg-slate-900 text-[10px] text-slate-300 border border-white/10">{s}</span>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//  COPY-PASTE BLOCKS
// ============================================================
function CopyBlocks({ data, copy }) {
  const blocks = [
    { id: "headline",   label: "Headline (60-char max)", text: data.headline },
    { id: "hourly",     label: "Hourly rate",            text: `$${data.hourly_rate_usd}` },
    { id: "min-budget", label: "Minimum project budget", text: `$${data.min_project_budget}` },
    { id: "overview",   label: "Profile overview",       text: data.overview,           multi: true },
    { id: "specialties", label: "Specialties (one per line)", text: data.specialties.join("\n"), multi: true },
    { id: "skills",     label: "Skills (comma-separated)", text: data.skills.join(", "),  multi: true },
  ];
  return (
    <div className="space-y-3" data-testid="copy-blocks">
      <Card className="p-4 bg-amber-500/5 border-amber-400/30">
        <div className="text-xs text-amber-200 leading-relaxed">
          <b>How to use:</b> open <span className="font-mono">upwork.com/freelancers/settings/contactInfo</span>,
          then paste each block into the matching field. Click <b>Copy</b> on any card below.
        </div>
      </Card>
      {blocks.map(b => (
        <Card key={b.id} data-testid={`copy-card-${b.id}`} className="p-4 bg-slate-950/60 border-white/10">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300">{b.label}</div>
            <Button size="sm" data-testid={`copy-btn-${b.id}`}
                    onClick={() => copy(b.text, b.label)}
                    className="h-7 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px]">
              <Copy size={11} className="mr-1" /> Copy
            </Button>
          </div>
          {b.multi ? (
            <pre className="text-xs text-slate-200 whitespace-pre-wrap bg-slate-900 border border-white/10 rounded p-3 max-h-64 overflow-y-auto font-mono leading-relaxed">{b.text}</pre>
          ) : (
            <div className="text-sm text-white font-mono">{b.text}</div>
          )}
        </Card>
      ))}

      {/* Per-tier Upwork project listings */}
      <Card className="p-4 bg-slate-950/60 border-white/10">
        <div className="text-[10px] font-mono uppercase tracking-widest text-amber-300 mb-3">Upwork project listings (per-tier)</div>
        <div className="space-y-3" data-testid="upwork-listings">
          {data.tiers.flatMap(t => t.services).map(s => (
            <div key={s.title} className="p-3 rounded bg-slate-900/60 border border-white/5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="text-sm font-semibold text-white">{s.title}</div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-emerald-500/15 text-emerald-200 border border-emerald-400/30 text-[10px] font-mono">
                    ${s.price.toLocaleString()}{s.price_unit || " fixed"}
                  </Badge>
                  <Button size="sm" data-testid={`copy-listing-${s.title.replace(/\W+/g, '_')}`}
                          onClick={() => copy(s.upwork_listing, s.title)}
                          className="h-6 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[10px]">
                    <Copy size={10} className="mr-1" /> Copy listing
                  </Button>
                </div>
              </div>
              <div className="text-xs text-slate-300 mt-2 italic">{s.upwork_listing}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================================================
//  SERVICE CATALOG (tier deep-dive)
// ============================================================
const TIER_ACCENT = {
  1: { border: "border-cyan-400/40",   text: "text-cyan-300",   bg: "bg-cyan-500/10",   chip: "bg-cyan-500/20 text-cyan-200" },
  2: { border: "border-amber-400/40",  text: "text-amber-300",  bg: "bg-amber-500/10",  chip: "bg-amber-500/20 text-amber-200" },
  3: { border: "border-violet-400/50", text: "text-violet-300", bg: "bg-violet-500/10", chip: "bg-violet-500/20 text-violet-200" },
};

function ServiceCatalog({ data, copy }) {
  return (
    <div className="space-y-5" data-testid="tier-catalog">
      {data.tiers.map(t => {
        const a = TIER_ACCENT[t.tier] || TIER_ACCENT[1];
        return (
          <Card key={t.tier} className={`p-5 bg-slate-950/60 border-2 ${a.border}`} data-testid={`tier-${t.tier}`}>
            <div className="flex items-start justify-between flex-wrap gap-3 mb-3">
              <div>
                <div className={`text-[10px] font-mono uppercase tracking-widest ${a.text}`}>TIER {t.tier}</div>
                <div className="text-xl font-bold text-white mt-0.5">{t.label}</div>
                <div className="text-sm text-slate-300 mt-1">{t.tagline}</div>
              </div>
              <div className="flex flex-col gap-1.5 items-end">
                <div className={`px-3 py-1 rounded-full text-[11px] font-mono ${a.chip} border ${a.border} inline-flex items-center gap-1`}>
                  <DollarSign size={11} /> {t.price_range}
                </div>
                <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                  <Clock size={10} /> {t.turnaround}
                </div>
                <div className="text-[10px] font-mono text-emerald-300 flex items-center gap-1">
                  <Target size={10} /> Effective {t.effective_rate}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {t.services.map(s => (
                <div key={s.title} className={`p-4 rounded ${a.bg} border ${a.border}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="text-sm font-semibold text-white">{s.title}</div>
                    <Badge className={`${a.chip} border ${a.border} text-[10px] font-mono shrink-0`}>
                      ${s.price.toLocaleString()}{s.price_unit || ""}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-slate-300 mt-2 italic">{s.upwork_listing}</div>
                  <ul className="mt-3 space-y-1">
                    {s.deliverables.map((d, i) => (
                      <li key={i} className="text-[11px] text-slate-300 flex items-start gap-1.5">
                        <CheckCircle2 size={11} className={`${a.text} shrink-0 mt-0.5`} />
                        <span>{d}</span>
                      </li>
                    ))}
                  </ul>
                  <Button size="sm"
                          data-testid={`copy-svc-${s.title.replace(/\W+/g, '_')}`}
                          onClick={() => copy(`${s.upwork_listing}\n\nDeliverables:\n` + s.deliverables.map(d => `• ${d}`).join("\n"), s.title)}
                          className="mt-3 h-7 w-full bg-slate-900 hover:bg-slate-800 border border-white/10 text-slate-200 text-[10px] font-mono">
                    <Copy size={11} className="mr-1" /> Copy full description
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
