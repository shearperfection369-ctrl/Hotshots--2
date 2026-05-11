import React, { useEffect, useState, useMemo } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Globe, AlertTriangle, ShieldCheck, FileText, ExternalLink, Search, TrendingUp, Anchor, Handshake } from "lucide-react";

const SECTIONS = [
  { id: "summary", label: "Overview" },
  { id: "incoterms", label: "Incoterms 2020" },
  { id: "tariffs", label: "Tariff Schedules" },
  { id: "programs", label: "Trade Programs" },
  { id: "section301", label: "Section 301" },
  { id: "section232", label: "Section 232" },
  { id: "coo", label: "Country of Origin" },
  { id: "watchlists", label: "Watchlists & Sanctions" },
  { id: "broker", label: "Broker / ACE" },
  { id: "regs", label: "Key Regulations" },
  { id: "alerts", label: "Alerts" },
  { id: "links", label: "Quick Links" },
];

// ICC Incoterms® 2020 — the 11 official rules. Authoritative source: ICC Publication 723E.
// Grouped by "mode" per ICC guidance: 7 rules for any mode of transport + 4 rules exclusive to sea/inland-waterway.
const INCOTERMS = [
  {
    code: "EXW", name: "Ex Works", mode: "Any mode",
    risk_transfer: "At seller's premises, when goods are placed at buyer's disposal — NOT loaded.",
    buyer_pays: "Everything: loading, export clearance, freight, insurance, import duties.",
    seller_pays: "Nothing beyond making goods available at the named place.",
    tennant_use: "Rarely used outbound — minimum seller obligation; risky for export documentation.",
    insurance: "Buyer's discretion.",
  },
  {
    code: "FCA", name: "Free Carrier", mode: "Any mode",
    risk_transfer: "When goods are handed to the buyer's nominated carrier at the named place.",
    buyer_pays: "Main carriage, insurance, import clearance & duties.",
    seller_pays: "Export clearance, pre-carriage to named place, loading IF named place is seller's premises.",
    tennant_use: "Preferred for containerized exports — replaces FOB for container/ro-ro shipments.",
    insurance: "Buyer's discretion. (2020 update: buyer can instruct carrier to issue on-board B/L to seller.)",
  },
  {
    code: "FAS", name: "Free Alongside Ship", mode: "Sea / inland waterway only",
    risk_transfer: "When goods are placed alongside the vessel at the named port of shipment.",
    buyer_pays: "Loading onto vessel, freight, insurance, import.",
    seller_pays: "Delivery to quay alongside the ship, export clearance.",
    tennant_use: "Bulk / oversized machine exports loaded by ship's tackle at the port.",
    insurance: "Buyer's discretion.",
  },
  {
    code: "FOB", name: "Free On Board", mode: "Sea / inland waterway only",
    risk_transfer: "When goods are loaded on board the vessel at the named port of shipment.",
    buyer_pays: "Sea freight, insurance, import clearance & duties.",
    seller_pays: "Export clearance, pre-carriage, loading onto vessel.",
    tennant_use: "Classic ocean term for non-containerized cargo. Use FCA for containers per ICC guidance.",
    insurance: "Buyer's discretion.",
  },
  {
    code: "CFR", name: "Cost and Freight", mode: "Sea / inland waterway only",
    risk_transfer: "When goods are on board the vessel — but seller pays main carriage.",
    buyer_pays: "Insurance, import clearance & duties, post-discharge transport.",
    seller_pays: "Export clearance, freight to named port of destination.",
    tennant_use: "Used when buyer prefers to arrange their own marine insurance.",
    insurance: "Buyer's discretion (NOT required of seller).",
  },
  {
    code: "CIF", name: "Cost, Insurance and Freight", mode: "Sea / inland waterway only",
    risk_transfer: "When goods are on board the vessel — seller pays freight AND minimum insurance.",
    buyer_pays: "Import clearance & duties, post-discharge transport.",
    seller_pays: "Export, freight to destination port, marine insurance (min ICC Clause C in 2020).",
    tennant_use: "Common for ocean exports to customers who want a single landed-cost quote.",
    insurance: "Seller must provide — ICC (C) minimum coverage, 110% of contract value.",
  },
  {
    code: "CPT", name: "Carriage Paid To", mode: "Any mode",
    risk_transfer: "When goods are handed to the first carrier — even though seller pays freight to destination.",
    buyer_pays: "Insurance, import clearance & duties, unloading at destination.",
    seller_pays: "Export, main carriage to named destination.",
    tennant_use: "Multimodal exports (rail + ocean + truck) where seller arranges through-freight.",
    insurance: "Buyer's discretion (NOT required of seller).",
  },
  {
    code: "CIP", name: "Carriage and Insurance Paid To", mode: "Any mode",
    risk_transfer: "When goods are handed to the first carrier — seller pays carriage AND high-level insurance.",
    buyer_pays: "Import clearance & duties, unloading.",
    seller_pays: "Export, main carriage, insurance to ICC Clause A (all-risks, 110% of value).",
    tennant_use: "Use when shipping high-value AMR units air freight — broad insurance protects in-transit damage.",
    insurance: "Seller must provide — ICC (A) all-risks coverage (2020 upgrade from Clause C).",
  },
  {
    code: "DAP", name: "Delivered At Place", mode: "Any mode",
    risk_transfer: "On arrival at named place of destination, ready for unloading — NOT yet unloaded.",
    buyer_pays: "Unloading at destination, import clearance & duties.",
    seller_pays: "Everything up to and including arrival at named place.",
    tennant_use: "Standard for cross-border North America (USMCA) deliveries to customer DC.",
    insurance: "Seller's discretion (assumes risk to destination).",
  },
  {
    code: "DPU", name: "Delivered at Place Unloaded", mode: "Any mode",
    risk_transfer: "On arrival at named place AND after unloading by seller.",
    buyer_pays: "Import clearance & duties only.",
    seller_pays: "All costs and risks including unloading at the named place.",
    tennant_use: "New 2020 term (replaced DAT). Only rule requiring seller to unload — useful for crated machines.",
    insurance: "Seller's discretion (assumes risk to destination & unload).",
  },
  {
    code: "DDP", name: "Delivered Duty Paid", mode: "Any mode",
    risk_transfer: "On arrival at named destination, cleared for import — maximum seller obligation.",
    buyer_pays: "Nothing beyond receiving the goods.",
    seller_pays: "Everything: export, freight, insurance, import clearance, duties, taxes.",
    tennant_use: "Used for premium customer experience — seller handles import. Caution: requires VAT registration in many jurisdictions.",
    insurance: "Seller's discretion (assumes full risk).",
  },
];

