import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { Trash2, AlertTriangle, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { toast } from "sonner";

export const DataWiperCard = () => {
  const [cats, setCats] = useState([]);
  const [selected, setSelected] = useState({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [wiping, setWiping] = useState(false);

  const load = () => api.get("/admin/wipe-categories").then(({ data }) => setCats(data.categories || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const picked = Object.keys(selected).filter((k) => selected[k]);
  const pickedRows = cats.filter((c) => selected[c.key]).reduce((a, c) => a + c.total, 0);

  const wipe = async () => {
    setWiping(true);
    try {
      const { data } = await api.post("/admin/wipe-data", { categories: picked, confirm: true });
      toast.success(`Wiped ${data.total_deleted.toLocaleString()} rows across ${picked.length} categories`);
      setConfirmOpen(false); setConfirmText(""); setSelected({});
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Wipe failed");
    } finally { setWiping(false); }
  };

  return (
    <Card className="hud-surface p-5 lg:col-span-6 border-red-500/20" data-testid="admin-section-data-wiper">
      <div className="flex items-center gap-2 mb-2">
        <Trash2 size={14} className="text-red-400" />
        <h3 className="font-display text-base font-bold text-white">Sample Data Wiper</h3>
      </div>
      <div className="text-[11px] text-slate-500 mb-4">
        Pick categories to permanently delete ALL rows (sample and real) in those collections — ideal for a clean pre-launch slate. This cannot be undone.
      </div>
      <div className="space-y-2">
        {cats.map((c) => (
          <label key={c.key} className="flex items-center justify-between p-2 rounded border border-white/10 bg-white/[0.02] cursor-pointer hover:border-red-500/30">
            <div className="flex items-center gap-2.5">
              <Checkbox checked={!!selected[c.key]} onCheckedChange={(v) => setSelected((s) => ({ ...s, [c.key]: !!v }))} data-testid={`wipe-cat-${c.key}`} />
              <span className="text-xs text-slate-200">{c.label}</span>
            </div>
            <span className="text-[10px] font-mono text-slate-500">{c.total.toLocaleString()} rows</span>
          </label>
        ))}
      </div>
      <Button onClick={() => setConfirmOpen(true)} disabled={!picked.length}
        className="w-full mt-4 bg-red-600 hover:bg-red-500 text-white font-bold" data-testid="wipe-data-open-btn">
        <Trash2 size={14} className="mr-1.5" /> Wipe {picked.length ? `${pickedRows.toLocaleString()} rows in ${picked.length} categor${picked.length > 1 ? "ies" : "y"}` : "selected data"}
      </Button>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="bg-slate-900 border-red-500/30" data-testid="wipe-confirm-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-300"><AlertTriangle size={16} /> Permanently delete data?</DialogTitle>
            <DialogDescription className="text-xs text-slate-400">
              You are about to delete <b className="text-red-300">{pickedRows.toLocaleString()} rows</b> across: {cats.filter((c) => selected[c.key]).map((c) => c.label).join(", ")}. Type <b className="text-white">WIPE</b> to confirm.
            </DialogDescription>
          </DialogHeader>
          <Input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} placeholder="Type WIPE" className="bg-[#11151F] border-white/10 font-mono" data-testid="wipe-confirm-input" />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button onClick={wipe} disabled={confirmText !== "WIPE" || wiping} className="bg-red-600 hover:bg-red-500 text-white font-bold" data-testid="wipe-confirm-btn">
              {wiping ? <Loader2 size={14} className="animate-spin mr-1.5" /> : <Trash2 size={14} className="mr-1.5" />} Delete forever
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default DataWiperCard;
