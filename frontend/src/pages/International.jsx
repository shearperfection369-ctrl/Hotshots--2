/**
 * /international — Ocean + Intermodal Rail command center.
 *
 * Four tabs:
 *   • Container Bookings — create + browse + drive lifecycle
 *   • Ocean Carriers     — SCAC + alliance directory
 *   • Rail Yards         — Class-I intermodal facilities (filter by railroad)
 *   • Gate Events        — ingate / outgate log across all bookings
 *
 * Lifecycle: BOOKED → GATE_IN_ORIGIN → ON_VESSEL → DISCHARGED → AT_RAIL_RAMP
 *            → OUTGATED → DELIVERED → EMPTY_RETURNED
 *
 * Branded House BL + SLI PDFs are downloadable from each booking row.
 */
import React, { useEffect, useMemo, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Ship, Train, Container, Anchor, MapPin, FileText, ArrowRight, RotateCw, Plus, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { authedDownload } from "@/lib/authedDownload";

const STATUS_COLORS = {
  BOOKED:          "bg-cyan-500/15 text-cyan-300 border-cyan-500/40",
  GATE_IN_ORIGIN:  "bg-blue-500/15 text-blue-300 border-blue-500/40",
  ON_VESSEL:       "bg-indigo-500/15 text-indigo-300 border-indigo-500/40",
  DISCHARGED:      "bg-violet-500/15 text-violet-300 border-violet-500/40",
  AT_RAIL_RAMP:    "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/40",
  OUTGATED:        "bg-amber-500/15 text-amber-300 border-amber-500/40",
  DELIVERED:       "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  EMPTY_RETURNED:  "bg-slate-500/15 text-slate-300 border-slate-500/40",
};

export default function International() {
  const [ref, setRef] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    api.get("/international/reference").then(({ data }) => setRef(data)).catch(() => {});
  }, []);
  useEffect(() => {
    api.get("/international/container-bookings").then(({ data }) => setBookings(data.items || []))
      .catch(() => setBookings([]));
  }, [refreshTick]);

  return (
    <div className="p-6 max-w-7xl mx-auto" data-testid="international-page">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-cyan-400 font-mono text-[11px] uppercase tracking-[0.18em] mb-1.5">
            <Ship size={14} /> International · Ocean & Intermodal Rail
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-black tracking-tighter">
            Containerized Cargo Command Center
          </h1>
          <p className="text-slate-400 text-sm mt-2 max-w-2xl">
            Book ocean containers with the world&apos;s top carriers, ride intermodal rail through every major
            Class-I yard, and log every ingate/outgate as cargo moves POL → POD → ramp → consignee.
          </p>
        </div>
        <Button onClick={() => setRefreshTick((t) => t + 1)} variant="outline" size="sm"
          className="border-cyan-500/40" data-testid="intl-refresh-btn">
          <RotateCw size={13} className="mr-1" /> Refresh
        </Button>
      </header>

      <Tabs defaultValue="bookings" className="space-y-4">
        <TabsList className="bg-[#0F1421] border border-white/5 p-1">
          <TabsTrigger value="bookings" data-testid="tab-bookings">
            <Container size={14} className="mr-1" /> Container Bookings
          </TabsTrigger>
          <TabsTrigger value="ocean" data-testid="tab-ocean">
            <Anchor size={14} className="mr-1" /> Ocean Carriers
          </TabsTrigger>
          <TabsTrigger value="yards" data-testid="tab-yards">
            <Train size={14} className="mr-1" /> Rail Yards
          </TabsTrigger>
          <TabsTrigger value="gates" data-testid="tab-gates">
            <MapPin size={14} className="mr-1" /> Gate Events
          </TabsTrigger>
        </TabsList>

        <TabsContent value="bookings">
          <BookingsTab ref_={ref} bookings={bookings} refresh={() => setRefreshTick((t) => t + 1)} />
        </TabsContent>
        <TabsContent value="ocean">
          <OceanCarriersTab carriers={ref?.ocean_carriers || []} />
        </TabsContent>
        <TabsContent value="yards">
          <RailYardsTab yards={ref?.rail_yards || []} railroads={ref?.rail_carriers || []} />
        </TabsContent>
        <TabsContent value="gates">
          <GateEventsTab bookings={bookings} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* =================== CONTAINER BOOKINGS =================== */
function BookingsTab({ ref_, bookings, refresh }) {
  const [openNew, setOpenNew] = useState(false);
  const [statusBooking, setStatusBooking] = useState(null);
  const [gateBooking, setGateBooking] = useState(null);
  const [waybillBooking, setWaybillBooking] = useState(null);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div className="text-xs text-slate-400 font-mono">
          {bookings.length} active booking{bookings.length === 1 ? "" : "s"}
        </div>
        <Button onClick={() => setOpenNew(true)} className="bg-cyan-500 text-black font-bold"
          data-testid="new-booking-btn">
          <Plus size={14} className="mr-1" /> New Container Booking
        </Button>
      </div>

      {bookings.length === 0 ? (
        <Card className="bg-[#0F1421] border-white/5">
          <CardContent className="py-10 text-center text-slate-500 text-sm">
            <Container size={32} className="mx-auto mb-3 opacity-40" />
            No container bookings yet. Click &quot;New Container Booking&quot; to book your first ocean container.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="bookings-list">
          {bookings.map((b) => (
            <Card key={b.booking_id} className="bg-[#0F1421] border-white/5"
              data-testid={`booking-row-${b.booking_id}`}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className={`${STATUS_COLORS[b.status] || ""} border font-mono text-[10px]`}>
                        {b.status}
                      </Badge>
                      <span className="font-mono text-cyan-300 text-sm">{b.booking_number}</span>
                      <span className="text-slate-500 text-xs">·</span>
                      <span className="text-slate-300 text-sm">{b.carrier_name}</span>
                      <span className="font-mono text-[10px] text-slate-500">({b.carrier_scac})</span>
                      {b.hazmat && (
                        <Badge variant="outline" className="border-red-500/40 text-red-300 text-[10px]">
                          <AlertTriangle size={10} className="mr-1" /> IMDG {b.imdg_class || "—"}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-2 text-sm text-slate-200 flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{b.pol}</span>
                      <ArrowRight size={12} className="text-cyan-400" />
                      <span className="font-medium">{b.pod}</span>
                      {b.final_destination && b.final_destination !== b.pod && (
                        <>
                          <ArrowRight size={12} className="text-amber-400" />
                          <span className="text-amber-200">{b.final_destination}</span>
                        </>
                      )}
                    </div>
                    <div className="mt-1 text-xs text-slate-500 font-mono">
                      {b.container_count} × {b.container_size_type} · {b.commodity}
                      {b.vessel_name && ` · ${b.vessel_name} v.${b.voyage_number || "TBA"}`}
                      {b.etd && ` · ETD ${b.etd}`}
                      {b.eta && ` · ETA ${b.eta}`}
                    </div>
                    <div className="mt-1 text-[11px] text-slate-400">
                      <span className="text-slate-500">Shipper:</span> {b.shipper_name}
                      <span className="text-slate-500 mx-1.5">·</span>
                      <span className="text-slate-500">Consignee:</span> {b.consignee_name}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 items-end">
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" className="border-cyan-500/30 text-cyan-200 h-7 text-[11px]"
                        onClick={() => authedDownload(`/international/container-bookings/${b.booking_id}/house-bl.pdf`,
                                                       `HouseBL_${b.booking_id}.pdf`)}
                        data-testid={`booking-bl-${b.booking_id}`}>
                        <FileText size={11} className="mr-1" /> House BL
                      </Button>
                      <Button size="sm" variant="outline" className="border-amber-500/30 text-amber-200 h-7 text-[11px]"
                        onClick={() => authedDownload(`/international/container-bookings/${b.booking_id}/sli.pdf`,
                                                       `SLI_${b.booking_id}.pdf`)}
                        data-testid={`booking-sli-${b.booking_id}`}>
                        <FileText size={11} className="mr-1" /> SLI
                      </Button>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" className="text-cyan-300 h-7 text-[11px]"
                        onClick={() => setGateBooking(b)}
                        data-testid={`booking-gate-${b.booking_id}`}>
                        Gate event
                      </Button>
                      <Button size="sm" variant="ghost" className="text-cyan-300 h-7 text-[11px]"
                        onClick={() => setWaybillBooking(b)}
                        data-testid={`booking-waybill-${b.booking_id}`}>
                        Rail bill
                      </Button>
                      <Button size="sm" variant="ghost" className="text-emerald-300 h-7 text-[11px]"
                        onClick={() => setStatusBooking(b)}
                        data-testid={`booking-status-${b.booking_id}`}>
                        Advance status
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {openNew && ref_ && (
        <NewBookingDialog
          ref_={ref_}
          onClose={() => setOpenNew(false)}
          onSaved={() => { setOpenNew(false); refresh(); }}
        />
      )}
      {statusBooking && ref_ && (
        <StatusDialog
          booking={statusBooking}
          statuses={ref_.container_statuses}
          onClose={() => setStatusBooking(null)}
          onSaved={() => { setStatusBooking(null); refresh(); }}
        />
      )}
      {gateBooking && (
        <GateDialog
          booking={gateBooking}
          onClose={() => setGateBooking(null)}
          onSaved={() => { setGateBooking(null); refresh(); }}
        />
      )}
      {waybillBooking && ref_ && (
        <WaybillDialog
          booking={waybillBooking}
          rails={ref_.rail_carriers}
          yards={ref_.rail_yards}
          onClose={() => setWaybillBooking(null)}
          onSaved={() => { setWaybillBooking(null); refresh(); }}
        />
      )}
    </div>
  );
}

function NewBookingDialog({ ref_, onClose, onSaved }) {
  const [form, setForm] = useState({
    carrier_scac: "MAEU", booking_number: "", vessel_name: "", voyage_number: "",
    etd: "", eta: "", pol: "", pod: "", final_destination: "",
    container_size_type: "40HC", container_count: 1, commodity: "",
    hs_code: "", weight_kg: "", cargo_value_usd: "",
    hazmat: false, imdg_class: "", un_number: "",
    shipper_name: "", shipper_address: "", shipper_contact_email: "",
    consignee_name: "", consignee_address: "", consignee_contact_email: "",
    incoterms: "FOB", freight_terms: "Prepaid", rate_usd: "", notes: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.carrier_scac || !form.booking_number.trim() || !form.pol.trim()
        || !form.pod.trim() || !form.commodity.trim()
        || !form.shipper_name.trim() || !form.consignee_name.trim()) {
      toast.error("Carrier, booking #, POL/POD, commodity, shipper and consignee are required");
      return;
    }
    try {
      const payload = { ...form,
        container_count: Number(form.container_count || 1),
        weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
        cargo_value_usd: form.cargo_value_usd ? Number(form.cargo_value_usd) : null,
        rate_usd: form.rate_usd ? Number(form.rate_usd) : null,
      };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      await api.post("/international/container-bookings", payload);
      toast.success(`Container booking created with ${form.carrier_scac}`);
      onSaved();
    } catch (e) {
      console.error(e); toast.error("Failed to create booking");
    }
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40 max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Ship size={16} /> New Container Booking
          </DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-[10px] font-mono uppercase">Ocean Carrier *</Label>
            <Select value={form.carrier_scac} onValueChange={(v) => set("carrier_scac", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="new-carrier-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30 max-h-72">
                {ref_.ocean_carriers.map((c) => (
                  <SelectItem key={c.scac} value={c.scac} data-testid={`carrier-opt-${c.scac}`}>
                    {c.name} <span className="text-slate-500 ml-1.5 font-mono text-[10px]">({c.scac})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field l="Booking # *" v={form.booking_number} on={(v) => set("booking_number", v)} t="new-booking-num" />
          <Field l="Vessel" v={form.vessel_name} on={(v) => set("vessel_name", v)} t="new-vessel" />
          <Field l="Voyage" v={form.voyage_number} on={(v) => set("voyage_number", v)} t="new-voyage" />
          <Field l="ETD" type="date" v={form.etd} on={(v) => set("etd", v)} t="new-etd" />
          <Field l="ETA" type="date" v={form.eta} on={(v) => set("eta", v)} t="new-eta" />
          <Field l="POL (Port of Loading) *" v={form.pol} on={(v) => set("pol", v)} t="new-pol"
            ph="e.g. CNSHA · Shanghai" />
          <Field l="POD (Port of Discharge) *" v={form.pod} on={(v) => set("pod", v)} t="new-pod"
            ph="e.g. USLAX · Los Angeles" />
          <Field l="Final destination" v={form.final_destination} on={(v) => set("final_destination", v)}
            t="new-final-dest" ph="e.g. Memphis, TN (rail ramp)" />
          <div>
            <Label className="text-[10px] font-mono uppercase">Container size/type *</Label>
            <Select value={form.container_size_type} onValueChange={(v) => set("container_size_type", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="new-container-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {ref_.container_types.map((t) => (
                  <SelectItem key={t.code} value={t.code} data-testid={`ctype-opt-${t.code}`}>
                    {t.name} <span className="text-slate-500 ml-1.5 font-mono text-[10px]">({t.code})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field l="Container count *" type="number" v={form.container_count} on={(v) => set("container_count", v)} t="new-count" />
          <Field l="Commodity *" v={form.commodity} on={(v) => set("commodity", v)} t="new-commodity" />
          <Field l="HS code" v={form.hs_code} on={(v) => set("hs_code", v)} t="new-hs" />
          <Field l="Weight (kg)" type="number" v={form.weight_kg} on={(v) => set("weight_kg", v)} t="new-weight" />
          <Field l="Cargo value (USD)" type="number" v={form.cargo_value_usd} on={(v) => set("cargo_value_usd", v)} t="new-value" />
          <Field l="Shipper name *" v={form.shipper_name} on={(v) => set("shipper_name", v)} t="new-shipper" />
          <Field l="Shipper email" type="email" v={form.shipper_contact_email} on={(v) => set("shipper_contact_email", v)} t="new-shipper-email" />
          <Field l="Consignee name *" v={form.consignee_name} on={(v) => set("consignee_name", v)} t="new-consignee" />
          <Field l="Consignee email" type="email" v={form.consignee_contact_email} on={(v) => set("consignee_contact_email", v)} t="new-consignee-email" />
          <Field l="Incoterms" v={form.incoterms} on={(v) => set("incoterms", v)} t="new-incoterms"
            ph="FOB / CIF / DAP / DDP" />
          <Field l="Freight terms" v={form.freight_terms} on={(v) => set("freight_terms", v)} t="new-freight-terms"
            ph="Prepaid / Collect" />
          <Field l="Rate (USD)" type="number" v={form.rate_usd} on={(v) => set("rate_usd", v)} t="new-rate" />
          <div className="col-span-2 flex items-center gap-2 mt-1">
            <input type="checkbox" id="hazmat" checked={form.hazmat}
              onChange={(e) => set("hazmat", e.target.checked)} data-testid="new-hazmat" />
            <Label htmlFor="hazmat" className="text-[12px] cursor-pointer">Dangerous Goods (IMDG-regulated)</Label>
          </div>
          {form.hazmat && (
            <>
              <Field l="IMDG Class" v={form.imdg_class} on={(v) => set("imdg_class", v)} t="new-imdg" />
              <Field l="UN Number" v={form.un_number} on={(v) => set("un_number", v)} t="new-un" />
            </>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="new-submit">
            Create Booking
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StatusDialog({ booking, statuses, onClose, onSaved }) {
  const idx = statuses.indexOf(booking.status);
  const next = statuses[idx + 1] || statuses[0];
  const [val, setVal] = useState(next);
  const [note, setNote] = useState("");
  const submit = async () => {
    try {
      await api.post(`/international/container-bookings/${booking.booking_id}/status`,
                      { new_status: val, note });
      toast.success(`Advanced to ${val}`);
      onSaved();
    } catch (e) { console.error(e); toast.error("Failed to advance status"); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40">
        <DialogHeader><DialogTitle>Advance Lifecycle</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div className="text-xs text-slate-400">
            Current: <span className="font-mono text-cyan-300">{booking.status}</span>
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase">New status</Label>
            <Select value={val} onValueChange={setVal}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="status-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {statuses.map((s) => (
                  <SelectItem key={s} value={s} data-testid={`status-opt-${s}`}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field l="Note (optional)" v={note} on={setNote} t="status-note" />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-emerald-500 text-black font-bold"
            data-testid="status-submit">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function GateDialog({ booking, onClose, onSaved }) {
  const [form, setForm] = useState({
    event_type: "ingate", terminal_code: "", container_number: "",
    chassis_number: "", trucker_scac: "", notes: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const submit = async () => {
    if (!form.terminal_code.trim()) { toast.error("Terminal code is required"); return; }
    try {
      await api.post(`/international/container-bookings/${booking.booking_id}/gate`, form);
      toast.success(`${form.event_type === "ingate" ? "Ingated" : "Outgated"} at ${form.terminal_code}`);
      onSaved();
    } catch (e) { console.error(e); toast.error("Failed to log gate event"); }
  };
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40">
        <DialogHeader><DialogTitle>Log Gate Event · {booking.booking_number}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-[10px] font-mono uppercase">Event type</Label>
            <Select value={form.event_type} onValueChange={(v) => set("event_type", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="gate-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                <SelectItem value="ingate" data-testid="gate-opt-ingate">Ingate (into terminal)</SelectItem>
                <SelectItem value="outgate" data-testid="gate-opt-outgate">Outgate (out of terminal)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Field l="Terminal code *" v={form.terminal_code} on={(v) => set("terminal_code", v)} t="gate-terminal"
            ph="e.g. APMT, ETS, ICTF" />
          <Field l="Container #" v={form.container_number} on={(v) => set("container_number", v)} t="gate-container" />
          <Field l="Chassis #" v={form.chassis_number} on={(v) => set("chassis_number", v)} t="gate-chassis" />
          <Field l="Trucker SCAC" v={form.trucker_scac} on={(v) => set("trucker_scac", v)} t="gate-trucker" />
          <Field l="Notes" v={form.notes} on={(v) => set("notes", v)} t="gate-notes" />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="gate-submit">
            Log Event
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function WaybillDialog({ booking, rails, yards, onClose, onSaved }) {
  const [form, setForm] = useState({
    railroad_scac: rails?.[0]?.scac || "BNSF", waybill_number: "",
    equipment_initial: "", equipment_number: "",
    origin_yard_code: "", destination_yard_code: "",
    waybill_date: "", rate_usd: "", notes: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const matchingYards = useMemo(
    () => yards.filter((y) => y.railroad.toLowerCase() === form.railroad_scac.toLowerCase()),
    [yards, form.railroad_scac]);

  const submit = async () => {
    if (!form.waybill_number.trim()) { toast.error("Waybill # is required"); return; }
    try {
      const payload = { ...form, rate_usd: form.rate_usd ? Number(form.rate_usd) : null };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      await api.post(`/international/container-bookings/${booking.booking_id}/waybill`, payload);
      toast.success(`Waybill ${form.waybill_number} attached`);
      onSaved();
    } catch (e) { console.error(e); toast.error("Failed to attach waybill"); }
  };

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-[#0B0E14] border-cyan-500/40 max-w-2xl">
        <DialogHeader><DialogTitle>Attach Rail Waybill · {booking.booking_number}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-[10px] font-mono uppercase">Railroad</Label>
            <Select value={form.railroad_scac} onValueChange={(v) => set("railroad_scac", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="wb-railroad">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {rails.map((r) => (
                  <SelectItem key={r.scac} value={r.scac} data-testid={`wb-rail-opt-${r.scac}`}>
                    {r.name} <span className="text-slate-500 ml-1.5 font-mono text-[10px]">({r.scac})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field l="Waybill # *" v={form.waybill_number} on={(v) => set("waybill_number", v)} t="wb-num" />
          <Field l="Equipment initial" v={form.equipment_initial} on={(v) => set("equipment_initial", v)} t="wb-eq-init"
            ph="e.g. BNSF, TTGX" />
          <Field l="Equipment #" v={form.equipment_number} on={(v) => set("equipment_number", v)} t="wb-eq-num" />
          <div>
            <Label className="text-[10px] font-mono uppercase">Origin Yard</Label>
            <Select value={form.origin_yard_code || "none"}
              onValueChange={(v) => set("origin_yard_code", v === "none" ? "" : v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="wb-origin">
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30 max-h-72">
                <SelectItem value="none">—</SelectItem>
                {matchingYards.map((y) => (
                  <SelectItem key={y.code} value={y.code} data-testid={`wb-yard-orig-${y.code}`}>
                    {y.name} · {y.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase">Destination Yard</Label>
            <Select value={form.destination_yard_code || "none"}
              onValueChange={(v) => set("destination_yard_code", v === "none" ? "" : v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="wb-dest">
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30 max-h-72">
                <SelectItem value="none">—</SelectItem>
                {matchingYards.map((y) => (
                  <SelectItem key={y.code} value={y.code} data-testid={`wb-yard-dest-${y.code}`}>
                    {y.name} · {y.city}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field l="Waybill date" type="date" v={form.waybill_date} on={(v) => set("waybill_date", v)} t="wb-date" />
          <Field l="Rate (USD)" type="number" v={form.rate_usd} on={(v) => set("rate_usd", v)} t="wb-rate" />
          <Field l="Notes" v={form.notes} on={(v) => set("notes", v)} t="wb-notes" />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} className="bg-cyan-500 text-black font-bold" data-testid="wb-submit">
            Attach
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* =================== OCEAN CARRIERS =================== */
function OceanCarriersTab({ carriers }) {
  return (
    <Card className="bg-[#0F1421] border-white/5">
      <CardHeader>
        <CardTitle className="text-base">Major Ocean Carriers · {carriers.length} loaded</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="ocean-table">
            <thead>
              <tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10">
                <th className="py-2 px-2">SCAC</th>
                <th className="py-2 px-2">Carrier</th>
                <th className="py-2 px-2">Alliance</th>
                <th className="py-2 px-2">HQ</th>
                <th className="py-2 px-2">Website</th>
              </tr>
            </thead>
            <tbody>
              {carriers.map((c) => (
                <tr key={c.scac} className="border-b border-white/5 hover:bg-cyan-500/5"
                  data-testid={`ocean-row-${c.scac}`}>
                  <td className="py-2 px-2 font-mono text-cyan-300">{c.scac}</td>
                  <td className="py-2 px-2">{c.name}</td>
                  <td className="py-2 px-2 text-slate-400">{c.alliance}</td>
                  <td className="py-2 px-2 text-slate-400">{c.hq}</td>
                  <td className="py-2 px-2">
                    <a href={c.website} target="_blank" rel="noreferrer noopener"
                      className="text-cyan-400 hover:underline text-[11px]">
                      {c.website.replace(/^https?:\/\//, "")}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

/* =================== RAIL YARDS =================== */
function RailYardsTab({ yards, railroads }) {
  const [railroad, setRailroad] = useState("ALL");
  const [city, setCity] = useState("");
  const filtered = useMemo(() => {
    let arr = yards;
    if (railroad !== "ALL") arr = arr.filter((y) => y.railroad === railroad);
    if (city.trim()) arr = arr.filter((y) => y.city.toLowerCase().includes(city.toLowerCase()));
    return arr;
  }, [yards, railroad, city]);

  return (
    <div className="space-y-3">
      <div className="flex gap-3 items-end flex-wrap">
        <div className="w-48">
          <Label className="text-[10px] font-mono uppercase">Railroad</Label>
          <Select value={railroad} onValueChange={setRailroad}>
            <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="yards-rail-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
              <SelectItem value="ALL" data-testid="yards-rail-all">All railroads</SelectItem>
              {railroads.map((r) => (
                <SelectItem key={r.scac} value={r.scac} data-testid={`yards-rail-${r.scac}`}>
                  {r.name} ({r.scac})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-64">
          <Label className="text-[10px] font-mono uppercase">City filter</Label>
          <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Chicago, Memphis…"
            className="bg-[#0B1320] border-white/10" data-testid="yards-city-filter" />
        </div>
        <div className="text-xs text-slate-500 font-mono ml-auto">
          Showing {filtered.length} / {yards.length} yards
        </div>
      </div>

      <Card className="bg-[#0F1421] border-white/5">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="yards-table">
              <thead>
                <tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/10">
                  <th className="py-2 px-3">Code</th>
                  <th className="py-2 px-3">Yard</th>
                  <th className="py-2 px-3">City</th>
                  <th className="py-2 px-3">Railroad</th>
                  <th className="py-2 px-3">Type</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((y) => (
                  <tr key={y.code} className="border-b border-white/5 hover:bg-cyan-500/5"
                    data-testid={`yard-row-${y.code}`}>
                    <td className="py-2 px-3 font-mono text-cyan-300">{y.code}</td>
                    <td className="py-2 px-3">{y.name}</td>
                    <td className="py-2 px-3 text-slate-300">{y.city}</td>
                    <td className="py-2 px-3 font-mono text-amber-300">{y.railroad}</td>
                    <td className="py-2 px-3 text-slate-400">{y.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* =================== GATE EVENTS =================== */
function GateEventsTab({ bookings }) {
  // Flatten all gate events across bookings, newest first.
  const events = useMemo(() => {
    const out = [];
    for (const b of bookings) {
      for (const e of b.gate_events || []) {
        out.push({ ...e, booking_number: b.booking_number, booking_id: b.booking_id,
                   carrier: b.carrier_scac, route: `${b.pol} → ${b.pod}` });
      }
    }
    return out.sort((a, b) => (b.at || "").localeCompare(a.at || ""));
  }, [bookings]);

  return (
    <Card className="bg-[#0F1421] border-white/5">
      <CardHeader>
        <CardTitle className="text-base">Gate Events · {events.length} total</CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <div className="text-center text-slate-500 text-sm py-8">
            No gate events logged yet.
          </div>
        ) : (
          <div className="space-y-2" data-testid="gate-events-list">
            {events.map((e) => (
              <div key={e.event_id} className="flex items-center gap-3 p-3 rounded border border-white/5
                bg-[#0B0E14] hover:border-cyan-500/30 transition-colors"
                data-testid={`gate-row-${e.event_id}`}>
                <Badge className={e.event_type === "ingate"
                  ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/40"
                  : "bg-amber-500/15 text-amber-300 border border-amber-500/40"}>
                  {e.event_type.toUpperCase()}
                </Badge>
                <div className="flex-1 min-w-0">
                  <div className="text-sm">
                    <span className="font-mono text-cyan-300">{e.booking_number}</span>
                    <span className="text-slate-500 mx-2">·</span>
                    {e.route}
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    Terminal {e.terminal_code}
                    {e.container_number && ` · CTNR ${e.container_number}`}
                    {e.chassis_number && ` · CHS ${e.chassis_number}`}
                    {e.trucker_scac && ` · Trucker ${e.trucker_scac}`}
                  </div>
                </div>
                <div className="text-[11px] text-slate-400 font-mono whitespace-nowrap">
                  {(e.at || "").replace("T", " ").slice(0, 16)}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* =================== Mini Field Helper =================== */
function Field({ l, v, on, type = "text", t, ph }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">{l}</Label>
      <Input type={type} value={v} onChange={(e) => on(e.target.value)}
        placeholder={ph} className="bg-[#0B1320] border-white/10 text-white" data-testid={t} />
    </div>
  );
}
