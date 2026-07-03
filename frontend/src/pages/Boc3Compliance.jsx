/**
 * /boc3-compliance — 50-state BOC-3 process agent tracker with renewal
 * calendar + color-coded alerts. Rivals Oversize Permits Inc.,
 * ComplianceIQ, Iron Bow.
 *
 * Tabs:
 *   • Coverage Map — 51 US jurisdictions with status per state
 *   • Renewal Calendar — 24-month view · yellow (≤60d) · red (≤30d)
 *   • Alerts — active red + yellow + expired filings
 */
import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { ShieldCheck, CalendarClock, AlertTriangle, RefreshCw, Upload, FileText } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { authedDownload } from "@/lib/authedDownload";

const STATUS_COLOR = {
  PENDING_FILE: "bg-slate-500/15 text-slate-300 border-slate-500/40",
  FILED:        "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  ACCEPTED:     "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  REJECTED:     "bg-red-500/15 text-red-300 border-red-500/40",
  EXPIRED:      "bg-red-600/20 text-red-200 border-red-600/50",
  RENEWAL_DUE:  "bg-amber-500/15 text-amber-300 border-amber-500/40",
  VOID:         "bg-zinc-500/15 text-zinc-400 border-zinc-500/40",
};

const ALERT_COLOR = {
  RED:     "bg-red-500/25 border-red-500 text-red-100",
  YELLOW:  "bg-amber-500/25 border-amber-500 text-amber-100",
  EXPIRED: "bg-red-700/30 border-red-700 text-red-100",
};

