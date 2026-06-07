/* eslint-disable */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Truck, MapPin, Camera, CheckCircle2, AlertCircle, Loader2,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/** Driver PWA · public no-auth page authenticated by booking_id + 4-digit PIN.
 *  URL: /driver?booking=BK-XXX&pin=1234 */
export default function DriverPwa() {
  const params = new URLSearchParams(window.location.search);
  const bookingId = params.get("booking") || "";
  const pin = params.get("pin") || "";
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  const fetchBooking = async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${REACT_APP_BACKEND_URL}/api/driver-pwa/booking/${bookingId}?pin=${pin}`);
      setBooking(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Invalid booking or PIN.");
    } finally { setLoading(false); }
  };
  useEffect(() => { if (bookingId && pin) fetchBooking(); else setLoading(false); }, []);

  const updateStatus = async (status) => {
    setUpdating(true);
    try {
      const loc = await new Promise((resolve) => {
        if (!navigator.geolocation) return resolve({});
        navigator.geolocation.getCurrentPosition(
          (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
          () => resolve({}), { timeout: 3000 }
        );
      });
      await axios.post(
        `${REACT_APP_BACKEND_URL}/api/driver-pwa/status?pin=${pin}`,
        { booking_id: bookingId, status, ...loc });
      await fetchBooking();
    } catch (e) {
      alert(e?.response?.data?.detail || "Update failed");
    } finally { setUpdating(false); }
  };

  if (!bookingId || !pin) {
    return (
      <Shell><Card className="hud-surface p-6 text-center">
        <AlertCircle className="text-red-400 mx-auto mb-2" size={32}/>
        <div className="font-bold">Missing booking ID or PIN</div>
        <div className="text-sm text-slate-400 mt-2">Open the link your dispatcher texted you.</div>
      </Card></Shell>
    );
  }
  if (loading) return <Shell><Loader2 className="animate-spin mx-auto" size={32}/></Shell>;
  if (error || !booking) return (
    <Shell><Card className="hud-surface p-6 text-center" data-testid="driver-error">
      <AlertCircle className="text-red-400 mx-auto mb-2" size={32}/>
      <div className="font-bold">{error}</div>
    </Card></Shell>
  );

  const STATUSES = [
    { id: "arrived_pickup", label: "Arrived at pickup" },
    { id: "loaded", label: "Loaded" },
    { id: "enroute", label: "Enroute" },
    { id: "arrived_delivery", label: "Arrived at delivery" },
    { id: "delivered", label: "Delivered" },
  ];

  return (
    <Shell>
      <Card className="hud-surface p-5" data-testid="driver-header">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
          Orisei Freight Solutions · Driver
        </div>
        <h1 className="font-display text-2xl font-black mt-1 flex items-center gap-2">
          <Truck className="text-cyan-400" size={24}/>
          {booking.origin || "—"} → {booking.destination || "—"}
        </h1>
        <div className="text-xs text-slate-400 mt-1 font-mono">
          {booking.booked_id || booking.booking_id} · {booking.equipment || "—"}
          {booking.miles && <> · {booking.miles} mi</>}
        </div>
        {booking.status && (
          <div className="mt-3">
            <span className="px-2 py-0.5 rounded text-xs font-mono uppercase tracking-wider border bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
              Current · {booking.status}
            </span>
          </div>
        )}
      </Card>

      <Card className="hud-surface p-5" data-testid="driver-status-list">
        <h3 className="font-display font-bold mb-3">Update status</h3>
        <div className="space-y-2">
          {STATUSES.map((s) => {
            const done = booking[`${s.id}_at`];
            return (
              <button key={s.id}
                onClick={() => updateStatus(s.id)}
                disabled={updating}
                data-testid={`driver-status-${s.id}`}
                className={`w-full p-3 rounded border text-left transition flex items-center justify-between gap-2 ${
                  done ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                       : "bg-white/[0.02] border-white/10 hover:bg-cyan-500/10 hover:border-cyan-500/30 text-white"
                }`}>
                <div className="flex items-center gap-3">
                  {done ? <CheckCircle2 size={18}/> : <div className="w-4 h-4 rounded-full border-2 border-current"/>}
                  <div>
                    <div className="font-bold text-sm">{s.label}</div>
                    {done && <div className="text-[10px] font-mono opacity-70">{done.slice(0,16).replace("T"," ")}</div>}
                  </div>
                </div>
                {!done && <span className="text-[10px] font-mono uppercase opacity-50">Tap</span>}
              </button>
            );
          })}
        </div>
      </Card>

      <div className="text-center text-xs text-slate-500 font-mono py-4">
        Hold this page open · GPS pings dispatcher on each update.
      </div>
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[#0B1118] text-white">
      <div className="p-4 max-w-md mx-auto space-y-4">{children}</div>
    </div>
  );
}
