import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LayoutDashboard, Package, Truck, Receipt, Users, Settings, LifeBuoy, LogOut, Zap } from "lucide-react";
import { tenantApi } from "./tenantApi";
import TenantDashboard from "./TenantDashboard";
import TenantLoads from "./TenantLoads";
import TenantCarriers from "./TenantCarriers";
import TenantInvoices from "./TenantInvoices";
import TenantTeam from "./TenantTeam";
import TenantSettings from "./TenantSettings";
import TenantHelp from "./TenantHelp";

export const TenantCtx = createContext(null);
export const useTenant = () => useContext(TenantCtx);

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, comp: TenantDashboard },
  { id: "loads", label: "Loads", icon: Package, comp: TenantLoads },
  { id: "carriers", label: "Carriers", icon: Truck, comp: TenantCarriers },
  { id: "invoices", label: "Invoices", icon: Receipt, comp: TenantInvoices },
  { id: "team", label: "Team", icon: Users, comp: TenantTeam, roles: ["admin"] },
  { id: "settings", label: "Settings", icon: Settings, comp: TenantSettings, roles: ["admin"] },
  { id: "help", label: "Help", icon: LifeBuoy, comp: TenantHelp },
];

export default function TenantPortal() {
  const { slug, tab = "dashboard" } = useParams();
  const nav = useNavigate();
  const [me, setMe] = useState(null);
  const [brand, setBrand] = useState(null);
  const api = tenantApi(slug);

  const loadBrand = useCallback(async () => {
    try { const { data } = await api.get("/branding/public"); setBrand(data); } catch (_) {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/auth/me"); setMe(data); }
      catch (_) { nav(`/t/${slug}/login`); return; }
      loadBrand();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const logout = () => { localStorage.removeItem(`hs_token_${slug}`); nav(`/t/${slug}/login`); };

  if (!me || !brand) return <div className="min-h-screen bg-[#0D1117] grid place-items-center text-slate-500 font-mono text-sm">Loading workspace…</div>;

  const p = brand.primary_color || "#F59E0B";
  const a = brand.accent_color || "#22D3EE";
  const visibleTabs = TABS.filter((t) => !t.roles || t.roles.includes(me.role));
  const activeTab = visibleTabs.find((t) => t.id === tab);
  if (!activeTab) {
    nav(`/t/${slug}/app`, { replace: true });
    return null;
  }
  const ActiveComp = activeTab.comp;

  return (
    <TenantCtx.Provider value={{ slug, api, me, brand, primary: p, accent: a, refreshBrand: loadBrand }}>
      <div className="min-h-screen bg-[#0D1117] text-slate-100 flex" data-testid="tenant-portal">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 border-r border-white/5 flex flex-col sticky top-0 h-screen">
          <div className="p-4 flex items-center gap-2.5 border-b border-white/5">
            {brand.logo_b64 ? (
              <img src={brand.logo_b64} alt="logo" className="h-9 w-9 rounded-lg object-contain bg-white/5" data-testid="tenant-portal-logo" />
            ) : (
              <div className="h-9 w-9 rounded-lg grid place-items-center" style={{ background: p }}><Zap size={16} className="text-black" /></div>
            )}
            <div className="min-w-0">
              <div className="font-black text-sm truncate" data-testid="tenant-portal-company">{brand.company_name}</div>
              <div className="text-[9px] font-mono uppercase tracking-widest text-slate-500">Hot Shot TMS</div>
            </div>
          </div>
          <nav className="flex-1 p-2 space-y-1">
            {visibleTabs.map((t) => (
              <button key={t.id} onClick={() => nav(`/t/${slug}/app/${t.id}`)} data-testid={`tenant-nav-${t.id}`}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-semibold transition-colors ${tab === t.id ? "text-black" : "text-slate-400 hover:text-white hover:bg-white/5"}`}
                      style={tab === t.id ? { background: p } : {}}>
                <t.icon size={15} /> {t.label}
              </button>
            ))}
          </nav>
          <div className="p-3 border-t border-white/5">
            <div className="text-xs text-slate-300 font-semibold truncate">{me.name}</div>
            <div className="text-[10px] font-mono uppercase" style={{ color: a }}>{me.role}</div>
            <button onClick={logout} data-testid="tenant-logout-btn"
                    className="mt-2 w-full flex items-center gap-2 text-xs text-slate-500 hover:text-red-400 px-1 py-1">
              <LogOut size={12} /> Sign out
            </button>
          </div>
        </aside>
        <main className="flex-1 min-w-0 p-5 md:p-8 overflow-y-auto">
          <ActiveComp />
        </main>
      </div>
    </TenantCtx.Provider>
  );
}
