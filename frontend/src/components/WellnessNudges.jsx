import React, { useEffect, useRef } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";

/**
 * WellnessNudges · drops friendly, on-brand wellness reminders into a
 * sonner toast at a slow cadence (default every ~22 minutes) throughout
 * the workday. Picks from a rotating server-side pool so messages don't
 * repeat for a while.
 *
 * Mount once at the App layout level — no JSX rendered (toasts only).
 */

const INTERVAL_MS = 22 * 60 * 1000; // ~22 minutes
const FIRST_DELAY_MS = 6 * 60 * 1000; // first nudge after 6 min
const STORAGE_KEY = "tms-wellness-seen-ids";

function getSeen() {
  try { return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveSeen(set) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...set].slice(-20))); }
  catch { /* ignore */ }
}

export default function WellnessNudges() {
  const nudgesRef = useRef([]);
  const timerRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/wellness/nudges");
        if (!cancelled) nudgesRef.current = data || [];
      } catch { /* offline — silently skip */ }
    })();

    const fire = () => {
      const all = nudgesRef.current;
      if (!all.length) return;
      const seen = getSeen();
      // Pick the next un-seen nudge — wrap around once all 15 are seen
      let pick = all.find((n) => !seen.has(n.id));
      if (!pick) {
        saveSeen(new Set());
        pick = all[Math.floor(Math.random() * all.length)];
      }
      seen.add(pick.id);
      saveSeen(seen);
      toast(pick.title, {
        description: pick.message,
        duration: 8500,
        className: "wellness-toast",
        // Sonner accepts `data-testid` via custom HTML id below
      });
    };

    const startId = setTimeout(() => {
      fire();
      timerRef.current = setInterval(fire, INTERVAL_MS);
    }, FIRST_DELAY_MS);

    return () => {
      cancelled = true;
      clearTimeout(startId);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return null;
}
