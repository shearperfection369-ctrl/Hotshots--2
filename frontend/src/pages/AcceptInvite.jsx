import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { TennantLogo } from "../components/TennantLogo";
import { Truck, ShieldCheck, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function AcceptInvite() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) setError("Missing invite token in the URL.");
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (!token || !email || !name) return;
    setSubmitting(true); setError("");
    try {
      const { data } = await api.post("/carrier-invites/accept", { token, email, name });
      // Persist session token
      document.cookie = `session_token=${data.session_token}; path=/; max-age=${7 * 24 * 60 * 60}; SameSite=None; Secure`;
      toast.success(`Welcome, ${data.carrier_company} portal access granted`);
      // Reload to get auth context to pick up the cookie
      window.location.href = "/shipments";
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to accept invite");
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center p-4">
      <Card className="hud-surface p-8 max-w-md w-full" data-testid="accept-invite-card">
        <div className="flex items-center gap-3 mb-6">
          <TennantLogo size="md" />
          <div>
            <div className="text-[10px] font-mono uppercase tracking-[0.25em] text-cyan-400">Tennant Companies</div>
            <div className="font-display text-lg font-bold text-white">Carrier Portal Access</div>
          </div>
        </div>

        <div className="flex items-start gap-2 mb-5 p-3 rounded bg-cyan-500/[0.05] border border-cyan-500/20">
          <ShieldCheck size={16} className="text-cyan-400 mt-0.5" />
          <div className="text-xs text-slate-300">
            You've been invited to a <span className="text-cyan-300 font-mono">scoped, read-mostly</span> portal. You'll only see shipments tendered to your carrier company.
          </div>
        </div>

        {error && (
          <div className="flex items-start gap-2 mb-4 p-3 rounded bg-red-500/[0.05] border border-red-500/30">
            <AlertTriangle size={14} className="text-red-400 mt-0.5" />
            <div className="text-xs text-red-300">{error}</div>
          </div>
        )}

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Your Name</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="John Driver" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-accept-name" />
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase tracking-wider text-cyan-400">Email</label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="dispatch@yourcarrier.com" className="mt-1 bg-[#0B0E14] border-white/10" data-testid="invite-accept-email" />
          </div>
          <Button type="submit" disabled={submitting || !token} className="w-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold mt-2" data-testid="invite-accept-submit">
            <Truck size={14} className="mr-2" /> {submitting ? "Granting access…" : "Accept & Enter Portal"}
          </Button>
        </form>
        <div className="text-[10px] font-mono text-slate-500 text-center mt-4">
          By accepting you agree to Tennant's carrier portal terms. Access can be revoked at any time.
        </div>
      </Card>
    </div>
  );
}
