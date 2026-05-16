import React from "react";
import { Link, useLocation } from "react-router-dom";

const ORISEI_GOLD = "#C9A24A";

/**
 * Shared sticky public-site navigation. Used by /home, /services, /lanes,
 * /contact, /about. Highlights the active route.
 */
export default function PublicNav({ brand }) {
  const loc = useLocation();
  const items = [
    { to: "/home",     label: "Home" },
    { to: "/services", label: "Services" },
    { to: "/lanes",    label: "Preferred Lanes" },
    { to: "/about",    label: "About" },
    { to: "/contact",  label: "Contact" },
  ];
  const isActive = (to) =>
    loc.pathname === to || (to === "/home" && loc.pathname === "/");
  return (
    <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#0B1320]/85 border-b border-white/5">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-3">
        <Link to="/home" className="flex items-center gap-3" data-testid="public-nav-logo">
          <img src={brand?.logo_url || "/brand/orisei_logo.png"} alt="Orisei" className="h-9 w-9 rounded" />
          <span className="font-display font-black text-lg tracking-tight" style={{ color: ORISEI_GOLD }}>
            ORISEI
            <span className="ml-2 text-xs font-mono text-slate-400 uppercase tracking-[0.2em]">Freight Solutions</span>
          </span>
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-300">
          {items.map((it) => (
            <Link
              key={it.to}
              to={it.to}
              data-testid={`public-nav-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
              className="transition-colors hover:text-white"
              style={isActive(it.to) ? { color: ORISEI_GOLD } : {}}
            >
              {it.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link
            to="/home#quote"
            data-testid="public-nav-quote-cta"
            className="hidden sm:inline-flex text-xs font-mono uppercase tracking-wider px-4 py-2 rounded-md font-bold"
            style={{ background: ORISEI_GOLD, color: "#0E3A6B" }}
          >
            Get a Quote
          </Link>
          <Link
            to="/login"
            data-testid="public-nav-signin"
            className="text-xs font-mono uppercase tracking-wider px-3 py-2 rounded-md border border-white/10 hover:border-[#C9A24A]/60 hover:text-[#C9A24A] transition-colors"
          >
            Sign-In →
          </Link>
        </div>
      </div>
    </header>
  );
}
