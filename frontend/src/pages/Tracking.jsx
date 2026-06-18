import React, { useEffect, useMemo, useState } from "react";
import { useBrandRefresh } from "../lib/branding";
import Topbar from "../components/Topbar";
import MapView from "../components/MapView";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Search, MapPin, RefreshCw, ExternalLink, Crosshair, X, Truck, Ship, Plane, Train, Package } from "lucide-react";
import { toast } from "sonner";
import WeatherRadar from "../components/WeatherRadar";
import CarrierTrackingPanel from "../components/CarrierTrackingPanel";
import GlobalSearch from "../components/GlobalSearch";

const MODE_ICON = { TL: Truck, LTL: Truck, Parcel: Package, Ocean: Ship, Air: Plane, Rail: Train };

const STATUS_PILL = {
  in_transit: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  delayed:    "bg-red-500/15 text-red-300 border-red-500/30",
  delivered:  "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  pending:    "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  at_origin:  "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
  at_dest:    "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled:  "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

export default function Tracking() {
  const [shipments, setShipments] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [focus, setFocus] = useState(null);
  const [q, setQ] = useState("");
  const [refreshAt, setRefreshAt] = useState(Date.now());

  const load = async () => {
    const [s, f, bk] = await Promise.all([
      api.get("/shipments"),
      api.get("/facilities"),
      api.get("/brokerage/margins").catch(() => ({ data: { bookings: [] } })),
    ]);
    // Convert brokerage bookings into shipment-shaped rows so they appear
    // in tracking alongside ocean / parcel / TL shipments. They have no
    // lat/lng yet (geocoding is a paid integration), so we omit them from
    // the map but keep them in the list + omni-search.
    const bookings = (bk.data?.bookings || []).filter(b => b.booked_id).map(b => ({
      shipment_id: b.booked_id,
      reference: b.load_id,
      booking_number: b.booked_id,
      carrier: b.carrier_name || "Unassigned",
      carrier_mc: b.carrier_mc,
      mode: "TL",
      status: b.status === "settled" ? "delivered"
            : b.delivered_at ? "delivered"
            : b.in_transit_at ? "in_transit"
            : b.dispatched_at ? "in_transit"
            : "pending",
      origin:      { city: b.origin || "—", name: b.origin || "—" },
      destination: { city: b.destination || "—", name: b.destination || "—" },
      commodity: b.equipment || b.commodity || "Freight",
      consignee: b.customer_name,
      supplier:  b.customer_name,
      eta: b.delivery_at,
      _booking: true,
      _noMap: true,  // hint to MapView: skip plotting this row
    }));
    setShipments([...(s.data || []), ...bookings]);
    setFacilities(f.data || []);
    setRefreshAt(Date.now());
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, []);
  useBrandRefresh(() => load());

  // Match against EVERY useful tracking identifier — not just container_no.
  const matches = useMemo(() => {
    const ql = q.trim().toLowerCase();
    if (!ql) return shipments;
    return shipments.filter((s) => {
      const hay = [
        s.reference, s.shipment_id, s.bol_no, s.pro_no, s.container_no,
        s.booking_number, s.carrier, s.mode,
        s.origin?.city, s.origin?.name, s.destination?.city, s.destination?.name,
        s.commodity, s.supplier, s.consignee, s.material_controller,
        ...(Array.isArray(s.po_numbers) ? s.po_numbers : [s.po_numbers || ""]),
      ].filter(Boolean).join(" | ").toLowerCase();
      return hay.includes(ql);
    });
  }, [shipments, q]);

  // Map shows matches only when actively searching, else everything.
  // Skip rows without geo coordinates (e.g. brokerage bookings) so MapView
  // markers don't crash.
  const mapShipments = (q.trim() ? matches : shipments).filter(
    s => !s._noMap
       && s.origin && typeof s.origin.lat === "number"
       && s.destination && typeof s.destination.lat === "number"
  );

  const trackOnCarrier = (s) => {
    const trackNum = s.pro_no || s.container_no || s.bol_no || s.booking_number || s.reference;
    if (!s.carrier) { toast.error("No carrier on this shipment"); return; }
    if (!trackNum)  { toast.error("No PRO / container / BOL on this shipment"); return; }
    // Pre-open the popup SYNCHRONOUSLY inside the click event — browsers
    // block popups opened from async callbacks (this was the silent failure
    // before). Then we resolve the carrier URL and redirect the popup.
    const popup = window.open("about:blank", "_blank", "noopener,noreferrer");
    api.get(`/carriers/tracking-url?carrier=${encodeURIComponent(s.carrier)}&tracking=${encodeURIComponent(trackNum)}`)
      .then(({ data }) => {
        if (popup && !popup.closed) {
          popup.location.href = data.url;
        } else {
          // Popup blocked — fall back to a clickable toast.
          toast.success(`${data.label} ready — click to open`, {
            duration: 12000,
            action: { label: "Open", onClick: () => window.open(data.url, "_blank", "noopener,noreferrer") },
          });
        }
      })
      .catch(() => {
        if (popup && !popup.closed) popup.close();
        toast.error(`No public tracking URL for "${s.carrier}"`);
      });
  };

  return (
    <>
      <Topbar title="Live Tracking" subtitle="Real-time positions · per-shipment lookup · carrier tracking · weather" />
      <div className="p-4 md:p-6 space-y-5">
        {/* S/4 + TMS omni-search across PO / SO / BOL / part / tracking / delivery */}
        <Card className="hud-surface p-4" data-testid="tracking-s4-search">
          <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-2 flex items-center gap-2">
            <Search size={11} /> SAP S/4HANA · TMS Cross-Document Search
          </div>
          <p className="text-[11px] text-slate-400 mb-2 leading-relaxed">
            Look up any record by PO, Sales Order, Part #, Tracking #, Delivery #, BOL or Container.
            Internal matches jump to the shipment record; S/4 matches open in Fiori.
          </p>
          <GlobalSearch />
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <Card className="hud-surface p-4 lg:col-span-8 space-y-2">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400">Live Map · {mapShipments.length} shipment{mapShipments.length === 1 ? "" : "s"}</div>
                <div className="text-[10px] font-mono text-slate-500">Auto-refresh every 30s · last updated {new Date(refreshAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>
              </div>
              <button onClick={load} data-testid="tracking-refresh-btn" className="px-2.5 py-1 rounded text-[10px] font-mono uppercase border border-white/10 text-slate-300 hover:border-cyan-400/40 flex items-center gap-1.5">
                <RefreshCw size={11} /> Refresh
              </button>
            </div>
            <MapView shipments={mapShipments} facilities={facilities} height={520} showRoutes focus={focus} />
          </Card>

          <div className="lg:col-span-4 space-y-4">
            <CarrierTrackingPanel />

            {/* ============= Shipment Tracker ============= */}
            <Card className="hud-surface p-4" data-testid="shipment-tracker">
              <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-400 mb-3 flex items-center gap-2">
                <Crosshair size={12} /> Shipment Tracker
              </div>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <Input
                  data-testid="shipment-tracker-input"
                  value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Track by ref, BOL, PRO, container, PO, carrier, city…"
                  className="pl-9 pr-9 bg-[#0B0E14] border-white/10"
                />
                {q && (
                  <button onClick={() => { setQ(""); setFocus(null); }} data-testid="tracker-clear"
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-slate-500 hover:text-slate-200">
                    <X size={13} />
                  </button>
                )}
              </div>
              <div className="text-[10px] font-mono text-slate-500 mt-2" data-testid="tracker-count">
                {q.trim()
                  ? `${matches.length} match${matches.length === 1 ? "" : "es"} for "${q}"`
                  : `${shipments.length} active shipments`}
              </div>

              <div className="mt-3 space-y-2 max-h-[440px] overflow-y-auto pr-1" data-testid="tracker-results">
                {matches.slice(0, 30).map((s) => {
                  const Icon = MODE_ICON[s.mode] || Truck;
                  const isFocused = focus?.shipment_id === s.shipment_id;
                  const pct = Math.round((s.progress || 0) * 100);
                  const trackNum = s.pro_no || s.container_no || s.bol_no || s.booking_number;
                  return (
                    <div
                      key={s.shipment_id}
                      data-testid={`tracker-row-${s.shipment_id}`}
                      className={`p-2.5 rounded-md border transition-all ${
                        isFocused
                          ? "border-cyan-500/50 bg-cyan-500/10 shadow-[0_0_0_1px_rgba(0,229,255,0.15)]"
                          : "border-white/5 bg-white/[0.02] hover:border-cyan-500/30"
                      }`}
                    >
                      <button onClick={() => setFocus(s)} className="w-full text-left" data-testid={`tracker-focus-${s.shipment_id}`}>
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <Icon size={11} className="text-cyan-400 shrink-0" />
                            <div className="font-mono text-xs text-cyan-200 truncate">{s.reference}</div>
                            <span className="px-1 py-0.5 rounded text-[8px] font-mono uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 shrink-0">{s.mode}</span>
                          </div>
                          <Badge className={`text-[9px] font-mono uppercase border ${STATUS_PILL[s.status] || STATUS_PILL.in_transit}`}>{s.status}</Badge>
                        </div>
                        <div className="text-[11px] text-slate-300 mt-1 truncate">
                          <span className="text-slate-400">{s.origin?.city}</span>
                          <span className="text-cyan-400 mx-1">→</span>
                          <span className="text-slate-400">{s.destination?.city}</span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                          <span className="text-cyan-300">{s.carrier || "—"}</span>
                          {trackNum && <span className="text-slate-500">· {trackNum}</span>}
                        </div>
                        <div className="mt-1.5 h-1 bg-white/5 rounded overflow-hidden">
                          <div className="h-full bg-gradient-to-r from-cyan-500 to-emerald-500" style={{ width: `${pct}%` }} />
                        </div>
                        <div className="flex justify-between mt-1 text-[10px] font-mono text-slate-500">
                          <span>{pct}%</span>
                          <span>ETA {s.eta ? new Date(s.eta).toLocaleDateString() : "—"}</span>
                        </div>
                      </button>
                      <div className="flex gap-1.5 mt-2">
                        <button
                          onClick={() => setFocus(s)}
                          className="flex-1 px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wider border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/10 flex items-center justify-center gap-1"
                          data-testid={`tracker-map-${s.shipment_id}`}
                        >
                          <MapPin size={10} /> Focus on map
                        </button>
                        <button
                          onClick={() => trackOnCarrier(s)}
                          className="flex-1 px-2 py-1 rounded text-[10px] font-mono uppercase tracking-wider border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10 flex items-center justify-center gap-1"
                          data-testid={`tracker-track-${s.shipment_id}`}
                          disabled={!s.carrier}
                          title={s.carrier ? `Open ${s.carrier} tracking` : "No carrier on shipment"}
                        >
                          <ExternalLink size={10} /> Track on carrier
                        </button>
                      </div>
                    </div>
                  );
                })}
                {matches.length === 0 && (
                  <div className="text-xs text-slate-500 text-center py-6">
                    No shipments match <span className="text-cyan-300">"{q}"</span>.
                    <div className="text-[10px] mt-1">Try a ref, BOL, PRO, container, PO, carrier or city.</div>
                  </div>
                )}
                {matches.length > 30 && (
                  <div className="text-[10px] font-mono text-slate-500 text-center py-2">
                    Showing first 30 of {matches.length} — refine your search to see more.
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>

        {/* Live weather radar below the map */}
        <WeatherRadar height={400} />
      </div>
    </>
  );
}