const SEV_BADGE = {
  high: "bg-red-500/10 text-red-300 border-red-500/30",
  medium: "bg-yellow-500/10 text-yellow-300 border-yellow-500/30",
  low: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
};

export default function TradeCompliance() {
  const [data, setData] = useState(null);
  const [section, setSection] = useState("summary");
  const [q, setQ] = useState("");

  useEffect(() => { api.get("/trade-compliance").then(({ data }) => setData(data)); }, []);

  const filteredTariffs = useMemo(() => {
    if (!data) return [];
    if (!q) return data.tariff_schedules;
    const ql = q.toLowerCase();
    return data.tariff_schedules.filter((t) => [t.hts, t.description, t.notes, t.section_301_list].some((v) => (v || "").toLowerCase().includes(ql)));
  }, [data, q]);

  if (!data) return (<><Topbar title="Trade Compliance" /><div className="p-6 text-slate-400">Loading…</div></>);

  return (
    <>
      <Topbar title="Trade Compliance" subtitle="Tariff schedules · Trade programs · CoO · Sanctions · ACE broker filings" />
      <div className="p-4 md:p-6 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-5">
        <Card className="hud-surface p-3 h-fit lg:sticky lg:top-4" data-testid="trade-nav">
          {SECTIONS.map((s) => (
            <button key={s.id} onClick={() => { setSection(s.id); document.getElementById(`tc-${s.id}`)?.scrollIntoView({ behavior: "smooth" }); }}
              data-testid={`tc-nav-${s.id}`}
              className={`block w-full text-left px-3 py-2 rounded text-sm ${section === s.id ? "bg-cyan-500/15 text-cyan-300 border-l-2 border-cyan-400" : "text-slate-400 hover:text-white hover:bg-white/[0.03]"}`}>
              {s.label}
            </button>
          ))}
        </Card>

        <div className="space-y-5">
          {/* Summary */}
          <Card className="hud-surface p-5" id="tc-summary">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Compliance Snapshot</div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
              <Tile label="Active HTS Codes" value={data.summary.active_tariff_codes} />
              <Tile label="Section 301 Exposure" value={`${data.summary.section_301_exposure_pct}%`} accent="text-yellow-400" />
              <Tile label="FTZ Open Lots" value={data.summary.ftz_active_lots} />
              <Tile label="Drawback YTD" value={`$${(data.summary.duty_drawback_ytd_usd / 1000).toFixed(0)}K`} accent="text-emerald-400" />
              <Tile label="Section 232 Steel/Al" value={data.summary.section_232_steel_aluminum_in_scope ? "IN SCOPE" : "OK"} accent={data.summary.section_232_steel_aluminum_in_scope ? "text-yellow-400" : "text-emerald-400"} />
            </div>
          </Card>

          {/* Incoterms 2020 */}
          <Card className="hud-surface p-5" id="tc-incoterms" data-testid="tc-incoterms">
            <div className="flex items-start justify-between mb-3 gap-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2">
                  <Handshake size={12} /> Incoterms® 2020 — ICC Rules of Trade
                </div>
                <h3 className="font-display text-lg font-bold mt-0.5">11 Rules · Risk · Cost · Insurance Obligations</h3>
              </div>
              <a
                href="https://iccwbo.org/business-solutions/incoterms-rules/"
                target="_blank" rel="noreferrer"
                className="text-[10px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 shrink-0 mt-1"
                data-testid="incoterms-icc-link"
              >
                ICC reference <ExternalLink size={10} />
              </a>
            </div>
            <p className="text-xs text-slate-400 mb-4 max-w-3xl leading-relaxed">
              Incoterms® rules define the responsibilities of buyer and seller for the delivery of goods —
              who pays which costs, when risk transfers, who arranges insurance, and who clears customs.
              Tennant's standard outbound terms are <span className="text-cyan-300 font-mono">FCA Origin</span> for containers,
              <span className="text-cyan-300 font-mono"> CIP Destination</span> for high-value air freight,
              and <span className="text-cyan-300 font-mono">DAP/DDP</span> for North American customers.
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {INCOTERMS.map((t) => (
                <div
                  key={t.code}
                  className="p-4 rounded-lg border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 transition-colors"
                  data-testid={`incoterm-${t.code}`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <div>
                      <span className="font-mono text-lg font-bold text-cyan-300 tracking-wider">{t.code}</span>
                      <span className="ml-2 font-display text-sm text-white">{t.name}</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase border ${
                      t.mode.startsWith("Sea")
                        ? "bg-blue-500/10 text-blue-300 border-blue-500/30"
                        : "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                    }`}>
                      {t.mode}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3 text-xs">
                    <IncoRow label="Risk Transfer" value={t.risk_transfer} accent="text-yellow-200" />
                    <IncoRow label="Insurance" value={t.insurance} accent="text-emerald-200" />
                    <IncoRow label="Seller Pays" value={t.seller_pays} accent="text-slate-300" />
                    <IncoRow label="Buyer Pays" value={t.buyer_pays} accent="text-slate-300" />
                  </div>
                  <div className="mt-3 pt-3 border-t border-white/5 text-xs text-cyan-200/80">
                    <span className="font-mono text-[9px] uppercase tracking-wider text-cyan-400">Tennant use · </span>
                    {t.tennant_use}
                  </div>
                </div>
              ))}
            </div>

            {/* Quick reference: risk vs. cost transfer matrix */}
            <div className="mt-5 p-3 rounded border border-cyan-500/15 bg-cyan-500/[0.03]">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Quick mnemonic</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div>
                  <span className="font-mono text-cyan-300">E · F-terms (EXW, FCA, FAS, FOB):</span>
                  <span className="text-slate-300"> Buyer arranges main carriage. Lowest seller obligation.</span>
                </div>
                <div>
                  <span className="font-mono text-cyan-300">C-terms (CFR, CIF, CPT, CIP):</span>
                  <span className="text-slate-300"> Seller pays freight, but risk transfers at origin. Cost ≠ risk.</span>
                </div>
                <div>
                  <span className="font-mono text-cyan-300">D-terms (DAP, DPU, DDP):</span>
                  <span className="text-slate-300"> Seller bears risk all the way to destination. Highest seller obligation.</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Tariff Schedules */}
          <Card className="hud-surface p-5" id="tc-tariffs" data-testid="tc-tariffs">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Tariff Schedules</div>
                <h3 className="font-display text-lg font-bold mt-0.5">HTS · Duty Rates · Section 301</h3>
              </div>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search HTS, keyword..." className="pl-9 w-72 bg-[#0B0E14] border-white/10" />
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider bg-[#0B0E14]">
                  <tr>
                    <th className="text-left py-2 px-3">HTS</th>
                    <th className="text-left py-2 px-3">Description</th>
                    <th className="text-left py-2 px-3">General</th>
                    <th className="text-left py-2 px-3">Special / FTA</th>
                    <th className="text-left py-2 px-3">Section 301</th>
                    <th className="text-left py-2 px-3">Notes</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {filteredTariffs.map((t) => (
                    <tr key={t.hts} className="border-t border-white/5 hover:bg-white/[0.02]">
                      <td className="py-2.5 px-3 text-cyan-300">{t.hts}</td>
                      <td className="py-2.5 px-3 text-slate-200 text-xs max-w-[280px]">{t.description}</td>
                      <td className="py-2.5 px-3 text-slate-300 text-xs">{t.general_duty}</td>
                      <td className="py-2.5 px-3 text-emerald-300 text-xs">{t.column_1_special}</td>
                      <td className="py-2.5 px-3">{t.section_301_list ? <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/30 text-[10px]">{t.section_301_list}</span> : <span className="text-slate-600 text-xs">—</span>}</td>
                      <td className="py-2.5 px-3 text-slate-500 text-xs max-w-[280px]">{t.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Trade Programs */}
          <Card className="hud-surface p-5" id="tc-programs" data-testid="tc-programs">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Trade Programs · FTAs · FTZ · Drawback</div>
            <h3 className="font-display text-lg font-bold mt-0.5 mb-3">Tennant's Active Programs</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {data.trade_programs.map((p) => (
                <div key={p.program} className="p-3 rounded border border-white/5 bg-white/[0.02]">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-display text-sm font-bold text-cyan-300">{p.program}</div>
                      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{p.abbr} · {p.type}</div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase ${p.status.includes("Expired") ? "bg-red-500/10 text-red-300 border border-red-500/30" : "bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"}`}>{p.status}</span>
                  </div>
                  <div className="text-xs text-slate-300 mt-2">{p.tennant_use}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Section 301 */}
          <Card className="hud-surface p-5" id="tc-section301" data-testid="tc-section301">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Section 301 — China Tariffs</div>
            <h3 className="font-display text-lg font-bold mt-0.5 mb-3">Lists, Rates, Exclusions & Mitigation</h3>
            <table className="w-full text-sm mb-4">
              <thead className="text-[10px] font-mono text-cyan-400 uppercase">
                <tr>
                  <th className="text-left py-2 px-3">List</th>
                  <th className="text-right py-2 px-3">Rate</th>
                  <th className="text-left py-2 px-3">Effective</th>
                  <th className="text-left py-2 px-3">Tennant Exposure</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {data.section_301.lists.map((l) => (
                  <tr key={l.list} className="border-t border-white/5">
                    <td className="py-2 px-3 text-cyan-300">{l.list}</td>
                    <td className="py-2 px-3 text-right text-red-300">+{l.rate_pct}%</td>
                    <td className="py-2 px-3 text-slate-400 text-xs">{l.effective}</td>
                    <td className="py-2 px-3 text-slate-300 text-xs">{l.applies_to_tennant}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="p-3 rounded bg-cyan-500/[0.05] border border-cyan-500/20">
              <div className="text-[10px] font-mono uppercase text-cyan-400">Mitigation Strategy</div>
              <div className="text-sm text-slate-200 mt-1">{data.section_301.mitigation}</div>
            </div>
          </Card>

          {/* Section 232 */}
          <Card className="hud-surface p-5" id="tc-section232" data-testid="tc-section232">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Section 232 — Steel & Aluminum</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
              <Tile label="Scope" value={data.section_232.scope} accent="text-cyan-300" />
              <Tile label="Rate" value={`+${data.section_232.rate_pct}%`} accent="text-red-400" />
              <Tile label="TRQ" value={data.section_232.tariff_rate_quota} accent="text-cyan-300" />
            </div>
            <div className="text-sm text-slate-300 mt-3">{data.section_232.tennant_exposure}</div>
          </Card>

          {/* CoO */}
          <Card className="hud-surface p-5" id="tc-coo" data-testid="tc-coo">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Country of Origin Rules</div>
            <h3 className="font-display text-lg font-bold mt-0.5 mb-3">Tennant Products · Marking · US Content %</h3>
            <table className="w-full text-sm">
              <thead className="text-[10px] font-mono text-cyan-400 uppercase">
                <tr>
                  <th className="text-left py-2 px-3">Product</th>
                  <th className="text-left py-2 px-3">Assembled In</th>
                  <th className="text-right py-2 px-3">US Content %</th>
                  <th className="text-left py-2 px-3">Marking</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {data.country_of_origin_rules.map((c) => (
                  <tr key={c.product} className="border-t border-white/5">
                    <td className="py-2 px-3 text-cyan-300">{c.product}</td>
                    <td className="py-2 px-3 text-slate-300 text-xs">{c.assembled_in}</td>
                    <td className="py-2 px-3 text-right text-emerald-400">{c.us_content_pct}%</td>
                    <td className="py-2 px-3 text-slate-200 text-xs">{c.marking_required}<div className="text-[10px] text-slate-500 mt-0.5">{c.notes}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {/* Watchlists */}
          <Card className="hud-surface p-5" id="tc-watchlists" data-testid="tc-watchlists">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2"><ShieldCheck size={12} /> Sanctions & Watchlists</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
              <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
                <div className="text-[10px] font-mono uppercase text-slate-500">Denied Parties Source</div>
                <div className="text-sm text-cyan-300 mt-1">{data.watchlists.denied_parties.source}</div>
                <div className="text-[10px] font-mono text-slate-500 mt-2">Last screen: <span className="text-emerald-400">{data.watchlists.denied_parties.last_screened.slice(0, 16)}</span></div>
                <div className="text-[10px] font-mono text-slate-500 mt-1">Matches 30d: <span className="text-cyan-300">{data.watchlists.denied_parties.matches_30d}</span></div>
              </div>
              <div className="p-3 rounded border border-red-500/20 bg-red-500/[0.04]">
                <div className="text-[10px] font-mono uppercase text-red-400">Embargoed Countries</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {data.watchlists.embargoed_countries.map((c) => (
                    <span key={c} className="px-1.5 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/30 text-[10px] font-mono">{c}</span>
                  ))}
                </div>
              </div>
              <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
                <div className="text-[10px] font-mono uppercase text-slate-500">Restricted End-Use</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {data.watchlists.restricted_end_use.map((c) => (
                    <span key={c} className="px-1.5 py-0.5 rounded bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 text-[10px] font-mono">{c}</span>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 p-3 rounded bg-yellow-500/[0.05] border border-yellow-500/20">
              <div className="text-[10px] font-mono uppercase text-yellow-400 flex items-center gap-1.5"><AlertTriangle size={11} /> UFLPA / Xinjiang Due Diligence</div>
              <div className="text-sm text-slate-200 mt-1">{data.watchlists.uflpa_xinjiang_diligence}</div>
            </div>
          </Card>

          {/* Broker */}
          <Card className="hud-surface p-5" id="tc-broker" data-testid="tc-broker">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2"><Anchor size={12} /> Customs Broker & ACE</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
              <Tile label="Primary Broker" value={data.broker_filings.primary_broker} accent="text-cyan-300" />
              <Tile label="ACE Portal ID" value={data.broker_filings.ace_portal_id} accent="text-emerald-300" />
              <Tile label="Entries YTD" value={data.broker_filings.ytd_entry_summaries} />
              <Tile label="ISFs YTD" value={data.broker_filings.ytd_isf_filings} />
              <Tile label="Avg Clearance" value={`${data.broker_filings.average_clearance_hrs} h`} accent="text-emerald-300" />
              <Tile label="Exam Rate" value={`${data.broker_filings.exam_rate_pct}%`} accent="text-yellow-400" />
              <Tile label="PSC Corrections YTD" value={data.broker_filings.post_summary_corrections_ytd} accent="text-yellow-400" />
            </div>
          </Card>

          {/* Regulations */}
          <Card className="hud-surface p-5" id="tc-regs" data-testid="tc-regs">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Key Regulations</div>
            <div className="space-y-2 mt-3">
              {data.key_regulations.map((r) => (
                <div key={r.reg} className="flex items-start gap-3 p-2.5 rounded border border-white/5 hover:border-cyan-500/20">
                  <FileText size={14} className="text-cyan-400 mt-1 shrink-0" />
                  <div className="flex-1">
                    <div className="text-sm font-mono text-cyan-300">{r.reg}</div>
                    <div className="text-xs text-slate-300 mt-0.5">{r.scope}</div>
                  </div>
                  <div className="text-[10px] font-mono uppercase text-slate-500 shrink-0">{r.owner}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Alerts */}
          <Card className="hud-surface p-5" id="tc-alerts" data-testid="tc-alerts">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 flex items-center gap-2"><AlertTriangle size={12} /> Recent Alerts</div>
            <div className="space-y-2 mt-3">
              {data.recent_alerts.map((a, i) => (
                <div key={i} className="p-3 rounded border border-white/5">
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded border text-[9px] font-mono uppercase ${SEV_BADGE[a.severity]}`}>{a.severity}</span>
                    <span className="text-[10px] font-mono text-slate-500">{a.date}</span>
                  </div>
                  <div className="text-sm text-cyan-300 mt-1.5">{a.title}</div>
                  <div className="text-xs text-slate-300 mt-1">{a.impact}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Links */}
          <Card className="hud-surface p-5" id="tc-links" data-testid="tc-links">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Quick Links</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
              {data.quick_links.map((l) => (
                <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="p-2.5 rounded border border-white/5 hover:border-cyan-500/40 hover:text-cyan-300 text-xs text-slate-300 flex items-center gap-2">
                  <Globe size={12} className="text-cyan-400 shrink-0" />
                  <span className="flex-1">{l.label}</span>
                  <ExternalLink size={10} className="opacity-50" />
                </a>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

function Tile({ label, value, accent = "text-white" }) {
  return (
    <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1 font-mono font-bold ${accent}`}>{value}</div>
    </div>
  );
}

function IncoRow({ label, value, accent = "text-slate-300" }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-0.5 leading-snug ${accent}`}>{value}</div>
    </div>
  );
}
