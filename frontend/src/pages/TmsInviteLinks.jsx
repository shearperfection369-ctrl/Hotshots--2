import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import Topbar from "@/components/Topbar";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Copy, Mail, Trash2, ExternalLink, Eye, Stamp, Clock,
  CheckCircle2, AlertTriangle, BarChart3, Link as LinkIcon,
} from "lucide-react";

/**
 * /investor-invite-links — Admin page for one-time-link gate.
 *
 * Workflow:
 *   1. Type a VC firm name → click "Generate Link"
 *   2. Copy the share URL (auto-personalized + audit-logged per visit)
 *   3. Send it via DM / email
 *   4. Watch the per-link visit log fill in (page views, downloads, IPs)
 */
export default function TmsInviteLinks() {
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    firm_name: "", contact_name: "", contact_email: "", note: "",
    max_visits: "", days_valid: "",
  });
  const [creating, setCreating] = useState(false);

  const fetchLinks = async () => {
    try {
      const { data } = await api.get("/investor/invite-links");
      setLinks(data.items || []);
    } catch (e) { toast.error("Failed to load invite links"); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchLinks(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.firm_name.trim()) { toast.error("Firm name is required"); return; }
    setCreating(true);
    try {
      const payload = {
        firm_name: form.firm_name.trim(),
        contact_name: form.contact_name.trim() || null,
        contact_email: form.contact_email.trim() || null,
        note: form.note.trim() || null,
        max_visits: form.max_visits ? parseInt(form.max_visits, 10) : null,
        days_valid: form.days_valid ? parseInt(form.days_valid, 10) : null,
      };
      const { data } = await api.post("/investor/invite-links", payload);
      toast.success(`Generated invite link for ${data.firm_name}`);
      try { await navigator.clipboard.writeText(data.share_url); toast.success("Share URL copied to clipboard"); } catch { /* noop */ }
      setForm({ firm_name: "", contact_name: "", contact_email: "", note: "", max_visits: "", days_valid: "" });
      fetchLinks();
    } catch (e) { toast.error(e?.response?.data?.detail || "Create failed"); }
    finally { setCreating(false); }
  };

  const copyLink = async (url) => {
    try { await navigator.clipboard.writeText(url); toast.success("Share URL copied"); }
    catch { toast.error("Clipboard blocked — long-press the URL to copy"); }
  };

  const disableLink = async (token) => {
    if (!window.confirm("Disable this invite link? The VC will see an 'expired' message next time they open it.")) return;
    try {
      await api.post(`/investor/invite-links/${token}/disable`);
      toast.success("Link disabled");
      fetchLinks();
    } catch { toast.error("Disable failed"); }
  };

  const deleteLink = async (token) => {
    if (!window.confirm("Delete this invite link? This cannot be undone.")) return;
    try {
      await api.delete(`/investor/invite-links/${token}`);
      toast.success("Link deleted");
      fetchLinks();
    } catch { toast.error("Delete failed"); }
  };

  const totalVisits = links.reduce((sum, l) => sum + (l.visit_count || 0), 0);
  const totalDownloads = links.reduce(
    (s, l) => s + (l.download_counts?.deck || 0) + (l.download_counts?.["one-pager"] || 0) + (l.download_counts?.zip || 0),
    0,
  );

  return (
    <>
      <Topbar title="Investor Invite Links" />
      <div className="p-6 max-w-7xl mx-auto space-y-6">

        {/* HEADER + STATS */}
        <Card className="hud-surface p-6" data-testid="invite-links-header">
          <div className="flex items-start justify-between flex-wrap gap-5">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">
                Hot Shot TMS · One-time-link Gate
              </div>
              <h1 className="font-display text-3xl font-black mt-1">Investor Invite Links</h1>
              <p className="text-sm text-slate-400 mt-2 max-w-2xl leading-relaxed">
                Generate a unique, watermarked URL per VC firm. Every visit and download is
                logged with IP, user-agent, and timestamp. First-visit / first-download triggers
                a real-time Resend alert to oliver@livecleans.com.
              </p>
            </div>
            <div className="flex gap-3">
              <Stat v={links.length} k="Active links" />
              <Stat v={totalVisits} k="Total visits" />
              <Stat v={totalDownloads} k="PDFs delivered" />
            </div>
          </div>
        </Card>

        {/* GENERATE FORM */}
        <Card className="hud-surface p-6" data-testid="invite-links-form-card">
          <h2 className="font-display text-xl font-bold mb-1">Generate a new invite link</h2>
          <p className="text-xs text-slate-400 mb-5">Firm name is the only required field. Leave caps empty for unlimited / no expiry.</p>
          <form onSubmit={handleCreate} className="space-y-3" data-testid="invite-links-form">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <FormField label="VC firm name *" value={form.firm_name} testId="form-firm-name"
                onChange={(v) => setForm({ ...form, firm_name: v })} required />
              <FormField label="Contact / GP name (optional)" value={form.contact_name} testId="form-contact-name"
                onChange={(v) => setForm({ ...form, contact_name: v })} />
              <FormField label="Contact email (optional)" value={form.contact_email} type="email" testId="form-contact-email"
                onChange={(v) => setForm({ ...form, contact_email: v })} />
              <FormField label="Internal note (optional)" value={form.note} testId="form-note"
                onChange={(v) => setForm({ ...form, note: v })} placeholder="how / who introduced" />
              <FormField label="Max visits (optional)" value={form.max_visits} type="number" testId="form-max-visits"
                onChange={(v) => setForm({ ...form, max_visits: v })} placeholder="leave empty for unlimited" />
              <FormField label="Days valid (optional)" value={form.days_valid} type="number" testId="form-days-valid"
                onChange={(v) => setForm({ ...form, days_valid: v })} placeholder="leave empty for no expiry" />
            </div>
            <Button type="submit" disabled={creating}
                    className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold"
                    data-testid="form-create-button">
              {creating ? "Generating…" : (<><LinkIcon size={14} className="mr-2" /> Generate Invite Link & Copy URL</>)}
            </Button>
          </form>
        </Card>

        {/* LINKS TABLE */}
        <Card className="hud-surface p-6" data-testid="invite-links-table-card">
          <h2 className="font-display text-xl font-bold mb-4">Active & expired links · {links.length}</h2>
          {loading ? (
            <div className="text-slate-400 text-sm">Loading…</div>
          ) : links.length === 0 ? (
            <div className="text-slate-400 text-sm italic py-8 text-center" data-testid="invite-links-empty">
              No invite links yet. Generate your first one above.
            </div>
          ) : (
            <div className="space-y-3" data-testid="invite-links-list">
              {links.map((l) => <LinkCard key={l.token} link={l} onCopy={copyLink} onDisable={disableLink} onDelete={deleteLink} />)}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}

function Stat({ v, k }) {
  return (
    <div className="text-center p-3 rounded-lg border border-cyan-500/20 bg-cyan-500/5 min-w-[100px]">
      <div className="font-display text-3xl font-black text-cyan-300 tabular-nums">{v}</div>
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-400 mt-0.5">{k}</div>
    </div>
  );
}

function FormField({ label, value, onChange, type = "text", required = false, placeholder, testId }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-[0.15em] text-slate-400 mb-1.5 block">
        {label}
      </Label>
      <Input type={type} value={value} required={required}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        className="bg-[#0B1320] border-white/10 text-white" />
    </div>
  );
}

function LinkCard({ link, onCopy, onDisable, onDelete }) {
  const isDisabled = link.status === "disabled";
  const isExpired = link.expires_at && new Date(link.expires_at) < new Date();
  const isCapHit = link.max_visits && link.visit_count >= link.max_visits;
  const isLive = !isDisabled && !isExpired && !isCapHit;
  const downloads = link.download_counts || {};
  return (
    <div className="p-4 rounded-lg border bg-white/[0.02]"
         style={{ borderColor: isLive ? "rgba(34,211,238,0.25)" : "rgba(255,255,255,0.08)" }}
         data-testid={`link-card-${link.token}`}>
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div className="flex-1 min-w-[200px]">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-display text-xl font-bold">{link.firm_name}</span>
            {link.contact_name && <span className="text-slate-400 text-sm">· {link.contact_name}</span>}
            {isLive && (
              <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                <CheckCircle2 size={9} className="inline mr-1" />LIVE
              </span>
            )}
            {isDisabled && (
              <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-300 border border-slate-500/30">DISABLED</span>
            )}
            {isExpired && !isDisabled && (
              <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                <Clock size={9} className="inline mr-1" />EXPIRED
              </span>
            )}
            {isCapHit && !isDisabled && !isExpired && (
              <span className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">CAP HIT</span>
            )}
          </div>
          {link.note && <div className="text-xs text-slate-500 mb-2 italic">{link.note}</div>}
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <code className="text-[11px] font-mono px-2 py-1 rounded bg-black/40 text-cyan-300 truncate max-w-[450px]">
              {link.share_url}
            </code>
            <Button size="sm" variant="ghost" onClick={() => onCopy(link.share_url)} className="h-7 px-2 text-xs"
                    data-testid={`copy-${link.token}`}>
              <Copy size={12} className="mr-1" /> Copy
            </Button>
            <a href={link.share_url} target="_blank" rel="noopener noreferrer"
               className="inline-flex items-center text-xs text-cyan-300 hover:text-cyan-200 px-2 py-1">
              <ExternalLink size={12} className="mr-1" /> Open
            </a>
          </div>
        </div>
        <div className="flex gap-1.5">
          {isLive && (
            <Button size="sm" variant="ghost" onClick={() => onDisable(link.token)}
                    className="h-8 px-2 text-amber-400 hover:bg-amber-500/10"
                    data-testid={`disable-${link.token}`}>
              <AlertTriangle size={12} className="mr-1" /> Disable
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => onDelete(link.token)}
                  className="h-8 px-2 text-red-400 hover:bg-red-500/10"
                  data-testid={`delete-${link.token}`}>
            <Trash2 size={12} className="mr-1" /> Delete
          </Button>
        </div>
      </div>

      {/* Visit stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-4 pt-3 border-t border-white/5">
        <MiniStat icon={Eye} v={link.visit_count} k="Visits" />
        <MiniStat icon={BarChart3} v={link.unique_ip_count || 0} k="Unique IPs" />
        <MiniStat icon={Stamp} v={downloads.deck || 0} k="Deck" />
        <MiniStat icon={Stamp} v={downloads["one-pager"] || 0} k="One-Pager" />
        <MiniStat icon={Stamp} v={downloads.zip || 0} k="ZIP" />
        <MiniStat icon={Clock} v={link.last_visit_at ? new Date(link.last_visit_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" }) : "—"} k="Last visit" small />
      </div>

      {/* Per-visit details */}
      {link.visit_count > 0 && (
        <details className="mt-3" data-testid={`visits-detail-${link.token}`}>
          <summary className="text-[10px] font-mono uppercase tracking-wider text-slate-400 cursor-pointer hover:text-cyan-300">
            Show {link.visit_count} visit{link.visit_count === 1 ? "" : "s"}
          </summary>
        </details>
      )}
    </div>
  );
}

function MiniStat({ icon: Icon, v, k, small }) {
  return (
    <div className="text-center">
      <div className={`flex items-center justify-center gap-1 text-cyan-300 ${small ? "text-xs font-mono" : "font-display text-xl font-black"}`}>
        <Icon size={11} className="text-slate-500" /> {v}
      </div>
      <div className="text-[9px] font-mono uppercase tracking-wider text-slate-500 mt-0.5">{k}</div>
    </div>
  );
}
