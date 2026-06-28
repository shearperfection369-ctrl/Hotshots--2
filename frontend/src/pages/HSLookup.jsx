import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Search } from "lucide-react";

export default function HSLookup() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);

  useEffect(() => {
    const t = setTimeout(async () => {
      const { data } = await api.get(`/hs-lookup?q=${encodeURIComponent(q)}`);
      setItems(data);
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <>
      <Topbar title="HS Code Lookup" subtitle="Harmonized Tariff Schedule · Industry-relevant classifications" />
      <div className="p-4 md:p-6 space-y-4">
        <Card className="hud-surface p-5">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Search HTS</div>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="hs-search"
              value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search by code (e.g., 8479) or description (e.g., scrubber, battery, motor)..."
              className="pl-9 bg-[#0B0E14] border-white/10 text-base py-6"
            />
          </div>
          <div className="text-[11px] font-mono text-slate-500 mt-2">
            Tip: also see official <a className="text-cyan-400 hover:underline" href="https://hts.usitc.gov/" target="_blank" rel="noreferrer">hts.usitc.gov</a>
          </div>
        </Card>

        <Card className="hud-surface overflow-hidden" data-testid="hs-results">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">HS Code</th>
                  <th className="text-left py-3 px-4">Description</th>
                  <th className="text-left py-3 px-4">Category</th>
                  <th className="text-right py-3 px-4">Duty</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {items.map((it) => (
                  <tr key={it.code} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-4 text-cyan-300 font-bold">{it.code}</td>
                    <td className="py-2.5 px-4 text-slate-300">{it.description}</td>
                    <td className="py-2.5 px-4 text-slate-400">{it.category}</td>
                    <td className="py-2.5 px-4 text-right text-emerald-400">{it.duty_pct}%</td>
                  </tr>
                ))}
                {items.length === 0 && <tr><td colSpan={4} className="text-center py-10 text-slate-500">No matches.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
