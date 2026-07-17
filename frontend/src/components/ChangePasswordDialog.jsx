import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { KeyRound, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

export default function ChangePasswordDialog({ open, onOpenChange }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (next !== confirm) { toast.error("New passwords do not match"); return; }
    if (next.length < 8) { toast.error("New password must be at least 8 characters"); return; }
    setBusy(true);
    try {
      const r = await api.post("/auth/change-password", { current_password: current, new_password: next });
      toast.success(r.data?.message || "Password updated");
      setCurrent(""); setNext(""); setConfirm("");
      onOpenChange(false);
    } catch (err) {
      const d = err.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Failed to change password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#0E1420] border-white/10 text-slate-100 sm:max-w-md" data-testid="change-password-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-300">
            <KeyRound size={16} /> Change password
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            Update your partner sign-in password. Your other sessions will be signed out.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <Input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)}
                 placeholder="Current password" data-testid="cp-current-input"
                 className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
          <Input type="password" required value={next} onChange={(e) => setNext(e.target.value)}
                 placeholder="New password (min 8 characters)" data-testid="cp-new-input"
                 className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
          <Input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                 placeholder="Confirm new password" data-testid="cp-confirm-input"
                 className="bg-white/[0.03] border-white/10 text-white placeholder:text-slate-600" />
          <Button type="submit" disabled={busy} data-testid="cp-submit-btn"
                  className="w-full bg-amber-500 hover:bg-amber-400 text-black font-semibold">
            {busy ? <Loader2 size={14} className="mr-2 animate-spin" /> : <KeyRound size={14} className="mr-2" />}
            Update password
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
