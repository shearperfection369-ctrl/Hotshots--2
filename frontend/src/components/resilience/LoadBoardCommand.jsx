import React, { useCallback, useEffect, useState } from "react";
import { Radar, Mail, KeyRound, Send, RefreshCw, Loader2, ExternalLink, Layers } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const STATUS_META = {
  connected: ["CONNECTED", "#10B981"], healthy: ["HEALTHY", "#10B981"],
  no_credentials: ["NO KEYS", "#64748B"], connected_empty: ["EMPTY", "#F59E0B"], benched: ["BENCHED", "#F59E0B"],
};
const MODE_META = { api: ["API", "#10B981"], email: ["EMAIL", "#22D3EE"], queued: ["QUEUED", "#F59E0B"] };

export const LoadBoardCommand = () => {
  const [boards, setBoards] = useState(null);
  const [feed, setFeed] = useState(null);
  const [outbox, setOutbox] = useState(null);
  const [actions, setActions] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const [b, f, o, a] = await Promise.all([
        api.get("/loadboard-gateway/boards"), api.get("/loadboard-gateway/feed"),
        api.get("/loadboard-gateway/outbox"), api.get("/loadboard-gateway/actions")]);
      setBoards(b.data.boards); setFeed(f.data); setOutbox(o.data); setActions(a.data.actions);
    } catch (_) {}
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  const testBoard = async (id) => {
    setBusy(id);
    try { const { data: r } = await api.post(`/loadboard-gateway/boards/${id}/test`); toast[r.ok ? "success" : "info"](`${id}: ${r.status}${r.ok ? ` · ${r.loads_found} loads` : ""}`); load(); }
    catch (e) { toast.error(errTxt(e)); } finally { setBusy(""); }
  };
  const ingest = async () => {
    setBusy("ingest");
    try { const { data: r } = await api.post("/loadboard-gateway/ingest"); toast.success(`Ingested ${r.ingested} new, merged ${r.merged} dupes, expired ${r.expired}`); load(); }
    catch (e) { toast.error(errTxt(e)); } finally { setBusy(""); }
  };
  const flush = async () => {
    try { const { data: r } = await api.post("/loadboard-gateway/outbox/flush"); toast.success(r.sent ? `${r.sent} emails sent` : "Nothing sendable — add Resend key + booking emails"); load(); }
    catch (e) { toast.error(errTxt(e)); }
  };

  if (!boards) return <div className="p-6 text-slate-500 font-mono text-sm">Loading load board command…</div>;

  return (
    <div className="space-y-5" data-testid="loadboard-command">
      <p className="text-xs text-slate-400 max-w-3xl">Five-board adapter layer with a 60-second ingestion poller and deduped feed. Bookings are <b className="text-cyan-300">API-first</b> — when a board has no API keys, the desk automatically <b className="text-cyan-300">emails the board's booking desk</b> instead (set a Booking Email per board in Connections); with neither, emails queue in the outbox and auto-send when configured.</p>

      <div className="grid md:grid-cols-3 xl:grid-cols-5 gap-3" data-testid="lbc-boards">
        {boards.map((b) => {
          const [label, color] = STATUS_META[b.health?.status] || ["ERROR", "#EF4444"];
          return (
            <div key={b.board} className="p-3.5 rounded-2xl border border-white/10 bg-slate-950/70" data-testid={`lbc-board-${b.board}`}>
              <div className="flex items-center justify-between">
                <div className="text-[13px] font-black text-white">{b.label}</div>
                <span className="text-[8px] font-mono font-bold px-1.5 py-px rounded" style={{ color, border: `1px solid ${color}55` }}>{label}</span>
              </div>
              <div className="mt-2 space-y-1 text-[10px] font-mono">
                <div className={b.has_api_key ? "text-emerald-400" : "text-slate-500"}><KeyRound size={10} className="inline mr-1" />{b.has_api_key ? "API keys saved" : "No API keys"}</div>
                <div className={b.booking_email ? "text-cyan-300" : "text-slate-500"}><Mail size={10} className="inline mr-1" />{b.booking_email || "No booking email"}</div>
                <div className="text-slate-600">{b.rate_limit}</div>
              </div>
              <div className="mt-2 text-[9px] text-slate-500 leading-snug min-h-[42px]">{b.setup}</div>
              <div className="flex items-center gap-2 mt-2">
                <button onClick={() => testBoard(b.board)} disabled={busy === b.board} data-testid={`lbc-test-${b.board}`}
                        className="px-3 h-7 rounded-full border border-cyan-500/40 text-cyan-300 text-[10px] font-bold hover:bg-cyan-500/10 disabled:opacity-50">
                  {busy === b.board ? <Loader2 size={10} className="animate-spin" /> : "Test"}
                </button>
                {String(b.docs).startsWith("http") ? (
                  <a href={b.docs} target="_blank" rel="noreferrer" className="text-[10px] font-mono text-slate-500 hover:text-cyan-300 inline-flex items-center gap-1">docs <ExternalLink size={9} /></a>
                ) : <span className="text-[9px] font-mono text-slate-600">{b.docs}</span>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/60" data-testid="lbc-feed">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[10px] font-mono uppercase text-slate-500 flex items-center gap-1.5"><Layers size={11} /> Deduped ingestion feed · {feed?.open_count ?? 0} open</div>
            <button onClick={ingest} disabled={busy === "ingest"} data-testid="lbc-ingest-btn"
                    className="px-3 h-7 rounded-full border border-emerald-500/40 text-emerald-300 text-[10px] font-bold hover:bg-emerald-500/10 inline-flex items-center gap-1 disabled:opacity-50">
              {busy === "ingest" ? <Loader2 size={10} className="animate-spin" /> : <RefreshCw size={10} />} Poll Now
            </button>
          </div>
          <div className="space-y-1 max-h-[280px] overflow-y-auto">
            {(feed?.loads || []).slice(0, 20).map((l) => (
              <div key={l.fingerprint} className="p-2 rounded-lg border border-white/10 bg-white/[0.03] text-[10px] font-mono flex items-center gap-2">
                <span className="text-cyan-300 shrink-0">{l.board_id}</span>
                <span className="text-white font-bold truncate">{l.origin.split(",")[0]} → {l.dest.split(",")[0]}</span>
                <span className="text-slate-500">{l.equipment}</span>
                <span className="text-emerald-300 ml-auto shrink-0">${l.shipper_rate.toLocaleString()}</span>
                {(l.sources || []).length > 1 && <span className="text-[8px] px-1 rounded bg-purple-500/15 text-purple-300 font-black shrink-0">{l.sources.length} BOARDS</span>}
              </div>
            ))}
            {(feed?.loads || []).length === 0 && <div className="text-[11px] text-slate-600 font-mono">Feed empty — poll now or wait for the 60s loop.</div>}
          </div>
        </div>

        <div className="space-y-4">
          <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/60" data-testid="lbc-outbox">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-mono uppercase text-slate-500 flex items-center gap-1.5"><Mail size={11} /> Booking email outbox · {outbox?.queued ?? 0} queued · {outbox?.sent ?? 0} sent</div>
              <button onClick={flush} data-testid="lbc-flush-btn"
                      className="px-3 h-7 rounded-full border border-amber-500/40 text-amber-300 text-[10px] font-bold hover:bg-amber-500/10 inline-flex items-center gap-1"><Send size={10} /> Flush</button>
            </div>
            <div className="space-y-1 max-h-[130px] overflow-y-auto">
              {(outbox?.outbox || []).slice(0, 8).map((o) => (
                <div key={o.outbox_id} className="text-[10px] font-mono flex items-center gap-2">
                  <span className={`px-1.5 rounded text-[8px] font-black ${o.status === "sent" ? "text-emerald-300 bg-emerald-500/10" : "text-amber-300 bg-amber-500/10"}`}>{o.status.toUpperCase()}</span>
                  <span className="text-slate-300 truncate">{o.subject}</span>
                  <span className="text-slate-600 ml-auto shrink-0">{o.to_email || "no address yet"}</span>
                </div>
              ))}
              {(outbox?.outbox || []).length === 0 && <div className="text-[11px] text-slate-600 font-mono">No booking emails yet — book a load and they appear here.</div>}
            </div>
          </div>

          <div className="p-4 rounded-2xl border border-white/10 bg-slate-950/60" data-testid="lbc-actions">
            <div className="text-[10px] font-mono uppercase text-slate-500 mb-2 flex items-center gap-1.5"><Radar size={11} /> Board booking actions</div>
            <div className="space-y-1 max-h-[130px] overflow-y-auto">
              {(actions || []).slice(0, 8).map((a) => {
                const [ml, mc] = MODE_META[a.mode] || ["?", "#64748B"];
                return (
                  <div key={a.action_id} className="text-[10px] font-mono flex items-center gap-2">
                    <span className="px-1.5 rounded text-[8px] font-black" style={{ color: mc, border: `1px solid ${mc}55` }}>{ml}</span>
                    <span className="text-cyan-300 shrink-0">{a.load_id}</span>
                    <span className="text-slate-400 truncate">{a.detail}</span>
                  </div>
                );
              })}
              {(actions || []).length === 0 && <div className="text-[11px] text-slate-600 font-mono">No board actions yet.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
