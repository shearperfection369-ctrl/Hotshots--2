/* eslint-disable */
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api, BACKEND_URL } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Download, Copy, FileText, Mail, Linkedin, Video, Sparkles } from "lucide-react";

export default function GtmAssets() {
  const [emails, setEmails] = useState(null);
  const [linkedin, setLinkedin] = useState("");
  const [videoScript, setVideoScript] = useState("");

  useEffect(() => {
    api.get("/marketing/orisei/email-templates").then((r) => setEmails(r.data.templates));
    api.get("/marketing/orisei/linkedin-profile").then((r) => setLinkedin(r.data.markdown));
    api.get("/marketing/orisei/video-script").then((r) => setVideoScript(r.data.markdown));
  }, []);

  const downloadBrochure = async () => {
    try {
      const r = await api.get("/marketing/orisei/brochure-pdf", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = "Orisei_Brochure_2026.pdf"; a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Brochure downloaded");
    } catch { toast.error("Download failed"); }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`Copied · ${label}`);
  };

  return (
    <>
      <Topbar title="GTM Marketing Assets" />
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <Card className="hud-surface p-6" data-testid="gtm-header">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-amber-400">
            Hot Shot TMS · Marketing Operating System
          </div>
          <h1 className="font-display text-3xl font-black mt-1 flex items-center gap-3">
            <Sparkles className="text-amber-400" size={28}/>
            Orisei Freight · Ag/Grain GTM Kit
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-3xl">
            Four assets calibrated to win 5 lighthouse clients in western/southern
            Minnesota's grain belt. Download, copy, paste — they're ready to go.
          </p>
        </Card>

        {/* Logo block */}
        <Card className="hud-surface p-6" data-testid="gtm-logo">
          <h2 className="font-display text-xl font-bold mb-4">1 · Brand Identity</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-6 rounded border bg-white" style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <img src="/orisei-logo.svg" alt="Orisei Freight Solutions" className="w-full h-auto max-h-32 object-contain"/>
              <div className="mt-3 flex gap-2">
                <a href="/orisei-logo.svg" download="Orisei_Logo_Horizontal.svg"
                   data-testid="logo-download-h"
                   className="text-xs flex items-center gap-1 text-cyan-300 hover:underline">
                  <Download size={12}/> SVG (horizontal)
                </a>
              </div>
            </div>
            <div className="p-6 rounded border bg-slate-900 flex flex-col items-center justify-center"
                 style={{borderColor:"rgba(255,255,255,0.06)"}}>
              <img src="/orisei-mark.svg" alt="Orisei mark" className="w-32 h-32"/>
              <div className="mt-3 flex gap-2">
                <a href="/orisei-mark.svg" download="Orisei_Mark_Square.svg"
                   data-testid="logo-download-m"
                   className="text-xs flex items-center gap-1 text-cyan-300 hover:underline">
                  <Download size={12}/> SVG (square mark)
                </a>
              </div>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-400 space-y-1">
            <div><b className="text-amber-300">Primary navy:</b> <code className="px-1 bg-black/30 rounded">#0E3A6B</code></div>
            <div><b className="text-amber-300">Accent gold:</b> <code className="px-1 bg-black/30 rounded">#C9A24A</code></div>
            <div><b className="text-amber-300">Type:</b> Helvetica Neue Black for wordmark, Courier New for tagline (mono terminal feel)</div>
            <div className="italic mt-2">Mark concept: bold O = freight loop, gold chevron piercing it = motion, top-right gold dot = the North Star (Minnesota's state symbol).</div>
          </div>
        </Card>

        {/* Brochure */}
        <Card className="hud-surface p-6" data-testid="gtm-brochure">
          <h2 className="font-display text-xl font-bold mb-3 flex items-center gap-2">
            <FileText className="text-amber-400" size={20}/> 2 · 1-page Brochure PDF
          </h2>
          <p className="text-sm text-slate-400 mb-4">
            Branded PDF you can email to prospects or print for a trade show.
            Covers what you offer, insurance limits, coverage lanes, equipment,
            and how a load actually works.
          </p>
          <Button onClick={downloadBrochure} className="bg-amber-500 hover:bg-amber-400 text-black"
                  data-testid="brochure-dl">
            <Download size={14} className="mr-2"/> Download brochure PDF
          </Button>
        </Card>

        {/* Email templates */}
        <Card className="hud-surface p-6" data-testid="gtm-emails">
          <h2 className="font-display text-xl font-bold mb-3 flex items-center gap-2">
            <Mail className="text-amber-400" size={20}/> 3 · Cold Email Cadence (3 variants)
          </h2>
          {emails && Object.entries(emails).map(([key, t]) => (
            <div key={key} className="mb-5 p-4 rounded border bg-white/[0.02]"
                 style={{borderColor:"rgba(255,255,255,0.06)"}} data-testid={`email-${key}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-amber-400">
                  {key.replace(/_/g, " ")}
                </div>
                <Button size="sm" variant="ghost"
                  onClick={() => copyToClipboard(`Subject: ${t.subject}\n\n${t.body}`, key)}
                  className="text-cyan-300 h-7 text-xs">
                  <Copy size={11} className="mr-1"/> Copy
                </Button>
              </div>
              <div className="font-bold text-sm mb-2">Subject · <span className="font-normal text-slate-300">{t.subject}</span></div>
              <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono">{t.body}</pre>
            </div>
          ))}
          <div className="text-xs text-slate-500 italic mt-2">
            Replace {"{first_name}"}, {"{company}"}, {"{shipper_city}"}, {"{capacity_count}"},
            {"{portal_token}"}, {"{phone}"} with the prospect's data before sending.
          </div>
        </Card>

        {/* LinkedIn */}
        <Card className="hud-surface p-6" data-testid="gtm-linkedin">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-xl font-bold flex items-center gap-2">
              <Linkedin className="text-amber-400" size={20}/> 4 · LinkedIn Profile Rewrite
            </h2>
            <Button size="sm" variant="ghost" onClick={() => copyToClipboard(linkedin, "LinkedIn copy")}
                    className="text-cyan-300 h-7 text-xs" data-testid="li-copy">
              <Copy size={11} className="mr-1"/> Copy all
            </Button>
          </div>
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono p-3 rounded bg-black/30 max-h-96 overflow-y-auto">{linkedin}</pre>
        </Card>

        {/* Video script */}
        <Card className="hud-surface p-6" data-testid="gtm-video">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-xl font-bold flex items-center gap-2">
              <Video className="text-amber-400" size={20}/> 5 · 30-sec Demo Video Script
            </h2>
            <Button size="sm" variant="ghost" onClick={() => copyToClipboard(videoScript, "Video script")}
                    className="text-cyan-300 h-7 text-xs" data-testid="vid-copy">
              <Copy size={11} className="mr-1"/> Copy script
            </Button>
          </div>
          <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono p-3 rounded bg-black/30 max-h-96 overflow-y-auto">{videoScript}</pre>
          <div className="text-xs text-slate-400 italic mt-3">
            To generate the actual video, run
            <code className="mx-1 px-1.5 py-0.5 bg-black/40 rounded text-cyan-300">python /app/backend/scripts/build_hotshot_tms_promo.py</code>
            with the script above as input. The existing promo-video pipeline
            (Playwright + FFmpeg + OpenAI TTS "echo" voice) is already wired —
            just point it at the new copy.
          </div>
        </Card>

        <div className="text-center text-xs text-slate-500 font-mono py-6">
          Hot Shot TMS · GTM Operating System · 2026
        </div>
      </div>
    </>
  );
}
