import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { TennantLogo } from "../components/TennantLogo";
import {
  MapPin, Truck, Fuel, Coffee, AlertTriangle, CheckCircle2, Navigation, Clock, Package
} from "lucide-react";

const STATUS_OPTIONS = [
  { id: "arriving_pickup", label: "Arriving at Pickup", Icon: MapPin, color: "text-yellow-400" },
  { id: "loaded", label: "Loaded & Departing", Icon: Package, color: "text-cyan-400" },
  { id: "en_route", label: "En Route", Icon: Navigation, color: "text-cyan-400" },
  { id: "fuel", label: "Fuel Stop", Icon: Fuel, color: "text-yellow-400" },
  { id: "rest", label: "Rest Break / HOS", Icon: Coffee, color: "text-yellow-400" },
  { id: "delayed", label: "Delayed", Icon: AlertTriangle, color: "text-red-400" },
  { id: "arriving_dest", label: "Arriving at Destination", Icon: MapPin, color: "text-emerald-400" },
  { id: "delivered", label: "Delivered", Icon: CheckCircle2, color: "text-emerald-400" },
];

export default function DriverMobile() {
  const { shipmentId: paramId } = useParams();
  const [shipmentId, setShipmentId] = useState(paramId || "");
  const [shipment, setShipment] = useState(null);
  const [checkins, setCheckins] = useState([]);
  const [error, setError] = useState("");
  const [driverName, setDriverName] = useState(() => localStorage.getItem("driverName") || "");
  const [driverPhone, setDriverPhone] = useState(() => localStorage.getItem("driverPhone") || "");
  const [status, setStatus] = useState("en_route");
  const [note, setNote] = useState("");
  const [odometer, setOdometer] = useState("");
  const [fuelPct, setFuelPct] = useState("");
  const [loc, setLoc] = useState({ lat: null, lng: null, text: "" });
  const [submitting, setSubmitting] = useState(false);

  const lookup = async (id) => {
    setError("");
    try {
      const { data } = await api.get(`/driver/shipment/${id}`);
      setShipment(data.shipment);
      setCheckins(data.checkins);
    } catch (e) {
      setShipment(null); setCheckins([]);
      setError("Shipment not found. Check the ID and try again.");
    }
  };

  useEffect(() => {
    if (paramId) lookup(paramId);
  }, [paramId]);

  const getLocation = () => {
    if (!navigator.geolocation) { toast.error("GPS not available"); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setLoc({ lat: p.coords.latitude, lng: p.coords.longitude, text: loc.text }); toast.success("Location captured"); },
      () => toast.error("Unable to read GPS"),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!shipment) { toast.error("Look up shipment first"); return; }
    if (!driverName || !driverPhone) { toast.error("Driver name and phone required"); return; }
    setSubmitting(true);
    try {
      localStorage.setItem("driverName", driverName);
      localStorage.setItem("driverPhone", driverPhone);
      const payload = {
        shipment_id: shipment.shipment_id,
        driver_name: driverName,
        driver_phone: driverPhone,
        status,
        lat: loc.lat, lng: loc.lng,
        location_text: loc.text || null,
        note: note || null,
        odometer: odometer ? parseFloat(odometer) : null,
        fuel_pct: fuelPct ? parseInt(fuelPct) : null,
      };
      const { data } = await api.post("/driver/checkin", payload);
      toast.success("Check-in transmitted to dispatch");
      setNote(""); setOdometer(""); setFuelPct("");
      lookup(shipment.shipment_id);
    } catch {
      toast.error("Check-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white hud-grid-bg" data-testid="driver-mobile">
      <header className="sticky top-0 z-30 bg-[#0B0E14]/95 backdrop-blur-xl border-b border-white/5 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TennantLogo size="sm" />
          <span className="text-[10px] font-mono text-cyan-400 tracking-[0.2em] uppercase">Driver</span>
        </div>
        <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px] font-mono">
          <span className="relative flex h-2 w-2 mr-1.5"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span></span>
          LIVE
        </Badge>
      </header>

      <div className="px-4 py-5 max-w-md mx-auto space-y-4">

        {!shipment && (
          <Card className="hud-surface p-5">
            <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2">Find Your Load</div>
            <Label className="text-xs text-slate-400">Shipment ID</Label>
            <div className="flex gap-2 mt-1">
              <Input data-testid="shipment-id-input" value={shipmentId} onChange={(e) => setShipmentId(e.target.value.toUpperCase())} placeholder="SHP-XXXXXXXX" className="bg-[#0B0E14] border-white/10 font-mono" />
              <Button data-testid="lookup-shipment" onClick={() => lookup(shipmentId)} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shrink-0">GO</Button>
            </div>
            {error && <div className="mt-3 text-xs text-red-400">{error}</div>}
            <div className="mt-4 text-[11px] text-slate-500">Open the URL <span className="font-mono text-cyan-400">/driver/SHP-XXXX</span> on your phone to skip lookup.</div>
          </Card>
        )}

        {shipment && (
          <>
            <Card className="hud-surface p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Load Ticket</div>
                  <div className="text-lg font-display font-bold mt-1">{shipment.reference}</div>
                  <div className="text-[10px] font-mono text-slate-500">{shipment.shipment_id} · {shipment.mode}</div>
                </div>
                <Badge className="bg-cyan-500/10 text-cyan-400 border-cyan-500/30 font-mono text-[10px] uppercase">{shipment.status}</Badge>
              </div>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex items-start gap-2">
                  <MapPin size={14} className="text-cyan-400 mt-0.5 shrink-0" />
                  <div><div className="text-[10px] text-slate-500 uppercase">Pickup</div><div className="text-white">{shipment.origin.name}</div></div>
                </div>
                <div className="flex items-start gap-2">
                  <MapPin size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                  <div><div className="text-[10px] text-slate-500 uppercase">Delivery</div><div className="text-white">{shipment.destination.city}</div></div>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
                  <div><div className="text-[10px] text-slate-500 uppercase">Carrier</div><div className="text-slate-300 text-xs">{shipment.carrier}</div></div>
                  <div><div className="text-[10px] text-slate-500 uppercase">Weight</div><div className="text-slate-300 text-xs font-mono">{Number(shipment.weight_lbs).toLocaleString()} lbs</div></div>
                  <div><div className="text-[10px] text-slate-500 uppercase">BOL</div><div className="text-slate-300 text-xs font-mono">{shipment.bol_no}</div></div>
                  <div><div className="text-[10px] text-slate-500 uppercase">ETA</div><div className="text-slate-300 text-xs font-mono">{new Date(shipment.eta).toLocaleDateString()}</div></div>
                </div>
              </div>
            </Card>

            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Driver Identity</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[10px] text-slate-400">Name</Label>
                  <Input data-testid="driver-name" value={driverName} onChange={(e) => setDriverName(e.target.value)} className="mt-1 bg-[#0B0E14] border-white/10 h-9 text-sm" />
                </div>
                <div>
                  <Label className="text-[10px] text-slate-400">Phone</Label>
                  <Input data-testid="driver-phone" value={driverPhone} onChange={(e) => setDriverPhone(e.target.value)} className="mt-1 bg-[#0B0E14] border-white/10 h-9 text-sm font-mono" />
                </div>
              </div>
            </Card>

            <form onSubmit={submit} className="space-y-3">
              <Card className="hud-surface p-4">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3">Status Update</div>
                <div className="grid grid-cols-2 gap-2">
                  {STATUS_OPTIONS.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setStatus(s.id)}
                      data-testid={`status-${s.id}`}
                      className={`p-3 rounded-md border text-left transition-all ${
                        status === s.id ? "border-cyan-500/60 bg-cyan-500/10" : "border-white/5 bg-white/[0.02] hover:border-white/20"
                      }`}
                    >
                      <s.Icon size={16} className={s.color} />
                      <div className="text-xs text-white mt-1.5">{s.label}</div>
                    </button>
                  ))}
                </div>
              </Card>

              <Card className="hud-surface p-4 space-y-3">
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Location & Telematics</div>
                <Button type="button" data-testid="capture-gps" onClick={getLocation} className="w-full bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  <Navigation size={14} className="mr-2" /> Capture GPS
                </Button>
                {loc.lat && (
                  <div className="text-[11px] font-mono text-emerald-400">📍 {loc.lat.toFixed(4)}, {loc.lng.toFixed(4)}</div>
                )}
                <Input value={loc.text} onChange={(e) => setLoc({ ...loc, text: e.target.value })} placeholder="Location description (city, mile marker)" className="bg-[#0B0E14] border-white/10 h-9 text-sm" />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-[10px] text-slate-400">Odometer</Label>
                    <Input value={odometer} onChange={(e) => setOdometer(e.target.value)} type="number" className="mt-1 bg-[#0B0E14] border-white/10 h-9 text-sm font-mono" />
                  </div>
                  <div>
                    <Label className="text-[10px] text-slate-400">Fuel %</Label>
                    <Input value={fuelPct} onChange={(e) => setFuelPct(e.target.value)} type="number" max={100} className="mt-1 bg-[#0B0E14] border-white/10 h-9 text-sm font-mono" />
                  </div>
                </div>
                <Textarea data-testid="checkin-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note to dispatch (optional)" className="bg-[#0B0E14] border-white/10 min-h-[70px] text-sm" />
              </Card>

              <Button type="submit" data-testid="submit-checkin" disabled={submitting} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold h-12 text-base shadow-[0_0_20px_rgba(0,229,255,0.4)]">
                {submitting ? "TRANSMITTING..." : "TRANSMIT CHECK-IN →"}
              </Button>
            </form>

            <Card className="hud-surface p-4">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3 flex items-center gap-2">
                <Clock size={12} /> Recent Activity
              </div>
              <div className="space-y-2" data-testid="checkin-history">
                {checkins.length === 0 && <div className="text-xs text-slate-500 text-center py-4">No check-ins yet</div>}
                {checkins.map((c) => (
                  <div key={c.checkin_id} className="p-2.5 rounded-md border border-white/5 bg-white/[0.02]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-cyan-300 uppercase">{c.status.replace("_", " ")}</span>
                      <span className="text-[10px] font-mono text-slate-500">{new Date(c.created_at).toLocaleString()}</span>
                    </div>
                    {c.location_text && <div className="text-[11px] text-slate-400 mt-1">{c.location_text}</div>}
                    {c.note && <div className="text-[11px] text-slate-300 mt-1 italic">"{c.note}"</div>}
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