export default function Boc3Compliance() {
  const [states, setStates] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [filings, setFilings] = useState([]);
  const [coverage, setCoverage] = useState(null);
  const [alerts, setAlerts] = useState({ red: [], yellow: [], expired: [] });
  const [calendar, setCalendar] = useState({ months: [] });
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState(null);

  useEffect(() => {
    api.get("/boc3/states").then(({ data }) => { setStates(data.items || []); setStatuses(data.statuses || []); });
  }, []);
  useEffect(() => {
    api.get("/boc3/filings").then(({ data }) => setFilings(data.items || []));
    api.get("/boc3/coverage").then(({ data }) => setCoverage(data));
    api.get("/boc3/alerts").then(({ data }) => setAlerts(data));
    api.get("/boc3/calendar").then(({ data }) => setCalendar(data));
  }, [tick]);

  const byState = useMemo(() => {
    const m = {};
    for (const f of filings) m[f.state_code] = f;
    return m;
  }, [filings]);

  const refresh = () => setTick((t) => t + 1);

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="boc3-page">
      <header className="mb-6 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 font-mono text-[11px] uppercase tracking-[0.18em] mb-1.5">
            <ShieldCheck size={14} /> Compliance · BOC-3 Process Agent Coverage
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter">BOC-3 Compliance</h1>
          <p className="text-slate-400 text-sm mt-2 max-w-2xl">
            Track every state process-agent designation, renewal deadlines, rejections, and compliance certificates —
            with color-coded alerts at 60 and 30 days before expiration.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} className="border-cyan-500/40" data-testid="boc3-refresh">
          <RefreshCw size={13} className="mr-1" /> Refresh
        </Button>
      </header>

      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <StatCard label="Jurisdictions covered" value={coverage ? `${coverage.covered_count} / ${coverage.total_jurisdictions}` : "—"}
          sublabel={coverage ? `${coverage.percent_covered}%` : ""} testid="boc3-stat-coverage" tone="cyan" />
        <StatCard label="Red alerts (≤30d)" value={alerts.red_count} tone="red" testid="boc3-stat-red" />
        <StatCard label="Yellow alerts (≤60d)" value={alerts.yellow_count} tone="amber" testid="boc3-stat-yellow" />
        <StatCard label="Expired" value={alerts.expired_count} tone="red" testid="boc3-stat-expired" />
      </div>

      <Tabs defaultValue="coverage" className="space-y-4">
        <TabsList className="bg-[#0F1421] border border-white/5 p-1">
          <TabsTrigger value="coverage" data-testid="tab-coverage"><ShieldCheck size={13} className="mr-1" /> Coverage Map</TabsTrigger>
          <TabsTrigger value="calendar" data-testid="tab-calendar"><CalendarClock size={13} className="mr-1" /> Renewal Calendar</TabsTrigger>
          <TabsTrigger value="alerts" data-testid="tab-alerts"><AlertTriangle size={13} className="mr-1" /> Alerts</TabsTrigger>
        </TabsList>

        <TabsContent value="coverage">
          <Card className="bg-[#0F1421] border-white/5">
            <CardHeader><CardTitle className="text-base">All 51 Jurisdictions</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2" data-testid="boc3-state-grid">
                {states.map((s) => {
                  const f = byState[s.code];
                  const eff = f?.status_effective || f?.status;
                  const days = f?.days_to_expiry;
                  return (
                    <button key={s.code} onClick={() => setEditing({ state: s, filing: f })}
                      data-testid={`boc3-state-${s.code}`}
                      className={`text-left rounded-md border p-2.5 transition-colors ${
                        f ? "border-white/10 hover:border-cyan-500/60 bg-[#0B0E14]" : "border-dashed border-white/5 hover:border-cyan-500/40 bg-transparent opacity-70"
                      }`}>
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-sm">{s.code}</span>
                        <span className="text-[10px] text-slate-500 truncate">{s.name}</span>
                      </div>
                      {f ? (
                        <>
                          <Badge className={`${STATUS_COLOR[eff] || ""} border font-mono text-[9px] mt-1.5`}>
                            {eff}
                          </Badge>
                          {days !== null && days !== undefined && (
                            <div className={`text-[10px] mt-1 font-mono ${
                              days < 0 ? "text-red-400" : days <= 30 ? "text-red-300" : days <= 60 ? "text-amber-300" : "text-slate-500"
                            }`}>
                              {days < 0 ? `expired ${-days}d ago` : `${days}d to renew`}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-[10px] text-slate-600 mt-1.5 italic">no filing</div>
                      )}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="calendar">
          <Card className="bg-[#0F1421] border-white/5">
            <CardHeader>
              <CardTitle className="text-base">24-Month Renewal Calendar</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="boc3-calendar">
                {calendar.months?.map((m) => (
                  <div key={m.month}
                    className="rounded-md border border-white/5 bg-[#0B0E14] p-3"
                    data-testid={`boc3-month-${m.month}`}>
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-bold text-cyan-200 text-sm">{m.label}</span>
                      <span className="text-[10px] font-mono text-slate-500">{m.filings.length} due</span>
                    </div>
                    {m.filings.length === 0 ? (
                      <div className="text-[10px] text-slate-600 italic">—</div>
                    ) : (
                      <div className="space-y-1">
                        {m.filings.map((f) => (
                          <div key={f.filing_id}
                            className={`text-[11px] px-2 py-1 rounded border font-mono ${
                              ALERT_COLOR[f.alert] || "bg-slate-500/10 border-slate-500/30 text-slate-300"
                            }`}
                            data-testid={`boc3-cal-item-${f.state_code}`}>
                            <span className="font-bold">{f.state_code}</span>
                            <span className="ml-1 text-[10px] opacity-80">{f.days_to_expiry}d</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="alerts">
          <div className="space-y-3">
            {alerts.expired?.length > 0 && (
              <AlertGroup title="EXPIRED" tone="red" items={alerts.expired} onClick={(f) => setEditing({ state: states.find((s) => s.code === f.state_code), filing: f })} testid="alerts-expired" />
            )}
            {alerts.red?.length > 0 && (
              <AlertGroup title="RED — file within 30 days" tone="red" items={alerts.red} onClick={(f) => setEditing({ state: states.find((s) => s.code === f.state_code), filing: f })} testid="alerts-red" />
            )}
            {alerts.yellow?.length > 0 && (
              <AlertGroup title="YELLOW — review within 60 days" tone="amber" items={alerts.yellow} onClick={(f) => setEditing({ state: states.find((s) => s.code === f.state_code), filing: f })} testid="alerts-yellow" />
            )}
            {alerts.red?.length === 0 && alerts.yellow?.length === 0 && alerts.expired?.length === 0 && (
              <Card className="bg-emerald-500/[0.06] border-emerald-500/30">
                <CardContent className="p-6 text-center">
                  <ShieldCheck size={32} className="mx-auto text-emerald-400 mb-2" />
                  <div className="text-emerald-200 font-bold">All clear.</div>
                  <div className="text-emerald-400/70 text-xs">No renewals or rejections requiring action.</div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {editing && (
        <FilingDialog state={editing.state} existing={editing.filing} statuses={statuses}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); refresh(); }} />
      )}
    </div>
  );
}

function StatCard({ label, value, sublabel, testid, tone }) {
  const bg = { cyan: "border-cyan-500/30", red: "border-red-500/30", amber: "border-amber-500/30" }[tone] || "border-white/5";
  return (
    <Card className={`bg-[#0F1421] ${bg}`} data-testid={testid}>
      <CardContent className="p-3">
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">{label}</div>
        <div className="text-2xl font-black text-white mt-0.5">{value}</div>
        {sublabel && <div className="text-[11px] text-cyan-300 font-mono">{sublabel}</div>}
      </CardContent>
    </Card>
  );
}

function AlertGroup({ title, tone, items, onClick, testid }) {
  const border = tone === "red" ? "border-red-500/40" : "border-amber-500/40";
  return (
    <Card className={`bg-[#0F1421] ${border}`} data-testid={testid}>
      <CardHeader className="pb-2">
        <CardTitle className={`text-base ${tone === "red" ? "text-red-200" : "text-amber-200"}`}>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((f) => (
          <button key={f.filing_id} onClick={() => onClick(f)}
            data-testid={`alert-row-${f.state_code}`}
            className="w-full text-left flex justify-between items-center p-2.5 rounded border border-white/5 bg-[#0B0E14] hover:border-cyan-500/40 transition-colors">
            <div>
              <span className="font-mono font-bold text-cyan-300">{f.state_code}</span>
              <span className="ml-2 text-sm">{f.process_agent_name}</span>
              {f.certificate_number && <span className="ml-2 text-[10px] font-mono text-slate-500">Cert {f.certificate_number}</span>}
            </div>
            <div className={`text-xs font-mono ${tone === "red" ? "text-red-300" : "text-amber-300"}`}>
              {f.days_to_expiry < 0 ? `expired ${-f.days_to_expiry}d ago` : `${f.days_to_expiry}d`}
            </div>
          </button>
        ))}
      </CardContent>
    </Card>
  );
}

function FilingDialog({ state, existing, statuses, onClose, onSaved }) {
  const [form, setForm] = useState({
    state_code: state?.code || existing?.state_code || "",
    process_agent_name: existing?.process_agent_name || "",
    process_agent_address: existing?.process_agent_address || "",
    process_agent_phone: existing?.process_agent_phone || "",
    process_agent_email: existing?.process_agent_email || "",
    is_blanket: existing?.is_blanket || false,
    filed_at: existing?.filed_at?.slice(0, 10) || "",
    effective_date: existing?.effective_date?.slice(0, 10) || "",
    expires_at: existing?.expires_at?.slice(0, 10) || "",
    certificate_number: existing?.certificate_number || "",
    status: existing?.status || "PENDING_FILE",
    fees_usd: existing?.fees_usd ?? "",
    notes: existing?.notes || "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.state_code || !form.process_agent_name.trim() || !form.process_agent_address.trim()) {
      toast.error("State, agent name, and agent address are required");
      return;
    }
    try {
      const payload = { ...form,
        fees_usd: form.fees_usd === "" ? null : Number(form.fees_usd),
        filed_at: form.filed_at ? new Date(form.filed_at).toISOString() : null,
        effective_date: form.effective_date ? new Date(form.effective_date).toISOString() : null,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      await api.post("/boc3/filings", payload);
      toast.success(`Filing saved for ${form.state_code}`);
      onSaved();
    } catch (e) {
      console.error(e); toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const uploadCert = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !existing?.filing_id) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/boc3/filings/${existing.filing_id}/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Certificate uploaded");
      onSaved();
    } catch (er) {
      console.error(er); toast.error("Upload failed");
    }
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40 max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {state?.code} · {state?.name} · BOC-3 Filing
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-500">
            Track process-agent details, filing status, and renewal date. Attach the FMCSA-issued
            BOC-3 cert PDF once received.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2 flex items-center gap-2">
            <input type="checkbox" id="blanket" checked={form.is_blanket}
              onChange={(e) => set("is_blanket", e.target.checked)} data-testid="boc3-blanket" />
            <Label htmlFor="blanket" className="text-xs cursor-pointer">
              Blanket filing — covers all 51 jurisdictions in one designation
            </Label>
          </div>
          <F l="Process agent name *" v={form.process_agent_name} on={(v) => set("process_agent_name", v)} t="boc3-agent-name" />
          <F l="Process agent phone" v={form.process_agent_phone} on={(v) => set("process_agent_phone", v)} t="boc3-agent-phone" />
          <div className="col-span-2">
            <F l="Process agent address *" v={form.process_agent_address} on={(v) => set("process_agent_address", v)} t="boc3-agent-address" />
          </div>
          <F l="Agent email" type="email" v={form.process_agent_email} on={(v) => set("process_agent_email", v)} t="boc3-agent-email" />
          <F l="Certificate #" v={form.certificate_number} on={(v) => set("certificate_number", v)} t="boc3-cert" />
          <F l="Filed date" type="date" v={form.filed_at} on={(v) => set("filed_at", v)} t="boc3-filed-at" />
          <F l="Effective date" type="date" v={form.effective_date} on={(v) => set("effective_date", v)} t="boc3-effective" />
          <F l="Expires (renewal date)" type="date" v={form.expires_at} on={(v) => set("expires_at", v)} t="boc3-expires-at" />
          <F l="Fees paid (USD)" type="number" v={form.fees_usd} on={(v) => set("fees_usd", v)} t="boc3-fees" />
          <div>
            <Label className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 block">Status</Label>
            <Select value={form.status} onValueChange={(v) => set("status", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="boc3-status-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {statuses.map((s) => <SelectItem key={s} value={s} data-testid={`boc3-status-${s}`}>{s}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <F l="Notes / rejection reason" v={form.notes} on={(v) => set("notes", v)} t="boc3-notes" />
          </div>
          {existing?.filing_id && (
            <div className="col-span-2 mt-2 space-y-2">
              <Label className="text-[10px] font-mono uppercase text-slate-400">Certificate PDF</Label>
              <div className="flex items-center gap-2">
                {existing.cert_file_id ? (
                  <Button size="sm" variant="outline" className="border-cyan-500/40 text-cyan-200 h-8 text-xs"
                    onClick={() => authedDownload(`/boc3/filings/${existing.filing_id}/file`, existing.cert_filename || "boc3_cert.pdf")}
                    data-testid="boc3-cert-download">
                    <FileText size={12} className="mr-1" /> Download {existing.cert_filename}
                  </Button>
                ) : (
                  <span className="text-xs text-slate-500 italic">No cert attached yet</span>
                )}
                <label className="cursor-pointer">
                  <input type="file" accept=".pdf,.png,.jpg" className="hidden" onChange={uploadCert} data-testid="boc3-cert-upload" />
                  <span className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20">
                    <Upload size={12} /> Upload cert
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="boc3-submit">
            Save Filing
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function F({ l, v, on, type = "text", t }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 block">{l}</Label>
      <Input type={type} value={v ?? ""} onChange={(e) => on(e.target.value)}
        className="bg-[#0B1320] border-white/10 text-white" data-testid={t} />
    </div>
  );
}
