import React, { useEffect, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

const CARRIERS = {
  TL: ["XPO Logistics", "ArcBest", "Schneider", "J.B. Hunt"],
  LTL: ["SAIA", "R&L Carriers", "ArcBest", "XPO Logistics", "Consolidated Fastfrate"],
  Parcel: ["UPS", "FedEx", "DHL Express"],
  Ocean: ["Kuehne+Nagel", "Maersk", "MSC"],
  Air: ["FedEx", "DHL Express", "Kuehne+Nagel"],
  Rail: ["BNSF", "Union Pacific", "CSX"],
};

export default function BookLoad() {
  const navigate = useNavigate();
  const [facilities, setFacilities] = useState([]);
  const [form, setForm] = useState({
    mode: "TL",
    carrier: "XPO Logistics",
    origin_facility: "GVM",
    destination_city: "Dallas, TX",
    destination_lat: 32.7767,
    destination_lng: -96.7970,
    pickup_date: new Date().toISOString().slice(0, 10),
    weight_lbs: 12000,
    pieces: 6,
    commodity: "Floor scrubbers (T16AMR)",
    value_usd: 85000,
    reference: "",
  });

  useEffect(() => { api.get("/facilities").then(({ data }) => setFacilities(data)); }, []);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/shipments", { ...form });
      toast.success(`Load booked: ${data.reference}`, { description: `${data.mode} via ${data.carrier} — ${data.shipment_id}` });
      navigate("/shipments");
    } catch (err) {
      toast.error("Failed to book load");
    }
  };

  return (
    <>
      <Topbar title="Book Load" subtitle="Create a new shipment record" />
      <div className="p-4 md:p-6">
        <Card className="hud-surface p-6 max-w-4xl" data-testid="book-load-form">
          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Mode</Label>
              <Select value={form.mode} onValueChange={(v) => { set("mode", v); set("carrier", CARRIERS[v][0]); }}>
                <SelectTrigger data-testid="mode-select" className="mt-1 bg-[#131821] border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.keys(CARRIERS).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Carrier</Label>
              <Select value={form.carrier} onValueChange={(v) => set("carrier", v)}>
                <SelectTrigger data-testid="carrier-select" className="mt-1 bg-[#131821] border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CARRIERS[form.mode].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Origin Facility</Label>
              <Select value={form.origin_facility} onValueChange={(v) => set("origin_facility", v)}>
                <SelectTrigger data-testid="origin-select" className="mt-1 bg-[#131821] border-white/10"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {facilities.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Destination City</Label>
              <Input data-testid="destination-input" className="mt-1 bg-[#131821] border-white/10" value={form.destination_city} onChange={(e) => set("destination_city", e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Dest Lat</Label>
                <Input className="mt-1 bg-[#131821] border-white/10 font-mono" type="number" step="0.0001" value={form.destination_lat} onChange={(e) => set("destination_lat", parseFloat(e.target.value))} />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Dest Lng</Label>
                <Input className="mt-1 bg-[#131821] border-white/10 font-mono" type="number" step="0.0001" value={form.destination_lng} onChange={(e) => set("destination_lng", parseFloat(e.target.value))} />
              </div>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Pickup Date</Label>
              <Input data-testid="pickup-date-input" className="mt-1 bg-[#131821] border-white/10" type="date" value={form.pickup_date} onChange={(e) => set("pickup_date", e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Weight (lbs)</Label>
                <Input className="mt-1 bg-[#131821] border-white/10 font-mono" type="number" value={form.weight_lbs} onChange={(e) => set("weight_lbs", parseFloat(e.target.value))} />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Pieces</Label>
                <Input className="mt-1 bg-[#131821] border-white/10 font-mono" type="number" value={form.pieces} onChange={(e) => set("pieces", parseInt(e.target.value))} />
              </div>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Commodity</Label>
              <Input className="mt-1 bg-[#131821] border-white/10" value={form.commodity} onChange={(e) => set("commodity", e.target.value)} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Cargo Value (USD)</Label>
              <Input className="mt-1 bg-[#131821] border-white/10 font-mono" type="number" value={form.value_usd} onChange={(e) => set("value_usd", parseFloat(e.target.value))} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">Reference (optional)</Label>
              <Input className="mt-1 bg-[#131821] border-white/10" value={form.reference} onChange={(e) => set("reference", e.target.value)} placeholder="Auto-generated if blank" />
            </div>
            <div className="md:col-span-2 flex justify-end pt-3">
              <Button data-testid="submit-book-load" type="submit" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_20px_rgba(0,229,255,0.4)] px-8">
                BOOK LOAD →
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </>
  );
}
