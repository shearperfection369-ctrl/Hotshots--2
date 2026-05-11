import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { ExternalLink } from "lucide-react";

export default function QuickLinks() {
  const [links, setLinks] = useState([]);
  useEffect(() => { api.get("/links").then(({ data }) => setLinks(data)); }, []);
  const grouped = links.reduce((acc, l) => { (acc[l.category] ||= []).push(l); return acc; }, {});

  return (
    <>
      <Topbar title="Quick Links" subtitle="DOT · ACE Portal · Import/Export resources" />
      <div className="p-4 md:p-6 space-y-5">
        {Object.entries(grouped).map(([cat, list]) => (
          <Card key={cat} className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">{cat}</div>
            <h3 className="font-display text-lg font-bold mb-4">{cat}</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map((l) => (
                <a
                  key={l.url}
                  href={l.url} target="_blank" rel="noreferrer"
                  data-testid={`link-${l.url}`}
                  className="block p-4 rounded-md border border-white/5 bg-white/[0.02] hover:border-cyan-500/40 hover:bg-cyan-500/[0.04] transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-display font-semibold text-white">{l.name}</div>
                    <ExternalLink size={14} className="text-cyan-400 shrink-0" />
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{l.description}</div>
                  <div className="text-[10px] font-mono text-slate-500 mt-2 truncate">{l.url}</div>
                </a>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
