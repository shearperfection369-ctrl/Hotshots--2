import React, { useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Sparkles, Send, Trash2, Bot, User as UserIcon } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

const SUGGESTED = [
  "What HS code should I use for a Tennant T16 AMR scrubber?",
  "Compare XPO vs SAIA for a 12,000-lb LTL shipment Holland → Atlanta.",
  "Which Incoterms should I use for an export to Rotterdam via ocean K+N?",
  "Auto-disputable accessorials I should flag in our freight audit rules?",
  "What documents do I need for an export to Mexico City?",
  "Best mode for 250 lbs of replacement scrubber brushes Louisville → Phoenix?",
];

export default function AIAssistant() {
  const { user } = useAuth();
  const [sessionId] = useState(() => {
    const k = "ai_session_id";
    let v = localStorage.getItem(k);
    if (!v) { v = `sess_${Date.now()}`; localStorage.setItem(k, v); }
    return v;
  });
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const loadHistory = async () => {
    try {
      const { data } = await api.get(`/ai/history?session_id=${sessionId}`);
      setMessages(data);
    } catch { setMessages([]); }
  };
  useEffect(() => { loadHistory(); }, [sessionId]);
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const msg = (text || draft).trim();
    if (!msg || sending) return;
    setSending(true);
    setMessages((m) => [...m, { role: "user", text: msg, created_at: new Date().toISOString() }]);
    setDraft("");
    try {
      const { data } = await api.post("/ai/chat", { session_id: sessionId, message: msg });
      setMessages((m) => [...m, { role: "assistant", text: data.reply, created_at: new Date().toISOString() }]);
    } catch (e) {
      toast.error(e.response?.data?.detail || "AI request failed");
    } finally {
      setSending(false);
    }
  };

  const clear = async () => {
    await api.delete(`/ai/history?session_id=${sessionId}`);
    setMessages([]);
    toast.success("Conversation cleared");
  };

  return (
    <>
      <Topbar title="HUDLINK · AI Co-Pilot" subtitle="Claude Sonnet 4.5 · Logistics & operations intelligence" />
      <div className="p-4 md:p-6">
        <Card className="hud-surface flex flex-col h-[78vh] overflow-hidden" data-testid="ai-assistant">
          <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center hud-glow-cyan">
                <Sparkles size={16} className="text-cyan-400" />
              </div>
              <div>
                <div className="font-display font-bold text-white flex items-center gap-2">HUDLINK <Badge className="bg-cyan-500/10 text-cyan-300 border-cyan-500/30 font-mono text-[10px]">claude-sonnet-4.5</Badge></div>
                <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">on-prem context · transportation domain expert</div>
              </div>
            </div>
            <Button variant="ghost" onClick={clear} data-testid="ai-clear-btn" className="text-slate-400 hover:text-red-400 hover:bg-red-500/10">
              <Trash2 size={14} className="mr-1.5" /> Clear
            </Button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4" data-testid="ai-messages">
            {messages.length === 0 && (
              <div className="text-center pt-12">
                <Sparkles className="w-12 h-12 text-cyan-400 mx-auto mb-3 opacity-50" />
                <div className="font-display text-lg text-white mb-1">How can I help, {user?.name?.split(" ")[0] || "team"}?</div>
                <div className="text-sm text-slate-400 mb-6">Ask me about shipments, freight audit rules, HS codes, or carrier strategy.</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-w-2xl mx-auto">
                  {SUGGESTED.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      data-testid="ai-suggestion"
                      className="text-left p-3 rounded-md border border-white/5 bg-white/[0.02] hover:border-cyan-500/30 hover:bg-cyan-500/[0.04] text-sm text-slate-300 transition-all"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
                {m.role === "assistant" && (
                  <div className="w-8 h-8 rounded-md bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-1">
                    <Bot size={14} className="text-cyan-400" />
                  </div>
                )}
                <div className={`max-w-[78%] p-3.5 rounded-lg ${
                  m.role === "user"
                    ? "bg-cyan-500/15 border border-cyan-500/30 text-white"
                    : "bg-white/[0.02] border border-white/5 text-slate-200"
                }`}>
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">{m.text}</div>
                  <div className="text-[10px] font-mono text-slate-500 mt-2">{new Date(m.created_at).toLocaleTimeString()}</div>
                </div>
                {m.role === "user" && (
                  <div className="w-8 h-8 rounded-md bg-white/[0.04] border border-white/10 flex items-center justify-center shrink-0 mt-1">
                    <UserIcon size={14} className="text-slate-300" />
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-md bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center"><Bot size={14} className="text-cyan-400" /></div>
                <div className="bg-white/[0.02] border border-white/5 rounded-lg p-3.5">
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 blink-dot"></span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 blink-dot" style={{ animationDelay: "0.2s" }}></span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 blink-dot" style={{ animationDelay: "0.4s" }}></span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="border-t border-white/5 p-3 flex gap-2"
          >
            <Input
              data-testid="ai-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask HUDLINK anything about transportation, freight, customs..."
              disabled={sending}
              className="bg-[#0B0E14] border-white/10 flex-1"
            />
            <Button
              type="submit"
              disabled={sending || !draft.trim()}
              data-testid="ai-send-btn"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_18px_rgba(0,229,255,0.4)]"
            >
              <Send size={14} className="mr-1.5" /> Send
            </Button>
          </form>
        </Card>
      </div>
    </>
  );
}
