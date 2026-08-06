import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Card } from "../ui/card";
import { Inbox, CheckCircle2, X, ExternalLink } from "lucide-react";

const STATUS_STYLE = {
  new: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  converted: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  dismissed: "bg-slate-500/15 text-slate-400 border-slate-500/30",
};

export const TcBookings = ({ reloadAll }) => {
  const [rows, setRows] = useState([]);
  const load = useCallback(() => {
    api.get("/truck-cleaning/bookings").then(({ data }) => setRows(data.bookings || [])).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const convert = async (id) => {
    try {
      const { data } = await api.post(`/truck-cleaning/bookings/${id}/convert`);
      toast.success(`Converted — client + job ${data.job_id} created`);
      load();
      reloadAll && reloadAll();
    } catch (e) { toast.error(e?.response?.data?.detail || "Convert failed"); }
  };
  const dismiss = async (id) => {
    try { await api.post(`/truck-cleaning/bookings/${id}/dismiss`); load(); } catch { toast.error("Dismiss failed"); }
  };

  return (
    <Card className="p-4 bg-slate-950/70 border-white/10" data-testid="tc-bookings">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Inbox size={15} className="text-cyan-300" /> Booking Requests from the public page
          {rows.filter((r) => r.status === "new").length > 0 &&
            <span className="px-2 py-0.5 rounded-full bg-amber-500 text-black text-[10px] font-black">{rows.filter((r) => r.status === "new").length} NEW</span>}
        </h3>
        <a href="/wash" target="_blank" rel="noreferrer" className="text-[10px] font-mono text-cyan-300 flex items-center gap-1" data-testid="tc-bookings-page-link">
          view booking page <ExternalLink size={10} />
        </a>
      </div>
      <div className="space-y-2 max-h-[480px] overflow-y-auto">
        {rows.map((b) => (
          <div key={b.booking_id} className="p-3 rounded-xl border border-white/10 bg-white/[0.02]" data-testid={`tc-booking-${b.booking_id}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm text-white font-semibold">{b.company} <span className="text-slate-500 font-normal">· {b.cabs} cab{b.cabs > 1 ? "s" : ""}</span></div>
                <div className="text-[10px] font-mono text-slate-500">
                  {b.contact && `${b.contact} · `}{b.phone}{b.email ? ` · ${b.email}` : ""}{b.preferred_date ? ` · wants ${b.preferred_date}` : ""}
                </div>
                {b.services?.length > 0 && <div className="text-[10px] text-cyan-300 mt-0.5">add-ons: {b.services.join(", ")}</div>}
                {b.notes && <div className="text-[10px] text-slate-500 mt-0.5">{b.notes}</div>}
              </div>
              <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono uppercase shrink-0 ${STATUS_STYLE[b.status]}`}>{b.status}</span>
            </div>
            {b.status === "new" && (
              <div className="flex gap-2 mt-2">
                <button onClick={() => convert(b.booking_id)} data-testid={`tc-booking-convert-${b.booking_id}`}
                  className="px-3 py-1.5 rounded-full bg-emerald-500 text-black text-[10px] font-black flex items-center gap-1">
                  <CheckCircle2 size={11} /> CONVERT TO CLIENT + JOB
                </button>
                <button onClick={() => dismiss(b.booking_id)} data-testid={`tc-booking-dismiss-${b.booking_id}`}
                  className="px-3 py-1.5 rounded-full border border-white/15 text-slate-400 text-[10px] font-bold flex items-center gap-1">
                  <X size={11} /> Dismiss
                </button>
              </div>
            )}
          </div>
        ))}
        {!rows.length && <div className="py-8 text-center text-slate-500 text-sm">No booking requests yet — share <b>/wash</b> with clients and watch this inbox fill up.</div>}
      </div>
    </Card>
  );
};
