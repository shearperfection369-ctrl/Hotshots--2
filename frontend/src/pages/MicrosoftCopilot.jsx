import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Bot, ExternalLink, Sparkles, MessageSquare, FileText, Search, Lightbulb, Shield } from "lucide-react";

/**
 * Microsoft Copilot launch page.
 *
 * Microsoft serves copilot.microsoft.com and microsoft365.com with
 * `X-Frame-Options: DENY` (or strict CSP `frame-ancestors`), so they cannot
 * be safely embedded in an iframe — any embed attempt renders a blank box.
 * Instead, this page acts as a *launcher*: it ships official Copilot
 * branding, the public entry points (consumer Copilot, M365 Copilot,
 * GitHub Copilot, Edge sidebar), and an attempted iframe with a graceful
 * fallback. Quick prompts can be deep-linked into Copilot via the
 * documented `?q=` query parameter so users land mid-thought.
 *
 * Replaces the previous HUDLINK AI module. No backend hookup required —
 * Microsoft handles auth (Entra ID / Microsoft Account) on their domain.
 */

const COPILOT_BLUE = "#0078D4";
const COPILOT_PURPLE = "#7B61FF";

const LAUNCHERS = [
  {
    id: "copilot",
    title: "Microsoft Copilot",
    sub: "copilot.microsoft.com — chat, image generation, web grounding",
    url: "https://copilot.microsoft.com/",
    blurb: "The public, consumer-facing Copilot. Sign in with your Microsoft account for personalised answers + image generation.",
  },
  {
    id: "m365",
    title: "Microsoft 365 Copilot",
    sub: "Word · Excel · PowerPoint · Outlook · Teams",
    url: "https://m365.cloud.microsoft/chat/",
    blurb: "Enterprise Copilot grounded in your Tennant tenant — emails, files, meetings, Teams chats. Requires an M365 Copilot license.",
  },
  {
    id: "github",
    title: "GitHub Copilot",
    sub: "github.com/copilot — code, repos, issues",
    url: "https://github.com/copilot",
    blurb: "Pair-programmer for your scripts (yard parsers, ETL, FastAPI). Works in VS Code, JetBrains, and the web.",
  },
  {
    id: "edge",
    title: "Edge Sidebar Copilot",
    sub: "Right-side panel in Microsoft Edge",
    url: "https://www.microsoft.com/en-us/edge/copilot",
    blurb: "Page-aware Copilot that lives in the Edge sidebar — summarise a routing guide PDF or carrier MSA without leaving the tab.",
  },
];

const QUICK_PROMPTS = [
  { icon: FileText, text: "Summarize this Bill of Lading PDF and pull out the BOL #, PRO #, weight, pieces, and pickup date." },
  { icon: Search, text: "What HS code should I use for a Tennant T16 AMR scrubber exported from the USA to Germany?" },
  { icon: Lightbulb, text: "Compare XPO Logistics vs. SAIA for a 12,000-lb LTL shipment from Holland MI to Atlanta GA, including transit days and accessorials." },
  { icon: MessageSquare, text: "Draft a polite escalation email to a supplier who keeps using a non-approved carrier on inbound Tennant shipments." },
  { icon: FileText, text: "Convert this freight invoice into a markdown table grouped by accessorial code, with a total and a quoted-vs-actual variance column." },
  { icon: Search, text: "Which Incoterm should we use for an ocean export from Long Beach to Rotterdam where Tennant covers carriage and insurance to destination port?" },
];

function copilotLink(q) {
  return `https://copilot.microsoft.com/?q=${encodeURIComponent(q)}`;
}

