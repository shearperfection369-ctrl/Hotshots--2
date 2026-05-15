import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import { AlertTriangle, X, ExternalLink, Settings, MapPin, Plus, Loader2, Radio } from "lucide-react";
import { toast } from "sonner";
import { useBrandRefresh } from "../lib/branding";

/**
 * WeatherAlertsBanner — polls `/api/weather/alerts` every 60s and surfaces
 * NWS-style watches/warnings at the top of the page.
 *
 * Backend pulls **real, live alerts from api.weather.gov** for each
 * user-monitored location (US only). Falls back to brand mock alerts when
 * no live alerts are active. Admin can edit the location list via the gear
 * icon on the banner.
 */
const DISMISS_KEY = "tms-weather-alerts-dismissed";
const POLL_MS = 60 * 1000;

const SEVERITY = {
  high:     { bg: "from-red-500/30 to-red-900/10",   border: "border-red-500/40",   icon: "text-red-300",     label: "bg-red-500/20 text-red-200 border-red-500/40" },
  moderate: { bg: "from-yellow-500/25 to-yellow-900/5", border: "border-yellow-500/40", icon: "text-yellow-300", label: "bg-yellow-500/20 text-yellow-200 border-yellow-500/40" },
  low:      { bg: "from-cyan-500/15 to-cyan-900/0",  border: "border-cyan-500/30",  icon: "text-cyan-300",    label: "bg-cyan-500/15 text-cyan-200 border-cyan-500/30" },
};

const getDismissed = () => {
  try { return new Set(JSON.parse(sessionStorage.getItem(DISMISS_KEY) || "[]")); }
  catch { return new Set(); }
};
const setDismissed = (set) => {
  try { sessionStorage.setItem(DISMISS_KEY, JSON.stringify([...set])); }
  catch { /* noop */ }
};

