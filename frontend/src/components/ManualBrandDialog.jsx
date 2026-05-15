import React, { useEffect, useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "./ui/dialog";
import { Hammer, X, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * ManualBrandDialog — "Build Your Own" custom-company template.
 * Lets the admin manually type a complete brand profile (no LLM needed) and
 * activate it, OR seed a blank shell to be filled later via ERP sync.
 */
export default function ManualBrandDialog({ onActivated }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(null);

  // Pull blank template on first open
  useEffect(() => {
    if (!open || form) return;
    api.get("/branding/template").then(({ data }) => {
      setForm({
        ...data,
        sample_products: data.sample_products.join("\n"),
        sample_suppliers: data.sample_suppliers.join("\n"),
        sample_lanes: data.sample_lanes.join("\n"),
        facilities: data.facilities.map((f) => `${f.name || ""}|${f.city || ""}`).join("\n"),
      });
    }).catch(() => {
      setForm({
        company_name: "", short_name: "", tagline: "", industry: "", headquarters: "",
        primary_color: "#00E5FF", secondary_color: "#06B6D4", accent_color: "#10B981",
        logo_letter: "", catalog_label: "Product Catalog",
        sample_products: "", sample_suppliers: "", sample_lanes: "", facilities: "",
      });
    });
  }, [open, form]);

  const reset = () => setForm(null);

  const submit = async (activate) => {
    if (!form?.company_name?.trim()) { toast.error("Company name is required"); return; }
    setBusy(true);
    const t = toast.loading(`${activate ? "Activating" : "Saving"} ${form.company_name}…`);
    try {
      const payload = {
        company_name: form.company_name.trim(),
        short_name: form.short_name?.trim() || undefined,
        tagline: form.tagline,
        industry: form.industry,
        headquarters: form.headquarters,
        primary_color: form.primary_color,
        secondary_color: form.secondary_color,
        accent_color: form.accent_color,
        logo_letter: form.logo_letter?.trim() || undefined,
        catalog_label: form.catalog_label,
        sample_products: (form.sample_products || "").split("\n").map(s => s.trim()).filter(Boolean),
        sample_suppliers: (form.sample_suppliers || "").split("\n").map(s => s.trim()).filter(Boolean),
        sample_lanes: (form.sample_lanes || "").split("\n").map(s => s.trim()).filter(Boolean),
        facilities: (form.facilities || "").split("\n").map((line) => {
          const [name, city] = line.split("|").map(p => (p || "").trim());
          if (!name && !city) return null;
          return { name: name || city, city: city || name };
        }).filter(Boolean),
        activate,
      };
      const { data } = await api.post("/branding/manual", payload);
      toast.success(`${data.brand.short_name} ${activate ? "active" : "saved"}`, { id: t });
      setOpen(false);
      reset();
      onActivated && onActivated();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed", { id: t });
    } finally { setBusy(false); }
  };

  if (!form && open) {
    return (
      <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
        <DialogContent className="max-w-4xl bg-[#0B0E14] border-white/10">
          <DialogHeader>
            <DialogTitle>Loading template…</DialogTitle>
          </DialogHeader>
          <div className="py-10 text-center text-slate-400"><Loader2 className="inline animate-spin" /></div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          data-testid="brand-build-your-own-btn"
          className="border-cyan-500/40 hover:bg-cyan-500/10 hover:text-cyan-200 text-cyan-300 shrink-0"
        >
          <Hammer size={13} className="mr-1.5" /> Build Your Own
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-4xl bg-[#0B0E14] border-white/10 max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-lg flex items-center gap-2">
            <Hammer size={16} className="text-cyan-400" /> Build Your Own Company Theme
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Manually fill any brand template — no AI needed. Or save a blank shell
            now and connect an ERP later to auto-populate the data.
            <span className="block mt-1 text-cyan-300/80">Tip: leave fields blank to use defaults.</span>
          </DialogDescription>
        </DialogHeader>
        {form && (
          <div className="grid grid-cols-12 gap-3">
            {/* Identity row */}
            <div className="col-span-12 md:col-span-6">
              <Field label="Company Name *">
                <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="Acme Logistics Inc." data-testid="manual-company-name" />
              </Field>
            </div>
            <div className="col-span-6 md:col-span-3">
              <Field label="Short Name">
                <Input value={form.short_name} onChange={(e) => setForm({ ...form, short_name: e.target.value })} placeholder="Acme" />
              </Field>
            </div>
            <div className="col-span-6 md:col-span-3">
              <Field label="Logo Letter">
                <Input value={form.logo_letter} maxLength={1} onChange={(e) => setForm({ ...form, logo_letter: e.target.value.toUpperCase() })} placeholder="A" />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-6">
              <Field label="Tagline">
                <Input value={form.tagline} onChange={(e) => setForm({ ...form, tagline: e.target.value })} placeholder="Moving the world's industrial goods" />
              </Field>
            </div>
            <div className="col-span-6 md:col-span-3">
              <Field label="Industry">
                <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} placeholder="Logistics" />
              </Field>
            </div>
            <div className="col-span-6 md:col-span-3">
              <Field label="Headquarters">
                <Input value={form.headquarters} onChange={(e) => setForm({ ...form, headquarters: e.target.value })} placeholder="Phoenix, AZ" />
              </Field>
            </div>

            {/* Colors */}
            <div className="col-span-12 md:col-span-4">
              <Field label="Primary Color">
                <ColorRow value={form.primary_color} onChange={(v) => setForm({ ...form, primary_color: v })} />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-4">
              <Field label="Secondary Color">
                <ColorRow value={form.secondary_color} onChange={(v) => setForm({ ...form, secondary_color: v })} />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-4">
              <Field label="Accent Color">
                <ColorRow value={form.accent_color} onChange={(v) => setForm({ ...form, accent_color: v })} />
              </Field>
            </div>

            {/* Lists */}
            <div className="col-span-12 md:col-span-6">
              <Field label="Sample Products (one per line · max 8)">
                <Textarea rows={5} value={form.sample_products} onChange={(e) => setForm({ ...form, sample_products: e.target.value })} placeholder="Acme Drone X1&#10;Acme Robot Sorter&#10;…" data-testid="manual-products" />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-6">
              <Field label="Sample Suppliers (one per line · max 8)">
                <Textarea rows={5} value={form.sample_suppliers} onChange={(e) => setForm({ ...form, sample_suppliers: e.target.value })} placeholder="Yazaki Wiring&#10;BattCo Industries&#10;…" />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-6">
              <Field label="Transportation Lanes (one per line · 'Origin -> Destination')">
                <Textarea rows={5} value={form.sample_lanes} onChange={(e) => setForm({ ...form, sample_lanes: e.target.value })} placeholder="Phoenix, AZ -> Atlanta, GA&#10;Long Beach, CA -> Shanghai, CN" />
              </Field>
            </div>
            <div className="col-span-12 md:col-span-6">
              <Field label="Facilities (one per line · 'Facility Name | City, ST')">
                <Textarea rows={5} value={form.facilities} onChange={(e) => setForm({ ...form, facilities: e.target.value })} placeholder="Acme HQ | Phoenix, AZ&#10;East DC | Atlanta, GA&#10;West DC | Los Angeles, CA" data-testid="manual-facilities" />
              </Field>
            </div>
          </div>
        )}
        <DialogFooter className="flex-wrap gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)} data-testid="manual-cancel">
            <X size={14} className="mr-1.5" /> Cancel
          </Button>
          <Button onClick={() => submit(false)} disabled={busy} variant="outline" className="border-white/10" data-testid="manual-save-only">
            Save (Don't Activate)
          </Button>
          <Button onClick={() => submit(true)} disabled={busy} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="manual-save-activate">
            {busy ? <><Loader2 size={14} className="mr-1.5 animate-spin" /> Working…</> : "Save & Activate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1.5 block">{label}</Label>
      {children}
    </div>
  );
}

function ColorRow({ value, onChange }) {
  return (
    <div className="flex gap-2 items-center">
      <input type="color" value={value} onChange={(e) => onChange(e.target.value)} className="w-10 h-9 rounded border border-white/10 cursor-pointer bg-transparent" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} className="flex-1 font-mono text-xs" />
    </div>
  );
}
