import React, { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";

// Custom HTML icon for each shipment based on status
const buildIcon = (status, mode) =>
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

const FACILITY_ICON = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border:2px solid #00E5FF;background:#0B0E14;border-radius:2px;transform:rotate(45deg);box-shadow:0 0 10px #00E5FF;"></div>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

// Imperative child that flies the map to a selected shipment when `focus` changes.
function MapFocus({ focus }) {
  const map = useMap();
  useEffect(() => {
    if (!focus?.current_location) return;
    const { lat, lng } = focus.current_location;
    if (typeof lat !== "number" || typeof lng !== "number") return;
    map.flyTo([lat, lng], 6, { duration: 0.8 });
  }, [focus?.shipment_id]);  // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function MapView({ shipments = [], facilities = [], height = 480, showRoutes = false, focus = null }) {
  const center = useMemo(() => [39.5, -95.0], []);
  const routes = useMemo(() => {
    if (!showRoutes) return [];
    return shipments
      .filter((s) => s.status !== "delivered" && s.status !== "pending")
      .map((s) => ({
        id: s.shipment_id,
        positions: [
          [s.origin.lat, s.origin.lng],
          [s.current_location.lat, s.current_location.lng],
          [s.destination.lat, s.destination.lng],
        ],
        color: statusColor(s.status),
      }));
  }, [shipments, showRoutes]);

  return (
    <div className="rounded-lg overflow-hidden border border-white/5 hud-glow-cyan" style={{ height }} data-testid="map-view">
      <MapContainer center={center} zoom={3.5} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <MapFocus focus={focus} />
        <TileLayer
          attribution='© OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {facilities.map((f) => (
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
          <Polyline key={r.id} positions={r.positions} pathOptions={{ color: r.color, weight: 1.2, opacity: 0.35, dashArray: "4 6" }} />
        ))}
        {shipments.map((s) => (
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
                <div style={{ fontSize: 12 }}><strong>Origin:</strong> {s.origin.city}</div>
                <div style={{ fontSize: 12 }}><strong>Dest:</strong> {s.destination.city}</div>
                <div style={{ fontSize: 12 }}><strong>ETA:</strong> {new Date(s.eta).toLocaleDateString()}</div>
                {s.container_no && <div style={{ fontSize: 12 }}><strong>Container:</strong> {s.container_no}</div>}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
