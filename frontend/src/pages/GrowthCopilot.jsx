import React, { useCallback, useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import ReactMarkdown from "react-markdown";
import {
  Target, Sparkles, Loader2, RefreshCw, Send, ShieldCheck, ClipboardList,
  TrendingUp, CheckCircle2, Circle, AlertTriangle, MessageSquare,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

const money = (v) => `$${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const SEV = {
  critical: "bg-red-500/15 text-red-300 border-red-500/40",
  high: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  medium: "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
};
const CSTATUS = {
  met: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  in_progress: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  action_needed: "bg-red-500/15 text-red-300 border-red-500/40",
};
const CAT = { sales: "text-emerald-300", carriers: "text-cyan-300", ops: "text-slate-300", compliance: "text-red-300", finance: "text-amber-300" };

export default function GrowthCopilot() {
  const { user } = useAuth();
  const [state, setState] = useState(null);
  const [plan, setPlan] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [compliance, setCompliance] = useState(null);
  const [genPlan, setGenPlan] = useState(false);
  const [genBrief, setGenBrief] = useState(false);
  const [msg, setMsg] = useState("");
  const [chat, setChat] = useState([]);
  const [asking, setAsking] = useState(false);
  const sessionRef = useRef(`gc-${(user?.user_id || "u").slice(-6)}-${new Date().toISOString().slice(0, 10)}`);
  const chatEnd = useRef(null);

  const load = useCallback(async () => {
    try {
      const [s, p, b, c, h] = await Promise.all([
        api.get("/copilot/state"), api.get("/copilot/plan"),
        api.get("/copilot/briefing/latest"), api.get("/copilot/compliance"),
        api.get(`/copilot/chat/${sessionRef.current}`),
      ]);
      setState(s.data); setPlan(p.data.plan); setBriefing(b.data.briefing);
      setCompliance(c.data); setChat(h.data.messages || []);
    } catch (_) { toast.error("Failed to load copilot data"); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [chat]);

  const generatePlan = async () => {
    setGenPlan(true);
    try { const r = await api.post("/copilot/plan/generate"); setPlan(r.data); toast.success("Master growth plan generated"); }
    catch (err) { toast.error(err.response?.data?.detail || "Plan generation failed"); }
    finally { setGenPlan(false); }
  };

  const generateBrief = async () => {
    setGenBrief(true);
    try { const r = await api.post("/copilot/briefing"); setBriefing(r.data); toast.success("Weekly briefing ready"); }
    catch (err) { toast.error(err.response?.data?.detail || "Briefing failed"); }
    finally { setGenBrief(false); }
  };

  const toggleTask = async (id) => {
    try { await api.post(`/copilot/plan/tasks/${id}/toggle`); const r = await api.get("/copilot/plan"); setPlan(r.data.plan); }
    catch (_) { toast.error("Failed to update task"); }
  };

  const setCompStatus = async (id, status) => {
    try {
      await api.post(`/copilot/compliance/${id}/status`, { status });
      const [c, s] = await Promise.all([api.get("/copilot/compliance"), api.get("/copilot/state")]);
      setCompliance(c.data); setState(s.data);
    } catch (err) { toast.error(err.response?.data?.detail || "Update failed"); }
  };

  const ask = async () => {
    const text = msg.trim();
    if (!text) return;
    setMsg("");
    setChat((c) => [...c, { role: "user", content: text }]);
    setAsking(true);
    try {
      const r = await api.post("/copilot/chat", { session_id: sessionRef.current, message: text });
      setChat((c) => [...c, { role: "assistant", content: r.data.reply }]);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Copilot unavailable");
    } finally { setAsking(false); }
  };

  const wk = state?.week || {};
  const pct = Math.min(100, state?.progress_pct || 0);

  return (
    <>
      <Topbar title="AI Growth Copilot" subtitle="Mission: $20,000/week net margin after all expenses — planned, tracked, and guided in real time" />
      <div className="p-4 md:p-6 space-y-5" data-testid="growth-copilot-page">
        {/* Goal hero */}
        <Card className="p-5 bg-gradient-to-br from-slate-950 via-blue-950/30 to-slate-950 border-amber-400/30" data-testid="gc-goal-card">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-amber-300 flex items-center gap-1.5"><Target size={12} /> Mission Target</div>
              <div className="font-display text-3xl font-black text-white mt-1">
                <span data-testid="gc-net-week" className={wk.net_margin > 0 ? "text-emerald-300" : "text-red-300"}>{money(wk.net_margin)}</span>
                <span className="text-slate-500 text-xl"> / {money(state?.goal_weekly_net || 20000)} net · week</span>
              </div>
              <div className="text-xs text-slate-400 font-mono mt-1">
                Rev {money(wk.revenue)} · gross {money(wk.gross_margin)} · overhead {money(wk.overhead)} ({Object.keys(state?.overhead_breakdown || {}).length} expense lines) · {wk.loads || 0} loads · avg {money(wk.avg_margin_per_load)}/load
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-mono uppercase text-slate-500">Gap to goal</div>
              <div className="text-xl font-mono font-bold text-amber-300">{money(state?.gap_to_goal)}</div>
              {state?.loads_needed_per_week && (
                <div className="text-[11px] text-slate-400 font-mono">≈ {state.loads_needed_per_week} loads/wk at current margin</div>
              )}
            </div>
          </div>
          <div className="mt-3 h-2.5 rounded-full bg-white/5 overflow-hidden">
            <div className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 transition-all duration-700" style={{ width: `${pct}%` }} data-testid="gc-progress-bar" />
          </div>
          <div className="mt-1 text-[10px] font-mono text-slate-500">{pct}% of the $20k/wk mission · {state?.compliance_gaps ?? "—"} compliance items open · {state?.sentinel_active_alerts ?? 0} sentinel alerts</div>
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {/* Left: plan + briefing */}
          <div className="space-y-5">
            <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="gc-plan-card">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2"><ClipboardList size={13} /> Master Growth Plan</div>
                <Button size="sm" onClick={generatePlan} disabled={genPlan} data-testid="gc-generate-plan-btn"
                        className="bg-amber-500 hover:bg-amber-400 text-black font-semibold h-8 text-xs">
                  {genPlan ? <Loader2 size={12} className="mr-1 animate-spin" /> : <Sparkles size={12} className="mr-1" />}
                  {plan ? "Regenerate" : "Generate plan"}
                </Button>
              </div>
              {!plan ? (
                <div className="text-sm text-slate-500 py-6 text-center">No plan yet — let the copilot build the road to $20k/week.</div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-slate-300 leading-relaxed">{plan.summary}</p>
                  <div className="max-h-[440px] overflow-y-auto space-y-3 pr-1">
                    {plan.phases.map((p, i) => {
                      const done = p.tasks.filter((t) => t.done).length;
                      return (
                        <div key={i} className="rounded-md border border-white/10 bg-white/[0.02] p-3" data-testid={`gc-phase-${i}`}>
                          <div className="flex items-center justify-between">
                            <div className="text-sm font-semibold text-white">{p.name}</div>
                            <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/40 font-mono text-[10px]">{money(p.target_weekly_net)}/wk</Badge>
                          </div>
                          <div className="text-[10px] font-mono text-slate-500 mt-0.5">{p.timeframe} · {p.focus} · {done}/{p.tasks.length} done</div>
                          <div className="mt-2 space-y-1">
                            {p.tasks.map((t) => (
                              <button key={t.task_id} onClick={() => toggleTask(t.task_id)} data-testid={`gc-task-${t.task_id}`}
                                      className="w-full flex items-start gap-2 text-left p-1.5 rounded hover:bg-white/[0.04]">
                                {t.done ? <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" /> : <Circle size={14} className="text-slate-600 mt-0.5 shrink-0" />}
                                <span className="flex-1">
                                  <span className={`text-xs ${t.done ? "text-slate-500 line-through" : "text-slate-200"}`}>{t.title}</span>
                                  <span className="block text-[10px] text-slate-500">{t.detail}</span>
                                </span>
                                <span className={`text-[9px] font-mono uppercase ${CAT[t.category] || "text-slate-400"}`}>{t.category}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </Card>

            <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="gc-briefing-card">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2"><TrendingUp size={13} /> This Week's Briefing</div>
                <Button size="sm" variant="outline" onClick={generateBrief} disabled={genBrief} data-testid="gc-briefing-btn"
                        className="bg-cyan-500/10 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/20 h-8 text-xs">
                  {genBrief ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />} New briefing
                </Button>
              </div>
              {briefing ? (
                <div className="prose prose-invert prose-sm max-w-none text-slate-300 text-[13px] leading-relaxed max-h-[320px] overflow-y-auto pr-1" data-testid="gc-briefing-text">
                  <ReactMarkdown>{briefing.text}</ReactMarkdown>
                  <div className="text-[10px] font-mono text-slate-600 not-prose mt-2">{new Date(briefing.created_at).toLocaleString()}</div>
                </div>
              ) : (
                <div className="text-sm text-slate-500 py-4 text-center">Generate your first weekly action briefing.</div>
              )}
            </Card>
          </div>

          {/* Right: chat + compliance */}
          <div className="space-y-5">
            <Card className="p-4 bg-slate-950/60 border-white/10 flex flex-col" data-testid="gc-chat-card">
              <div className="text-xs font-mono uppercase tracking-widest text-emerald-300 flex items-center gap-2 mb-2"><MessageSquare size={13} /> Real-Time Copilot</div>
              <div className="flex-1 min-h-[220px] max-h-[340px] overflow-y-auto space-y-2 pr-1" data-testid="gc-chat-history">
                {chat.length === 0 && (
                  <div className="text-xs text-slate-500 space-y-1.5 py-2">
                    <div>Ask me anything about growing Orisei. Try:</div>
                    {["How many loads a week do we need to hit $20k net?",
                      "What compliance items must I close before my first 50 loads?",
                      "Build me a prospecting script for MN food-grade shippers"].map((s) => (
                      <button key={s} onClick={() => setMsg(s)} data-testid="gc-chat-suggestion"
                              className="block text-left px-2 py-1 rounded border border-white/10 hover:border-emerald-400/40 hover:text-emerald-200 w-full">{s}</button>
                    ))}
                  </div>
                )}
                {chat.map((m, i) => (
                  <div key={i} className={`p-2.5 rounded-md text-[13px] leading-relaxed ${m.role === "user" ? "bg-cyan-500/10 border border-cyan-500/20 text-cyan-100 ml-8" : "bg-white/[0.03] border border-white/10 text-slate-200 mr-4"}`}>
                    {m.role === "assistant" ? <div className="prose prose-invert prose-sm max-w-none"><ReactMarkdown>{m.content}</ReactMarkdown></div> : m.content}
                  </div>
                ))}
                {asking && <div className="flex items-center gap-2 text-xs text-slate-500"><Loader2 size={12} className="animate-spin" /> Copilot analyzing live business data…</div>}
                <div ref={chatEnd} />
              </div>
              <div className="flex gap-2 mt-3">
                <Input value={msg} onChange={(e) => setMsg(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()}
                       placeholder="Ask your growth copilot…" data-testid="gc-chat-input"
                       className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
                <Button onClick={ask} disabled={asking || !msg.trim()} data-testid="gc-chat-send-btn"
                        className="bg-emerald-500 hover:bg-emerald-400 text-black shrink-0"><Send size={14} /></Button>
              </div>
            </Card>

            <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="gc-compliance-card">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs font-mono uppercase tracking-widest text-red-300 flex items-center gap-2"><ShieldCheck size={13} /> Compliance Watchtower</div>
                {compliance && (
                  <Badge className={`${compliance.met === compliance.total ? CSTATUS.met : CSTATUS.action_needed} font-mono text-[10px]`}>
                    {compliance.met}/{compliance.total} met
                  </Badge>
                )}
              </div>
              <div className="max-h-[380px] overflow-y-auto space-y-1.5 pr-1">
                {(compliance?.items || []).map((c) => (
                  <div key={c.item_id} className="p-2.5 rounded-md border border-white/5 bg-white/[0.02]" data-testid={`gc-comp-${c.item_id}`}>
                    <div className="flex items-start gap-2">
                      {c.status === "met" ? <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" /> : <AlertTriangle size={14} className={`mt-0.5 shrink-0 ${c.severity === "critical" ? "text-red-400" : "text-amber-400"}`} />}
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-white">{c.title}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">{c.detail}</div>
                      </div>
                      <Badge className={`${SEV[c.severity]} font-mono text-[8px] uppercase shrink-0`}>{c.severity}</Badge>
                    </div>
                    <div className="flex gap-1.5 mt-1.5 ml-6">
                      {["met", "in_progress", "action_needed"].map((s) => (
                        <button key={s} onClick={() => setCompStatus(c.item_id, s)} data-testid={`gc-comp-${c.item_id}-${s}`}
                                className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase border ${c.status === s ? CSTATUS[s] : "border-white/10 text-slate-600 hover:text-slate-300"}`}>
                          {s.replace("_", " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
}
