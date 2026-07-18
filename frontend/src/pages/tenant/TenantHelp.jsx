import React, { useEffect, useState } from "react";
import { useTenant } from "./TenantPortal";

export default function TenantHelp() {
  const { api, primary } = useTenant();
  const [sections, setSections] = useState([]);
  useEffect(() => { api.get("/help").then((r) => setSections(r.data.sections)).catch(() => {}); }, [api]);
  return (
    <div className="max-w-3xl" data-testid="tenant-help">
      <h1 className="text-2xl font-black tracking-tight mb-1">Getting started</h1>
      <p className="text-slate-500 text-sm mb-6">Everything you need to run your desk from day one.</p>
      <div className="space-y-4">
        {sections.map((s) => (
          <div key={s.title} className="p-5 rounded-xl border border-white/10 bg-white/[0.02]">
            <div className="font-bold mb-1.5" style={{ color: primary }}>{s.title}</div>
            <p className="text-sm text-slate-300 leading-relaxed">{s.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
