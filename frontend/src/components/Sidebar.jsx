import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Package, PlusSquare, FileText, MapPinned,
  Search, Truck, Plug, BarChart3, MessagesSquare, ExternalLink, LogOut,
  Receipt, ShieldCheck, Smartphone
} from "lucide-react";
import { TennantLogo } from "./TennantLogo";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/dashboard", label: "Command Center", icon: LayoutDashboard, tid: "nav-dashboard" },
  { to: "/shipments", label: "Shipments", icon: Package, tid: "nav-shipments" },
  { to: "/book-load", label: "Book Load", icon: PlusSquare, tid: "nav-book-load" },
  { to: "/tracking", label: "Live Tracking", icon: MapPinned, tid: "nav-tracking" },
  { to: "/driver-console", label: "Driver Console", icon: Smartphone, tid: "nav-driver-console" },
  { to: "/freight-pay", label: "Freight Audit & Pay", icon: Receipt, tid: "nav-freight-pay" },
  { to: "/carrier-onboarding", label: "Carrier Onboarding", icon: ShieldCheck, tid: "nav-carrier-onboarding" },
  { to: "/documents", label: "Documents", icon: FileText, tid: "nav-documents" },
  { to: "/hs-lookup", label: "HS Code Lookup", icon: Search, tid: "nav-hs-lookup" },
  { to: "/trailers", label: "Trailer Specs", icon: Truck, tid: "nav-trailers" },
  { to: "/integrations", label: "Integrations", icon: Plug, tid: "nav-integrations" },
  { to: "/reports", label: "KPI Reports", icon: BarChart3, tid: "nav-reports" },
  { to: "/chat", label: "Team Chat", icon: MessagesSquare, tid: "nav-chat" },
  { to: "/links", label: "Quick Links", icon: ExternalLink, tid: "nav-links" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="hidden md:flex md:w-60 lg:w-64 flex-col h-screen sticky top-0 border-r border-white/5 bg-[#0B0E14]/95 backdrop-blur-xl z-40" data-testid="sidebar">
      <div className="px-5 py-5 border-b border-white/5 flex items-center gap-3">
        <TennantLogo size="md" />
        <div>
          <div className="font-display text-xs font-bold tracking-[0.25em] text-cyan-400 uppercase">TMS</div>
          <div className="text-[10px] font-mono text-slate-500 tracking-wider">v1.0 · LIVE</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.2em] px-3 mb-2">Operations</div>
        {NAV.map(({ to, label, icon: Icon, tid }) => (
          <NavLink
            key={to}
            to={to}
            data-testid={tid}
            className={({ isActive }) =>
              `group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-all ${
                isActive
                  ? "bg-cyan-500/10 text-cyan-300 border-l-2 border-cyan-400"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.03] border-l-2 border-transparent"
              }`
            }
          >
            <Icon size={16} strokeWidth={1.6} />
            <span className="font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/5 p-3">
        {user && (
          <div className="flex items-center gap-3 px-2 py-2 rounded-md bg-white/[0.02]" data-testid="sidebar-user">
            {user.picture ? (
              <img src={user.picture} alt={user.name} className="w-8 h-8 rounded-full" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-cyan-500 text-black flex items-center justify-center font-bold text-sm">
                {user.name?.[0]}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-sm text-white truncate" data-testid="sidebar-username">{user.name}</div>
              <div className="text-[10px] font-mono text-slate-500 truncate">{user.email}</div>
            </div>
            <button
              onClick={logout}
              data-testid="logout-btn"
              className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-red-500/10"
              title="Log out"
            >
              <LogOut size={15} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
