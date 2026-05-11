import React, { useEffect, useRef, useState } from "react";
import Topbar from "../components/Topbar";
import { api, BACKEND_URL } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Hash, Send } from "lucide-react";
import { useAuth } from "../lib/auth";

export default function Chat() {
  const { user } = useAuth();
  const [channels, setChannels] = useState([]);
  const [active, setActive] = useState("general");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const wsRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => { api.get("/chat/channels").then(({ data }) => setChannels(data)); }, []);

  useEffect(() => {
    (async () => {
      const { data } = await api.get(`/chat/messages?channel=${active}`);
      setMessages(data);
    })();
  }, [active]);

  useEffect(() => {
    // Get session_token cookie value to authenticate WS (cookie not auto-attached on WS to all domains)
    // We rely on backend cookie auth — pass token via query for explicit handshake.
    const tokenMatch = document.cookie.match(/(?:^|;\s*)session_token=([^;]+)/);
    const token = tokenMatch ? tokenMatch[1] : null;
    if (!token) return;
    const wsUrl = BACKEND_URL.replace(/^http/, "ws") + `/api/ws/chat?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const { type, data } = JSON.parse(e.data);
      if (type === "message" && data.channel === active) {
        setMessages((m) => [...m, data]);
      }
    };
    ws.onclose = () => { wsRef.current = null; };
    return () => ws.close();
  }, [active]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = (e) => {
    e?.preventDefault();
    if (!draft.trim() || !wsRef.current || wsRef.current.readyState !== 1) return;
    wsRef.current.send(JSON.stringify({ channel: active, text: draft.trim() }));
    setDraft("");
  };

  return (
    <>
      <Topbar title="Team Chat" subtitle="Real-time messaging across operations" />
      <div className="p-4 md:p-6">
        <Card className="hud-surface overflow-hidden grid grid-cols-1 md:grid-cols-12 min-h-[70vh]">
          <aside className="md:col-span-3 border-r border-white/5 p-3">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 px-2 mb-2">Channels</div>
            {channels.map((c) => (
              <button
                key={c.id}
                onClick={() => setActive(c.id)}
                data-testid={`channel-${c.id}`}
                className={`w-full text-left flex items-start gap-2 px-3 py-2 rounded-md mb-1 transition-all ${
                  active === c.id ? "bg-cyan-500/10 text-cyan-300 border-l-2 border-cyan-400" : "text-slate-400 hover:bg-white/[0.03] border-l-2 border-transparent"
                }`}
              >
                <Hash size={13} className="mt-0.5" />
                <div>
                  <div className="text-sm">{c.name}</div>
                  <div className="text-[10px] font-mono text-slate-500">{c.description}</div>
                </div>
              </button>
            ))}
          </aside>

          <section className="md:col-span-9 flex flex-col">
            <div className="px-5 py-3 border-b border-white/5 flex items-center gap-2">
              <Hash size={15} className="text-cyan-400" />
              <span className="font-display font-semibold">{active}</span>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-3" data-testid="chat-messages">
              {messages.map((m) => (
                <div key={m.message_id} className="flex items-start gap-3">
                  {m.user_picture ? (
                    <img src={m.user_picture} alt={m.user_name} className="w-8 h-8 rounded-full" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-cyan-500/30 text-cyan-200 flex items-center justify-center font-bold text-xs">
                      {m.user_name?.[0]?.toUpperCase() || "?"}
                    </div>
                  )}
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-white">{m.user_name}</span>
                      <span className="text-[10px] font-mono text-slate-500">{new Date(m.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div className="text-sm text-slate-300 mt-0.5">{m.text}</div>
                  </div>
                </div>
              ))}
              {messages.length === 0 && <div className="text-slate-500 text-sm text-center py-12">No messages yet — be the first to post in #{active}</div>}
            </div>
            <form onSubmit={send} className="border-t border-white/5 p-3 flex gap-2">
              <Input
                data-testid="chat-input"
                value={draft} onChange={(e) => setDraft(e.target.value)}
                placeholder={`Message #${active}`}
                className="bg-[#0B0E14] border-white/10 flex-1"
              />
              <Button type="submit" data-testid="chat-send" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
                <Send size={14} className="mr-1" /> Send
              </Button>
            </form>
          </section>
        </Card>
      </div>
    </>
  );
}
