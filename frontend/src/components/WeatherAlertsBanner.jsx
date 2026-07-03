import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import { AlertTriangle, X, ExternalLink, Settings, MapPin, Plus, Loader2, Radio, CheckCircle2, Navigation } from "lucide-react";
import { toast } from "sonner";
import { useBrandRefresh } from "../lib/branding";

/**
 * WeatherAlertsBanner — real-time NWS alerts scoped to the user's actual
 * browser geolocation. NO mock/synthetic fallback.
 *
 * Flow:
 *   1. On mount, ask `navigator.geolocation.getCurrentPosition()` for
 *      real coords. Cache in localStorage (24h) so we don't re-prompt.
 *   2. GET /api/weather/alerts?lat=…&lng=… → live api.weather.gov feed.
 *   3. If NWS returns zero active alerts → show a clean "all clear" pill.
 *   4. If the user denies geolocation → show a "Grant location access"
 *      prompt with a button that retries the browser API.
 *   5. Poll every 60s; auto-refetch on active-brand swap.
 */
const DISMISS_KEY = "tms-weather-alerts-dismissed";
const GEO_KEY = "tms-weather-geo";                    // {lat,lng,label,cachedAt}
const GEO_TTL_MS = 24 * 60 * 60 * 1000;               // 24h
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
const readCachedGeo = () => {
  try {
    const raw = JSON.parse(localStorage.getItem(GEO_KEY) || "null");
    if (!raw || !raw.cachedAt || Date.now() - raw.cachedAt > GEO_TTL_MS) return null;
    if (typeof raw.lat !== "number" || typeof raw.lng !== "number") return null;
    return raw;
  } catch { return null; }
};
const writeCachedGeo = (geo) => {
  try { localStorage.setItem(GEO_KEY, JSON.stringify({ ...geo, cachedAt: Date.now() })); }
  catch { /* noop */ }
};

export default function WeatherAlertsBanner() {
  const [alerts, setAlerts] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [dismissedTick, setDismissedTick] = useState(0);
  const [configOpen, setConfigOpen] = useState(false);
  const [geo, setGeo] = useState(() => readCachedGeo());
  const [geoState, setGeoState] = useState(geo ? "ready" : "idle");   // idle | requesting | denied | unsupported | ready
  const [meta, setMeta] = useState(null);   // { no_active_alerts, resolved_from, needs_location, count }
  const geoRef = useRef(geo);
  geoRef.current = geo;

  // Ask the browser for real coords.  We treat prior localStorage cache as
  // a fast path; if the user hasn't granted access yet, prompt them.
  const requestGeo = useCallback((forcePrompt = false) => {
    if (!navigator?.geolocation) { setGeoState("unsupported"); return; }
    if (!forcePrompt) {
      const cached = readCachedGeo();
      if (cached) { setGeo(cached); setGeoState("ready"); return; }
    }
    setGeoState("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const g = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        };
        writeCachedGeo(g);
        setGeo(g);
        setGeoState("ready");
      },
      (err) => {
        // 1 = PERMISSION_DENIED, 2 = POSITION_UNAVAILABLE, 3 = TIMEOUT
        if (err?.code === 1) setGeoState("denied");
        else setGeoState("unavailable");
      },
      { enableHighAccuracy: false, maximumAge: 5 * 60 * 1000, timeout: 8000 }
    );
  }, []);

  const load = useCallback(async () => {
    try {
      const g = geoRef.current;
      const url = g
        ? `/weather/alerts?lat=${g.lat}&lng=${g.lng}`
        : "/weather/alerts";
      const { data } = await api.get(url);
      // Backend now always returns { items, count, no_active_alerts, needs_location, ... }
      // Preserve backward compatibility if a proxy ever returns a bare list.
      const items = Array.isArray(data) ? data : (data?.items || []);
      const nextMeta = Array.isArray(data)
        ? { count: items.length, no_active_alerts: items.length === 0 }
        : data;
      setAlerts(items);
      setMeta(nextMeta);
      setLastUpdated(new Date());
    } catch { /* noop */ }
  }, []);

  // On mount: try cached geo, fall through to browser prompt.
  useEffect(() => { requestGeo(false); }, [requestGeo]);

  // Whenever geo changes, immediately reload.
  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
  }, [load, geo]);

  useBrandRefresh(() => load());

  const dismissed = getDismissed();
  const visible = alerts.filter((a) => !dismissed.has(a.alert_id));

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
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 text-emerald-300">
            <Radio size={10} className="animate-pulse" /> LIVE WEATHER FEED · NWS
          </span>
          {geoState === "ready" && geo && (
            <span className="text-slate-500 inline-flex items-center gap-1">
              <MapPin size={9} /> your location · {geo.lat.toFixed(2)}, {geo.lng.toFixed(2)}
            </span>
          )}
          {lastUpdated && (
            <span className="text-slate-500">· updated {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
          )}
          {sorted.length === 0 && meta?.no_active_alerts && geoState === "ready" && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-[9px]" data-testid="weather-all-clear">
              <CheckCircle2 size={9} /> ALL CLEAR
            </span>
          )}
        </div>
        <button
          onClick={() => setConfigOpen(true)}
          data-testid="weather-alerts-config-btn"
          className="inline-flex items-center gap-1 text-slate-400 hover:text-cyan-300 transition"
        >
          <Settings size={10} /> Locations
        </button>
      </div>

      {/* Geolocation prompt states */}
      {geoState !== "ready" && sorted.length === 0 && (
        <Card
          data-testid="weather-geo-prompt"
          className="p-3 bg-slate-900/60 border-white/10 flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2 min-w-0">
            <Navigation size={14} className="text-cyan-300 shrink-0" />
            <div className="text-xs text-slate-200">
              {geoState === "requesting" && (
                <><b>Requesting your location…</b> click Allow in the browser prompt to see NWS alerts for your area.</>
              )}
              {geoState === "denied" && (
                <><b>Location access blocked.</b> Enable it in your browser settings, or add locations manually via <span className="text-cyan-300">Locations →</span>.</>
              )}
              {geoState === "unavailable" && (
                <><b>Couldn&apos;t determine your location.</b> Try again, or add a monitored location manually.</>
              )}
              {geoState === "unsupported" && (
                <><b>Your browser doesn&apos;t support geolocation.</b> Add locations manually.</>
              )}
              {geoState === "idle" && (
                <><b>Real-time NWS weather alerts for your area.</b> Grant location access to start.</>
              )}
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            {(geoState === "idle" || geoState === "denied" || geoState === "unavailable") && (
              <Button size="sm" onClick={() => requestGeo(true)}
                data-testid="weather-geo-grant-btn"
                className="bg-cyan-500 hover:bg-cyan-400 text-black h-7">
                <Navigation size={11} className="mr-1" /> Use my location
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setConfigOpen(true)}
              className="text-slate-300 h-7">
              Add manually
            </Button>
          </div>
        </Card>
      )}

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
