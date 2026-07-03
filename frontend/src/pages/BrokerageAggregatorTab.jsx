import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import {
  Truck, Layers, Pin, PinOff, Filter, RefreshCw, ShieldCheck, ShieldAlert,
  Snowflake, MapPin, DollarSign, Award, Radio, Clock, CheckCircle2, Loader2,
  Sparkles, FileText, PackageCheck,
} from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

/**
 * BrokerageAggregatorTab — high-tech unified feed across every configured
 * load board. Solves the "load-swap tab fatigue" problem: broker sees DAT,
 * Truckstop, Convoy, Uber Freight, 123Loadboard in ONE feed, scored + de-
 * duped + pinnable. Companion sub-view tracks board data-retention
 * compliance (attestation flow).
 */
const SORTS = [
  { id: "score",         label: "Best Match"   },
  { id: "rate_per_mile", label: "RPM ↑"        },
  { id: "rate_usd",      label: "Rate USD"     },
  { id: "posted_at",     label: "Freshness"    },
];

const EQUIPMENT = ["Van", "Reefer", "Flatbed", "Power Only", "Step Deck"];
const STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME",
  "MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
  "RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
];

export default function BrokerageAggregatorTab() {
  const navigate = useNavigate();
  const [view, setView] = useState("feed"); // feed | retention | prefs | pins
  const [boards, setBoards] = useState([]);
  const [feed, setFeed] = useState(null);
  const [busy, setBusy] = useState(false);
  const [activeBoards, setActiveBoards] = useState(new Set());
  const [bookingLoad, setBookingLoad] = useState(null);
  const [filters, setFilters] = useState({
    equipment: "",
    origin_state: "",
    dest_state: "",
    min_rate_per_mile: "",
    exclude_hazmat: false,
    sort_by: "score",
  });
  const [pins, setPins] = useState([]);

  const loadBoards = useCallback(async () => {
    try {
      const { data } = await api.get("/aggregator/boards");
      setBoards(data.items || []);
      // default: activate every board
      setActiveBoards((prev) =>
        prev.size ? prev : new Set((data.items || []).map((b) => b.id))
      );
    } catch (e) { /* no-op */ }
  }, []);

  const loadFeed = useCallback(async () => {
    setBusy(true);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== "" && v !== false && v !== null && v !== undefined) params.set(k, String(v));
      });
      if (activeBoards.size && boards.length && activeBoards.size < boards.length) {
        params.set("boards_csv", Array.from(activeBoards).join(","));
      }
      params.set("limit", "150");
      const { data } = await api.get(`/aggregator/feed?${params.toString()}`);
      setFeed(data);
    } catch (e) {
      toast.error("Feed failed to load");
    } finally {
      setBusy(false);
    }
  }, [filters, activeBoards, boards.length]);

  const loadPins = useCallback(async () => {
    try {
      const { data } = await api.get("/aggregator/pins");
      setPins(data.items || []);
    } catch (e) { /* no-op */ }
  }, []);

  useEffect(() => { loadBoards(); loadPins(); }, [loadBoards, loadPins]);
  useEffect(() => { if (boards.length) loadFeed(); }, [boards, loadFeed]);

  return (
    <div className="space-y-4" data-testid="aggregator-root">
      {/* Sub-view switch */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: "feed",      label: "Unified Feed", icon: Layers },
          { id: "pins",      label: `Pinned (${pins.length})`, icon: Pin },
          { id: "prefs",     label: "Preferences", icon: Filter },
          { id: "retention", label: "Retention Compliance", icon: ShieldCheck },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setView(id)}
            data-testid={`aggregator-view-${id}`}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded text-[11px] font-mono uppercase tracking-widest border transition ${
              view === id
                ? "bg-cyan-500/15 border-cyan-400 text-cyan-100 shadow-[0_0_18px_rgba(34,211,238,0.25)]"
                : "border-white/10 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-100"
            }`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={loadFeed} disabled={busy} data-testid="aggregator-refresh">
            {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} Refresh
          </Button>
        </div>
      </div>

      {view === "feed" && (
        <FeedView
          boards={boards}
          feed={feed}
          busy={busy}
          filters={filters}
          setFilters={setFilters}
          activeBoards={activeBoards}
          setActiveBoards={setActiveBoards}
          onPinChanged={loadPins}
          onBook={(row) => setBookingLoad(row)}
        />
      )}
      {view === "pins" && <PinsView pins={pins} onChange={loadPins} />}
      {view === "prefs" && <PrefsView onSaved={loadFeed} />}
      {view === "retention" && <RetentionView />}

      <BookLoadDialog
        load={bookingLoad}
        onClose={() => setBookingLoad(null)}
        onBooked={(booked) => {
          setBookingLoad(null);
          toast.success(`Booked · ${booked.booked_id} → routing to workflow`);
          navigate(`/workflow?booked_id=${encodeURIComponent(booked.booked_id)}`);
        }}
      />
    </div>
  );
}

// ============================================================
//                     FEED VIEW
// ============================================================
function FeedView({ boards, feed, busy, filters, setFilters, activeBoards, setActiveBoards, onPinChanged, onBook }) {
  const toggleBoard = (id) => {
    setActiveBoards((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };
  const boardById = useMemo(() => Object.fromEntries(boards.map((b) => [b.id, b])), [boards]);
  const items = feed?.items || [];

  return (
    <div className="space-y-4">
      {/* Board pills */}
      <Card className="p-3 bg-slate-900/60 border-white/10">
        <div className="flex items-center gap-2 mb-2">
          <Radio size={13} className="text-cyan-400" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            Live boards — {activeBoards.size}/{boards.length} active
          </span>
        </div>
        <div className="flex flex-wrap gap-2" data-testid="aggregator-board-pills">
          {boards.map((b) => {
            const on = activeBoards.has(b.id);
            return (
              <button
                key={b.id}
                onClick={() => toggleBoard(b.id)}
                data-testid={`aggregator-board-${b.id}`}
                style={on ? { boxShadow: `0 0 16px ${b.color}55`, borderColor: b.color, color: b.color } : {}}
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-mono uppercase tracking-wide border transition ${
                  on ? "bg-black/60" : "border-white/10 text-slate-500 hover:border-white/30"
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ background: on ? b.color : "#334155" }}
                />
                {b.name}
                {b.retention_months ? (
                  <span className="opacity-60 ml-1">· {b.retention_months}mo</span>
                ) : null}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-3 bg-slate-900/60 border-white/10">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
          <Field label="Equipment">
            <select
              value={filters.equipment}
              onChange={(e) => setFilters((f) => ({ ...f, equipment: e.target.value }))}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="aggregator-filter-equipment"
            >
              <option value="">Any</option>
              {EQUIPMENT.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
          </Field>
          <Field label="Origin state">
            <select
              value={filters.origin_state}
              onChange={(e) => setFilters((f) => ({ ...f, origin_state: e.target.value }))}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="aggregator-filter-origin-state"
            >
              <option value="">Any</option>
              {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Dest state">
            <select
              value={filters.dest_state}
              onChange={(e) => setFilters((f) => ({ ...f, dest_state: e.target.value }))}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="aggregator-filter-dest-state"
            >
              <option value="">Any</option>
              {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
          <Field label="Min RPM">
            <Input
              type="number"
              step="0.05"
              min="0"
              value={filters.min_rate_per_mile}
              onChange={(e) => setFilters((f) => ({ ...f, min_rate_per_mile: e.target.value }))}
              className="bg-black/40 border-white/10 h-8 text-xs"
              data-testid="aggregator-filter-min-rpm"
            />
          </Field>
          <Field label="Hazmat">
            <label className="flex items-center gap-2 pt-1.5 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={filters.exclude_hazmat}
                onChange={(e) => setFilters((f) => ({ ...f, exclude_hazmat: e.target.checked }))}
                data-testid="aggregator-filter-hazmat"
              />
              Exclude
            </label>
          </Field>
          <Field label="Sort">
            <select
              value={filters.sort_by}
              onChange={(e) => setFilters((f) => ({ ...f, sort_by: e.target.value }))}
              className="w-full bg-black/40 border border-white/10 rounded px-2 py-1.5 text-xs text-slate-100"
              data-testid="aggregator-filter-sort"
            >
              {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </Field>
        </div>
      </Card>

      {/* Feed table */}
      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 flex items-center justify-between border-b border-white/10">
          <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-300">
            <Layers size={12} className="inline mr-1" />
            {feed ? `${feed.total} matching loads · ${feed.boards_polled?.length || 0} boards polled` : "Loading…"}
          </span>
          <span className="text-[10px] font-mono text-slate-500">Cross-listed loads are merged (see &quot;also on&quot;)</span>
        </div>
        {busy && !items.length && (
          <div className="p-8 text-center text-xs text-slate-500">
            <Loader2 size={16} className="animate-spin inline mr-2" /> Polling every board…
          </div>
        )}
        {!busy && !items.length && (
          <div className="p-8 text-center text-xs text-slate-500">No loads match your filters. Loosen and refresh.</div>
        )}
        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="aggregator-feed-table">
              <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
                <tr>
                  <th className="px-3 py-2 text-left">Board</th>
                  <th className="px-3 py-2 text-left">Lane</th>
                  <th className="px-3 py-2 text-left">Equipment</th>
                  <th className="px-3 py-2 text-right">Rate</th>
                  <th className="px-3 py-2 text-right">RPM</th>
                  <th className="px-3 py-2 text-right">Miles</th>
                  <th className="px-3 py-2 text-left">Fresh</th>
                  <th className="px-3 py-2 text-left">Match</th>
                  <th className="px-3 py-2 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((r, i) => (
                  <LoadRow key={`${r.load_id}-${i}`} row={r} board={boardById[r.board_id]} onPin={onPinChanged} onBook={onBook} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function LoadRow({ row, board, onPin, onBook }) {
  const [pinning, setPinning] = useState(false);
  const pin = async () => {
    setPinning(true);
    try {
      await api.post("/aggregator/pin", { load_id: row.load_id, board_id: row.board_id });
      toast.success(`Pinned ${row.load_id}`);
      onPin?.();
    } catch (e) {
      toast.error("Pin failed");
    } finally {
      setPinning(false);
    }
  };
  const scoreColor = row.score >= 75 ? "#10B981" : row.score >= 50 ? "#F59E0B" : "#EF4444";
  const fresh = row.posted_minutes_ago == null ? "—" : row.posted_minutes_ago < 60
    ? `${row.posted_minutes_ago}m` : `${Math.round(row.posted_minutes_ago / 60)}h`;
  return (
    <tr className="border-t border-white/5 hover:bg-white/[0.02]" data-testid={`aggregator-row-${row.load_id}`}>
      <td className="px-3 py-2">
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-mono uppercase"
          style={{ borderColor: `${board?.color || "#0EA5E9"}66`, color: board?.color || "#0EA5E9" }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: board?.color || "#0EA5E9" }} />
          {board?.name || row.board_id}
        </span>
        {row.also_on?.length ? (
          <div className="text-[9px] text-slate-500 mt-1">also on: {row.also_on.join(", ")}</div>
        ) : null}
      </td>
      <td className="px-3 py-2 text-slate-200">
        <div className="flex items-center gap-1.5"><MapPin size={11} className="text-slate-500" />{row.origin}</div>
        <div className="flex items-center gap-1.5 text-slate-400"><MapPin size={11} className="text-slate-600" />{row.destination}</div>
      </td>
      <td className="px-3 py-2 text-slate-300">
        <div className="flex items-center gap-1">
          {row.equipment === "Reefer" && <Snowflake size={11} className="text-cyan-400" />}
          {row.equipment}
        </div>
        {row.hazmat && (
          <div className="text-[9px] text-red-400 flex items-center gap-1 mt-0.5">
            <ShieldAlert size={9} /> HAZMAT
          </div>
        )}
      </td>
      <td className="px-3 py-2 text-right text-emerald-300 font-mono">${(row.rate_usd || 0).toLocaleString()}</td>
      <td className="px-3 py-2 text-right text-slate-200 font-mono">${(row.rate_per_mile || 0).toFixed(2)}</td>
      <td className="px-3 py-2 text-right text-slate-400 font-mono">{row.miles || "—"}</td>
      <td className="px-3 py-2 text-slate-400 font-mono"><Clock size={10} className="inline mr-1" />{fresh}</td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${row.score || 0}%`, background: scoreColor }} />
          </div>
          <span className="text-[10px] font-mono" style={{ color: scoreColor }}>{row.score}</span>
        </div>
      </td>
      <td className="px-3 py-2 text-right">
        <div className="flex items-center gap-1 justify-end">
          <Button
            size="sm"
            onClick={() => onBook?.(row)}
            className="h-7 px-2 bg-emerald-500 hover:bg-emerald-400 text-black"
            data-testid={`aggregator-book-${row.load_id}`}
          >
            <PackageCheck size={12} className="mr-1" /> Book
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={pinning}
            onClick={pin}
            className="h-7 px-2 text-cyan-300 hover:text-cyan-100"
            data-testid={`aggregator-pin-${row.load_id}`}
          >
            {pinning ? <Loader2 size={12} className="animate-spin" /> : <Pin size={12} />}
          </Button>
        </div>
      </td>
    </tr>
  );
}

