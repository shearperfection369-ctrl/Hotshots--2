import React, { useEffect, useState } from "react";
import { useBranding } from "../lib/branding";
import { useAuth } from "../lib/auth";
import Topbar from "../components/Topbar";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Truck, Phone, Mail, ExternalLink, Shield, Award, Activity, Plus, Edit2, Trash2, X } from "lucide-react";
import { toast } from "sonner";

/**
 * SpecialtyCarriers · profile pages for the active company's white-glove,
 * expedite, cross-border, and capacity-assurance carriers. Built-in carriers
 * (Logix, ArcBest Panther, Fastfrate, Ryan) can be edited or hidden via the
 * admin-only Edit/Delete buttons. New carriers can be added inline.
 */

const DEFAULT_FORM = {
  name: "", type: "Specialty", description: "", coverage: "",
  website: "", phone: "", primary_contact: "", primary_email: "", notes: "",
};

function Initials({ initials, color }) {
  return (
    <div
      className="w-14 h-14 rounded-xl flex items-center justify-center font-display text-xl font-bold shrink-0"
      style={{ background: (color || "#22D3EE") + "22", border: `1px solid ${(color || "#22D3EE")}66`, color: color || "#22D3EE" }}
    >
      {initials}
    </div>
  );
}

function Stat({ label, value, accent = "text-cyan-300" }) {
  return (
    <div className="p-2 rounded bg-white/[0.02] border border-white/5">
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-sm font-display font-bold tabular-nums ${accent} mt-0.5`}>{value}</div>
    </div>
  );
}

function CarrierCard({ c, canEdit, onEdit, onDelete }) {
  const [tracking, setTracking] = useState("");
  const initials = (c.initials || c.name || "?").slice(0, 2).toUpperCase();
  const color = c.color || "#22D3EE";
  const services = c.specialty || c.services || [];
  const ytdLoads = c.ytd_loads ?? "—";
  const otp = c.on_time_pct ?? "—";
  const claim = c.claim_rate_pct ?? "—";

  const openTracking = () => {
    if (!c.website) { toast.error("No website on file for this carrier"); return; }
    const popup = window.open(c.website, "_blank", "noopener,noreferrer");
    if (popup && tracking) {
      // Some carriers accept ?tracking=, fallback is to just open their site.
      try { popup.location.href = c.website + (c.website.includes("?") ? "&" : "?") + "tracking=" + encodeURIComponent(tracking); } catch (e) { /* cross-origin */ }
    }
  };

  return (
    <Card className="hud-surface p-5 relative group" data-testid={`specialty-card-${c.id}`}>
      {canEdit && (
        <div className="absolute top-3 right-3 flex items-center gap-1 opacity-60 group-hover:opacity-100 transition">
          <button onClick={() => onEdit(c)} data-testid={`specialty-edit-${c.id}`} title="Edit"
                  className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-cyan-500/10">
            <Edit2 size={12} />
          </button>
          <button onClick={() => onDelete(c)} data-testid={`specialty-delete-${c.id}`} title="Delete"
                  className="p-1 rounded text-slate-400 hover:text-red-400 hover:bg-red-500/10">
            <Trash2 size={12} />
          </button>
        </div>
      )}
      <div className="flex items-start gap-4">
        <Initials initials={initials} color={color} />
        <div className="flex-1 min-w-0 pr-12">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-display text-lg font-bold text-white truncate">{c.name}</h3>
            {c.priority && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border"
                    style={{ background: color + "1A", color, borderColor: color + "55" }}>{c.priority}</span>
            )}
            {!c.is_seed && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border border-emerald-500/40 bg-emerald-500/10 text-emerald-300">Custom</span>
            )}
          </div>
          {c.tagline && <div className="text-[11px] font-mono mt-0.5" style={{ color }}>{c.tagline}</div>}
          <p className="text-sm text-slate-300 mt-2 leading-relaxed">{c.summary || c.description || ""}</p>
        </div>
      </div>

      {services.length > 0 && (
        <div className="mt-4">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5">Specialty Services</div>
          <div className="flex flex-wrap gap-1.5">
            {services.map((s) => (
              <span key={s} className="px-2 py-0.5 rounded text-[10px] font-mono bg-white/[0.04] text-slate-200 border border-white/10">{s}</span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-4">
        <Stat label="YTD Loads" value={typeof ytdLoads === "number" ? ytdLoads.toLocaleString() : ytdLoads} />
        <Stat label="On-Time %" value={typeof otp === "number" ? `${otp}%` : otp} accent="text-emerald-300" />
        <Stat label="Claim Rate" value={typeof claim === "number" ? `${claim}%` : claim} accent="text-yellow-300" />
        <Stat label="Partner Since" value={c.since || "—"} accent="text-slate-300" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
        <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1">
            <Phone size={9} /> Contact
          </div>
          {(c.contact?.name || c.primary_contact) && <div className="text-xs font-mono text-cyan-200">{c.contact?.name || c.primary_contact}</div>}
          {(c.contact?.phone || c.phone) && (
            <div className="text-xs font-mono text-slate-300 flex items-center gap-1 mt-0.5">
              <Phone size={10} /> <a href={`tel:${c.contact?.phone || c.phone}`} className="hover:text-cyan-300">{c.contact?.phone || c.phone}</a>
            </div>
          )}
          {(c.contact?.email || c.primary_email) && (
            <div className="text-xs font-mono text-slate-300 flex items-center gap-1 mt-0.5">
              <Mail size={10} /> <a href={`mailto:${c.contact?.email || c.primary_email}`} className="hover:text-cyan-300 truncate">{c.contact?.email || c.primary_email}</a>
            </div>
          )}
          {c.website && (
            <a href={c.website} target="_blank" rel="noreferrer" data-testid={`specialty-website-${c.id}`}
               className="mt-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-cyan-300 hover:text-cyan-200">
              Open carrier portal <ExternalLink size={9} />
            </a>
          )}
        </div>
        <div className="p-3 rounded border border-white/5 bg-white/[0.02]">
          <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mb-1.5 flex items-center gap-1">
            <Activity size={9} /> Direct Tracking
          </div>
          <div className="flex items-center gap-1.5">
            <Input value={tracking} onChange={(e) => setTracking(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && openTracking()}
                   placeholder="Tracking / PRO / Probill"
                   data-testid={`specialty-tracking-input-${c.id}`}
                   className="flex-1 bg-[#11151F] border-white/10 text-xs font-mono" />
            <Button onClick={openTracking} data-testid={`specialty-tracking-go-${c.id}`}
                    className="text-black font-bold" style={{ background: color }}>Track →</Button>
          </div>
        </div>
      </div>

      {c.notes && <div className="mt-3 text-[11px] text-slate-400 leading-relaxed">{c.notes}</div>}
    </Card>
  );
}

export default function SpecialtyCarriers() {
  const { brand } = useBranding();
  const { user } = useAuth();
  const shortName = brand?.short_name || "Tennant";
  const canEdit = user?.role === "admin" || user?.role === "dispatcher";
  const [carriers, setCarriers] = useState([]);
  const [editing, setEditing] = useState(null);  // null=closed, "new"|carrier id when open
  const [form, setForm] = useState(DEFAULT_FORM);

  const load = () => api.get("/specialty-carriers").then((r) => setCarriers(r.data.carriers || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setForm(DEFAULT_FORM); setEditing("new"); };
  const openEdit = (c) => {
    setForm({
      name: c.name || "",
      type: c.type || "Specialty",
      description: c.summary || c.description || "",
      coverage: c.coverage || (Array.isArray(c.lanes) ? c.lanes.join(", ") : ""),
      website: c.website || "",
      phone: c.contact?.phone || c.phone || "",
      primary_contact: c.contact?.name || c.primary_contact || "",
      primary_email: c.contact?.email || c.primary_email || "",
      services: (c.specialty || c.services || []).join(", "),
      notes: c.notes || "",
    });
    setEditing(c.id);
  };

  const save = async () => {
    if (!form.name.trim()) { toast.error("Name is required"); return; }
    const services = typeof form.services === "string"
      ? form.services.split(",").map((s) => s.trim()).filter(Boolean)
      : form.services || [];
    const payload = { ...form, services };
    try {
      if (editing === "new") {
        await api.post("/specialty-carriers", payload);
        toast.success("Carrier added");
      } else {
        await api.put(`/specialty-carriers/${editing}`, payload);
        toast.success("Carrier updated");
      }
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (c) => {
    if (!window.confirm(`${c.is_seed ? "Hide" : "Delete"} "${c.name}"?`)) return;
    try {
      await api.delete(`/specialty-carriers/${c.id}`);
      toast.success(c.is_seed ? "Carrier hidden" : "Carrier deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <>
      <Topbar title="Specialty Carriers" subtitle="White-glove · Expedite · Cross-border · Capacity Assurance" />
      <div className="p-4 md:p-6 space-y-5" data-testid="specialty-carriers-page">
        <Card className="hud-surface p-4 flex items-center gap-3 flex-wrap">
          <Award size={20} className="text-cyan-400" />
          <div className="flex-1 min-w-[260px]">
            <h2 className="font-display text-lg font-bold text-white">{shortName}&rsquo;s priority-use &amp; special-handling roster</h2>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              These carriers operate outside the standard rate-shop flow. Use them when freight requires
              white-glove pad-wrap protection, expedited time-critical pickup, cross-border CA ↔ US specialty,
              or surge capacity beyond the contracted fleet.
            </p>
          </div>
          {canEdit && (
            <Button onClick={openNew} data-testid="specialty-add-btn"
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              <Plus size={13} className="mr-1" /> Add Carrier
            </Button>
          )}
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {carriers.map((c) => (
            <CarrierCard key={c.id} c={c} canEdit={canEdit} onEdit={openEdit} onDelete={remove} />
          ))}
          {carriers.length === 0 && (
            <Card className="hud-surface p-8 text-center text-slate-500 xl:col-span-2">
              No specialty carriers configured. {canEdit && <span className="text-cyan-300">Add the first one above.</span>}
            </Card>
          )}
        </div>
      </div>

      <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="bg-[#0B0E14] border-cyan-500/20 max-w-2xl" data-testid="specialty-dialog">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Truck size={14} className="text-cyan-400" /> {editing === "new" ? "Add Specialty Carrier" : "Edit Specialty Carrier"}
            </DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Field label="Carrier Name *" v={form.name} k="name" s={setForm} f={form} />
            <Field label="Type" v={form.type} k="type" s={setForm} f={form} placeholder="Expedite · White-glove · Cross-border · Capacity" />
            <Field label="Website" v={form.website} k="website" s={setForm} f={form} placeholder="https://" />
            <Field label="Coverage" v={form.coverage} k="coverage" s={setForm} f={form} placeholder="North America · Cross-border CA·US" />
            <Field label="Phone" v={form.phone} k="phone" s={setForm} f={form} />
            <Field label="Primary Contact" v={form.primary_contact} k="primary_contact" s={setForm} f={form} />
            <Field label="Contact Email" v={form.primary_email} k="primary_email" s={setForm} f={form} className="md:col-span-2" />
            <Field label="Services (comma-separated)" v={form.services} k="services" s={setForm} f={form} className="md:col-span-2" placeholder="Pad-wrap, Air, Team drivers" />
            <Field label="Description" v={form.description} k="description" s={setForm} f={form} className="md:col-span-2" />
            <Field label="Notes" v={form.notes} k="notes" s={setForm} f={form} className="md:col-span-2" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)} className="border-white/10 text-slate-300">Cancel</Button>
            <Button onClick={save} data-testid="specialty-save-btn"
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold">
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function Field({ label, v, k, s, f, placeholder, className = "" }) {
  return (
    <div className={className}>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</Label>
      <Input value={v ?? ""} onChange={(e) => s({ ...f, [k]: e.target.value })}
             placeholder={placeholder} data-testid={`specialty-field-${k}`}
             className="bg-[#11151F] border-white/10 mt-1" />
    </div>
  );
}
