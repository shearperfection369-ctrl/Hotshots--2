import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { useBranding } from "../lib/branding";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import {
  Archive, FileText, Mail, Linkedin, Newspaper, Copy, Truck, Briefcase,
  PackageCheck, MessageSquare,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function MarketingPack() {
  const { brand } = useBranding();
  const accent = brand?.accent_color || "#C9A24A";
  const primary = brand?.primary_color || "#0E3A6B";
  const short = brand?.short_name || "Orisei";
  const company = brand?.company_name || "Orisei Freight Solutions LLC";

  const [posts, setPosts] = useState([]);
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(null);
  const [tab, setTab] = useState("linkedin"); // linkedin | emails

  useEffect(() => {
    (async () => {
      try {
        const [p, e] = await Promise.all([
          api.get("/marketing/linkedin-posts"),
          api.get("/marketing/cold-emails"),
        ]);
        setPosts(p.data.posts || []);
        setEmails(e.data.emails || []);
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Failed to load marketing pack");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const triggerDownload = async (path, label, filename) => {
    setDownloading(label);
    try {
      const token = localStorage.getItem("session_token");
      const r = await fetch(`${REACT_APP_BACKEND_URL}/api${path}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!r.ok) throw new Error((await r.text()) || "Download failed");
      const blob = await r.blob();
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`${label} downloaded`);
    } catch (e) {
      toast.error(`${label} failed: ${e.message || e}`);
    } finally {
      setDownloading(null);
    }
  };

  const copyText = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  return (
    <>
      <Topbar
        title={`${short} · Marketing Pack`}
        subtitle="Launch-week kit · Carrier & shipper sell sheets · LinkedIn posts · Cold emails · Press release"
      />
      <div className="p-4 md:p-6 space-y-6 max-w-7xl mx-auto">

        {/* DOWNLOAD HUB */}
        <Card className="hud-surface p-5" style={{ borderColor: `${accent}33` }} data-testid="marketing-hub">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                Full Marketing Pack · One-Click ZIP
              </div>
              <h2 className="font-display text-2xl font-bold mt-1" style={{ color: accent }}>
                Everything you need to launch {short}
              </h2>
              <p className="text-sm text-slate-400 mt-1">
                3 PDFs · 3 LinkedIn posts · 3 cold-email sequences (with follow-ups) — all brand-stamped, all ready to ship.
              </p>
            </div>
            <Button
              onClick={() => triggerDownload("/marketing/pack.zip", "Marketing Pack ZIP",
                `${company.replace(/ /g, "_")}_Marketing_Pack.zip`)}
              disabled={!!downloading}
              className="font-bold text-black"
              style={{ background: accent }}
              data-testid="marketing-pack-zip"
            >
              <Archive size={14} className="mr-2" />
              {downloading === "Marketing Pack ZIP" ? "Bundling…" : "Download Marketing Pack (ZIP)"}
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
            <DownloadCard
              icon={Truck} label="Carrier Sell Sheet"
              sublabel="One-page PDF · For carriers we want in our network"
              testId="dl-carrier" accent={accent}
              onClick={() => triggerDownload("/marketing/carrier-sell-sheet.pdf", "Carrier Sell Sheet",
                `${company.replace(/ /g, "_")}_Carrier_Sell_Sheet.pdf`)}
              loading={downloading === "Carrier Sell Sheet"}
            />
            <DownloadCard
              icon={PackageCheck} label="Shipper Sell Sheet"
              sublabel="One-page PDF · For shippers tired of mega-3PL service"
              testId="dl-shipper" accent={accent}
              onClick={() => triggerDownload("/marketing/shipper-sell-sheet.pdf", "Shipper Sell Sheet",
                `${company.replace(/ /g, "_")}_Shipper_Sell_Sheet.pdf`)}
              loading={downloading === "Shipper Sell Sheet"}
            />
            <DownloadCard
              icon={Newspaper} label="Press Release"
              sublabel="MC-launch release · Ready for newswire"
              testId="dl-press" accent={accent}
              onClick={() => triggerDownload("/marketing/press-release.pdf", "Press Release",
                `${company.replace(/ /g, "_")}_Press_Release.pdf`)}
              loading={downloading === "Press Release"}
            />
          </div>
        </Card>

        {/* TABS */}
        <div className="flex gap-2 border-b border-white/10">
          <TabButton active={tab === "linkedin"} onClick={() => setTab("linkedin")}
            icon={Linkedin} label="LinkedIn Launch Posts" count={posts.length} accent={accent}
            testId="tab-linkedin" />
          <TabButton active={tab === "emails"} onClick={() => setTab("emails")}
            icon={Mail} label="Cold-Email Templates" count={emails.length} accent={accent}
            testId="tab-emails" />
        </div>

        {/* LINKEDIN POSTS */}
        {tab === "linkedin" && (
          <div className="space-y-4" data-testid="linkedin-posts-panel">
            {loading ? <div className="text-slate-500">Loading…</div> : null}
            {posts.map((p, idx) => (
              <Card key={p.id} className="hud-surface p-5" style={{ borderColor: `${accent}22` }} data-testid={`linkedin-post-${p.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                      Post {idx + 1} · Audience: {p.audience}
                    </div>
                    <h3 className="font-display text-xl font-bold mt-1 text-white">{p.title}</h3>
                  </div>
                  <Button
                    onClick={() => copyText(p.body + "\n\n" + (p.hashtags || []).join(" "), `Post ${idx + 1}`)}
                    variant="outline" className="border-white/10 text-xs"
                    data-testid={`copy-post-${p.id}`}>
                    <Copy size={12} className="mr-1.5" /> Copy
                  </Button>
                </div>
                <div className="mt-3 p-4 rounded border bg-white/[0.02] whitespace-pre-wrap text-sm text-slate-200 leading-relaxed"
                     style={{ borderColor: `${primary}55` }}>
                  {p.body}
                </div>
                {p.hashtags?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {p.hashtags.map((h) => (
                      <span key={h} className="text-[11px] font-mono px-2 py-0.5 rounded border"
                            style={{ borderColor: `${accent}44`, color: accent }}>{h}</span>
                    ))}
                  </div>
                )}
                {p.cta && (
                  <div className="mt-3 flex items-start gap-2 text-xs text-slate-400">
                    <MessageSquare size={12} style={{ color: accent, marginTop: 2 }} />
                    <span><strong style={{ color: accent }}>CTA:</strong> {p.cta}</span>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}

        {/* COLD EMAILS */}
        {tab === "emails" && (
          <div className="space-y-4" data-testid="cold-emails-panel">
            {loading ? <div className="text-slate-500">Loading…</div> : null}
            {emails.map((e) => (
              <Card key={e.id} className="hud-surface p-5" style={{ borderColor: `${accent}22` }} data-testid={`cold-email-${e.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: accent }}>
                      {e.audience}
                    </div>
                    <h3 className="font-display text-xl font-bold mt-1 text-white">
                      {e.id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </h3>
                    <div className="mt-2 text-xs">
                      <span className="text-slate-400 mr-2">Subject:</span>
                      <span className="font-mono text-white">{e.subject}</span>
                    </div>
                  </div>
                  <Button onClick={() => copyText(e.body, "Email body")}
                    variant="outline" className="border-white/10 text-xs"
                    data-testid={`copy-email-${e.id}`}>
                    <Copy size={12} className="mr-1.5" /> Copy Body
                  </Button>
                </div>
                <div className="mt-3 p-4 rounded border bg-white/[0.02] whitespace-pre-wrap text-sm text-slate-200 leading-relaxed"
                     style={{ borderColor: `${primary}55` }}>
                  {e.body}
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <span className="text-[10px] font-mono text-slate-500 mr-2 mt-1">Merge tokens:</span>
                  {e.merge_tokens?.map((t) => (
                    <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded border bg-white/5"
                          style={{ borderColor: `${accent}33`, color: accent }}>{`{{${t}}}`}</span>
                  ))}
                </div>
                <div className="mt-4 p-3 rounded border border-emerald-500/20 bg-emerald-500/[0.04]">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-300">
                      Follow-up · Day +{e.follow_up_days}
                    </span>
                    <button onClick={() => copyText(e.follow_up_body, "Follow-up")}
                      className="text-[10px] flex items-center gap-1 text-emerald-300 hover:text-emerald-100"
                      data-testid={`copy-followup-${e.id}`}>
                      <Copy size={10} /> Copy
                    </button>
                  </div>
                  <div className="text-xs text-slate-300 whitespace-pre-wrap">{e.follow_up_body}</div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function DownloadCard({ icon: Icon, label, sublabel, onClick, accent, loading, testId }) {
  return (
    <button onClick={onClick} disabled={loading} data-testid={testId}
      className="text-left p-4 rounded-lg border transition hover:scale-[1.02] disabled:opacity-50 group"
      style={{ borderColor: `${accent}44`, background: `${accent}0a` }}>
      <div className="flex items-center gap-2">
        <Icon size={18} style={{ color: accent }} />
        <div className="text-base text-white font-semibold">{label}</div>
      </div>
      <div className="text-[11px] mt-1.5 text-slate-400">{loading ? "Generating…" : sublabel}</div>
    </button>
  );
}

function TabButton({ active, onClick, icon: Icon, label, count, accent, testId }) {
  return (
    <button onClick={onClick} data-testid={testId}
      className="px-4 py-2 -mb-px flex items-center gap-2 text-sm font-mono border-b-2 transition"
      style={{
        borderColor: active ? accent : "transparent",
        color: active ? accent : "#94a3b8",
      }}>
      <Icon size={14} />
      {label}
      <span className="text-[10px] px-1.5 py-0.5 rounded-full border"
            style={{ borderColor: `${accent}55`, color: accent }}>{count}</span>
    </button>
  );
}
