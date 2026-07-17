import React, { useCallback, useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Checkbox } from "../components/ui/checkbox";
import { Megaphone, Send, Loader2, Mail, Users, FlaskConical } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

export default function LaunchBlast() {
  const [preview, setPreview] = useState(null);
  const [recipients, setRecipients] = useState([]);
  const [checked, setChecked] = useState({});
  const [testTo, setTestTo] = useState("");
  const [sending, setSending] = useState(false);
  const [testing, setTesting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const load = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([
        api.get("/launch-blast/preview"),
        api.get("/launch-blast/recipients"),
      ]);
      setPreview(p.data);
      setRecipients(r.data.recipients || []);
      setChecked(Object.fromEntries((r.data.recipients || []).map((x) => [x.email, true])));
    } catch (_) {
      toast.error("Failed to load launch blast data");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selected = useMemo(() => recipients.filter((r) => checked[r.email]), [recipients, checked]);

  const describeResult = (d) => {
    if (d.sent > 0) toast.success(`${d.sent} email(s) sent via Resend`);
    if (d.queued_awaiting_key > 0) toast.info(`${d.queued_awaiting_key} email(s) queued — will send the moment your Resend key is connected`);
    if (d.failed > 0) toast.error(`${d.failed} email(s) failed`);
  };

  const sendTest = async () => {
    if (!testTo) { toast.error("Enter an email for the test send"); return; }
    setTesting(true);
    try {
      const r = await api.post("/launch-blast/send", { test_to: testTo });
      describeResult(r.data);
      setLastResult(r.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Test send failed");
    } finally {
      setTesting(false);
    }
  };

  const sendBlast = async () => {
    if (selected.length === 0) { toast.error("Select at least one recipient"); return; }
    if (!window.confirm(`Send the launch announcement to ${selected.length} prospect(s)?`)) return;
    setSending(true);
    try {
      const r = await api.post("/launch-blast/send", { emails: selected.map((s) => s.email) });
      describeResult(r.data);
      setLastResult(r.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Blast failed");
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Topbar title="Launch Email Blast" subtitle="The launch card, turned into a ready-to-send announcement for your shipper prospect list" />
      <div className="p-4 md:p-6 grid grid-cols-1 xl:grid-cols-2 gap-5" data-testid="launch-blast-page">
        {/* Left: preview */}
        <Card className="p-4 bg-slate-950/60 border-white/10 flex flex-col" data-testid="launch-blast-preview-card">
          <div className="text-xs font-mono uppercase tracking-widest text-amber-300 flex items-center gap-2 mb-2">
            <Mail size={13} /> Email preview
          </div>
          <div className="text-sm text-white mb-1">Subject: <span className="text-amber-200">{preview?.subject || "…"}</span></div>
          <div className="flex-1 min-h-[480px] rounded-md overflow-hidden border border-white/10 bg-[#0B1320]">
            {preview?.html ? (
              <iframe title="launch-email-preview" srcDoc={preview.html} className="w-full h-full min-h-[480px]" data-testid="launch-blast-iframe" />
            ) : (
              <div className="grid place-items-center h-full text-slate-500 text-sm">Loading preview…</div>
            )}
          </div>
        </Card>

        {/* Right: recipients + send */}
        <div className="space-y-5">
          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="launch-blast-test-card">
            <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2 mb-3">
              <FlaskConical size={13} /> Test send
            </div>
            <div className="flex gap-2">
              <Input value={testTo} onChange={(e) => setTestTo(e.target.value)} type="email"
                     placeholder="you@oriseifreight.com" data-testid="launch-blast-test-input"
                     className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
              <Button onClick={sendTest} disabled={testing} data-testid="launch-blast-test-btn"
                      variant="outline" className="bg-cyan-500/10 border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/20 shrink-0">
                {testing ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Send size={14} className="mr-1" />} Send test
              </Button>
            </div>
            <div className="text-[11px] text-slate-500 mt-2">
              No Resend key yet? Sends are safely queued and fire automatically the moment the key lands in Connections.
            </div>
          </Card>

          <Card className="p-4 bg-slate-950/60 border-white/10" data-testid="launch-blast-recipients-card">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-mono uppercase tracking-widest text-cyan-300 flex items-center gap-2">
                <Users size={13} /> Prospect list
                <Badge className="bg-cyan-500/15 text-cyan-300 border-cyan-500/40 text-[10px]">{selected.length}/{recipients.length} selected</Badge>
              </div>
              <button
                className="text-[11px] font-mono text-slate-400 hover:text-cyan-300"
                data-testid="launch-blast-toggle-all"
                onClick={() => {
                  const all = selected.length !== recipients.length;
                  setChecked(Object.fromEntries(recipients.map((r) => [r.email, all])));
                }}>
                {selected.length !== recipients.length ? "Select all" : "Deselect all"}
              </button>
            </div>
            <div className="max-h-[300px] overflow-y-auto space-y-1 pr-1">
              {recipients.map((r) => (
                <label key={r.email} data-testid={`launch-blast-recipient-${r.email}`}
                       className="flex items-center gap-3 p-2 rounded-md hover:bg-white/[0.03] cursor-pointer">
                  <Checkbox checked={!!checked[r.email]}
                            onCheckedChange={(v) => setChecked({ ...checked, [r.email]: !!v })} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate">{r.company || r.email}</div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">{r.contact_name ? `${r.contact_name} · ` : ""}{r.email}</div>
                  </div>
                  <Badge className="bg-white/5 text-slate-400 border-white/10 text-[9px] font-mono shrink-0">{r.source}</Badge>
                </label>
              ))}
              {recipients.length === 0 && (
                <div className="text-sm text-slate-500 py-4 text-center">No prospects with email addresses yet.</div>
              )}
            </div>
            <Button onClick={sendBlast} disabled={sending || selected.length === 0}
                    data-testid="launch-blast-send-btn"
                    className="w-full mt-4 bg-amber-500 hover:bg-amber-400 text-black font-bold py-5">
              {sending ? <Loader2 size={15} className="mr-2 animate-spin" /> : <Megaphone size={15} className="mr-2" />}
              Send launch blast to {selected.length} prospect{selected.length === 1 ? "" : "s"}
            </Button>
            {lastResult && (
              <div className="mt-3 text-[11px] font-mono text-slate-400" data-testid="launch-blast-result">
                Last run: {lastResult.sent} sent · {lastResult.queued_awaiting_key} queued · {lastResult.failed} failed
                {!lastResult.resend_connected && " — Resend key not connected, everything queued"}
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
