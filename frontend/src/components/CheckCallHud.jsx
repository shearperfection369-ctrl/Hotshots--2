/**
 * <CheckCallHud bookingId={id} />
 *
 * In-transit load monitoring HUD. Log manual check-calls with driver
 * location, ETA, notes; the panel auto-advances the booking's
 * transit_status pill (DISPATCHED → AT_SHIPPER → LOADED → IN_TRANSIT →
 * AT_RECEIVER → UNLOADED → DELIVERED · plus EXCEPTION escape hatch).
 */
import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PhoneCall, MapPin, Clock } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const STATUS_ORDER = ["DISPATCHED", "AT_SHIPPER", "LOADED", "IN_TRANSIT", "AT_RECEIVER", "UNLOADED", "DELIVERED", "EXCEPTION"];
const STATUS_COLOR = {
  DISPATCHED:   "bg-slate-500/15 text-slate-300 border-slate-500/40",
  AT_SHIPPER:   "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  LOADED:       "bg-indigo-500/15 text-indigo-300 border-indigo-500/40",
  IN_TRANSIT:   "bg-blue-500/15 text-blue-300 border-blue-500/40",
  AT_RECEIVER:  "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40",
  UNLOADED:     "bg-amber-500/15 text-amber-300 border-amber-500/40",
  DELIVERED:    "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  EXCEPTION:    "bg-red-500/15 text-red-300 border-red-500/40",
};

export function CheckCallHud({ bookingId }) {
  const [data, setData] = useState({ calls: [], transit_status: null, available_statuses: STATUS_ORDER });
  const [form, setForm] = useState({ status: "IN_TRANSIT", location: "", miles_remaining: "", eta_iso: "", driver_name: "", notes: "" });
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!bookingId) return;
    api.get(`/brokerage/bookings/${bookingId}/check-calls`)
      .then(({ data: d }) => setData(d))
      .catch(() => {});
  }, [bookingId, tick]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.status) return;
    setBusy(true);
    try {
      const payload = { ...form,
        miles_remaining: form.miles_remaining ? Number(form.miles_remaining) : null,
        eta_iso: form.eta_iso ? new Date(form.eta_iso).toISOString() : null };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      await api.post(`/brokerage/bookings/${bookingId}/check-call`, payload);
      toast.success("Check-call logged");
      setForm({ ...form, location: "", miles_remaining: "", notes: "" });
      setTick((t) => t + 1);
    } catch (e) {
      console.error(e); toast.error("Failed to log call");
    } finally { setBusy(false); }
  };

  const cur = data.transit_status;

  return (
    <Card className="bg-[#0F1421] border-cyan-500/30" data-testid={`check-call-hud-${bookingId}`}>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-sm flex items-center gap-2">
            <PhoneCall size={14} className="text-cyan-400" /> Check-Call HUD
          </CardTitle>
          {cur && (
            <Badge className={`${STATUS_COLOR[cur] || ""} border font-mono text-[10px]`}
              data-testid="check-call-current-status">
              {cur}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Progress rail */}
        <div className="flex items-center gap-1 flex-wrap">
          {STATUS_ORDER.slice(0, 7).map((s, i) => {
            const idx = STATUS_ORDER.indexOf(cur);
            const reached = idx >= 0 && i <= idx;
            return (
              <div key={s} className={`flex-1 min-w-16 text-[9px] font-mono py-1.5 rounded text-center border ${
                reached ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-200" : "bg-black/20 border-white/5 text-slate-600"
              }`} data-testid={`rail-${s}`}>
                {s.replace("_", " ")}
              </div>
            );
          })}
        </div>

        {/* Compose form */}
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5">
          <div>
            <Label className="text-[10px] font-mono uppercase">Status *</Label>
            <Select value={form.status} onValueChange={(v) => set("status", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {(data.available_statuses || STATUS_ORDER).map((s) => (
                  <SelectItem key={s} value={s} data-testid={`cc-status-${s}`}>{s.replace("_", " ")}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <Label className="text-[10px] font-mono uppercase">Location</Label>
            <Input value={form.location} onChange={(e) => set("location", e.target.value)}
              placeholder="I-94 W, Madison WI" className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-location" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase">Miles remaining</Label>
            <Input type="number" value={form.miles_remaining} onChange={(e) => set("miles_remaining", e.target.value)}
              className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-miles" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase">ETA (datetime)</Label>
            <Input type="datetime-local" value={form.eta_iso} onChange={(e) => set("eta_iso", e.target.value)}
              className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-eta" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase">Driver</Label>
            <Input value={form.driver_name} onChange={(e) => set("driver_name", e.target.value)}
              className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-driver" />
          </div>
          <div className="col-span-3">
            <Label className="text-[10px] font-mono uppercase">Notes</Label>
            <Input value={form.notes} onChange={(e) => set("notes", e.target.value)}
              placeholder="30 min ahead of plan, no dock issues" className="bg-[#0B1320] border-white/10 h-9" data-testid="cc-notes" />
          </div>
        </div>
        <div className="flex justify-end">
          <Button size="sm" onClick={submit} disabled={busy}
            className="bg-cyan-500 text-black font-bold" data-testid="cc-submit">
            Log Check-Call
          </Button>
        </div>

        {/* History */}
        {(data.calls || []).length > 0 && (
          <div className="pt-3 border-t border-white/5 space-y-1.5" data-testid="cc-history">
            <div className="text-[10px] font-mono uppercase text-slate-500 tracking-wider">Recent calls</div>
            {data.calls.slice(0, 6).map((c) => (
              <div key={c.call_id} className="flex items-start gap-2 p-2 rounded bg-[#0B0E14] border border-white/5 text-xs"
                data-testid={`cc-row-${c.call_id}`}>
                <Badge className={`${STATUS_COLOR[c.status] || ""} border font-mono text-[9px]`}>
                  {c.status}
                </Badge>
                <div className="flex-1 min-w-0">
                  {c.location && (
                    <div className="text-slate-200 truncate">
                      <MapPin size={10} className="inline mr-1 text-cyan-400" />{c.location}
                    </div>
                  )}
                  <div className="text-[10px] text-slate-500 font-mono">
                    {c.at?.slice(0, 16)?.replace("T", " ")}
                    {c.driver_name && ` · ${c.driver_name}`}
                    {c.miles_remaining !== null && c.miles_remaining !== undefined && ` · ${c.miles_remaining}mi`}
                    {c.eta_iso && ` · ETA ${c.eta_iso.slice(0, 16).replace("T", " ")}`}
                  </div>
                  {c.notes && <div className="text-[11px] text-slate-400 mt-0.5">{c.notes}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
