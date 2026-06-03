import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Package, FileText, DollarSign, Truck, CheckCircle2, Clock,
  AlertCircle, Building2, MapPin,
} from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/** Public, token-gated customer self-service portal.
 *  URL: /customer-portal?token=XXX  — issued from /orisei-operations.
 */
export default function CustomerPortal() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token") || "";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError("Missing portal token. Please use the link your Orisei contact sent you.");
      setLoading(false);
      return;
    }
    axios
      .get(`${REACT_APP_BACKEND_URL}/api/public/customer-portal/${token}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || "Unable to load portal."))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <Shell><div className="text-slate-400 text-sm">Loading your portal…</div></Shell>
    );
  }
  if (error) {
    return (
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
  }

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
          {data.customer?.primary_contact_name && (
            <> · Contact · {data.customer.primary_contact_name}</>
          )}
        </div>
      </Card>

      {/* Summary stat tiles */}
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

      <Section title="Your shipments" testid="portal-bookings">
        {(data.bookings || []).length === 0 ? (
          <Empty msg="No shipments on file yet." />
        ) : (
          <div className="space-y-2">
            {data.bookings.map((b) => (
              <Row key={b.booking_id} testid={`portal-booking-${b.booking_id}`}>
                <RowMain icon={Package}>
                  <div className="font-bold">{b.origin || "—"} → {b.destination || "—"}</div>
                  <div className="text-xs text-slate-500 font-mono mt-0.5">
                    {b.booking_id}
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

      <Section title="Invoices" testid="portal-invoices">
        {(data.invoices || []).length === 0 ? (
          <Empty msg="No invoices issued yet." />
        ) : (
          <div className="space-y-2">
            {data.invoices.map((inv) => (
              <Row key={inv.invoice_id} testid={`portal-invoice-${inv.invoice_id}`}>
                <RowMain icon={DollarSign}>
                  <div className="font-bold">
                    ${Number(inv.amount_usd || 0).toLocaleString()}
                  </div>
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

      <Section title="Quotes" testid="portal-quotes">
        {(data.quotes || []).length === 0 ? (
          <Empty msg="No quotes on file." />
        ) : (
          <div className="space-y-2">
            {data.quotes.map((q) => (
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

      <div className="text-center text-xs text-slate-500 font-mono py-6">
        Orisei Freight Solutions LLC · Plymouth, MN ·
        shearperfection369@gmail.com
      </div>
    </Shell>
  );
}

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
        <div className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400">
          {label}
        </div>
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
         style={{ borderColor: "rgba(255,255,255,0.06)" }} data-testid={testid}>
      {children}
    </div>
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

function Empty({ msg }) {
  return <div className="text-slate-500 text-sm italic py-4 text-center">{msg}</div>;
}

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
