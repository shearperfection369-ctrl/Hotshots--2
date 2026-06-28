import React, { useEffect, useMemo, useState } from "react";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Database, AlertTriangle, Search, FileText, Download, ArrowRight } from "lucide-react";
import { BACKEND_URL } from "../lib/api";
import { CITY_NAMES, lookupCity } from "../lib/freightCities";
import { Autocomplete } from "../components/Autocomplete";
import { CarrierCombobox } from "../components/CarrierCombobox";

const CARRIERS = {
  TL: ["XPO Logistics", "ArcBest", "Schneider", "J.B. Hunt"],
  LTL: ["SAIA", "R&L Carriers", "ArcBest", "XPO Logistics", "Consolidated Fastfrate"],
  Parcel: ["UPS", "FedEx", "DHL Express"],
  Ocean: ["Kuehne+Nagel", "Maersk", "MSC"],
  Air: ["FedEx", "DHL Express", "Kuehne+Nagel"],
  Rail: ["BNSF", "Union Pacific", "CSX"],
};

// Density-based suggested LTL freight class — standard NMFC table
function suggestFreightClass(density) {
  if (density >= 50) return "50";
  if (density >= 35) return "55";
  if (density >= 30) return "60";
  if (density >= 22.5) return "65";
  if (density >= 15) return "70";
  if (density >= 13.5) return "77.5";
  if (density >= 12) return "85";
  if (density >= 10.5) return "92.5";
  if (density >= 9) return "100";
  if (density >= 8) return "110";
  if (density >= 7) return "125";
  if (density >= 6) return "150";
  if (density >= 5) return "175";
  if (density >= 4) return "200";
  if (density >= 3) return "250";
  if (density >= 2) return "300";
  if (density >= 1) return "400";
  return "500";
}

const PLANT_DEFAULTS = {
  "GVM": { destination_city: "Atlanta, GA", lat: 33.749, lng: -84.388 },
  "HOM": { destination_city: "Chicago, IL", lat: 41.878, lng: -87.629 },
  "LVK": { destination_city: "Dallas, TX", lat: 32.776, lng: -96.797 },
};

