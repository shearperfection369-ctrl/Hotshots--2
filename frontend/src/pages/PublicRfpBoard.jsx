/* eslint-disable */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Trophy, MapPin, Calendar, ArrowRight } from "lucide-react";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

/** Public, no-auth RFP board where carriers/brokers can see open RFPs and bid. */
export default function PublicRfpBoard() {
  const [rfps, setRfps] = useState([]);
  const [activeRfp, setActiveRfp] = useState(null);

  useEffect(() => {
    axios.get(`${REACT_APP_BACKEND_URL}/api/public/rfps`)
      .then((r) => setRfps(r.data.items || []))
      .catch(() => setRfps([]));
  }, []);

  return (
    <div className="min-h-screen bg-[#0B1118] text-white">
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <Card className="hud-surface p-6">
          <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
            Orisei Freight Solutions · Public RFP Board
          </div>
          <h1 className="font-display text-3xl font-black mt-1 flex items-center gap-3">
            <Trophy className="text-amber-400" size={28}/> Active Lane RFPs
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Carriers — submit competitive bids on the lanes below. No registration
            required. Awarded contracts run 6–12 months with weekly committed volume.
          </p>
        </Card>

        {rfps.length === 0 ? (
          <Card className="hud-surface p-6 text-center">
            <div className="text-slate-400">No open RFPs at this time.</div>
          </Card>
        ) : (
          <div className="space-y-3">
            {rfps.map((r) => (
              <Card key={r.rfp_id} className="hud-surface p-5" data-testid={`public-rfp-${r.rfp_id}`}>
                <div className="flex items-start justify-between flex-wrap gap-2">
                  <div className="flex-1">
                    <div className="font-bold text-lg">{r.title}</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">
                      {r.rfp_id} · {r.shipper_name}
                    </div>
                    {r.description && <div className="text-sm text-slate-400 mt-2">{r.description}</div>}
                    <div className="flex flex-wrap gap-4 mt-3 text-xs">
                      <span className="text-slate-500 font-mono">
                        <Calendar size={11} className="inline mr-1"/> Deadline · {r.submission_deadline}
                      </span>
                      <span className="text-slate-500 font-mono">
                        <MapPin size={11} className="inline mr-1"/> {r.lanes?.length} lanes
                      </span>
                      <span className="text-cyan-300 font-mono">{r.bid_count} bids submitted</span>
                    </div>
                    <div className="mt-3 space-y-1">
                      {(r.lanes || []).slice(0, 5).map((L, i) => (
                        <div key={i} className="text-xs font-mono text-slate-400">
                          → {L.origin} → {L.destination} · {L.equipment} · ~{L.est_volume_per_week}/wk
                        </div>
                      ))}
                    </div>
                  </div>
                  <Button onClick={() => setActiveRfp(r)} className="bg-cyan-500 hover:bg-cyan-400 text-black"
                    data-testid={`bid-${r.rfp_id}`}>
                    Submit bid <ArrowRight size={14} className="ml-2"/>
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {activeRfp && <BidDialog rfp={activeRfp} onClose={() => setActiveRfp(null)} />}

        <div className="text-center text-xs text-slate-500 font-mono py-6">
          Orisei Freight Solutions LLC · oliver@oriseifreightsolutions.com
        </div>
      </div>
    </div>
  );
}

function BidDialog({ rfp, onClose }) {
  const [bidder_name, setBidderName] = useState("");
  const [bidder_email, setBidderEmail] = useState("");
  const [bidder_mc, setBidderMc] = useState("");
  const [notes, setNotes] = useState("");
  const [rates, setRates] = useState(rfp.lanes.map(() => ""));
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async () => {
    if (!bidder_name) return alert("Name required");
    if (rates.some((r) => !r)) return alert("Enter a rate for every lane");
    setSubmitting(true);
    try {
      await axios.post(`${REACT_APP_BACKEND_URL}/api/public/rfps/${rfp.rfp_id}/bid`, {
        bidder_name, bidder_email: bidder_email || undefined,
        bidder_mc: bidder_mc || undefined, notes: notes || undefined,
        lane_rates: rates.map((r, i) => ({ lane_index: i, rate_per_load: parseFloat(r) })),
      });
      setDone(true);
    } catch (e) {
      alert(e?.response?.data?.detail || "Bid failed");
    } finally { setSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
         onClick={onClose} data-testid="bid-dialog">
      <Card className="hud-surface p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}>
        {done ? (
          <div className="text-center py-8">
            <div className="text-emerald-300 font-bold text-2xl mb-2">Bid received</div>
            <div className="text-sm text-slate-400">We'll be in touch within 5 business days.</div>
            <Button onClick={onClose} className="mt-6 bg-cyan-500 text-black">Close</Button>
          </div>
        ) : (
          <>
            <div className="font-bold text-lg mb-1">Submit bid · {rfp.title}</div>
            <div className="text-xs text-slate-500 mb-4">Deadline · {rfp.submission_deadline}</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Name *</Label>
                <Input value={bidder_name} onChange={(e)=>setBidderName(e.target.value)} data-testid="bid-name"
                       className="bg-[#0B1320] border-white/10"/>
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Email</Label>
                <Input type="email" value={bidder_email} onChange={(e)=>setBidderEmail(e.target.value)} data-testid="bid-email"
                       className="bg-[#0B1320] border-white/10"/>
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">MC #</Label>
                <Input value={bidder_mc} onChange={(e)=>setBidderMc(e.target.value)} data-testid="bid-mc"
                       className="bg-[#0B1320] border-white/10"/>
              </div>
            </div>
            <div className="text-xs font-mono uppercase tracking-[0.15em] text-slate-400 mb-2">Per-lane rate (USD per load)</div>
            <div className="space-y-2 mb-4">
              {rfp.lanes.map((L, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="flex-1 text-sm">{L.origin} → {L.destination} <span className="text-slate-500 text-xs">({L.equipment})</span></div>
                  <Input type="number" value={rates[i]} onChange={(e) => {
                    const r = [...rates]; r[i] = e.target.value; setRates(r);
                  }} placeholder="$/load" className="bg-[#0B1320] border-white/10 w-32" data-testid={`bid-rate-${i}`}/>
                </div>
              ))}
            </div>
            <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">Notes</Label>
            <Textarea value={notes} onChange={(e)=>setNotes(e.target.value)} data-testid="bid-notes"
                      className="bg-[#0B1320] border-white/10 mb-4" rows={3}/>
            <div className="flex gap-2">
              <Button onClick={submit} disabled={submitting} className="bg-cyan-500 hover:bg-cyan-400 text-black flex-1"
                      data-testid="bid-submit">
                {submitting ? "Submitting…" : "Submit bid"}
              </Button>
              <Button onClick={onClose} variant="outline" className="border-white/10">Cancel</Button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
