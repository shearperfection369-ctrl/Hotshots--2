import React, { useCallback, useEffect, useState } from "react";
import { Zap, Loader2, Moon, Crosshair, TrendingUp, Clock3, Radar, Sunrise, Copy, BookCheck } from "lucide-react";
import { toast } from "sonner";
import { Card } from "./ui/card";
import { Switch } from "./ui/switch";
import { Slider } from "./ui/slider";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { api } from "../lib/api";

const usd = (n) => (n == null ? "—" : `$${Number(n).toLocaleString()}`);
const pct = (n) => (n == null ? "—" : `${Math.round(n * 100)}%`);
const BADGE_META = {
  "known-shipper": ["Known Shipper", "#10B981"],
  "truck-nearby": ["Truck Nearby", "#38BDF8"],
  "after-hours": ["After-Hours", "#A78BFA"],
};

export const FirstStrikePanel = () => {
  const [status, setStatus] = useState(null);
  const [cands, setCands] = useState(null);
  const [busy, setBusy] = useState("");
  const [aggr, setAggr] = useState(null);
  const [digest, setDigest] = useState(null);

  const openDigest = async () => {
    setBusy("digest");
    try { const { data } = await api.get("/load-hunter/first-strike/digest"); setDigest(data); }
    catch (_) { toast.error("Digest failed"); } finally { setBusy(""); }
  };

  const load = useCallback(async () => {
    try {
      const [{ data: s }, { data: c }] = await Promise.all([
        api.get("/load-hunter/first-strike/status"),
        api.get("/load-hunter/first-strike/candidates")]);
      setStatus(s); setCands(c);
      setAggr((prev) => (prev == null ? s.config.aggressiveness : prev));
    } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const setConfig = async (updates) => {
    try {
      const { data } = await api.post("/load-hunter/first-strike/config", updates);
      setStatus((s) => ({ ...s, config: data.config }));
    } catch (_) { toast.error("Config update failed"); }
  };

  const fireBid = async (c) => {
    setBusy(c.load_id);
    try {
      const { data } = await api.post("/load-hunter/first-strike/bid", { load_id: c.load_id });
      if (data.ok) {
        const o = data.outcome;
        o.won ? toast.success(`WON ${o.lane} at ${usd(o.suggested_bid_usd)}${o.booked_id ? ` — BOOKED ${o.booked_id}` : o.book_blocked ? ` (book blocked: ${o.book_blocked[0]})` : ""}`)
              : toast.error(`Lost ${o.lane} — bid ${usd(o.suggested_bid_usd)}. Lane learning updated.`);
        load();
      } else toast.error(data.error);
    } catch (_) { toast.error("Bid failed"); } finally { setBusy(""); }
  };

  if (!status) return null;
  const { config, totals } = status;

  return (
    <Card className="hud-surface p-4 border-violet-500/25" data-testid="first-strike-panel">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Zap size={15} className="text-violet-300" />
          <span className="text-[12px] font-black text-white uppercase tracking-wider">First Strike — beat them to it</span>
          {status.after_hours_now && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full border border-violet-400/40 text-violet-300 text-[9px] font-mono uppercase" data-testid="fs-afterhours-badge">
              <Moon size={9} /> After-hours mode — competition asleep
            </span>
          )}
          <span className="text-[9px] font-mono text-slate-600 uppercase">simulated until board keys go live</span>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={openDigest} disabled={busy === "digest"} data-testid="fs-digest-btn"
                  className="flex items-center gap-1 px-2.5 h-7 rounded-full border border-amber-400/40 text-amber-300 text-[10px] font-mono font-bold uppercase hover:bg-amber-500/10 disabled:opacity-40">
            {busy === "digest" ? <Loader2 size={10} className="animate-spin" /> : <Sunrise size={11} />} Morning Digest
          </button>
          <label className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-slate-400">
            Auto-hunt {config.interval_sec}s
            <Switch checked={!!config.enabled} onCheckedChange={(v) => setConfig({ enabled: v })} data-testid="fs-autohunt-toggle" />
          </label>
          <label className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-slate-400">
            Learning
            <Switch checked={!!config.learning_enabled} onCheckedChange={(v) => setConfig({ learning_enabled: v })} data-testid="fs-learning-toggle" />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-3" data-testid="fs-stats">
        {[["Bids fired", totals.bids, Crosshair, "#22D3EE"],
          ["Wins", totals.wins, TrendingUp, "#10B981"],
          ["Win rate", totals.win_rate == null ? "—" : pct(totals.win_rate), Radar, "#FBBF24"],
          ["Auto-booked", totals.booked ?? 0, BookCheck, "#F472B6"],
          ["Avg response", totals.avg_response_sec == null ? "—" : `${totals.avg_response_sec}s`, Clock3, "#A78BFA"],
          ["Revenue won", usd(totals.revenue_won_usd), Zap, "#34D399"]].map(([l, v, Icon, col]) => (
          <div key={l} className="p-2 rounded-xl border border-white/10 bg-slate-950/60 text-center" data-testid={`fs-stat-${l.toLowerCase().replace(/ /g, "-")}`}>
            <Icon size={11} className="mx-auto mb-0.5" style={{ color: col }} />
            <div className="text-sm font-black tabular-nums" style={{ color: col }}>{v}</div>
            <div className="text-[8px] font-mono uppercase text-slate-500">{l}</div>
          </div>
        ))}
      </div>

      <div className="mb-3">
        <div className="flex justify-between text-[10px] font-mono mb-1">
          <span className="text-slate-500 uppercase">Bid aggressiveness — {aggr <= 25 ? "Conservative" : aggr <= 55 ? "Competitive" : aggr <= 80 ? "Aggressive" : "Cutthroat"}</span>
          <span className="text-violet-300 font-bold">{aggr} · up to −{((aggr / 100) * 6).toFixed(1)}% off posted</span>
        </div>
        <Slider value={[aggr ?? 55]} min={0} max={100} step={5} data-testid="fs-aggressiveness-slider"
                onValueChange={(v) => setAggr(v[0])}
                onValueCommit={(v) => setConfig({ aggressiveness: v[0] })} />
      </div>

      <div className="grid lg:grid-cols-2 gap-3">
        <div data-testid="fs-candidates">
          <div className="text-[10px] font-mono uppercase text-violet-300 mb-1.5">Strike candidates — priced to win</div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
            {(cands?.items || []).length === 0 && (
              <div className="text-[10px] font-mono text-slate-500 p-3 border border-white/10 rounded-lg" data-testid="fs-no-candidates">
                No unbid candidates right now — the loop already struck everything above {config.min_margin_pct}% margin.
              </div>
            )}
            {(cands?.items || []).map((c) => (
              <div key={c.load_id} className="p-2 rounded-lg border border-white/10 bg-slate-950/60" data-testid={`fs-candidate-${c.load_id}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[11px] font-bold text-white truncate">{c.origin} → {c.destination}</div>
                    <div className="text-[9px] text-slate-500 font-mono">{c.poster} · {c.equipment} · {c.miles} mi · {c.board_id}</div>
                  </div>
                  <button onClick={() => fireBid(c)} disabled={busy === c.load_id} data-testid={`fs-fire-${c.load_id}`}
                          className="shrink-0 px-2.5 h-7 rounded-full bg-violet-500 hover:bg-violet-400 text-black text-[10px] font-black uppercase disabled:opacity-40">
                    {busy === c.load_id ? <Loader2 size={11} className="animate-spin" /> : "Fire Bid"}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 mt-1">
                  <span className="text-[10px] font-mono text-slate-400">posted {usd(c.posted_rate_usd)} → bid <b className="text-violet-300">{usd(c.suggested_bid_usd)}</b> (−{c.discount_pct}%)</span>
                  <span className="text-[10px] font-mono text-emerald-300 font-bold">{pct(c.win_probability)} win est.</span>
                  {c.badges.map((b) => (
                    <span key={b} className="px-1.5 py-0.5 rounded-full border text-[8px] font-mono uppercase"
                          style={{ color: BADGE_META[b]?.[1], borderColor: `${BADGE_META[b]?.[1]}55` }}>{BADGE_META[b]?.[0]}</span>
                  ))}
                  {c.lane_adjustment !== "—" && <span className="text-[8px] font-mono text-amber-300">{c.lane_adjustment}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          <div data-testid="fs-lane-learning">
            <div className="text-[10px] font-mono uppercase text-violet-300 mb-1.5">Lane learning — win/loss memory</div>
            <table className="w-full text-[10px]">
              <thead><tr className="text-slate-600 font-mono text-[8px] uppercase">
                <th className="text-left">Lane</th><th className="text-right">Bids</th>
                <th className="text-right">Win rate</th><th className="text-right">Auto-adjust</th></tr></thead>
              <tbody>
                {(status.lane_learning || []).slice(0, 6).map((l) => (
                  <tr key={l.lane} className="border-t border-white/5 text-slate-300">
                    <td className="py-1 font-mono font-bold text-white">{l.lane}</td>
                    <td className="text-right tabular-nums">{l.bids}</td>
                    <td className={`text-right tabular-nums font-bold ${l.win_rate >= 0.5 ? "text-emerald-300" : "text-amber-300"}`}>{pct(l.win_rate)}</td>
                    <td className="text-right text-[9px] font-mono text-slate-400">{l.adjustment}</td>
                  </tr>
                ))}
                {(status.lane_learning || []).length === 0 && (
                  <tr><td colSpan={4} className="py-2 text-slate-500 font-mono text-[9px]">No bid history yet — the loop is warming up.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div data-testid="fs-predictions">
            <div className="text-[10px] font-mono uppercase text-violet-300 mb-1.5">Posting predictions — call before the post</div>
            <div className="space-y-1">
              {(status.predictions || []).slice(0, 4).map((p) => (
                <div key={p.poster} className="flex items-center justify-between px-2 py-1 rounded border border-white/10 bg-slate-950/60">
                  <span className="text-[10px] font-bold text-white">{p.poster}</span>
                  <span className="text-[9px] font-mono text-slate-400">{p.pattern} · next <b className="text-cyan-300">{p.next_predicted_ct}</b> · n={p.sample_size}</span>
                </div>
              ))}
              {(status.predictions || []).length === 0 && (
                <div className="text-[9px] font-mono text-slate-500">Patterns emerge after the loop logs a few cycles of poster activity.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <Dialog open={!!digest} onOpenChange={(o) => !o && setDigest(null)}>
        <DialogContent className="bg-slate-950 border-white/15 max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-white text-sm font-black uppercase flex items-center gap-2">
              <Sunrise size={14} className="text-amber-300" /> First Strike Morning Digest
            </DialogTitle>
            <DialogDescription className="text-[10px] text-slate-500 font-mono">
              Overnight after-hours wins + today's predicted postings
            </DialogDescription>
          </DialogHeader>
          {digest && (
            <>
              <div className="flex flex-wrap gap-2" data-testid="fs-digest-stats">
                {[["Bids", digest.bids], ["Wins", digest.wins], ["Overnight wins", digest.after_hours_wins.length],
                  ["Booked", digest.booked], ["Revenue won", usd(digest.revenue_won_usd)]].map(([l, v]) => (
                  <span key={l} className="px-2 py-1 rounded-lg border border-white/10 text-[10px] font-mono text-slate-300">
                    <b className="text-amber-300">{v}</b> {l}
                  </span>
                ))}
              </div>
              <pre className="whitespace-pre-wrap text-[10px] text-slate-300 bg-slate-900/70 rounded-lg p-3 max-h-[40vh] overflow-y-auto font-mono" data-testid="fs-digest-text">
                {digest.text}
              </pre>
              <button onClick={() => { navigator.clipboard.writeText(digest.text); toast.success("Digest copied"); }}
                      data-testid="fs-digest-copy"
                      className="self-end px-3 h-8 rounded-full bg-amber-500 hover:bg-amber-400 text-black text-[10px] font-black uppercase flex items-center gap-1">
                <Copy size={11} /> Copy Digest
              </button>
            </>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
};
