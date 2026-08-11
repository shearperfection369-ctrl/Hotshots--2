import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import { Card } from "../ui/card";
import { MapPin } from "lucide-react";

const pinIcon = (color) => L.divIcon({
  className: "",
  html: `<div style="width:20px;height:20px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${color};border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.55)"></div>`,
  iconSize: [20, 20], iconAnchor: [10, 20],
});

export const TcJobsMap = ({ api }) => {
  const [data, setData] = useState(null);
  const [date, setDate] = useState("");
  useEffect(() => {
    api.get(`/truck-cleaning/jobs-map${date ? `?date=${date}` : ""}`)
      .then(({ data: d }) => setData(d)).catch(() => {});
  }, [api, date]);
  const pins = data?.pins || [];
  const center = pins.length ? [pins[0].lat, pins[0].lng] : [44.9778, -93.265];
  return (
    <Card className="p-4 bg-slate-950/70 border-cyan-500/25 mb-3" data-testid="tc-jobs-map">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <MapPin size={15} className="text-cyan-300" /> Work Location Map
          <span className="px-2 py-0.5 rounded-full bg-cyan-500/15 border border-cyan-500/40 text-cyan-300 text-[10px] font-black" data-testid="tc-map-pin-count">
            {pins.length} pinned{data && data.total_jobs > pins.length ? ` · ${data.total_jobs - pins.length} without coords` : ""}
          </span>
        </h3>
        <div className="flex items-center gap-2">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
            className="h-8 px-2 rounded-lg bg-[#11151F] border border-white/15 text-[11px] text-slate-300 outline-none"
            data-testid="tc-map-date-filter" />
          {date && <button onClick={() => setDate("")} className="text-[10px] font-mono text-slate-500 hover:text-white" data-testid="tc-map-clear-date">ALL DATES</button>}
        </div>
      </div>
      <div className="rounded-xl overflow-hidden border border-white/10" style={{ height: 340 }}>
        <MapContainer center={center} zoom={10} style={{ height: "100%", width: "100%", background: "#0B0E14" }} scrollWheelZoom>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
          />
          {pins.map((p) => (
            <Marker key={p.job_id} position={[p.lat, p.lng]}
              icon={pinIcon(p.status === "in_progress" ? "#22D3EE" : "#F59E0B")}>
              <Popup>
                <div style={{ fontSize: 12, minWidth: 180 }}>
                  <b>{p.company}</b><br />
                  {p.date} · {p.cabs} vehicle{p.cabs > 1 ? "s" : ""} · ${Math.round(p.price)}<br />
                  {p.address}<br />
                  {p.vehicle_location && <i>Vehicles: {p.vehicle_location}<br /></i>}
                  <span style={{ textTransform: "uppercase", fontWeight: 700, color: p.status === "in_progress" ? "#0891B2" : "#B45309" }}>{p.status}</span>
                  {" · "}
                  <a href={`https://maps.google.com/?q=${encodeURIComponent(p.address || `${p.lat},${p.lng}`)}`} target="_blank" rel="noreferrer">Google Maps</a>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <div className="flex gap-4 mt-2 text-[10px] font-mono text-slate-500">
        <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 mr-1" />scheduled</span>
        <span><span className="inline-block w-2.5 h-2.5 rounded-full bg-cyan-400 mr-1" />in progress</span>
      </div>
    </Card>
  );
};
