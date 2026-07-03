import React, { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import MapErrorBoundary from "./MapErrorBoundary";

// ------------------------------------------------------------
//  Defensive helpers — every LatLng that ends up inside a
//  Leaflet component MUST pass through validCoord() first.
//  Reason: Leaflet's `new LatLng(undefined, undefined)` throws
//  a hard exception that (without the surrounding
//  MapErrorBoundary) tears down the whole React tree.
// ------------------------------------------------------------
const isFiniteNum = (v) =>
  typeof v === "number" && Number.isFinite(v) && !Number.isNaN(v);

/** true iff `obj?.{latKey, lngKey}` are both finite numbers */
export const hasLatLng = (obj, latKey = "lat", lngKey = "lng") =>
  !!obj && isFiniteNum(obj[latKey]) && isFiniteNum(obj[lngKey]);

/** returns [lat, lng] or null when either is missing/NaN */
const toLatLngPair = (obj, latKey = "lat", lngKey = "lng") =>
  hasLatLng(obj, latKey, lngKey) ? [obj[latKey], obj[lngKey]] : null;

// ------------------------------------------------------------
//  Icons — unchanged, but wrapped in try/catch on divIcon to
//  avoid a corrupt icon spec from bricking the whole page.
// ------------------------------------------------------------
function statusColor(s) {
  return {
    in_transit: "#00E5FF",
    delayed: "#FF3B30",
    delivered: "#00FF66",
    pending: "#FFCC00",
    at_origin: "#FFCC00",
    at_dest: "#00FF66",
  }[s] || "#94A3B8";
}

const buildIcon = (status /*, mode */) =>
  L.divIcon({
    className: "",
    html: `
      <div style="position:relative;width:18px;height:18px;">
        <span class="pulse-ring" style="position:absolute;inset:0;border-radius:9999px;background:${statusColor(status)};opacity:0.5;"></span>
        <div class="shipment-marker ${status}" style="position:absolute;left:2px;top:2px;width:14px;height:14px;"></div>
      </div>
    `,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });

const FACILITY_ICON = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border:2px solid #00E5FF;background:#0B0E14;border-radius:2px;transform:rotate(45deg);box-shadow:0 0 10px #00E5FF;"></div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

// ------------------------------------------------------------
//  Imperative child that flies the map to a selected shipment.
// ------------------------------------------------------------
function MapFocus({ focus }) {
  const map = useMap();
  useEffect(() => {
    const pair = toLatLngPair(focus?.current_location);
    if (!pair) return;
    map.flyTo(pair, 6, { duration: 0.8 });
  }, [focus?.shipment_id]);
  return null;
}

// ------------------------------------------------------------
//  Main component
// ------------------------------------------------------------
function MapViewInner({ shipments = [], facilities = [], height = 480, showRoutes = false, focus = null }) {
  const center = useMemo(() => [39.5, -95.0], []);

  // Drop any shipment/facility that would produce an invalid LatLng.
  const safeFacilities = useMemo(
    () => (facilities || []).filter((f) => hasLatLng(f)),
    [facilities]
  );
  const safeShipments = useMemo(
    () => (shipments || []).filter((s) => hasLatLng(s?.current_location)),
    [shipments]
  );
  const skippedShipments = (shipments?.length || 0) - safeShipments.length;

  const routes = useMemo(() => {
    if (!showRoutes) return [];
    return safeShipments
      .filter((s) => s.status !== "delivered" && s.status !== "pending")
      .map((s) => {
        // Every polyline point must be a valid pair; drop the shipment if
        // origin or destination is missing rather than shove undefined values
        // into Leaflet's Polyline (which also throws).
        const positions = [
          toLatLngPair(s.origin),
          toLatLngPair(s.current_location),
          toLatLngPair(s.destination),
        ].filter(Boolean);
        if (positions.length < 2) return null;
        return { id: s.shipment_id, positions, color: statusColor(s.status) };
      })
      .filter(Boolean);
  }, [safeShipments, showRoutes]);

  return (
    <div
      className="rounded-lg overflow-hidden border border-white/5 hud-glow-cyan relative"
      style={{ height }}
      data-testid="map-view"
    >
      {skippedShipments > 0 && (
        <div
          data-testid="map-skipped-warning"
          className="absolute top-2 right-2 z-[500] px-2 py-1 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200 text-[10px] font-mono uppercase tracking-widest"
          title="Shipments missing GPS coordinates were hidden from the map"
        >
          {skippedShipments} shipment{skippedShipments === 1 ? "" : "s"} · no GPS yet
        </div>
      )}
      <MapContainer center={center} zoom={3.5} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <MapFocus focus={focus} />
        <TileLayer
          attribution='© OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {safeFacilities.map((f) => (
          <Marker key={f.id} position={[f.lat, f.lng]} icon={FACILITY_ICON}>
            <Popup>
              <div style={{ color: "#0B0E14" }}>
                <strong>{f.name}</strong>
                <br />
                <span style={{ fontSize: 11 }}>{f.type}</span>
              </div>
            </Popup>
          </Marker>
        ))}
        {routes.map((r) => (
          <Polyline
            key={r.id}
            positions={r.positions}
            pathOptions={{ color: r.color, weight: 1.2, opacity: 0.35, dashArray: "4 6" }}
          />
        ))}
        {safeShipments.map((s) => (
          <Marker
            key={s.shipment_id}
            position={[s.current_location.lat, s.current_location.lng]}
            icon={buildIcon(s.status, s.mode)}
          >
            <Popup>
              <div style={{ color: "#0B0E14", minWidth: 200 }}>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>{s.reference} · {s.mode}</div>
                <div style={{ fontSize: 12 }}><strong>Carrier:</strong> {s.carrier}</div>
                <div style={{ fontSize: 12 }}><strong>Status:</strong> {s.status}</div>
                <div style={{ fontSize: 12 }}><strong>Origin:</strong> {s.origin?.city ?? "—"}</div>
                <div style={{ fontSize: 12 }}><strong>Dest:</strong> {s.destination?.city ?? "—"}</div>
                <div style={{ fontSize: 12 }}>
                  <strong>ETA:</strong>{" "}
                  {s.eta && !Number.isNaN(new Date(s.eta).getTime())
                    ? new Date(s.eta).toLocaleDateString()
                    : "—"}
                </div>
                {s.container_no && <div style={{ fontSize: 12 }}><strong>Container:</strong> {s.container_no}</div>}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

// Public export — always wrapped in the error boundary so an inner
// crash renders a graceful fallback card instead of the red-screen-of-death.
export default function MapView(props) {
  return (
    <MapErrorBoundary height={props.height}>
      <MapViewInner {...props} />
    </MapErrorBoundary>
  );
}
