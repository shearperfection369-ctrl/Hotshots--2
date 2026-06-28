import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { BarChart3, ExternalLink, RefreshCw, User, Folder } from "lucide-react";
import { useBranding, useBrandRefresh } from "../lib/branding";

const MS_BLUE = "#F2C811"; // Power BI yellow
const PBI_BLUE = "#0078D4";

export default function PowerBI() {
  const { brand } = useBranding();
  const shortName = brand?.short_name || "Orisei";
  const companyName = brand?.company_name || "Orisei Freight Solutions";
  const [config, setConfig] = useState(null);
  const [activeReportId, setActiveReportId] = useState(null);
  const [embedFailed, setEmbedFailed] = useState(false);

  const loadConfig = () => {
    api.get("/integrations/powerbi/config").then((r) => {
      setConfig(r.data);
      setActiveReportId(r.data.reports?.[0]?.id || null);
    }).catch(() => {});
  };
  useEffect(() => { loadConfig(); }, []);
  useBrandRefresh(() => loadConfig());

  useEffect(() => {
    setEmbedFailed(false);
    const t = setTimeout(() => setEmbedFailed(true), 2800);
    return () => clearTimeout(t);
  }, [activeReportId]);

  const activeReport = config?.reports?.find((r) => r.id === activeReportId);

  return (
    <>
      <Topbar title="Power BI" subtitle={`${shortName} · live executive dashboards & analytics`} />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Card className="hud-surface p-5 lg:col-span-4" data-testid="powerbi-reports-list">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={14} style={{ color: PBI_BLUE }} />
            <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: PBI_BLUE }}>
              Reports · {config?.reports?.length || 0}
            </div>
          </div>
          <div className="space-y-1.5">
            {(config?.reports || []).map((r) => (
              <button
                key={r.id}
                onClick={() => setActiveReportId(r.id)}
                data-testid={`powerbi-report-${r.id}`}
                className={[
                  "w-full text-left p-2.5 rounded border transition-colors",
                  activeReportId === r.id
                    ? "border-cyan-500/50 bg-cyan-500/[0.07]"
                    : "border-white/5 bg-white/[0.02] hover:border-cyan-500/30",
                ].join(" ")}
              >
                <div className="text-sm font-display font-bold text-white truncate">{r.name}</div>
                <div className="text-[10px] font-mono text-slate-400 mt-0.5 truncate">{r.description}</div>
                <div className="flex items-center gap-2 mt-1.5 text-[9px] font-mono text-slate-500">
                  <Folder size={9} /> {r.workspace} · <User size={9} /> {r.owner}
                </div>
              </button>
            ))}
          </div>
          <a
            href={config?.workspace_url}
            target="_blank" rel="noreferrer"
            data-testid="powerbi-workspace-link"
            className="mt-4 block w-full text-center px-3 py-2 rounded font-bold text-black text-[10px] uppercase tracking-wider"
            style={{ background: MS_BLUE }}
          >
            Open {shortName} Workspace in Power BI ↗
          </a>
        </Card>

        <Card className="hud-surface lg:col-span-8 overflow-hidden" data-testid="powerbi-embed">
          <div className="px-4 py-2 border-b border-white/5 flex items-center justify-between gap-2 flex-wrap">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.2em]" style={{ color: PBI_BLUE }}>
                {activeReport?.workspace || "Power BI"}
              </div>
              <h3 className="font-display text-base font-bold text-white">{activeReport?.name || "Select a report"}</h3>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => { setEmbedFailed(false); setTimeout(() => setEmbedFailed(true), 2800); }}
                data-testid="powerbi-reload"
                className="px-2 py-1 rounded border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 text-[9px] font-mono uppercase tracking-wider inline-flex items-center gap-1"
              >
                <RefreshCw size={9} /> Retry
              </button>
              {activeReport?.view_url && (
                <a
                  href={activeReport.view_url}
                  target="_blank" rel="noreferrer"
                  data-testid="powerbi-open-fullscreen"
                  className="px-2 py-1 rounded text-black text-[9px] font-mono uppercase tracking-wider"
                  style={{ background: PBI_BLUE }}
                >
                  Open Full · {activeReport.view_url ? "↗" : ""}
                </a>
              )}
            </div>
          </div>
          {!embedFailed && activeReport?.embed_url ? (
            <iframe
              key={activeReport.embed_url}
              src={activeReport.embed_url}
              title={activeReport.name}
              data-testid="powerbi-iframe"
              className="w-full bg-black"
              style={{ height: 720, border: 0 }}
              allowFullScreen
            />
          ) : (
            <div className="p-10 text-center" data-testid="powerbi-fallback">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl mb-3" style={{ background: PBI_BLUE + "20", border: `1px solid ${PBI_BLUE}55` }}>
                <BarChart3 size={26} style={{ color: PBI_BLUE }} />
              </div>
              <h3 className="font-display text-xl font-bold text-white">Power BI embed unavailable</h3>
              <p className="text-sm text-slate-400 mt-2 max-w-xl mx-auto">
                Power BI blocks framing for unauthenticated sessions. Click below to open this
                report in Power BI — your {shortName} Entra ID sign-on carries over.
              </p>
              {activeReport?.view_url && (
                <a
                  href={activeReport.view_url}
                  target="_blank" rel="noreferrer"
                  data-testid="powerbi-fallback-open"
                  className="inline-flex items-center mt-5 px-5 py-2.5 rounded font-bold text-black text-xs uppercase tracking-wider"
                  style={{ background: PBI_BLUE }}
                >
                  Open “{activeReport.name}” ↗
                </a>
              )}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
