import React, { useCallback, useEffect, useState } from "react";
import { Card } from "../ui/card";
import { UserPlus, Link2, Copy, Check, X, FileDown } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const errTxt = (e) => (typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Something went wrong");
const STATUS_STYLE = {
  invited: "border-cyan-500/40 text-cyan-300",
  submitted: "border-amber-500/50 text-amber-300",
  approved: "border-emerald-500/50 text-emerald-400",
  rejected: "border-red-500/40 text-red-400",
};

export const TcOnboarding = ({ reloadAll }) => {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({ company: "", contact: "", email: "" });
  const [copied, setCopied] = useState("");

  const load = useCallback(async () => {
    try { const { data } = await api.get("/truck-cleaning/onboarding"); setRows(data.onboardings); } catch (_) {}
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/truck-cleaning/onboarding", form);
      toast.success("Onboarding link created");
      setForm({ company: "", contact: "", email: "" });
      load();
      copyLink(data.onboarding.token, data.onboarding.onboard_id);
    } catch (e2) { toast.error(errTxt(e2)); }
  };

  const copyLink = (token, id) => {
    const url = `${window.location.origin}/tc/onboard/${token}`;
    navigator.clipboard?.writeText(url).then(() => {
      setCopied(id); toast.success("Link copied — send it to your client");
      setTimeout(() => setCopied(""), 2500);
    }).catch(() => toast.info(url));
  };

  const act = async (id, action) => {
    try {
      await api.post(`/truck-cleaning/onboarding/${id}/${action}`);
      toast.success(action === "approve" ? "Client approved & added to CRM" : "Onboarding rejected");
      load(); if (action === "approve") reloadAll();
    } catch (e2) { toast.error(errTxt(e2)); }
  };

  const packet = async (id) => {
    try {
      const r = await api.get(`/truck-cleaning/onboarding/${id}/welcome-packet.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `Orisei_Welcome_Packet_${id}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch (_) { toast.error("Packet generation failed"); }
  };

  return (
    <div className="space-y-4" data-testid="tc-onboarding">
      <form onSubmit={create} className="p-4 rounded-xl border border-white/10 bg-slate-950/70 flex flex-wrap gap-2 items-center" data-testid="tc-onboarding-form">
        <UserPlus className="text-amber-400" size={18} />
        <span className="text-xs text-slate-400 font-mono mr-1">NEW ONBOARDING LINK</span>
        {[["company", "Company (optional prefill)"], ["contact", "Contact"], ["email", "Email"]].map(([k, ph]) => (
          <input key={k} value={form[k]} placeholder={ph} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                 data-testid={`tc-onboarding-${k}-input`}
                 className="h-9 rounded-lg bg-slate-950 border border-white/15 px-2.5 text-xs flex-1 min-w-[150px] outline-none focus:border-amber-400" />
        ))}
        <button type="submit" data-testid="tc-onboarding-create-btn"
                className="h-9 px-4 rounded-full bg-amber-500 text-black font-bold text-xs inline-flex items-center gap-1.5"><Link2 size={13} /> Create Link</button>
      </form>
      <Card className="bg-slate-950/70 border-white/10 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-[10px] font-mono uppercase text-slate-500 border-b border-white/5">
            <th className="p-3">Prospect</th><th className="p-3">Fleet</th><th className="p-3">Plan</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={5} className="p-6 text-center text-slate-600 text-xs font-mono">Create a link above and send it to a fleet — submissions land here for your approval.</td></tr>}
            {rows.map((r) => (
              <tr key={r.onboard_id} className="border-b border-white/5" data-testid={`tc-onboarding-row-${r.onboard_id}`}>
                <td className="p-3">
                  <div className="font-semibold text-white text-xs">{r.company || <span className="text-slate-600 italic">awaiting client info</span>}</div>
                  <div className="text-[10px] text-slate-500">{r.contact} {r.email && `· ${r.email}`}</div>
                </td>
                <td className="p-3 text-xs tabular-nums text-slate-300">{r.status === "invited" ? "—" : `${r.cabs} cabs`}</td>
                <td className="p-3 text-[11px] text-cyan-300 font-mono">{r.status === "invited" ? "—" : r.plan?.replace("_", " ")}</td>
                <td className="p-3"><span className={`px-2 py-0.5 rounded-full border text-[10px] font-mono uppercase ${STATUS_STYLE[r.status] || ""}`}>{r.status}</span></td>
                <td className="p-3">
                  <div className="flex gap-2 items-center">
                    <button onClick={() => copyLink(r.token, r.onboard_id)} data-testid={`tc-onboarding-copy-${r.onboard_id}`}
                            title="Copy onboarding link" className="text-slate-400 hover:text-amber-300">
                      {copied === r.onboard_id ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    </button>
                    {r.status === "submitted" && (
                      <>
                        <button onClick={() => act(r.onboard_id, "approve")} data-testid={`tc-onboarding-approve-${r.onboard_id}`}
                                className="px-2.5 py-1 rounded-full border border-emerald-500/50 text-emerald-400 text-[10px] font-bold inline-flex items-center gap-1 hover:bg-emerald-500/10"><Check size={11} /> APPROVE</button>
                        <button onClick={() => act(r.onboard_id, "reject")} data-testid={`tc-onboarding-reject-${r.onboard_id}`}
                                className="px-2.5 py-1 rounded-full border border-red-500/40 text-red-400 text-[10px] font-bold inline-flex items-center gap-1 hover:bg-red-500/10"><X size={11} /> REJECT</button>
                      </>
                    )}
                    {(r.status === "approved" || r.status === "submitted") && (
                      <button onClick={() => packet(r.onboard_id)} data-testid={`tc-onboarding-packet-${r.onboard_id}`}
                              title="Download branded welcome packet" className="px-2.5 py-1 rounded-full border border-amber-500/50 text-amber-300 text-[10px] font-bold inline-flex items-center gap-1 hover:bg-amber-500/10"><FileDown size={11} /> PACKET</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};
