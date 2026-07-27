import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Loader2, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TcProofPublic() {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [zoom, setZoom] = useState(null);

  useEffect(() => {
    axios.get(`${API}/truck-cleaning/proof/${token}`)
      .then(({ data: d }) => { setData(d); setState("ready"); })
      .catch(() => setState("invalid"));
  }, [token]);

  const url = (p) => `${API}/truck-cleaning/proof/${token}/photo/${p.photo_id}`;
  const before = (data?.photos || []).filter((p) => p.kind === "before");
  const after = (data?.photos || []).filter((p) => p.kind === "after");

  const Section = ({ title, items, accent }) => (
    <div className="mb-6">
      <div className="text-[11px] font-mono uppercase tracking-[0.25em] mb-2" style={{ color: accent }}>{title}</div>
      <div className="grid grid-cols-2 gap-3">
        {items.map((p) => (
          <button key={p.photo_id} onClick={() => setZoom(url(p))} className="group relative overflow-hidden rounded-xl border border-white/10">
            <img src={url(p)} alt={p.kind} className="w-full h-44 object-cover group-hover:scale-[1.03] transition-transform duration-300" />
            {p.caption && <div className="absolute bottom-0 inset-x-0 bg-black/60 text-[10px] text-slate-300 px-2 py-1">{p.caption}</div>}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#0D1117] text-white relative">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div style={{ position: "absolute", top: -120, right: "5%", width: 480, height: 480, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(245,158,11,0.26), transparent 65%)" }} />
        <div style={{ position: "absolute", bottom: -140, left: -80, width: 500, height: 500, borderRadius: 9999, filter: "blur(52px)", background: "radial-gradient(circle, rgba(34,211,238,0.22), transparent 65%)" }} />
      </div>
      <div className="relative max-w-xl mx-auto px-5 py-12">
        <div className="flex items-center gap-3 mb-8">
          <img src="/tc-logo.png" alt="Orisei Truck Cleaning" className="h-16 w-auto drop-shadow-[0_0_18px_rgba(59,130,246,0.55)]" />
          <div>
            <div className="font-black text-lg leading-tight">ORISEI <span className="text-amber-400">TRUCK CLEANING</span></div>
            <div className="text-[11px] text-slate-500 font-mono">Photo proof gallery</div>
          </div>
        </div>

        {state === "loading" && <div className="text-slate-500 font-mono text-sm flex gap-2 items-center"><Loader2 size={14} className="animate-spin" /> Loading gallery…</div>}
        {state === "invalid" && <div className="p-6 rounded-2xl border border-red-500/30 bg-red-500/5 text-sm" data-testid="tcpr-invalid">Gallery not found. Contact oliver@oriseifreightsolutions.com.</div>}

        {state === "ready" && data && (
          <div className="rounded-2xl border border-white/10 bg-slate-950/85 backdrop-blur p-6" data-testid="tcpr-gallery">
            <div className="flex items-center gap-2 mb-1"><Sparkles size={15} className="text-amber-400" /><span className="font-black">{data.company}</span></div>
            <div className="text-xs text-slate-500 mb-5">{data.date} · {data.cabs} cab{data.cabs !== 1 ? "s" : ""} · 45-minute showroom spec</div>
            {before.length > 0 && <Section title="Before" items={before} accent="#94A3B8" />}
            {after.length > 0 && <Section title="After — showroom clean" items={after} accent="#34D399" />}
            {data.photos.length === 0 && <div className="text-slate-600 text-xs font-mono">Photos are being uploaded — check back shortly.</div>}
          </div>
        )}
        <div className="text-center text-[10px] text-slate-600 font-mono mt-8">Orisei Truck Cleaning Solutions · every job ships with time-stamped proof · (763) 443-4459</div>
      </div>
      {zoom && (
        <div className="fixed inset-0 z-50 bg-black/85 grid place-items-center p-4" onClick={() => setZoom(null)}>
          <img src={zoom} alt="zoom" className="max-h-[88vh] max-w-full rounded-xl" />
        </div>
      )}
    </div>
  );
}