export default function BookLoad() {
  const navigate = useNavigate();
  const [facilities, setFacilities] = useState([]);
  const [nmfcCodes, setNmfcCodes] = useState([]);
  const [freightClasses, setFreightClasses] = useState([]);
  const [accessorialOpts, setAccessorialOpts] = useState([]);
  const [sapOpen, setSapOpen] = useState(false);
  const [sapDeliveries, setSapDeliveries] = useState([]);
  const [sapSearch, setSapSearch] = useState("");

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
    pallet_count: 6,
    commodity: "Floor scrubbers (T16AMR)",
    value_usd: 85000,
    reference: "",
    sap_delivery_no: "",
    sap_material_numbers: [],
    customer_contact_email: "",
    carrier_contact_email: "",
    // Dimensions
    length_in: 48,
    width_in: 40,
    height_in: 56,
    // NMFC / class
    nmfc_code: "105820",
    freight_class: "85",
    // Accessorials
    liftgate_required: false,
    accessorials: [],
  });
  // BOL preview modal state
  const [bookedShipment, setBookedShipment] = useState(null);
  const [generatedBol, setGeneratedBol] = useState(null);

  useEffect(() => {
    api.get("/facilities").then(({ data }) => setFacilities(data));
    api.get("/nmfc/codes").then(({ data }) => {
      setNmfcCodes(data.codes || []);
      setFreightClasses(data.freight_classes || []);
      setAccessorialOpts(data.accessorials || []);
    });
  }, []);

  // Density auto-calc (lbs / cubic foot)
  const density = useMemo(() => {
    const cubicFt = (Number(form.length_in) * Number(form.width_in) * Number(form.height_in)) / 1728;
    const palletCount = Math.max(1, Number(form.pallet_count) || 1);
    const totalCuFt = cubicFt * palletCount;
    if (!totalCuFt) return 0;
    return Number(form.weight_lbs) / totalCuFt;
  }, [form.length_in, form.width_in, form.height_in, form.weight_lbs, form.pallet_count]);

  const suggestedClass = useMemo(() => (density > 0 ? suggestFreightClass(density) : null), [density]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleAccessorial = (id) => setForm((f) => {
    const has = f.accessorials.includes(id);
    return { ...f, accessorials: has ? f.accessorials.filter((x) => x !== id) : [...f.accessorials, id] };
  });

  const openSapPicker = async () => {
    try {
      const { data } = await api.get("/sap/open-deliveries");
      setSapDeliveries(data.deliveries || []);
      setSapOpen(true);
    } catch (e) {
      toast.error("Failed to fetch SAP deliveries");
    }
  };

  const pickSapDelivery = (d) => {
    setForm((f) => ({
      ...f,
      reference: `SO ${d.so_no}`,
      sap_delivery_no: d.delivery_no,
      sap_material_numbers: [d.material],
      commodity: d.material_desc,
      pieces: d.qty,
      pallet_count: Math.max(1, d.qty),
    }));
    setSapOpen(false);
    toast.success(`Pulled SO ${d.so_no} → Delivery ${d.delivery_no} from S/4HANA`);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...form,
        sap_material_numbers: form.sap_material_numbers && form.sap_material_numbers.length ? form.sap_material_numbers : null,
      };
      const { data: shipment } = await api.post("/shipments", payload);
      toast.success(`Load booked: ${shipment.reference}`, {
        description: `${shipment.mode} via ${shipment.carrier} — routed to Workflow, Factoring & Cash Flow automatically.`,
        action: {
          label: "Open Workflow",
          onClick: () => navigate("/workflow"),
        },
      });

      // Auto-generate the BOL so it shows up as a preview the dispatcher can save.
      try {
        const { data: bol } = await api.post(`/shipments/${shipment.shipment_id}/generate-bol`, {
          shipper: "",
        });
        setBookedShipment(shipment);
        setGeneratedBol(bol);
      } catch (bolErr) {
        // If BOL generation fails for any reason we still consider the booking a success.
        console.error("BOL generation failed", bolErr);
        navigate("/shipments");
      }
    } catch (err) {
      toast.error("Failed to book load");
    }
  };

  // Persist BOL to Document Vault is implicit (already saved by generate-bol).
  // This handler downloads the PDF to the user's machine.
  const downloadBol = () => {
    if (!generatedBol?.document_id) return;
    const url = `${BACKEND_URL}/api/documents/${generatedBol.document_id}/pdf`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `BOL-${generatedBol.shipment_ref || generatedBol.document_id}.pdf`;
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast.success("BOL download started");
  };

  const labelCls = "text-[10px] font-mono uppercase tracking-wider text-slate-400";
  const inpCls = "mt-1 bg-[#131821] border-white/10";

  const filteredDeliveries = sapDeliveries.filter((d) => {
    if (!sapSearch) return true;
    const q = sapSearch.toLowerCase();
    return [d.delivery_no, d.so_no, d.customer, d.material, d.material_desc].some((v) => (v || "").toLowerCase().includes(q));
  });

  return (
    <>
      <Topbar title="Book Load" subtitle="Create a new shipment · S/4HANA-aware · NMFC/freight class auto-suggestion" />
      <div className="p-4 md:p-6">
        <Card className="hud-surface p-6 max-w-6xl" data-testid="book-load-form">
          {/* SAP pull bar */}
          <div className="mb-5 flex items-center gap-3 p-3 rounded bg-cyan-500/[0.04] border border-cyan-500/20">
            <Database size={16} className="text-cyan-400" />
            <div className="flex-1">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">SAP S/4HANA</div>
              <div className="text-xs text-slate-300">Pull an open delivery to auto-fill reference, material, commodity & qty</div>
            </div>
            {form.sap_delivery_no && (
              <span className="text-[10px] font-mono px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                ✓ Delivery {form.sap_delivery_no}
              </span>
            )}
            <Button type="button" onClick={openSapPicker} data-testid="pull-from-sap-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              Pull from SAP →
            </Button>
          </div>

          <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Row 1 */}
            <div>
              <Label className={labelCls}>Mode</Label>
              <Select value={form.mode} onValueChange={(v) => { set("mode", v); set("carrier", CARRIERS[v][0]); }}>
                <SelectTrigger data-testid="mode-select" className={inpCls}><SelectValue /></SelectTrigger>
                <SelectContent>{Object.keys(CARRIERS).map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className={labelCls}>Carrier <span className="text-cyan-300 normal-case text-[10px]">· type-ahead from full directory + suggestions for {form.mode}</span></Label>
              <CarrierCombobox
                value={form.carrier}
                onChange={(v) => set("carrier", v)}
                onSelect={(rec) => {
                  set("carrier", rec.name);
                  if (rec.contact_email) set("carrier_contact_email", rec.contact_email);
                }}
                testid="carrier-select"
                className={inpCls}
              />
            </div>
            <div>
              <Label className={labelCls}>Origin Facility</Label>
              <Select value={form.origin_facility} onValueChange={(v) => { set("origin_facility", v); const d = PLANT_DEFAULTS[v]; if (d) { set("destination_city", d.destination_city); set("destination_lat", d.lat); set("destination_lng", d.lng); } }}>
                <SelectTrigger data-testid="origin-select" className={inpCls}><SelectValue /></SelectTrigger>
                <SelectContent>{facilities.map((f) => <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>

            {/* Destination */}
            <div className="md:col-span-2">
              <Label className={labelCls}>Destination City <span className="text-cyan-300 normal-case text-[10px]">· type to search · lat/lng auto-fills</span></Label>
              <Input
                data-testid="destination-input"
                list="freight-cities-list"
                className={inpCls}
                value={form.destination_city}
                onChange={(e) => {
                  const v = e.target.value;
                  set("destination_city", v);
                  const m = lookupCity(v);
                  if (m) {
                    set("destination_lat", m.lat);
                    set("destination_lng", m.lng);
                  }
                }}
                placeholder="Start typing — e.g. Dallas, TX"
              />
              <datalist id="freight-cities-list">
                {CITY_NAMES.map(c => <option key={c} value={c} />)}
              </datalist>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className={labelCls}>Lat</Label>
                <Input className={`${inpCls} font-mono`} type="number" step="0.0001" value={form.destination_lat} onChange={(e) => set("destination_lat", parseFloat(e.target.value))} />
              </div>
              <div>
                <Label className={labelCls}>Lng</Label>
                <Input className={`${inpCls} font-mono`} type="number" step="0.0001" value={form.destination_lng} onChange={(e) => set("destination_lng", parseFloat(e.target.value))} />
              </div>
            </div>

            {/* Reference / Pickup / Commodity */}
            <div>
              <Label className={labelCls}>Reference {form.sap_delivery_no && <span className="text-emerald-400 normal-case">· from SAP</span>}</Label>
              <Input className={inpCls} value={form.reference} onChange={(e) => set("reference", e.target.value)} placeholder="Auto-generated if blank" data-testid="reference-input" />
            </div>
            <div>
              <Label className={labelCls}>SAP Delivery #</Label>
              <Input className={`${inpCls} font-mono`} value={form.sap_delivery_no} onChange={(e) => set("sap_delivery_no", e.target.value)} placeholder="8000234" />
            </div>
            <div>
              <Label className={labelCls}>Pickup Date</Label>
              <Input data-testid="pickup-date-input" className={inpCls} type="date" value={form.pickup_date} onChange={(e) => set("pickup_date", e.target.value)} />
            </div>

            <div className="md:col-span-2">
              <Label className={labelCls}>Commodity <span className="text-cyan-300 normal-case text-[10px]">· type-ahead from common freight</span></Label>
              <Autocomplete
                kind="commodities"
                value={form.commodity}
                onChange={(v) => set("commodity", v)}
                testid="commodity-input"
                className={inpCls}
              />
            </div>
            <div>
              <Label className={labelCls}>Cargo Value (USD)</Label>
              <Input className={`${inpCls} font-mono`} type="number" value={form.value_usd} onChange={(e) => set("value_usd", parseFloat(e.target.value))} />
            </div>

            {/* Weight + pieces + pallets */}
            <div className="md:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-white/5">
              <div>
                <Label className={labelCls}>Weight (lbs)</Label>
                <Input className={`${inpCls} font-mono`} type="number" value={form.weight_lbs} onChange={(e) => set("weight_lbs", parseFloat(e.target.value))} data-testid="weight-input" />
              </div>
              <div>
                <Label className={labelCls}>Pallet Count</Label>
                <Input className={`${inpCls} font-mono`} type="number" min={1} value={form.pallet_count} onChange={(e) => set("pallet_count", parseInt(e.target.value || 0))} data-testid="pallet-count-input" />
              </div>
              <div>
                <Label className={labelCls}>Pieces / Units</Label>
                <Input className={`${inpCls} font-mono`} type="number" min={1} value={form.pieces} onChange={(e) => set("pieces", parseInt(e.target.value || 0))} />
              </div>
              <div className="flex flex-col">
                <Label className={labelCls}>Density (auto)</Label>
                <div className="mt-1 px-3 py-2 rounded border border-white/10 bg-[#0B0E14] font-mono text-sm text-cyan-300">
                  {density.toFixed(2)} <span className="text-slate-500 text-xs">lb/ft³</span>
                </div>
              </div>
            </div>

            {/* Dimensions */}
            <div className="md:col-span-3 grid grid-cols-3 gap-3">
              <div>
                <Label className={labelCls}>Length (in) · per pallet</Label>
                <Input className={`${inpCls} font-mono`} type="number" min={1} value={form.length_in} onChange={(e) => set("length_in", parseFloat(e.target.value || 0))} data-testid="length-input" />
              </div>
              <div>
                <Label className={labelCls}>Width (in) · per pallet</Label>
                <Input className={`${inpCls} font-mono`} type="number" min={1} value={form.width_in} onChange={(e) => set("width_in", parseFloat(e.target.value || 0))} data-testid="width-input" />
              </div>
              <div>
                <Label className={labelCls}>Height (in) · per pallet</Label>
                <Input className={`${inpCls} font-mono`} type="number" min={1} value={form.height_in} onChange={(e) => set("height_in", parseFloat(e.target.value || 0))} data-testid="height-input" />
              </div>
            </div>

            {/* NMFC + class */}
            <div className="md:col-span-2">
              <Label className={labelCls}>NMFC Code</Label>
              <Select value={form.nmfc_code} onValueChange={(v) => { set("nmfc_code", v); const c = nmfcCodes.find((x) => x.nmfc === v); if (c) set("freight_class", c.freight_class); }}>
                <SelectTrigger data-testid="nmfc-select" className={inpCls}><SelectValue placeholder="Select NMFC" /></SelectTrigger>
                <SelectContent className="max-h-72">
                  {nmfcCodes.map((c) => (
                    <SelectItem key={c.nmfc} value={c.nmfc}>
                      <span className="font-mono text-cyan-300">{c.nmfc}</span> · {c.description} <span className="text-slate-500">(class {c.freight_class})</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className={labelCls}>
                Freight Class {suggestedClass && form.freight_class !== suggestedClass && (
                  <span className="ml-2 text-yellow-400 normal-case" title="Suggested by density formula">
                    <AlertTriangle size={9} className="inline" /> suggested: {suggestedClass}
                  </span>
                )}
              </Label>
              <Select value={form.freight_class} onValueChange={(v) => set("freight_class", v)}>
                <SelectTrigger data-testid="freight-class-select" className={inpCls}><SelectValue /></SelectTrigger>
                <SelectContent>{freightClasses.map((fc) => <SelectItem key={fc} value={fc}>Class {fc}</SelectItem>)}</SelectContent>
              </Select>
            </div>

            {/* Accessorials */}
            <div className="md:col-span-3">
              <Label className={labelCls}>Accessorials</Label>
              <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2">
                {accessorialOpts.map((opt) => {
                  const active = form.accessorials.includes(opt.id) || (opt.id === "liftgate" && form.liftgate_required);
                  return (
                    <button
                      type="button"
                      key={opt.id}
                      data-testid={`accessorial-${opt.id}`}
                      onClick={() => { toggleAccessorial(opt.id); if (opt.id === "liftgate") set("liftgate_required", !form.liftgate_required); }}
                      className={`px-3 py-2 rounded border text-xs font-mono uppercase tracking-wider transition-all text-left ${
                        active ? "bg-cyan-500 text-black border-cyan-400 hud-glow-cyan" : "bg-white/[0.02] text-slate-400 border-white/10 hover:border-cyan-400/40 hover:text-cyan-300"
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Contact emails */}
            <div>
              <Label className={labelCls}>Customer Contact Email</Label>
              <Input className={inpCls} type="email" value={form.customer_contact_email} onChange={(e) => set("customer_contact_email", e.target.value)} placeholder="receiver@customer.com" data-testid="customer-email-input" />
            </div>
            <div>
              <Label className={labelCls}>Carrier Contact Email</Label>
              <Input className={inpCls} type="email" value={form.carrier_contact_email} onChange={(e) => set("carrier_contact_email", e.target.value)} placeholder="dispatch@carrier.com" data-testid="carrier-email-input" />
            </div>
            <div />

            <div className="md:col-span-3 flex justify-end pt-3">
              <Button data-testid="submit-book-load" type="submit" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_20px_rgba(0,229,255,0.4)] px-8">
                BOOK LOAD →
              </Button>
            </div>
          </form>
        </Card>
      </div>

      {/* SAP delivery picker */}
      <Dialog open={sapOpen} onOpenChange={setSapOpen}>
        <DialogContent className="bg-[#131821] border border-cyan-500/30 text-white max-w-4xl max-h-[80vh] overflow-hidden flex flex-col" data-testid="sap-picker-dialog">
          <DialogHeader>
            <DialogTitle className="font-display text-cyan-300 flex items-center gap-2">
              <Database size={18} /> SAP S/4HANA · Open Deliveries
            </DialogTitle>
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">Select a delivery to auto-fill the booking form</div>
          </DialogHeader>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="sap-search"
              value={sapSearch}
              onChange={(e) => setSapSearch(e.target.value)}
              placeholder="Search delivery #, SO #, customer, material..."
              className="pl-9 bg-[#0B0E14] border-white/10"
            />
          </div>
          <div className="flex-1 overflow-y-auto mt-3 space-y-2">
            {filteredDeliveries.map((d) => (
              <button
                key={d.delivery_no}
                type="button"
                data-testid={`sap-delivery-${d.delivery_no}`}
                onClick={() => pickSapDelivery(d)}
                className="w-full text-left p-3 rounded border border-white/10 bg-white/[0.02] hover:border-cyan-500/40 hover:bg-cyan-500/[0.04] transition"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-mono text-sm text-cyan-300">Delivery {d.delivery_no} · SO {d.so_no}</div>
                    <div className="text-white text-sm mt-0.5">{d.customer}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5"><span className="font-mono text-cyan-400">{d.material}</span> · {d.material_desc}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-xs text-emerald-400">Plant {d.plant}</div>
                    <div className="text-[11px] text-slate-300 mt-1">{d.qty} EA · {d.requested_date}</div>
                    <div className="text-[10px] font-mono text-slate-500 mt-0.5">{d.incoterms}</div>
                  </div>
                </div>
              </button>
            ))}
            {filteredDeliveries.length === 0 && (
              <div className="text-center py-12 text-slate-500">No deliveries match the search.</div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* BOL Preview Modal — auto-opens after a load is booked */}
      <Dialog
        open={!!generatedBol}
        onOpenChange={(v) => { if (!v) { setGeneratedBol(null); setBookedShipment(null); navigate("/shipments"); } }}
      >
        <DialogContent className="max-w-4xl bg-[#0B0E14] border-cyan-500/30 max-h-[92vh] overflow-y-auto" data-testid="bol-preview-modal">
          <DialogHeader>
            <DialogTitle className="font-display text-lg flex items-center gap-2">
              <FileText size={18} className="text-cyan-400" />
              Bill of Lading — {bookedShipment?.reference}
            </DialogTitle>
          </DialogHeader>

          {generatedBol && bookedShipment && (
            <div className="space-y-4">
              <div className="px-3 py-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
                ✓ Load booked as <span className="font-mono">{bookedShipment.shipment_id}</span>.
                BOL <span className="font-mono">{generatedBol.document_id}</span> auto-saved to the Document Vault.
              </div>

              {/* BOL preview card */}
              <div className="bg-white text-slate-900 rounded-md p-6 shadow-lg" data-testid="bol-preview-card">
                <div className="flex items-start justify-between border-b-2 border-slate-900 pb-3 mb-4">
                  <div>
                    <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-slate-500">Straight Bill of Lading — Short Form</div>
                    <div className="font-display text-2xl font-black tracking-tight">{generatedBol.data?.shipper || "Shipper"}</div>
                  </div>
                  <div className="text-right text-xs">
                    <div className="font-mono text-slate-500">DOC: {generatedBol.document_id}</div>
                    <div className="font-mono text-slate-500">SHIP REF: {generatedBol.shipment_ref}</div>
                    <div className="font-mono text-slate-500">DATE: {new Date(generatedBol.created_at).toLocaleDateString()}</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                  <BolField label="From (Origin)" value={generatedBol.data?.origin} />
                  <BolField label="To (Consignee)" value={generatedBol.data?.consignee} />
                  <BolField label="To (Destination)" value={generatedBol.data?.destination} />
                  <BolField label="Carrier" value={generatedBol.data?.carrier} />
                  <BolField label="Commodity" value={generatedBol.data?.commodity} />
                  <BolField label="Country of Origin" value={generatedBol.data?.country_origin} />
                  <BolField label="Weight (lbs)" value={generatedBol.data?.weight} />
                  <BolField label="Pieces / Skids" value={generatedBol.data?.pieces} />
                  <BolField label="Declared Value (USD)" value={generatedBol.data?.value ? `$${Number(generatedBol.data.value).toLocaleString()}` : ""} />
                  <BolField label="BOL #" value={generatedBol.data?.bol_no} />
                  <BolField label="PRO #" value={generatedBol.data?.pro_no} />
                  <BolField label="NMFC / Freight Class" value={`${form.nmfc_code} · Class ${form.freight_class}`} />
                </div>

                <div className="mt-6 pt-3 border-t border-slate-300 grid grid-cols-2 gap-x-6 text-[10px] font-mono uppercase tracking-wider text-slate-600">
                  <div>
                    <div className="mt-6 border-t border-slate-500 pt-1">Shipper Signature</div>
                  </div>
                  <div>
                    <div className="mt-6 border-t border-slate-500 pt-1">Carrier Signature</div>
                  </div>
                </div>
                <div className="mt-3 text-[9px] text-slate-500">
                  RECEIVED, subject to the classifications and tariffs in effect on the date of issue of this Bill of Lading,
                  the property described above in apparent good order, except as noted, marked, consigned, and destined as indicated above.
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-2 justify-end">
                <Button variant="ghost" onClick={() => navigate("/documents")} data-testid="bol-go-documents">
                  Open in Documents <ArrowRight size={13} className="ml-1.5" />
                </Button>
                <Button onClick={downloadBol} data-testid="bol-download-btn" className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
                  <Download size={14} className="mr-1.5" /> Save BOL (PDF)
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function BolField({ label, value }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className="font-medium text-slate-900 mt-0.5">{value || <span className="text-slate-400 italic">—</span>}</div>
    </div>
  );
}
