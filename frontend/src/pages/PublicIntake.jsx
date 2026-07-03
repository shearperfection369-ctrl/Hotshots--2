/**
 * /i/:token — Public shipper intake page.
 *
 * The shipper receives a token URL, clicks it (no login), and fills out
 * the branded intake form. Submission creates a pending_review booking
 * in the broker's Workflow inbox.
 */
import React, { useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, AlertCircle, Ship, ArrowRight } from "lucide-react";
import { toast, Toaster } from "sonner";

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function PublicIntake() {
  const token = window.location.pathname.split("/i/")[1];
  const [phase, setPhase] = useState("loading"); // loading | ready | already | expired | not_found | submitted
  const [meta, setMeta] = useState(null);
  const [confirmedBookedId, setConfirmedBookedId] = useState(null);
  const [form, setForm] = useState({
    shipper_name: "", shipper_contact_name: "", shipper_email: "", shipper_phone: "",
    origin_address: "", destination_address: "",
    pickup_date: "", pickup_window_start: "", pickup_window_end: "",
    delivery_date: "", delivery_window_start: "", delivery_window_end: "",
    commodity: "", weight_lbs: "", pieces: "",
    equipment_required: "Dry Van", hazmat: false, un_number: "", hazmat_class: "",
    pickup_special_instructions: "", delivery_special_instructions: "", references: "",
  });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    if (!token) { setPhase("not_found"); return; }
    axios.get(`${BACKEND}/api/intake/public/${token}`)
      .then(({ data }) => {
        if (data.status === "already_submitted") { setPhase("already"); setMeta(data); return; }
        setMeta(data);
        // Prefill from meta if provided by broker
        setForm((f) => ({
          ...f,
          shipper_name: data.shipper_name || "",
          shipper_contact_name: data.shipper_contact_name || "",
          shipper_email: data.shipper_email || "",
          origin_address: data.prefill?.origin || "",
          destination_address: data.prefill?.destination || "",
          commodity: data.prefill?.commodity || "",
          equipment_required: data.prefill?.equipment || "Dry Van",
          pickup_date: data.prefill?.pickup_date || "",
          delivery_date: data.prefill?.delivery_date || "",
        }));
        setPhase("ready");
      })
      .catch((e) => {
        if (e?.response?.status === 410) { setPhase("expired"); return; }
        setPhase("not_found");
      });
  }, [token]);

  const submit = async () => {
    if (!form.shipper_name.trim() || !form.origin_address.trim() || !form.destination_address.trim()
        || !form.pickup_date || !form.commodity.trim()) {
      toast.error("Shipper name, origin, destination, pickup date, and commodity are required");
      return;
    }
    try {
      const payload = { ...form,
        weight_lbs: form.weight_lbs ? Number(form.weight_lbs) : null,
        pieces: form.pieces ? Number(form.pieces) : null };
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      const { data } = await axios.post(`${BACKEND}/api/intake/public/${token}/submit`, payload);
      setConfirmedBookedId(data.booked_id);
      setPhase("submitted");
    } catch (e) {
      console.error(e);
      toast.error(e?.response?.data?.detail || "Submission failed — please retry");
    }
  };

  const brand = meta?.brand || {};
  const brandBg = `linear-gradient(135deg, ${brand.primary_color || "#0E3A6B"} 0%, ${brand.accent_color || "#C9A24A"} 100%)`;

  if (phase === "loading") {
    return <div className="min-h-screen bg-[#0A0E14] flex items-center justify-center text-slate-500">Loading…</div>;
  }
  if (phase === "not_found") {
    return (
      <div className="min-h-screen bg-[#0A0E14] flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <AlertCircle size={40} className="mx-auto text-red-400 mb-3" />
          <h1 className="text-white text-xl font-bold">Intake link not found</h1>
          <p className="text-slate-400 mt-2 text-sm">This link may have been deleted. Please contact your freight broker for a new one.</p>
        </div>
      </div>
    );
  }
  if (phase === "expired") {
    return (
      <div className="min-h-screen bg-[#0A0E14] flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <AlertCircle size={40} className="mx-auto text-amber-400 mb-3" />
          <h1 className="text-white text-xl font-bold">This intake link has expired</h1>
          <p className="text-slate-400 mt-2 text-sm">Please reply to your broker&apos;s email for a fresh link.</p>
        </div>
      </div>
    );
  }
  if (phase === "already") {
    return (
      <div className="min-h-screen bg-[#0A0E14] flex items-center justify-center p-6">
        <div className="text-center max-w-md">
          <CheckCircle2 size={40} className="mx-auto text-emerald-400 mb-3" />
          <h1 className="text-white text-xl font-bold">Already submitted</h1>
          <p className="text-slate-400 mt-2 text-sm">
            This intake form was submitted on {meta?.submitted_at?.slice(0, 16)?.replace("T", " ")}. Thank you.
          </p>
        </div>
      </div>
    );
  }
  if (phase === "submitted") {
    return (
      <div className="min-h-screen bg-[#0A0E14] flex items-center justify-center p-6">
        <Card className="bg-[#0F1421] border-emerald-500/40 max-w-md">
          <CardContent className="p-8 text-center">
            <CheckCircle2 size={48} className="mx-auto text-emerald-400 mb-3" />
            <h1 className="text-white text-xl font-bold">Received. Thank you.</h1>
            <p className="text-slate-400 mt-2 text-sm">
              Your freight request has been logged with {brand.company_name || "our team"}.
              A member of operations will confirm your carrier and rate within
              4 business hours.
            </p>
            {confirmedBookedId && (
              <div className="mt-4 font-mono text-[11px] text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 rounded px-3 py-2 inline-block">
                Booking ref: {confirmedBookedId}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0E14] text-slate-100">
      <Toaster position="top-right" richColors />
      {/* Branded hero */}
      <div className="w-full py-10 px-6" style={{ background: brandBg }}>
        <div className="max-w-3xl mx-auto flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-black/40 border-2 border-white/50 flex items-center justify-center text-white text-2xl font-black">
            {(brand.short_name || "O")[0]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] font-mono uppercase tracking-[0.18em] text-white/70">
              {brand.company_name || "Orisei Freight Solutions"}
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Shipper Intake · Freight Details
            </h1>
            <p className="text-white/80 text-sm mt-1">{brand.tagline || "Mission-control transportation"}</p>
          </div>
          <Ship size={40} className="text-white/40" />
        </div>
      </div>

      <div className="max-w-3xl mx-auto p-6 space-y-4">
        {meta?.note_to_shipper && (
          <Card className="bg-cyan-500/[0.06] border-cyan-500/30">
            <CardContent className="p-4 text-sm text-cyan-100">
              <div className="text-[10px] font-mono uppercase text-cyan-300 mb-1">Note from your broker</div>
              {meta.note_to_shipper}
            </CardContent>
          </Card>
        )}

        <Section title="Shipper Contact">
          <F l="Company / Shipper name *" v={form.shipper_name} on={(v) => set("shipper_name", v)} t="pub-shipper-name" />
          <F l="Primary contact" v={form.shipper_contact_name} on={(v) => set("shipper_contact_name", v)} t="pub-contact" />
          <F l="Email" type="email" v={form.shipper_email} on={(v) => set("shipper_email", v)} t="pub-email" />
          <F l="Phone" v={form.shipper_phone} on={(v) => set("shipper_phone", v)} t="pub-phone" />
        </Section>

        <Section title="Pickup (Origin)">
          <div className="col-span-2">
            <F l="Full origin address * (facility name, street, city, state, ZIP)"
              v={form.origin_address} on={(v) => set("origin_address", v)} t="pub-origin" />
          </div>
          <F l="Pickup date *" type="date" v={form.pickup_date} on={(v) => set("pickup_date", v)} t="pub-pickup-date" />
          <F l="Window start" type="time" v={form.pickup_window_start} on={(v) => set("pickup_window_start", v)} t="pub-pickup-start" />
          <F l="Window end" type="time" v={form.pickup_window_end} on={(v) => set("pickup_window_end", v)} t="pub-pickup-end" />
          <div className="col-span-2">
            <F l="Pickup special instructions" v={form.pickup_special_instructions}
              on={(v) => set("pickup_special_instructions", v)} t="pub-pickup-instr" />
          </div>
        </Section>

        <Section title="Delivery (Destination)">
          <div className="col-span-2">
            <F l="Full destination address * (facility name, street, city, state, ZIP)"
              v={form.destination_address} on={(v) => set("destination_address", v)} t="pub-dest" />
          </div>
          <F l="Delivery date" type="date" v={form.delivery_date} on={(v) => set("delivery_date", v)} t="pub-delivery-date" />
          <F l="Window start" type="time" v={form.delivery_window_start} on={(v) => set("delivery_window_start", v)} t="pub-delivery-start" />
          <F l="Window end" type="time" v={form.delivery_window_end} on={(v) => set("delivery_window_end", v)} t="pub-delivery-end" />
          <div className="col-span-2">
            <F l="Delivery special instructions" v={form.delivery_special_instructions}
              on={(v) => set("delivery_special_instructions", v)} t="pub-delivery-instr" />
          </div>
        </Section>

        <Section title="Freight Details">
          <div className="col-span-2">
            <F l="Commodity *" v={form.commodity} on={(v) => set("commodity", v)} t="pub-commodity" />
          </div>
          <F l="Total weight (lbs)" type="number" v={form.weight_lbs} on={(v) => set("weight_lbs", v)} t="pub-weight" />
          <F l="Piece / pallet count" type="number" v={form.pieces} on={(v) => set("pieces", v)} t="pub-pieces" />
          <div>
            <Label className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 block">Equipment</Label>
            <Select value={form.equipment_required} onValueChange={(v) => set("equipment_required", v)}>
              <SelectTrigger className="bg-[#0B1320] border-white/10" data-testid="pub-equipment">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-[#0B0E14] border-cyan-500/30">
                {["Dry Van", "Reefer", "Flatbed", "Step Deck", "Conestoga", "Power Only", "Box Truck", "Sprinter Van", "LTL", "Container (20'/40'/40'HC)"].map((e) => (
                  <SelectItem key={e} value={e}>{e}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <F l="References / PO#" v={form.references} on={(v) => set("references", v)} t="pub-refs" />
          <div className="col-span-2 flex items-center gap-2">
            <input type="checkbox" id="hazmat" checked={form.hazmat}
              onChange={(e) => set("hazmat", e.target.checked)} data-testid="pub-hazmat" />
            <Label htmlFor="hazmat" className="text-sm cursor-pointer">Hazardous materials?</Label>
          </div>
          {form.hazmat && (
            <>
              <F l="UN number" v={form.un_number} on={(v) => set("un_number", v)} t="pub-un" />
              <F l="Hazmat class" v={form.hazmat_class} on={(v) => set("hazmat_class", v)} t="pub-hazclass" />
            </>
          )}
        </Section>

        <div className="pt-3 flex justify-end">
          <Button onClick={submit}
            className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-base px-8 py-6"
            data-testid="pub-submit">
            Submit Freight Request
            <ArrowRight size={16} className="ml-2" />
          </Button>
        </div>

        <div className="text-center text-[10px] text-slate-600 pt-3 pb-6 font-mono">
          Powered by {brand.company_name || "Orisei Freight Solutions"}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <Card className="bg-[#0F1421] border-white/5">
      <CardContent className="p-4">
        <h2 className="font-bold text-cyan-200 mb-3 text-sm font-mono uppercase tracking-wider">
          {title}
        </h2>
        <div className="grid grid-cols-2 gap-3">{children}</div>
      </CardContent>
    </Card>
  );
}

function F({ l, v, on, type = "text", t }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase text-slate-400 mb-1.5 block">{l}</Label>
      <Input type={type} value={v} onChange={(e) => on(e.target.value)}
        className="bg-[#0B1320] border-white/10 text-white" data-testid={t} />
    </div>
  );
}
