import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";
import {
  Video, Users, MessageSquare, Calendar, Send, ExternalLink, CheckCircle2, Plus
} from "lucide-react";

export default function Webex() {
  const [config, setConfig] = useState(null);
  const [spaces, setSpaces] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [log, setLog] = useState([]);
  const [tab, setTab] = useState("spaces");

  const [notifyOpen, setNotifyOpen] = useState(false);
  const [notifyForm, setNotifyForm] = useState({ space_id: "", text: "", shipment_ref: "" });

  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [schedForm, setSchedForm] = useState({ title: "", when: "", duration_min: 30, invitees: "" });

  const load = async () => {
    const [c, s, m, l] = await Promise.all([
      api.get("/webex/config"),
      api.get("/webex/spaces"),
      api.get("/webex/meetings"),
      api.get("/webex/log"),
    ]);
    setConfig(c.data); setSpaces(s.data); setMeetings(m.data); setLog(l.data);
  };
  useEffect(() => { load(); }, []);

  const notify = async () => {
    if (!notifyForm.space_id || !notifyForm.text) { toast.error("Space and message required"); return; }
    try {
      await api.post("/webex/notify", notifyForm);
      toast.success("Message posted to Webex space");
      setNotifyOpen(false);
      setNotifyForm({ space_id: "", text: "", shipment_ref: "" });
      load();
    } catch { toast.error("Failed to post"); }
  };

  const schedule = async () => {
    if (!schedForm.title || !schedForm.when) { toast.error("Title and start time required"); return; }
    try {
      const invitees = schedForm.invitees.split(",").map(s => s.trim()).filter(Boolean);
      const { data } = await api.post("/webex/schedule", { ...schedForm, invitees });
      toast.success(`Meeting scheduled: ${data.title}`, { description: data.join_url });
      setScheduleOpen(false);
      setSchedForm({ title: "", when: "", duration_min: 30, invitees: "" });
      load();
    } catch { toast.error("Failed to schedule"); }
  };

  return (
    <>
      <Topbar title="Cisco Webex" subtitle="Spaces · Meetings · Real-time team collaboration" />
      <div className="p-4 md:p-6 space-y-5">

        {config && (
          <Card className="hud-surface p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-1">Webex Integration</div>
                <h3 className="font-display text-lg font-bold flex items-center gap-2"><Video size={18} className="text-cyan-400" /> {config.site}</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 mt-4 text-xs">
                  <Field label="Org ID" value={config.org_id.slice(0, 24) + "…"} mono />
                  <Field label="Bot Email" value={config.bot_email} mono />
                  <Field label="Scopes" value={config.scopes.length + " granted"} />
                  <Field label="Status" value={<span className="text-emerald-400 inline-flex items-center gap-1"><CheckCircle2 size={11}/>CONNECTED</span>} />
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={() => setNotifyOpen(true)} data-testid="webex-notify-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
                  <Send size={14} className="mr-1.5" /> Post Message
                </Button>
                <Button onClick={() => setScheduleOpen(true)} data-testid="webex-schedule-btn" className="bg-white/5 hover:bg-white/10 text-white border border-white/10">
                  <Calendar size={14} className="mr-1.5" /> Schedule Meeting
                </Button>
              </div>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Spaces" value={spaces.length} accent="text-cyan-400" icon={Users} />
          <Stat label="Upcoming Meetings" value={meetings.length} accent="text-emerald-400" icon={Calendar} />
          <Stat label="Total Members" value={spaces.reduce((s, x) => s + x.members, 0)} accent="text-purple-400" icon={Users} />
          <Stat label="Messages Sent" value={log.length} accent="text-yellow-400" icon={MessageSquare} />
        </div>

        <Card className="hud-surface overflow-hidden">
          <div className="border-b border-white/5 px-5 py-3 flex items-center gap-1">
            {[
              { id: "spaces", label: "Spaces", count: spaces.length },
              { id: "meetings", label: "Meetings", count: meetings.length },
              { id: "log", label: "Activity Log", count: log.length },
            ].map((t) => (
              <button
                key={t.id} onClick={() => setTab(t.id)} data-testid={`webex-tab-${t.id}`}
                className={`px-4 py-2 rounded-md text-xs font-mono uppercase tracking-wider transition-all ${
                  tab === t.id ? "bg-cyan-500/15 text-cyan-300" : "text-slate-400 hover:text-white"
                }`}
              >{t.label} <span className="opacity-60 ml-1">({t.count})</span></button>
            ))}
          </div>

          {tab === "spaces" && (
            <div className="divide-y divide-white/5">
              {spaces.map((s) => (
                <div key={s.id} className="px-5 py-3 flex items-center justify-between hover:bg-white/[0.02]" data-testid={`webex-space-${s.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-md bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
                      {s.type === "direct" ? <MessageSquare size={15} className="text-cyan-400" /> : <Users size={15} className="text-cyan-400" />}
                    </div>
                    <div>
                      <div className="text-white font-medium">{s.title}</div>
                      <div className="text-[10px] font-mono text-slate-500">{s.id} · {s.members} members · last activity {s.last_activity}</div>
                    </div>
                  </div>
                  <Button
                    onClick={() => { setNotifyForm({ ...notifyForm, space_id: s.id }); setNotifyOpen(true); }}
                    className="bg-white/5 hover:bg-white/10 text-cyan-300 border border-cyan-500/20 h-8 text-xs"
                  >
                    <Send size={12} className="mr-1" /> Post
                  </Button>
                </div>
              ))}
            </div>
          )}

          {tab === "meetings" && (
            <div className="divide-y divide-white/5">
              {meetings.map((m) => (
                <div key={m.id} className="px-5 py-4 hover:bg-white/[0.02]" data-testid={`webex-meeting-${m.id}`}>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-white font-display font-semibold">{m.title}</div>
                      <div className="text-[11px] font-mono text-slate-500 mt-0.5">{m.id} · hosted by {m.host}</div>
                      <div className="flex items-center gap-4 mt-2 text-xs">
                        <span className="text-slate-300 font-mono">{new Date(m.start).toLocaleString()}</span>
                        <span className="text-slate-400">{m.duration_min} min</span>
                        <Badge className="bg-cyan-500/10 text-cyan-300 border-cyan-500/30 font-mono text-[10px]">{m.attendees} invited</Badge>
                      </div>
                    </div>
                    <a href={m.join_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs">
                      JOIN <ExternalLink size={12} />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "log" && (
            <table className="w-full text-sm">
              <thead className="bg-[#0B0E14] text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="text-left py-3 px-4">Time</th>
                  <th className="text-left py-3 px-4">Space</th>
                  <th className="text-left py-3 px-4">User</th>
                  <th className="text-left py-3 px-4">Shipment</th>
                  <th className="text-left py-3 px-4">Message</th>
                  <th className="text-right py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {log.map((l) => (
                  <tr key={l.log_id} className="border-t border-white/5 hover:bg-white/[0.02]">
                    <td className="py-2.5 px-4 text-slate-400 text-xs">{new Date(l.posted_at).toLocaleString()}</td>
                    <td className="py-2.5 px-4 text-cyan-300">{l.space_id}</td>
                    <td className="py-2.5 px-4 text-slate-300">{l.user_name}</td>
                    <td className="py-2.5 px-4 text-slate-400">{l.shipment_ref || "—"}</td>
                    <td className="py-2.5 px-4 text-slate-300 max-w-md truncate">{l.text}</td>
                    <td className="py-2.5 px-4 text-right text-emerald-400 text-[10px]">✓ {l.status}</td>
                  </tr>
                ))}
                {log.length === 0 && <tr><td colSpan={6} className="text-center py-10 text-slate-500">No messages posted yet.</td></tr>}
              </tbody>
            </table>
          )}
        </Card>
      </div>

      {/* Notify dialog */}
      <Dialog open={notifyOpen} onOpenChange={setNotifyOpen}>
        <DialogContent className="bg-[#131821] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Post to Webex Space</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Space</label>
              <Select value={notifyForm.space_id} onValueChange={(v) => setNotifyForm({ ...notifyForm, space_id: v })}>
                <SelectTrigger className="mt-1 bg-[#0B0E14] border-white/10"><SelectValue placeholder="Select a space" /></SelectTrigger>
                <SelectContent>
                  {spaces.map((s) => <SelectItem key={s.id} value={s.id}>{s.title}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Shipment Ref (optional)</label>
              <Input value={notifyForm.shipment_ref} onChange={(e) => setNotifyForm({ ...notifyForm, shipment_ref: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" placeholder="TN-12345" />
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Message</label>
              <Textarea data-testid="webex-notify-text" value={notifyForm.text} onChange={(e) => setNotifyForm({ ...notifyForm, text: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10 min-h-[100px]" placeholder="Type your message to the team..." />
            </div>
            <Button data-testid="webex-notify-submit" onClick={notify} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">POST TO SPACE</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Schedule dialog */}
      <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
        <DialogContent className="bg-[#131821] border-white/10">
          <DialogHeader><DialogTitle className="font-display">Schedule Webex Meeting</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Title</label>
              <Input value={schedForm.title} onChange={(e) => setSchedForm({ ...schedForm, title: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Start</label>
                <Input type="datetime-local" value={schedForm.when} onChange={(e) => setSchedForm({ ...schedForm, when: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" />
              </div>
              <div>
                <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Duration (min)</label>
                <Input type="number" value={schedForm.duration_min} onChange={(e) => setSchedForm({ ...schedForm, duration_min: parseInt(e.target.value) || 30 })} className="mt-1 bg-[#0B0E14] border-white/10 font-mono" />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Invitees (comma-separated emails)</label>
              <Input value={schedForm.invitees} onChange={(e) => setSchedForm({ ...schedForm, invitees: e.target.value })} className="mt-1 bg-[#0B0E14] border-white/10" placeholder="kirk.juergins@tennantco.com, ..." />
            </div>
            <Button onClick={schedule} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold">SCHEDULE MEETING</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Field({ label, value, mono }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-slate-300 mt-0.5 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

function Stat({ label, value, accent, icon: Icon }) {
  return (
    <Card className="hud-surface p-5 relative">
      {Icon && <Icon size={16} className={`absolute top-4 right-4 ${accent} opacity-50`} />}
      <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">{label}</div>
      <div className={`mt-2 text-2xl font-mono font-bold tabular-nums ${accent}`}>{value}</div>
    </Card>
  );
}