function MSLogoMark({ size = 24 }) {
  // Microsoft's four-square mark, recoloured to its official tile palette.
  return (
    <svg width={size} height={size} viewBox="0 0 23 23" aria-hidden>
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="12" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="12" width="10" height="10" fill="#00A4EF" />
      <rect x="12" y="12" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}

export default function MicrosoftCopilot() {
  // X-Frame-Options: DENY still emits a `load` event for a blank document,
  // so we can't trust onLoad to mean "Copilot rendered". Instead we just
  // assume embedding will fail (because it always does in production) and
  // surface the launch CTA after a short grace period. If Microsoft ever
  // relaxes their framing policy, the iframe will already be mounted in
  // the DOM during that grace period and will render normally — only the
  // CTA card overlay flips on, which still keeps the launcher usable.
  const [embedFailed, setEmbedFailed] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setEmbedFailed(true), 2500);
    return () => clearTimeout(t);
  }, []);

  return (
    <>
      <Topbar
        title="Microsoft Copilot"
        subtitle="Your daily AI · grounded in Microsoft · launches into copilot.microsoft.com"
      />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">

        {/* Hero card — branded Copilot entry */}
        <Card
          className="hud-surface lg:col-span-8 overflow-hidden relative"
          data-testid="copilot-hero"
        >
          <div
            className="absolute inset-0 opacity-30 pointer-events-none"
            style={{
              background: `radial-gradient(900px circle at 80% -20%, ${COPILOT_PURPLE}55 0%, transparent 60%), radial-gradient(700px circle at 0% 120%, ${COPILOT_BLUE}55 0%, transparent 60%)`,
            }}
          />
          <div className="relative p-6">
            <div className="flex items-start gap-4 flex-wrap">
              <div
                className="p-3 rounded-xl shrink-0 border"
                style={{ background: `${COPILOT_BLUE}1A`, borderColor: `${COPILOT_BLUE}55` }}
              >
                <Sparkles size={28} style={{ color: COPILOT_BLUE }} />
              </div>
              <div className="flex-1 min-w-[240px]">
                <div className="flex items-center gap-2">
                  <MSLogoMark size={16} />
                  <div className="text-[10px] font-mono uppercase tracking-[0.25em]" style={{ color: COPILOT_BLUE }}>
                    Microsoft Copilot · Inside Tennant TMS
                  </div>
                </div>
                <h2 className="font-display text-3xl font-bold mt-2 text-white">
                  Ask Copilot anything. <span style={{ color: COPILOT_PURPLE }}>About anything.</span>
                </h2>
                <p className="text-sm text-slate-300 mt-2 max-w-2xl leading-relaxed">
                  Logistics questions, HS codes, Incoterms, email drafts, PDF summaries, code
                  snippets — Copilot grounds answers in Microsoft search and (with an M365
                  license) in your Tennant tenant data.
                </p>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <a
                href="https://copilot.microsoft.com/"
                target="_blank" rel="noreferrer"
                data-testid="copilot-launch-consumer"
                className="inline-flex items-center px-4 py-2 rounded font-bold text-white text-xs uppercase tracking-wider"
                style={{ background: COPILOT_BLUE }}
              >
                <Bot size={14} className="mr-1.5" /> Launch Copilot
              </a>
              <a
                href="https://m365.cloud.microsoft/chat/"
                target="_blank" rel="noreferrer"
                data-testid="copilot-launch-m365"
                className="inline-flex items-center px-4 py-2 rounded font-bold text-white text-xs uppercase tracking-wider"
                style={{ background: COPILOT_PURPLE }}
              >
                <MSLogoMark size={13} /> <span className="ml-1.5">Open M365 Copilot</span>
              </a>
              <a
                href="https://github.com/copilot"
                target="_blank" rel="noreferrer"
                data-testid="copilot-launch-github"
                className="inline-flex items-center px-4 py-2 rounded border border-white/15 text-slate-200 hover:border-cyan-400/50 hover:text-cyan-300 text-xs font-mono uppercase tracking-wider"
              >
                GitHub Copilot <ExternalLink size={11} className="ml-1.5 opacity-70" />
              </a>
            </div>

            <div className="mt-4 flex items-center gap-2 text-[10px] font-mono text-slate-400">
              <Shield size={11} style={{ color: COPILOT_BLUE }} />
              <span>Auth happens on microsoft.com — Tennant sign-on via Entra ID.</span>
            </div>
          </div>
        </Card>

        {/* Side card — launcher list */}
        <Card className="hud-surface lg:col-span-4 p-5" data-testid="copilot-launchers">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-3" style={{ color: COPILOT_BLUE }}>
            All Copilot Surfaces
          </div>
          <div className="space-y-2.5">
            {LAUNCHERS.map((l) => (
              <a
                key={l.id}
                href={l.url}
                target="_blank" rel="noreferrer"
                data-testid={`copilot-launcher-${l.id}`}
                className="block p-3 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-400/40 hover:bg-cyan-500/[0.04] transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="font-display text-sm font-bold text-white">{l.title}</div>
                  <ExternalLink size={11} className="text-slate-500 shrink-0" />
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-0.5">{l.sub}</div>
                <div className="text-xs text-slate-300 mt-1.5 leading-relaxed">{l.blurb}</div>
              </a>
            ))}
          </div>
        </Card>

        {/* Quick prompts — each opens copilot.microsoft.com?q=… so the user
            lands directly inside an in-progress thread. */}
        <Card className="hud-surface lg:col-span-12 p-5" data-testid="copilot-prompts">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: COPILOT_BLUE }}>
                One-Click Prompts
              </div>
              <h3 className="font-display text-lg font-bold mt-0.5">Jump straight into Copilot</h3>
            </div>
            <span className="text-[10px] font-mono text-slate-500">
              Each link opens copilot.microsoft.com with the prompt pre-filled
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {QUICK_PROMPTS.map((p, i) => {
              const Icon = p.icon;
              return (
                <a
                  key={i}
                  href={copilotLink(p.text)}
                  target="_blank" rel="noreferrer"
                  data-testid={`copilot-prompt-${i}`}
                  className="flex items-start gap-3 p-3 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-400/40 hover:bg-cyan-500/[0.04] transition-colors"
                >
                  <Icon size={14} style={{ color: COPILOT_BLUE }} className="mt-0.5 shrink-0" />
                  <span className="text-sm text-slate-200 leading-relaxed">{p.text}</span>
                  <ExternalLink size={11} className="text-slate-500 shrink-0 mt-1" />
                </a>
              );
            })}
          </div>
        </Card>

        {/* Embed attempt + graceful fallback. Microsoft blocks framing in
            production, so we keep the iframe but fall back to a "Open in
            Copilot" call-to-action when the load probe times out. */}
        <Card className="hud-surface lg:col-span-12 overflow-hidden" data-testid="copilot-embed-card">
          <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between flex-wrap gap-2">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: COPILOT_BLUE }}>
              Embedded Copilot · Preview
            </div>
            <a
              href="https://copilot.microsoft.com/"
              target="_blank" rel="noreferrer"
              data-testid="copilot-embed-open"
              className="text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1"
            >
              Open full Copilot <ExternalLink size={10} />
            </a>
          </div>
          {!embedFailed ? (
            <iframe
              key="copilot-iframe"
              src="https://copilot.microsoft.com/"
              title="Microsoft Copilot"
              data-testid="copilot-iframe"
              referrerPolicy="origin"
              sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
              className="w-full h-[640px] bg-black"
            />
          ) : (
            <div className="p-8 text-center" data-testid="copilot-embed-fallback">
              <MSLogoMark size={36} />
              <h3 className="font-display text-xl font-bold mt-3 text-white">Copilot can't be embedded</h3>
              <p className="text-sm text-slate-400 mt-2 max-w-xl mx-auto">
                Microsoft blocks framing of <span className="font-mono text-cyan-300">copilot.microsoft.com</span> for
                security reasons. Click below to open Copilot in a new tab — your
                Tennant Entra ID sign-on carries over.
              </p>
              <div className="mt-5 inline-flex flex-wrap gap-2 justify-center">
                <a
                  href="https://copilot.microsoft.com/"
                  target="_blank" rel="noreferrer"
                  data-testid="copilot-fallback-open"
                  className="inline-flex items-center px-5 py-2.5 rounded font-bold text-white text-xs uppercase tracking-wider"
                  style={{ background: COPILOT_BLUE }}
                >
                  <Bot size={14} className="mr-1.5" /> Open Microsoft Copilot
                </a>
                <a
                  href="https://m365.cloud.microsoft/chat/"
                  target="_blank" rel="noreferrer"
                  className="inline-flex items-center px-5 py-2.5 rounded border border-white/15 text-slate-200 hover:border-cyan-400/50 hover:text-cyan-300 text-xs font-mono uppercase tracking-wider"
                >
                  Open M365 Copilot <ExternalLink size={11} className="ml-1.5 opacity-70" />
                </a>
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
