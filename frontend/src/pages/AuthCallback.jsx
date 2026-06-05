import React, { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, setStoredToken } from "../lib/api";
import { useAuth } from "../lib/auth";
import { TennantLogo } from "../components/TennantLogo";

export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const hasProcessed = useRef(false);
  const { setUser } = useAuth();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = location.hash || window.location.hash;
    const params = new URLSearchParams(hash.replace(/^#/, ""));
    const sessionId = params.get("session_id");
    if (!sessionId) {
      navigate("/login", { replace: true });
      return;
    }
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sessionId });
        // Persist Bearer token for cross-origin (cookies often blocked).
        if (data.session_token) setStoredToken(data.session_token);
        setUser(data);
        navigate("/dashboard", { replace: true, state: { user: data } });
      } catch (_) {
        navigate("/login", { replace: true });
      }
    })();
  }, [location, navigate, setUser]);

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white flex items-center justify-center hud-grid-bg">
      <div className="text-center">
        <TennantLogo size="lg" />
        <div className="mt-8 text-[10px] font-mono text-cyan-400 tracking-[0.3em] uppercase">Establishing Secure Session...</div>
        <div className="mt-3 flex justify-center">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
          </span>
        </div>
      </div>
    </div>
  );
}