export default function WeatherAlertsBanner() {
  const [alerts, setAlerts] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [dismissedTick, setDismissedTick] = useState(0);
  const [configOpen, setConfigOpen] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/weather/alerts");
      setAlerts(data || []);
      setLastUpdated(new Date());
    } catch { /* noop */ }
  };
  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, []);
  // Re-fetch when admin switches the active brand so the alert locations
  // re-seed from the new brand's facilities.
  useBrandRefresh(() => load());

  const dismissed = getDismissed();
  const visible = alerts.filter((a) => !dismissed.has(a.alert_id));

  // If nothing is visible we still want to render the configure-gear so
  // admins know where to manage their monitored locations.
  const sevRank = { high: 0, moderate: 1, low: 2 };
  const sorted = [...visible].sort((a, b) => (sevRank[a.severity] || 9) - (sevRank[b.severity] || 9)).slice(0, 3);

  const dismiss = (id) => {
    const d = getDismissed();
    d.add(id);
    setDismissed(d);
    setDismissedTick((t) => t + 1);
  };

  return (
    <div className="px-4 md:px-6 pt-3 space-y-2" data-testid="weather-alerts-banner">
      {/* Header row — Live indicator + config gear */}
      <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.18em] text-slate-500">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 text-emerald-300">
            <Radio size={10} className="animate-pulse" /> LIVE WEATHER FEED
          </span>
          {lastUpdated && (
            <span className="text-slate-500">· updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          )}
          {sorted.some((a) => a.live) && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[9px]">NWS live</span>
          )}
        </div>
        <button
          onClick={() => setConfigOpen(true)}
          data-testid="weather-alerts-config-btn"
          className="inline-flex items-center gap-1 text-slate-400 hover:text-cyan-300 transition"
        >
          <Settings size={10} /> Configure Locations
        </button>
      </div>

      {sorted.map((a) => {
        const sev = SEVERITY[a.severity] || SEVERITY.low;
        return (
          <Card
            key={a.alert_id}
            data-testid={`weather-alert-${a.alert_id}`}
            className={`p-3 bg-gradient-to-r ${sev.bg} ${sev.border} border relative`}
          >
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className={`${sev.icon} mt-0.5 shrink-0`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border ${sev.label}`}>
                    {a.type}
                  </span>
                  {a.live && (
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border bg-emerald-500/15 text-emerald-300 border-emerald-500/40 inline-flex items-center gap-0.5">
                      <Radio size={8} className="animate-pulse" /> LIVE
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-slate-300 uppercase tracking-wider">{a.area}</span>
                  {a.affected_facility && (
                    <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-wider">
                      Affects · {a.affected_facility}
                    </span>
                  )}
                </div>
                <div className="text-sm font-bold text-white mt-1">{a.headline}</div>
                <div className="text-xs text-slate-300 mt-1 leading-relaxed line-clamp-3">{a.body}</div>
                <div className="flex items-center gap-3 mt-2 text-[10px] font-mono text-slate-400 flex-wrap">
                  <span>Issued {new Date(a.issued_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
                  <span>· Expires {new Date(a.expires_at).toLocaleString("en-US", { dateStyle: "short", timeStyle: "short" })}</span>
                  {a.source_url && (
                    <a href={a.source_url} target="_blank" rel="noreferrer"
                       className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200">
                      {a.source} <ExternalLink size={9} />
                    </a>
                  )}
                </div>
              </div>
              <button
                onClick={() => dismiss(a.alert_id)}
                data-testid={`weather-alert-dismiss-${a.alert_id}`}
                aria-label="Dismiss alert"
                className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 shrink-0"
              >
                <X size={14} />
              </button>
            </div>
          </Card>
        );
      })}
      <span className="hidden" data-testid="weather-alerts-count">{sorted.length}</span>
      <span className="hidden" data-tick={dismissedTick} />

      <WeatherLocationsDialog
        open={configOpen}
        onOpenChange={setConfigOpen}
        onSaved={() => load()}
      />
    </div>
  );
}


/**
 * WeatherLocationsDialog — manages the user's monitored locations.
 * Uses Open-Meteo's free geocoding API for "Add Location" autocomplete.
 */
function WeatherLocationsDialog({ open, onOpenChange, onSaved }) {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    api.get("/weather/alert-locations").then(({ data }) => {
      setLocations(data.locations || []);
    }).catch(() => { /* noop */ }).finally(() => setLoading(false));
  }, [open]);

  // Debounced geocode search
  useEffect(() => {
    if (!open) return;
    if (search.trim().length < 2) { setSuggestions([]); return; }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const r = await fetch(
          `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(search.trim())}&count=8&language=en&format=json`
        );
        const j = await r.json();
        setSuggestions(j.results || []);
      } catch {
        setSuggestions([]);
      } finally { setSearching(false); }
    }, 320);
    return () => clearTimeout(t);
  }, [search, open]);

  const addLocation = (hit) => {
    const next = {
      label: `${hit.name}${hit.admin1 ? ", " + hit.admin1 : ""}${hit.country_code && hit.country_code !== "US" ? " · " + hit.country_code : ""}`,
      lat: hit.latitude,
      lng: hit.longitude,
      state: hit.country_code === "US" ? (hit.admin1 || "").slice(0, 2).toUpperCase() : null,
      country: hit.country_code || "US",
    };
    if (locations.some((l) => l.lat === next.lat && l.lng === next.lng)) {
      toast.info("Already monitoring that location");
      return;
    }
    setLocations([...locations, next]);
    setSearch("");
    setSuggestions([]);
  };

  const removeLocation = (i) => {
    setLocations(locations.filter((_, idx) => idx !== i));
  };

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/weather/alert-locations", { locations });
      toast.success(`Saved · monitoring ${data.locations.length} location${data.locations.length === 1 ? "" : "s"}`);
      onSaved && onSaved();
      onOpenChange(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save");
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl bg-[#0B0E14] border-cyan-500/30">
        <DialogHeader>
          <DialogTitle className="font-display text-lg flex items-center gap-2">
            <MapPin size={16} className="text-cyan-400" /> Weather Alert Locations
          </DialogTitle>
          <DialogDescription className="text-xs text-slate-400">
            Pick the cities and facilities you want monitored. The TMS pulls{" "}
            <span className="text-emerald-300">live National Weather Service alerts</span>{" "}
            for each US location every 60 seconds. International locations are listed but NWS only covers the United States.
          </DialogDescription>
        </DialogHeader>

        {/* Search */}
        <div className="space-y-2">
          <label className="text-[10px] font-mono uppercase tracking-wider text-slate-400 block">Add a Location</label>
          <div className="relative">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Type a city — e.g. Denver, Pearl River NY, Tokyo…"
              data-testid="weather-config-search"
              className="bg-[#11151F] border-white/10 font-mono text-sm"
            />
            {searching && <Loader2 size={12} className="absolute right-3 top-3 text-slate-500 animate-spin" />}
          </div>
          {suggestions.length > 0 && (
            <div className="max-h-44 overflow-y-auto rounded border border-white/10 divide-y divide-white/5" data-testid="weather-config-suggestions">
              {suggestions.map((h) => (
                <button
                  key={`${h.id}-${h.latitude}-${h.longitude}`}
                  onClick={() => addLocation(h)}
                  data-testid={`weather-config-suggestion-${h.id}`}
                  className="w-full text-left px-3 py-2 hover:bg-cyan-500/10 transition flex items-center justify-between gap-2"
                >
                  <div>
                    <div className="text-sm text-slate-200">{h.name}{h.admin1 ? `, ${h.admin1}` : ""}</div>
                    <div className="text-[10px] font-mono text-slate-500">{h.country} · {h.latitude.toFixed(2)}, {h.longitude.toFixed(2)}</div>
                  </div>
                  <Plus size={14} className="text-cyan-300 shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Current list */}
        <div className="mt-3">
          <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-2 flex items-center justify-between">
            <span>Currently Monitoring · {locations.length}</span>
            {locations.length === 0 && <span className="text-slate-500 italic normal-case tracking-normal">(will auto-seed from active brand)</span>}
          </div>
          {loading ? (
            <div className="text-center py-6 text-slate-500"><Loader2 className="inline animate-spin" size={14} /></div>
          ) : (
            <div className="space-y-1.5">
              {locations.map((l, i) => (
                <div key={`${l.lat}-${l.lng}-${i}`} className="flex items-center justify-between gap-2 px-3 py-2 rounded border border-white/5 bg-white/[0.02]" data-testid={`weather-config-row-${i}`}>
                  <div className="min-w-0">
                    <div className="text-sm text-slate-200 truncate">{l.label}</div>
                    <div className="text-[10px] font-mono text-slate-500">
                      {l.country || "US"}{l.state ? ` · ${l.state}` : ""} · {Number(l.lat).toFixed(3)}, {Number(l.lng).toFixed(3)}
                      {(l.country && l.country !== "US") && <span className="text-amber-300 ml-2">· NWS unavailable (US-only)</span>}
                    </div>
                  </div>
                  <button
                    onClick={() => removeLocation(i)}
                    data-testid={`weather-config-remove-${i}`}
                    className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition shrink-0"
                    title="Stop monitoring"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="flex-wrap gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="weather-config-cancel">Cancel</Button>
          <Button onClick={save} disabled={saving} className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold" data-testid="weather-config-save">
            {saving ? <><Loader2 size={13} className="mr-1.5 animate-spin" /> Saving…</> : "Save & Refresh"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
