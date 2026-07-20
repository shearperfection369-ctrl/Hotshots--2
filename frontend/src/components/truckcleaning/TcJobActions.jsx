import React, { useEffect, useRef, useState } from "react";
import { Card } from "../ui/card";
import { BellRing, Camera, Trash2, Link2, Mail, Loader2, ImagePlus, Palette } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");

export const TcJobActions = ({ job, reload }) => {
  const [proofOpen, setProofOpen] = useState(false);
  const [reminding, setReminding] = useState(false);

  const remind = async () => {
    setReminding(true);
    try {
      const { data } = await api.post(`/truck-cleaning/jobs/${job.job_id}/remind`);
      if (data.status === "sent") toast.success(`SMS sent to ${data.to}`);
      else if (data.status === "queued") toast.info("Reminder queued — add Twilio keys in Connections to send for real");
      else if (data.status === "failed") toast.error("SMS failed — check your Twilio keys in Connections · Keys");
      else toast.error(data.note || `Reminder ${data.status}`);
      reload();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setReminding(false); }
  };

  const scentLink = async () => {
    try {
      const { data } = await api.post(`/truck-cleaning/jobs/${job.job_id}/scent-card`);
      const url = `${window.location.origin}${data.link_path}`;
      navigator.clipboard?.writeText(url).then(() => toast.success("Scent card link copied — text it to the driver")).catch(() => toast.info(url));
    } catch (e2) { toast.error(errTxt(e2)); }
  };

  return (
    <div className="flex gap-2 items-center">
      {job.status === "scheduled" && (
        <button onClick={remind} disabled={reminding} title="Send SMS reminder w/ one-tap reschedule"
                data-testid={`tc-job-remind-${job.job_id}`} className="text-cyan-300 hover:text-cyan-200 disabled:opacity-50">
          {reminding ? <Loader2 size={14} className="animate-spin" /> : <BellRing size={14} />}
        </button>
      )}
      <button onClick={() => setProofOpen(true)} title="Before/after photo proof"
              data-testid={`tc-job-proof-${job.job_id}`} className="text-amber-400 hover:text-amber-300">
        <Camera size={14} />
      </button>
      <button onClick={scentLink} title="Copy driver scent card link"
              data-testid={`tc-job-scent-${job.job_id}`} className="text-rose-400 hover:text-rose-300">
        <Palette size={14} />
      </button>
      {job.reminder_status && <span className="text-[9px] font-mono text-slate-600 uppercase">SMS {job.reminder_status}</span>}
      {proofOpen && <ProofDialog job={job} onClose={() => setProofOpen(false)} />}
    </div>
  );
};

function ProofDialog({ job, onClose }) {
  const [photos, setPhotos] = useState([]);
  const [proofToken, setProofToken] = useState(null);
  const [busy, setBusy] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const beforeRef = useRef(null);
  const afterRef = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.get(`/truck-cleaning/jobs/${job.job_id}/photos`);
      setPhotos(data.photos); setProofToken(data.proof_token);
    } catch (_) {}
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const upload = async (kind, ref) => {
    const file = ref.current?.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file); fd.append("kind", kind);
    setBusy(true);
    try {
      const { data } = await api.post(`/truck-cleaning/jobs/${job.job_id}/photos`, fd);
      setProofToken(data.proof_token);
      toast.success(`${kind} photo added`);
      ref.current.value = ""; load();
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  const del = async (pid) => {
    try { await api.delete(`/truck-cleaning/photos/${pid}`); load(); } catch (e2) { toast.error(errTxt(e2)); }
  };

  const copyLink = () => {
    const url = `${window.location.origin}/tc/proof/${proofToken}`;
    navigator.clipboard?.writeText(url).then(() => toast.success("Proof gallery link copied")).catch(() => toast.info(url));
  };

  const send = async () => {
    setBusy(true);
    try {
      await api.post(`/truck-cleaning/jobs/${job.job_id}/proof/send`, { to_email: emailTo, message: "" });
      toast.success("Proof email sent to client");
    } catch (e2) { toast.error(errTxt(e2)); }
    finally { setBusy(false); }
  };

  const thumb = (p) => `${api.defaults.baseURL}/truck-cleaning/proof/${proofToken}/photo/${p.photo_id}`;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 grid place-items-center p-4" onClick={onClose}>
      <Card className="w-full max-w-lg p-5 bg-slate-950 border-amber-500/30" onClick={(e) => e.stopPropagation()} data-testid="tc-proof-dialog">
        <div className="font-black text-white mb-0.5 flex items-center gap-2"><Camera size={16} className="text-amber-400" /> Photo Proof · {job.job_id}</div>
        <p className="text-[11px] text-slate-500 mb-4">{job.company} · {job.date} · snap before/after on your phone, then send the gallery to the client.</p>
        <div className="grid grid-cols-2 gap-3 mb-4">
          {[["before", beforeRef], ["after", afterRef]].map(([kind, ref]) => (
            <label key={kind} className="cursor-pointer p-3 rounded-xl border border-dashed border-white/20 hover:border-amber-400/60 text-center transition" data-testid={`tc-proof-add-${kind}`}>
              <input type="file" accept="image/*" capture="environment" ref={ref} className="hidden"
                     onChange={() => upload(kind, ref)} />
              <ImagePlus size={18} className="mx-auto text-amber-400 mb-1" />
              <div className="text-[11px] font-mono uppercase text-slate-300">Add {kind}</div>
            </label>
          ))}
        </div>
        {busy && <div className="text-[11px] text-slate-500 font-mono flex items-center gap-1.5 mb-2"><Loader2 size={12} className="animate-spin" /> processing…</div>}
        {photos.length > 0 && (
          <div className="grid grid-cols-4 gap-2 mb-4" data-testid="tc-proof-grid">
            {photos.map((p) => (
              <div key={p.photo_id} className="relative group">
                <img src={thumb(p)} alt={p.kind} className="h-20 w-full object-cover rounded-lg border border-white/10" />
                <span className={`absolute bottom-1 left-1 text-[8px] font-mono px-1 rounded uppercase ${p.kind === "before" ? "bg-slate-800 text-slate-300" : "bg-emerald-600 text-white"}`}>{p.kind}</span>
                <button onClick={() => del(p.photo_id)} className="absolute top-1 right-1 hidden group-hover:grid h-5 w-5 place-items-center rounded-full bg-black/70 text-red-400"><Trash2 size={11} /></button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-center">
          <button onClick={copyLink} disabled={!proofToken || photos.length === 0} data-testid="tc-proof-copy-link"
                  className="px-3.5 py-2 rounded-full border border-cyan-500/50 text-cyan-300 text-[11px] font-bold inline-flex items-center gap-1.5 disabled:opacity-40"><Link2 size={12} /> Copy Gallery Link</button>
          <input value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="client@fleet.com"
                 data-testid="tc-proof-email-input" className="flex-1 h-9 rounded-lg bg-slate-900 border border-white/15 px-2.5 text-xs outline-none focus:border-amber-400" />
          <button onClick={send} disabled={busy || !emailTo || photos.length === 0} data-testid="tc-proof-email-send"
                  className="px-3.5 py-2 rounded-full bg-amber-500 text-black text-[11px] font-bold inline-flex items-center gap-1.5 disabled:opacity-40"><Mail size={12} /> Send</button>
        </div>
      </Card>
    </div>
  );
}
