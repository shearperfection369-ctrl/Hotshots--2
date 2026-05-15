import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { FolderOpen, ExternalLink, FileText, Users, Clock } from "lucide-react";
import { useBranding, useBrandRefresh } from "../lib/branding";

const SP_BLUE = "#03787C"; // SharePoint teal

export default function SharePoint() {
  const { brand } = useBranding();
  const shortName = brand?.short_name || "Tennant";
  const companyName = brand?.company_name || "Tennant Companies";
  const [data, setData] = useState({ sites: [], recent_files: [], tenant_url: "" });
  const loadConfig = () => {
    api.get("/integrations/sharepoint/config").then((r) => setData(r.data)).catch(() => {});
  };
  useEffect(() => { loadConfig(); }, []);
  useBrandRefresh(() => loadConfig());
  // Derive the displayable tenant host from whatever the API returns (the
  // backend already brand-swaps this for non-Tennant brands).
  const tenantHost = (data.tenant_url || "").replace(/^https?:\/\//, "") || `${shortName.toLowerCase()}.sharepoint.com`;

  return (
    <>
      <Topbar title="SharePoint" subtitle={`${companyName} · sites · libraries · recent activity`} />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Card className="hud-surface p-5 lg:col-span-12 flex items-center justify-between flex-wrap gap-3" data-testid="sharepoint-hero">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg" style={{ background: SP_BLUE + "20", border: `1px solid ${SP_BLUE}55` }}>
              <FolderOpen size={24} style={{ color: SP_BLUE }} />
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: SP_BLUE }}>
                Microsoft SharePoint · Online
              </div>
              <h2 className="font-display text-xl font-bold text-white">{tenantHost}</h2>
              <p className="text-xs text-slate-400 mt-0.5">Single sign-on via {shortName} Entra ID. All edits sync back to SharePoint Online in real time.</p>
            </div>
          </div>
          <a
            href={data.tenant_url}
            target="_blank" rel="noreferrer"
            data-testid="sharepoint-open-tenant"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded font-bold text-white text-xs uppercase tracking-wider"
            style={{ background: SP_BLUE }}
          >
            Open SharePoint <ExternalLink size={11} />
          </a>
        </Card>

        <Card className="hud-surface p-5 lg:col-span-7" data-testid="sharepoint-sites">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-3" style={{ color: SP_BLUE }}>
            Sites · {data.sites?.length || 0}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(data.sites || []).map((s) => (
              <a
                key={s.id}
                href={s.url}
                target="_blank" rel="noreferrer"
                data-testid={`sharepoint-site-${s.id}`}
                className="block p-3 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 hover:bg-cyan-500/[0.04] transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-display text-sm font-bold text-white">{s.name}</div>
                  <ExternalLink size={11} className="text-slate-500 shrink-0 mt-0.5" />
                </div>
                <div className="text-xs text-slate-300 mt-1 leading-relaxed">{s.description}</div>
                <div className="flex items-center gap-3 mt-2 text-[9px] font-mono text-slate-500">
                  <span className="flex items-center gap-1"><Users size={9} /> {s.members}</span>
                  <span className="flex items-center gap-1"><Clock size={9} /> updated {new Date(s.updated_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
                </div>
              </a>
            ))}
          </div>
        </Card>

        <Card className="hud-surface p-5 lg:col-span-5" data-testid="sharepoint-recent">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] mb-3" style={{ color: SP_BLUE }}>
            Recently Modified · {data.recent_files?.length || 0}
          </div>
          <div className="space-y-1">
            {(data.recent_files || []).map((f, i) => (
              <a
                key={i}
                href={f.url}
                target="_blank" rel="noreferrer"
                data-testid={`sharepoint-file-${i}`}
                className="block p-2.5 rounded border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 hover:bg-cyan-500/[0.04] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <FileText size={12} style={{ color: SP_BLUE }} className="shrink-0" />
                  <span className="text-xs font-mono text-cyan-100 truncate flex-1">{f.name}</span>
                </div>
                <div className="text-[10px] font-mono text-slate-500 mt-1 ml-5">
                  {f.modified_by} · {new Date(f.modified_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })} · {f.size}
                </div>
              </a>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}
