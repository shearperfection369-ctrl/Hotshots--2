import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, setStoredToken } from "./api";

const AuthContext = createContext(null);

const PUBLIC_ROUTE_PREFIXES = [
  "/home", "/services", "/lanes", "/contact", "/about",
  "/investors", "/press", "/exec-summary",
  "/tms-investors", "/tms-pitch", "/demo",
  "/marketing", "/landing", "/accept-invite", "/customer-portal", "/rfp-board", "/driver",
  "/driver", "/login", "/t",
];

function isPublicRoute() {
  if (typeof window === "undefined") return false;
  const path = window.location.pathname;
  // Root path "/" is also public (landing page)
  if (path === "/") return true;
  return PUBLIC_ROUTE_PREFIXES.some((p) => path === p || path.startsWith(p + "/"));
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (_) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (typeof window !== "undefined" && window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    // Skip /auth/me for purely public routes so visiting VCs / journalists
    // don't see 401 console errors when they open DevTools on the
    // /investors page.
    if (isPublicRoute()) {
      setLoading(false);
      return;
    }
    checkAuth();
  }, [checkAuth]);

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (_) {}
    setStoredToken("");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
