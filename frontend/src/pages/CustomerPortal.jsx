import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Package, FileText, DollarSign, Truck, CheckCircle2,
  AlertCircle, Building2, MapPin, Camera, Clock, Activity, Route,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/** Public, token-gated customer self-service portal. */
export default function CustomerPortal() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    if (!token) {
      setError("Missing portal token. Please use the link your Orisei contact sent you.");
      setLoading(false); return;
    }
    axios.get(`${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || "Unable to load portal."))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <Shell><div className="text-slate-400 text-sm">Loading…</div></Shell>;
  if (error) return (
    <Shell>
      <Card className="hud-surface p-6" data-testid="portal-error">
        <div className="flex items-start gap-3">
          <AlertCircle className="text-red-400 mt-1" size={20} />
          <div>
            <div className="font-bold text-red-300">Portal unavailable</div>
            <div className="text-sm text-slate-400 mt-1">{error}</div>
            <div className="text-xs text-slate-500 mt-3 font-mono">
              Contact us · shearperfection369@gmail.com · Orisei Freight Solutions
            </div>
          </div>
        </div>
      </Card>
    </Shell>
  );

  const summary = data.summary || {};

  return (
    <Shell>
      <Card className="hud-surface p-6" data-testid="portal-header">
        <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
          Orisei Freight Solutions · Customer Portal
        </div>
        <div className="flex items-center justify-between flex-wrap gap-3 mt-1">
          <h1 className="font-display text-3xl font-black flex items-center gap-3">
            <Building2 className="text-cyan-400" size={28} />
            {data.customer_name}
          </h1>
          <Badge className="bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 font-mono text-[10px] uppercase">
            Live · token verified
          </Badge>
        </div>
        <div className="text-xs text-slate-400 mt-2">
          Terms · {data.customer?.payment_terms || "Net 30"}
          {data.customer?.primary_contact_name && (<> · Contact · {data.customer.primary_contact_name}</>)}
        </div>

        <div className="flex flex-wrap gap-2 mt-5 border-t border-white/5 pt-4">
          {[
            { id: "overview", label: "Overview", icon: Building2 },
            { id: "tracking", label: "Tracking", icon: Truck },
            { id: "routing", label: "Routing Guide", icon: Route },
            { id: "invoices", label: "Invoices", icon: DollarSign },
            { id: "quotes", label: "Quotes", icon: FileText },
          ].map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              data-testid={`portal-tab-${t.id}`}
              className={`px-4 py-2 rounded text-xs font-mono uppercase tracking-wider transition flex items-center gap-2 ${
                tab === t.id
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-cyan-300 border border-transparent hover:bg-white/5"
              }`}>
              <t.icon size={13} /> {t.label}
            </button>
          ))}
        </div>
      </Card>

      {tab === "overview" && <OverviewTab summary={summary} bookings={data.bookings} />}
      {tab === "tracking" && <TrackingTab token={token} bookings={data.bookings} />}
      {tab === "routing" && <RoutingGuideTab token={token} />}
      {tab === "invoices" && <InvoicesTab invoices={data.invoices} />}
      {tab === "quotes" && <QuotesTab quotes={data.quotes} />}

      <div className="text-center text-xs text-slate-500 font-mono py-6">
        Orisei Freight Solutions LLC · Plymouth, MN · shearperfection369@gmail.com
      </div>
    </Shell>
  );
}

// ============================ OVERVIEW ============================
function OverviewTab({ summary, bookings }) {
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Tile testid="stat-active" icon={Truck} label="Active shipments"
              value={summary.active_shipments ?? 0} accent="text-cyan-300" />
        <Tile testid="stat-delivered" icon={CheckCircle2} label="Delivered · 30d"
              value={summary.delivered_past_30d ?? 0} accent="text-emerald-300" />
        <Tile testid="stat-invoices" icon={DollarSign} label="Outstanding A/R"
              value={`$${(summary.outstanding_invoices_usd ?? 0).toLocaleString()}`}
              accent="text-amber-300" />
        <Tile testid="stat-quotes" icon={FileText} label="Open quotes"
              value={summary.open_quotes ?? 0} accent="text-violet-300" />
      </div>
      <Section title="Recent shipments" testid="portal-bookings">
        {(bookings || []).length === 0 ? <Empty msg="No shipments on file yet." /> : (
          <div className="space-y-2">
            {bookings.slice(0, 8).map((b) => (
              <Row key={b.booked_id || b.booking_id}
                   testid={`portal-booking-${b.booked_id || b.booking_id}`}>
                <RowMain icon={Package}>
                  <div className="font-bold">{b.origin || "—"} → {b.destination || "—"}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {b.booked_id || b.booking_id}
                    {b.commodity && <> · {b.commodity}</>}
                    {b.pickup_date && <> · Pickup {b.pickup_date}</>}
                  </div>
                </RowMain>
                <StatusPill status={b.status} />
              </Row>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}

// ============================ TRACKING ============================
function TrackingTab({ token, bookings }) {
  const active = (bookings || []).filter(
    (b) => ["booked", "tendered", "in_transit", "delivered"].includes((b.status || "").toLowerCase())
  );
  return (
    <Section title="Live tracking" testid="portal-tracking">
      {active.length === 0 ? <Empty msg="No shipments to track right now." /> : (
        <div className="space-y-4">
          {active.map((b) => (
            <TrackingCard key={b.booked_id || b.booking_id} token={token} booking={b} />
          ))}
        </div>
      )}
    </Section>
  );
}

function TrackingCard({ token, booking }) {
  const bid = booking.booked_id || booking.booking_id;
  const t = booking.tracking || { timeline: [], photo_count: 0 };
  const photoCount = t.photo_count || 0;
  const [photos, setPhotos] = useState([]);
  const [showPhotos, setShowPhotos] = useState(false);

  const loadPhotos = async () => {
    if (photos.length || !photoCount) return;
    try {
      const r = await axios.get(
        `${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}/bookings/${bid}/photos`);
      setPhotos(r.data.items || []);
    } catch (_) { /* swallow — show photo_count only */ }
  };

  return (
    <div className="p-4 rounded border bg-white/[0.02]"
         style={{ borderColor: "rgba(255,255,255,0.06)" }}
         data-testid={`portal-track-${bid}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-bold flex items-center gap-2">
            <Truck size={14} className="text-cyan-400" />
            {booking.origin || "—"} → {booking.destination || "—"}
          </div>
          <div className="text-xs text-slate-500 font-mono mt-0.5">
            {bid}
            {booking.carrier_name && <> · {booking.carrier_name}</>}
            {booking.miles && <> · {booking.miles} mi</>}
            {t.eta && <> · ETA {t.eta}</>}
          </div>
        </div>
        <StatusPill status={t.current_status || booking.status} />
      </div>

      {/* Timeline */}
      {t.timeline?.length > 0 && (
        <div className="mt-4 space-y-2">
          {t.timeline.map((entry, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <CheckCircle2 size={14} className="text-emerald-400 mt-1 flex-shrink-0" />
              <div className="flex-1">
                <div className="font-medium">{entry.label}</div>
                <div className="text-[11px] text-slate-500 font-mono">
                  {entry.at?.slice(0, 16).replace("T", " ")} UTC
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Delivery photos */}
      {photoCount > 0 && (
        <div className="mt-4 border-t border-white/5 pt-3">
          <button onClick={() => { setShowPhotos((s) => !s); if (!showPhotos) loadPhotos(); }}
            className="text-xs font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200 flex items-center gap-2"
            data-testid={`portal-show-photos-${bid}`}>
            <Camera size={12} /> {photoCount} delivery photo{photoCount === 1 ? "" : "s"}
            {showPhotos ? " · hide" : " · view"}
          </button>
          {showPhotos && (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-3">
              {photos.map((p) => (
                <a key={p.photo_id}
                   href={`${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}/bookings/${bid}/photos/${p.photo_id}`}
                   target="_blank" rel="noreferrer"
                   className="block aspect-video bg-black/40 rounded overflow-hidden border border-white/5 hover:border-cyan-500/40 transition">
                  <img
                    src={`${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}/bookings/${bid}/photos/${p.photo_id}`}
                    alt={p.caption || "Delivery"}
                    className="w-full h-full object-cover"
                    loading="lazy" />
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================ ROUTING GUIDE ============================
function RoutingGuideTab({ token }) {
  const [guide, setGuide] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    axios.get(`${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}/routing-guide`)
      .then((r) => setGuide(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Routing guide unavailable"));
  }, [token]);

  if (err) return <Section title="Routing Guide" testid="portal-routing">
    <div className="text-sm text-red-300">{err}</div></Section>;
  if (!guide) return <Section title="Routing Guide" testid="portal-routing">
    <div className="text-sm text-slate-400">Building your live routing guide…</div></Section>;

  return (
    <>
      <Section title="Your live routing guide" testid="portal-routing">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          <MiniStat label="Lanes you ship" value={guide.your_lane_count} />
          <MiniStat label="Lanes we run" value={guide.lane_count} />
          <MiniStat label="Refreshed" value={guide.generated_at?.slice(11, 16) + " UTC"} />
          <MiniStat label="Status" value="LIVE" accent="text-emerald-300" />
        </div>
        <p className="text-xs text-slate-500 italic mb-4">
          Live pricing bands + carrier performance derived from {guide.lane_count} lanes
          in our active book. Refresh this page to re-pull rates.
        </p>
        {guide.lanes.length === 0 ? <Empty msg="No lanes published yet." /> : (
          <div className="space-y-3">
            {guide.lanes.map((L, i) => <LaneCard key={i} L={L} />)}
          </div>
        )}
      </Section>
    </>
  );
}

function MiniStat({ label, value, accent }) {
  return (
    <div className="p-3 rounded border bg-white/[0.02]"
         style={{ borderColor: "rgba(255,255,255,0.06)" }}>
      <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className={`font-display text-lg font-bold mt-1 ${accent || "text-cyan-300"}`}>{value}</div>
    </div>
  );
}

function LaneCard({ L }) {
  const band = L.pricing_band;
  return (
    <div className="p-4 rounded border bg-white/[0.02]"
         style={{ borderColor: "rgba(255,255,255,0.06)" }}
         data-testid={`portal-lane-${L.origin}-${L.destination}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-bold flex items-center gap-2">
            <Route size={14} className="text-cyan-400" />
            {L.origin} → {L.destination}
          </div>
          <div className="text-xs text-slate-500 font-mono mt-0.5">
            {L.avg_miles ? `${L.avg_miles} mi` : "—"} · {L.total_loads} total loads
            {L.your_loads > 0 && <> · <span className="text-cyan-300">{L.your_loads} for you</span></>}
          </div>
        </div>
        {L.your_loads > 0 && (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border bg-cyan-500/15 text-cyan-300 border-cyan-500/30">
            Active lane
          </span>
        )}
      </div>

      {/* Pricing band */}
      {band ? (
        <div className="mt-4 grid grid-cols-3 gap-2">
          <Band label="Low" value={band.low_usd} rpm={band.rpm?.low} accent="text-emerald-300" />
          <Band label="Median" value={band.median_usd} rpm={band.rpm?.median} accent="text-cyan-300" />
          <Band label="High" value={band.high_usd} rpm={band.rpm?.high} accent="text-amber-300" />
        </div>
      ) : (
        <div className="text-xs text-slate-500 italic mt-3">
          No closed rates yet on this lane — request a spot quote.
        </div>
      )}

      {/* Top carriers */}
      {L.top_carriers?.length > 0 && (
        <div className="mt-4 border-t border-white/5 pt-3">
          <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-2">
            Preferred carriers · ranked
          </div>
          <div className="space-y-1.5">
            {L.top_carriers.map((c, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <div className="font-medium">
                  <span className="text-slate-500 font-mono mr-2">#{i + 1}</span>
                  {c.name}
                  {c.mc && <span className="text-slate-500 font-mono ml-1">· MC {c.mc}</span>}
                </div>
                <div className="font-mono text-slate-400 text-[11px]">
                  {c.loads} loads
                  {c.on_time_pct !== null && <> · {c.on_time_pct}% OTP</>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Band({ label, value, rpm, accent }) {
  return (
    <div className="p-2 rounded bg-black/30 text-center">
      <div className="text-[9px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
      <div className={`font-bold text-sm mt-0.5 ${accent}`}>
        ${Number(value).toLocaleString()}
      </div>
      {rpm && <div className="text-[10px] text-slate-500 font-mono mt-0.5">${rpm}/mi</div>}
    </div>
  );
}

// ============================ INVOICES ============================
function InvoicesTab({ invoices }) {
  return (
    <Section title="Invoices" testid="portal-invoices">
      {(invoices || []).length === 0 ? <Empty msg="No invoices issued yet." /> : (
        <div className="space-y-2">
          {invoices.map((inv) => (
            <Row key={inv.invoice_id} testid={`portal-invoice-${inv.invoice_id}`}>
              <RowMain icon={DollarSign}>
                <div className="font-bold">${Number(inv.amount_usd || 0).toLocaleString()}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">
                  {inv.invoice_id} · {inv.issued_at?.slice(0, 10)}
                </div>
              </RowMain>
              <StatusPill status={inv.status} />
            </Row>
          ))}
        </div>
      )}
    </Section>
  );
}

// ============================ QUOTES ============================
function QuotesTab({ quotes }) {
  return (
    <Section title="Quotes" testid="portal-quotes">
      {(quotes || []).length === 0 ? <Empty msg="No quotes on file." /> : (
        <div className="space-y-2">
          {quotes.map((q) => (
            <Row key={q.quote_id} testid={`portal-quote-${q.quote_id}`}>
              <RowMain icon={FileText}>
                <div className="font-bold">{q.origin} → {q.destination}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">
                  {q.quote_id} · ${q.total_usd?.toLocaleString()}
                  {q.valid_until && <> · valid until {q.valid_until.slice(0, 10)}</>}
                </div>
              </RowMain>
              <StatusPill status={q.status} />
            </Row>
          ))}
        </div>
      )}
    </Section>
  );
}

// ============================ shared ============================
function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[#0B1118] text-white">
      <div className="p-6 max-w-5xl mx-auto space-y-6">{children}</div>
    </div>
  );
}
function Tile({ icon: Icon, label, value, accent, testid }) {
  return (
    <Card className="hud-surface p-4" data-testid={testid}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">{label}</div>
        <Icon className={accent} size={16} />
      </div>
      <div className={`font-display text-2xl font-black mt-2 ${accent}`}>{value}</div>
    </Card>
  );
}
function Section({ title, testid, children }) {
  return (
    <Card className="hud-surface p-5" data-testid={testid}>
      <h2 className="font-display text-lg font-bold mb-3">{title}</h2>
      {children}
    </Card>
  );
}
function Row({ children, testid }) {
  return (
    <div className="p-3 rounded border bg-white/[0.02] flex items-center justify-between flex-wrap gap-2"
         style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={testid}>{children}</div>
  );
}
function RowMain({ icon: Icon, children }) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="text-cyan-400 mt-0.5" size={16} />
      <div>{children}</div>
    </div>
  );
}
function Empty({ msg }) { return <div className="text-slate-500 text-sm italic py-4 text-center">{msg}</div>; }
function StatusPill({ status }) {
  const s = (status || "").toLowerCase();
  const palette =
    s === "delivered" || s === "paid" ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" :
    s === "in_transit" || s === "tendered" || s === "booked" ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/30" :
    s === "open" || s === "issued" ? "bg-amber-500/15 text-amber-300 border-amber-500/30" :
    s === "cancelled" || s === "expired" ? "bg-red-500/15 text-red-300 border-red-500/30" :
    "bg-slate-500/15 text-slate-300 border-slate-500/30";
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${palette}`}>
      {status || "—"}
    </span>
  );
}