// ============================================================
//                    PINS VIEW
// ============================================================
function PinsView({ pins, onChange }) {
  const unpin = async (pin_id) => {
    try {
      await api.delete(`/aggregator/pins/${pin_id}`);
      toast.success("Unpinned");
      onChange?.();
    } catch (e) { toast.error("Failed to unpin"); }
  };
  if (!pins.length) return (
    <Card className="p-8 text-center bg-slate-900/60 border-white/10">
      <PinOff size={22} className="mx-auto text-slate-600 mb-2" />
      <div className="text-xs text-slate-500">No pinned loads yet. Pin from the feed to revisit later.</div>
    </Card>
  );
  return (
    <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
      <table className="w-full text-xs">
        <thead className="bg-black/40 text-slate-400 font-mono uppercase tracking-wider">
          <tr>
            <th className="px-3 py-2 text-left">Pin ID</th>
            <th className="px-3 py-2 text-left">Load</th>
            <th className="px-3 py-2 text-left">Board</th>
            <th className="px-3 py-2 text-left">Pinned At</th>
            <th className="px-3 py-2 text-left">Reason</th>
            <th className="px-3 py-2 text-right"></th>
          </tr>
        </thead>
        <tbody>
          {pins.map((p) => (
            <tr key={p.pin_id} className="border-t border-white/5" data-testid={`aggregator-pin-row-${p.pin_id}`}>
              <td className="px-3 py-2 text-slate-500 font-mono">{p.pin_id}</td>
              <td className="px-3 py-2 text-slate-100 font-mono">{p.load_id}</td>
              <td className="px-3 py-2 text-cyan-300 font-mono uppercase">{p.board_id}</td>
              <td className="px-3 py-2 text-slate-400 font-mono">{p.pinned_at?.slice(0, 19).replace("T", " ")}</td>
              <td className="px-3 py-2 text-slate-300">{p.reason || "—"}</td>
              <td className="px-3 py-2 text-right">
                <Button size="sm" variant="ghost" onClick={() => unpin(p.pin_id)}
                  className="h-7 px-2 text-red-300 hover:text-red-100"
                  data-testid={`aggregator-unpin-${p.pin_id}`}
                >
                  <PinOff size={12} />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

// ============================================================
//                    PREFS VIEW
// ============================================================
function PrefsView({ onSaved }) {
  const [form, setForm] = useState({
    equipment: [],
    min_rate_per_mile: "",
    origin_states: [],
    dest_states: [],
    max_weight_lbs: "",
    exclude_hazmat: false,
    saved_filter_name: "",
  });
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.get("/aggregator/prefs").then(({ data }) => {
      setForm((f) => ({
        ...f,
        equipment: data.equipment || [],
        min_rate_per_mile: data.min_rate_per_mile ?? "",
        origin_states: data.origin_states || [],
        dest_states: data.dest_states || [],
        max_weight_lbs: data.max_weight_lbs ?? "",
        exclude_hazmat: !!data.exclude_hazmat,
        saved_filter_name: data.saved_filter_name || "",
      }));
    }).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    try {
      const payload = { ...form };
      ["min_rate_per_mile", "max_weight_lbs"].forEach((k) => {
        payload[k] = payload[k] === "" ? undefined : Number(payload[k]);
      });
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      await api.post("/aggregator/prefs", payload);
      toast.success("Preferences saved · feed will re-rank");
      onSaved?.();
    } catch (e) { toast.error("Failed to save"); }
  };

  const toggle = (key, val) => {
    setForm((f) => ({ ...f, [key]: f[key].includes(val) ? f[key].filter((x) => x !== val) : [...f[key], val] }));
  };

  if (loading) return <Loader />;

  return (
    <Card className="p-4 bg-slate-900/60 border-white/10 space-y-4">
      <div>
        <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">Equipment</div>
        <div className="flex flex-wrap gap-2">
          {EQUIPMENT.map((e) => (
            <button
              key={e}
              onClick={() => toggle("equipment", e)}
              data-testid={`aggregator-prefs-eq-${e}`}
              className={`px-3 py-1 rounded-full text-[11px] font-mono uppercase border transition ${
                form.equipment.includes(e)
                  ? "bg-cyan-500/20 border-cyan-400 text-cyan-100"
                  : "border-white/10 text-slate-400 hover:border-cyan-400/40"
              }`}
            >{e}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Field label="Min RPM ($/mi)">
          <Input type="number" step="0.05" value={form.min_rate_per_mile}
            onChange={(e) => setForm((f) => ({ ...f, min_rate_per_mile: e.target.value }))}
            className="bg-black/40 border-white/10 text-xs h-8"
            data-testid="aggregator-prefs-min-rpm" />
        </Field>
        <Field label="Max weight (lbs)">
          <Input type="number" step="500" value={form.max_weight_lbs}
            onChange={(e) => setForm((f) => ({ ...f, max_weight_lbs: e.target.value }))}
            className="bg-black/40 border-white/10 text-xs h-8"
            data-testid="aggregator-prefs-max-weight" />
        </Field>
        <Field label="Saved filter name">
          <Input value={form.saved_filter_name}
            onChange={(e) => setForm((f) => ({ ...f, saved_filter_name: e.target.value }))}
            placeholder="e.g. Southeast reefer over $2.30"
            className="bg-black/40 border-white/10 text-xs h-8"
            data-testid="aggregator-prefs-saved-name" />
        </Field>
      </div>

      <StatePicker
        label="Preferred origin states"
        selected={form.origin_states}
        onToggle={(s) => toggle("origin_states", s)}
        testid="aggregator-prefs-origin"
      />
      <StatePicker
        label="Preferred destination states"
        selected={form.dest_states}
        onToggle={(s) => toggle("dest_states", s)}
        testid="aggregator-prefs-dest"
      />

      <label className="flex items-center gap-2 text-xs text-slate-300">
        <input type="checkbox" checked={form.exclude_hazmat}
          onChange={(e) => setForm((f) => ({ ...f, exclude_hazmat: e.target.checked }))}
          data-testid="aggregator-prefs-hazmat" />
        Exclude hazmat loads
      </label>

      <div className="flex justify-end">
        <Button onClick={save} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="aggregator-prefs-save">
          <CheckCircle2 size={14} className="mr-1" /> Save Preferences
        </Button>
      </div>
    </Card>
  );
}

function StatePicker({ label, selected, onToggle, testid }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-cyan-300 mb-2">{label}</div>
      <div className="flex flex-wrap gap-1">
        {STATES.map((s) => (
          <button
            key={s}
            onClick={() => onToggle(s)}
            data-testid={`${testid}-${s}`}
            className={`w-9 h-7 rounded text-[10px] font-mono border transition ${
              selected.includes(s)
                ? "bg-cyan-500/20 border-cyan-400 text-cyan-100"
                : "border-white/10 text-slate-500 hover:border-cyan-400/40"
            }`}
          >{s}</button>
        ))}
      </div>
    </div>
  );
}

// ============================================================
//                    RETENTION COMPLIANCE VIEW
// ============================================================
function RetentionView() {
  const [audit, setAudit] = useState(null);
  const [policy, setPolicy] = useState([]);
  const [attesting, setAttesting] = useState(null); // board object
  const [findingText, setFindingText] = useState("");
  const [isCompliant, setIsCompliant] = useState(true);
  const [sending, setSending] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([
        api.get("/aggregator/retention/audit"),
        api.get("/aggregator/retention/policy"),
      ]);
      setAudit(a.data);
      setPolicy(p.data.items || []);
    } catch (e) { toast.error("Failed to load retention data"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitAttest = async () => {
    if (!findingText.trim()) { toast.error("Finding required"); return; }
    setSending(true);
    try {
      await api.post("/aggregator/retention/attest", {
        board_id: attesting.board_id,
        finding: findingText.trim(),
        is_compliant: isCompliant,
      });
      toast.success("Attestation recorded");
      setAttesting(null); setFindingText(""); setIsCompliant(true);
      load();
    } catch (e) {
      const msg = e?.response?.data?.detail || "Failed";
      toast.error(String(msg));
    } finally { setSending(false); }
  };

  if (!audit) return <Loader />;

  const statusColor = (s) => ({
    COMPLIANT: "text-emerald-400 border-emerald-400/40 bg-emerald-500/10",
    STALE: "text-amber-400 border-amber-400/40 bg-amber-500/10",
    NON_COMPLIANT: "text-red-400 border-red-400/40 bg-red-500/10",
    UNATTESTED: "text-slate-400 border-white/10 bg-white/[0.02]",
  }[s] || "text-slate-400 border-white/10");

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Compliant" value={audit.compliant} color="#10B981" icon={ShieldCheck} />
        <StatTile label="Stale" value={audit.stale} color="#F59E0B" icon={Clock} />
        <StatTile label="Non-Compliant" value={audit.non_compliant} color="#EF4444" icon={ShieldAlert} />
        <StatTile label="Unattested" value={audit.unattested} color="#64748B" icon={FileText} />
      </div>

      <Card className="p-0 bg-slate-900/60 border-white/10 overflow-hidden">
        <div className="px-3 py-2 border-b border-white/10 text-[10px] font-mono uppercase tracking-widest text-cyan-300">
          <Sparkles size={12} className="inline mr-1" /> Retention audit per board
        </div>
        <div className="divide-y divide-white/5">
          {audit.items.map((r) => (
            <div key={r.board_id} className="p-4 space-y-2" data-testid={`aggregator-retention-${r.board_id}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm text-slate-100 font-medium">{r.board_name}</div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500 mt-0.5">
                    {r.retention_months} months · {r.citations?.[0] || "internal SLA"}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-widest border ${statusColor(r.status)}`}>
                    {r.status.replace("_", " ")}
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setAttesting(r)}
                    data-testid={`aggregator-attest-btn-${r.board_id}`}
                  >
                    <Award size={12} className="mr-1" /> Attest
                  </Button>
                </div>
              </div>
              <div className="text-[11px] text-slate-400 leading-relaxed">
                <span className="text-cyan-300 font-mono uppercase text-[9px] tracking-widest mr-2">Records:</span>
                {r.record_types.join(" · ")}
              </div>
              <div className="text-[11px] text-slate-500">
                <span className="text-cyan-300 font-mono uppercase text-[9px] tracking-widest mr-2">Storage:</span>
                {r.storage_requirements}
              </div>
              {r.latest_attestation && (
                <div className="text-[10px] text-slate-500 border-l-2 border-cyan-500/30 pl-2 mt-2">
                  Last attested by <b className="text-slate-300">{r.latest_attestation.attester_name}</b> on {r.latest_attestation.attested_at?.slice(0, 10)} · &quot;{r.latest_attestation.finding}&quot;
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Attest modal */}
      <Dialog open={!!attesting} onOpenChange={(o) => !o && setAttesting(null)}>
        <DialogContent className="max-w-lg bg-slate-950 border-white/10" data-testid="aggregator-attest-modal">
          <DialogHeader>
            <DialogTitle className="text-cyan-100">
              Attest · {attesting?.board_name}
            </DialogTitle>
            <DialogDescription className="text-slate-400 text-xs">
              Record a compliance finding. Attesters must be admin or auditor.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label className="text-[10px] uppercase font-mono text-cyan-300">Finding</Label>
            <Textarea
              value={findingText}
              onChange={(e) => setFindingText(e.target.value)}
              placeholder="e.g. Verified 24-mo audit trail restore window; test restore completed 2026-02-15."
              className="bg-black/40 border-white/10 text-xs min-h-[100px]"
              data-testid="aggregator-attest-finding"
            />
            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input type="checkbox" checked={isCompliant}
                onChange={(e) => setIsCompliant(e.target.checked)}
                data-testid="aggregator-attest-compliant" />
              Board is compliant with the retention policy
            </label>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAttesting(null)}>Cancel</Button>
            <Button onClick={submitAttest} disabled={sending} className="bg-cyan-500 hover:bg-cyan-400 text-black" data-testid="aggregator-attest-submit">
              {sending ? <Loader2 size={13} className="animate-spin mr-1" /> : <CheckCircle2 size={13} className="mr-1" />}
              Record Attestation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================
//                    BOOK LOAD DIALOG (aggregator → workflow)
// ============================================================
function BookLoadDialog({ load, onClose, onBooked }) {
  const [form, setForm] = useState({
    carrier_name: "", carrier_mc: "", customer_name: "", customer_email: "", notes: "",
  });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (load) setForm({ carrier_name: "", carrier_mc: "", customer_name: "", customer_email: "", notes: "" });
  }, [load]);

  if (!load) return null;

  const submit = async () => {
    if (!form.carrier_name.trim()) { toast.error("Carrier name required"); return; }
    setBusy(true);
    try {
      const payload = {
        load_id: load.load_id,
        board_id: load.board_id,
        carrier_name: form.carrier_name.trim(),
        carrier_mc: form.carrier_mc.trim() || undefined,
        customer_name: form.customer_name.trim() || undefined,
        customer_email: form.customer_email.trim() || undefined,
        notes: form.notes.trim() || undefined,
      };
      Object.keys(payload).forEach((k) => payload[k] === undefined && delete payload[k]);
      const { data } = await api.post("/brokerage/loads/book", payload);
      onBooked?.(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to book");
    } finally { setBusy(false); }
  };

  const margin = ((load.rate_usd || 0) - (load.carrier_pay_usd || 0)).toFixed(0);

  return (
    <Dialog open={!!load} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="max-w-lg bg-slate-950 border-white/10" data-testid="aggregator-book-modal">
        <DialogHeader>
          <DialogTitle className="text-emerald-100 flex items-center gap-2">
            <PackageCheck size={16} /> Book Load · {load.load_id}
          </DialogTitle>
          <DialogDescription className="text-slate-400 text-xs">
            After booking, you&apos;ll auto-route to the Run-the-Load workflow. The load will also appear on the Live Tracking map.
          </DialogDescription>
        </DialogHeader>

        <div className="p-3 rounded bg-black/40 border border-white/10 text-xs space-y-1">
          <div className="flex justify-between"><span className="text-slate-400">Lane</span><span className="text-slate-100">{load.origin} → {load.destination}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Miles / Equipment</span><span className="text-slate-100">{load.miles} · {load.equipment}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Rate / RPM</span><span className="text-emerald-300 font-mono">${(load.rate_usd || 0).toLocaleString()} · ${(load.rate_per_mile || 0).toFixed(2)}/mi</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Forecast margin</span><span className="text-amber-300 font-mono">${margin}</span></div>
          <div className="flex justify-between"><span className="text-slate-400">Board</span><span className="text-cyan-300 font-mono uppercase">{load.board_name || load.board_id}</span></div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Carrier Name *</div>
            <Input value={form.carrier_name} onChange={(e) => setForm({ ...form, carrier_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs"
              data-testid="aggregator-book-carrier" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Carrier MC #</div>
            <Input value={form.carrier_mc} onChange={(e) => setForm({ ...form, carrier_mc: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" placeholder="MC-123456" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Customer / Shipper</div>
            <Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
          <div>
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Customer email</div>
            <Input type="email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })}
              className="bg-black/40 border-white/10 h-8 text-xs" />
          </div>
          <div className="col-span-2">
            <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">Notes</div>
            <Textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
              className="bg-black/40 border-white/10 text-xs" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy} className="bg-emerald-500 hover:bg-emerald-400 text-black"
            data-testid="aggregator-book-submit">
            {busy ? <Loader2 size={13} className="animate-spin mr-1" /> : <PackageCheck size={13} className="mr-1" />}
            Book &amp; Route to Workflow
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================
//                    SHARED UI PRIMS
// ============================================================
function Field({ label, children }) {
  return (
    <div>
      <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500 mb-1">{label}</div>
      {children}
    </div>
  );
}
function Loader() {
  return (
    <div className="p-8 text-center text-xs text-slate-500">
      <Loader2 size={16} className="animate-spin inline mr-2" /> Loading…
    </div>
  );
}
function StatTile({ label, value, color, icon: Icon }) {
  return (
    <Card className="p-3 bg-slate-900/60 border-white/10">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-mono uppercase tracking-widest text-slate-500">{label}</div>
        {Icon && <Icon size={13} style={{ color }} />}
      </div>
      <div className="text-2xl font-mono mt-1" style={{ color }}>{value}</div>
    </Card>
  );
}
