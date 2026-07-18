import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Package, PlusSquare, FileText, MapPinned,
  Search, Truck, Plug, BarChart3, MessagesSquare, ExternalLink, LogOut, TrendingUp, Lightbulb,
  Receipt, ShieldCheck, Smartphone, Users, Database, Sparkles, Video, Film, Table2,
  DollarSign, Music as MusicIcon, BookOpen, Archive, FileWarning, UserPlus, Globe, Factory, Wrench, Gamepad2, Truck as TrailerIcon,
  PieChart, FolderOpen, Settings as SettingsIcon, Award, IdCard, Activity, Calculator, KeyRound, Send, Briefcase, Megaphone, Building2, Trophy, Wallet, ShieldAlert, Ship, Rocket, Satellite, FlaskConical, Target, Zap
} from "lucide-react";
import { TennantLogo } from "./TennantLogo";
import { useAuth } from "../lib/auth";
import ChangePasswordDialog from "./ChangePasswordDialog";

// Each item declares which roles can see it. Admin always sees everything.
const NAV = [
  { to: "/dashboard", label: "Command Center", icon: LayoutDashboard, tid: "nav-dashboard", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/launch-plan", label: "Launch Runway", icon: Sparkles, tid: "nav-launch-plan", roles: ["admin"] },
  { to: "/workbook", label: "Truckload Booking Sheet", icon: Table2, tid: "nav-workbook", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/hudlink", label: "HUDLINK AI", icon: Sparkles, tid: "nav-hudlink", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/shipments", label: "Shipments", icon: Package, tid: "nav-shipments", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/book-load", label: "Book Load", icon: PlusSquare, tid: "nav-book-load", roles: ["admin", "dispatcher"] },
  { to: "/brokerage", label: "Brokerage · Accounting", icon: Calculator, tid: "nav-brokerage", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/sandbox", label: "Operation Sandbox", icon: FlaskConical, tid: "nav-sandbox", roles: ["admin", "dispatcher"] },
  { to: "/live-ops", label: "Live Ops Command", icon: Activity, tid: "nav-live-ops", roles: ["admin", "dispatcher"] },
  { to: "/sentinel", label: "Agent Sentinel", icon: ShieldAlert, tid: "nav-sentinel", roles: ["admin"] },
  { to: "/growth-copilot", label: "AI Growth Copilot", icon: Target, tid: "nav-growth-copilot", roles: ["admin", "dispatcher"] },
  { to: "/hotshot-sales", label: "Hot Shot TMS Sales", icon: Zap, tid: "nav-hotshot-sales", roles: ["admin"] },
  { to: "/route-optimizer", label: "Route Optimizer", icon: MapPinned, tid: "nav-route-optimizer", roles: ["admin", "dispatcher", "auditor"] },
  { to: "/launch-blast", label: "Launch Email Blast", icon: Megaphone, tid: "nav-launch-blast", roles: ["admin"] },
  { to: "/revenue", label: "Revenue Engine", icon: TrendingUp, tid: "nav-revenue", roles: ["admin", "dispatcher"] },
  { to: "/invoices", label: "Invoices", icon: Receipt, tid: "nav-invoices", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/workflow", label: "Workflow · Run-the-Load", icon: Activity, tid: "nav-workflow", roles: ["admin", "dispatcher"] },
  { to: "/factoring", label: "Factoring & ABL", icon: DollarSign, tid: "nav-factoring", roles: ["admin", "dispatcher"] },
  { to: "/cash-flow", label: "Cash Flow HUD", icon: Wallet, tid: "nav-cash-flow", roles: ["admin", "dispatcher"] },
  { to: "/triage", label: "AI Triage Console", icon: ShieldAlert, tid: "nav-triage", roles: ["admin", "dispatcher"] },
  { to: "/brand-kit", label: "Brand Kit", icon: Award, tid: "nav-brand-kit", roles: ["admin", "dispatcher"] },
  { to: "/margin-shield", label: "Margin Shield", icon: Calculator, tid: "nav-margin-shield", roles: ["admin", "dispatcher"] },
  { to: "/brokerage-ops-kpis", label: "Ops KPIs", icon: Calculator, tid: "nav-brokerage-ops-kpis", roles: ["admin", "dispatcher"] },
  { to: "/orisei-operations", label: "Orisei Operations", icon: Building2, tid: "nav-orisei-operations", roles: ["admin", "dispatcher"] },
  { to: "/international", label: "International · Ocean/Rail", icon: Ship, tid: "nav-international", roles: ["admin", "dispatcher", "auditor"] },
  { to: "/shipper-relations", label: "Shipper Relations", icon: UserPlus, tid: "nav-shipper-relations", roles: ["admin", "dispatcher"] },
  { to: "/claims-master", label: "Claims Master", icon: FileWarning, tid: "nav-claims-master", roles: ["admin", "dispatcher", "auditor"] },
  { to: "/qbr-studio", label: "QBR Studio", icon: TrendingUp, tid: "nav-qbr-studio", roles: ["admin", "dispatcher"] },
  { to: "/lighthouse-outreach", label: "Lighthouse Outreach", icon: Lightbulb, tid: "nav-lighthouse-outreach", roles: ["admin", "dispatcher"] },
  { to: "/boc3-compliance", label: "BOC-3 Compliance", icon: ShieldCheck, tid: "nav-boc3", roles: ["admin", "dispatcher", "auditor"] },
  { to: "/onboarding-checklist", label: "Onboarding Checklist", icon: Rocket, tid: "nav-onboarding", roles: ["admin"] },
  { to: "/broker-settings", label: "Broker Settings", icon: SettingsIcon, tid: "nav-broker-settings", roles: ["admin", "dispatcher"] },
  { to: "/competitive-tms", label: "Competitive TMS", icon: Trophy, tid: "nav-competitive-tms", roles: ["admin", "dispatcher"] },
  { to: "/enterprise-tms", label: "Enterprise TMS", icon: Globe, tid: "nav-enterprise-tms", roles: ["admin", "dispatcher"] },
  { to: "/research-analytics", label: "Research & Analytics", icon: PieChart, tid: "nav-research-analytics", roles: ["admin", "dispatcher", "auditor"] },
  { to: "/gtm-assets", label: "GTM Marketing", icon: Sparkles, tid: "nav-gtm-assets", roles: ["admin"] },
  { to: "/tracking", label: "Live Tracking", icon: MapPinned, tid: "nav-tracking", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/fleet-routing", label: "Fleet · Routing", icon: Satellite, tid: "nav-fleet-routing", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/carrier-integrations", label: "Carrier · EDI", icon: Plug, tid: "nav-carrier-integrations", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/dispatch-autopilot", label: "Dispatch Autopilot", icon: Rocket, tid: "nav-dispatch-autopilot", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/driver-console", label: "Driver Console", icon: Smartphone, tid: "nav-driver-console", roles: ["admin", "dispatcher"] },
  { to: "/driver-registry", label: "Drivers & Trailers", icon: IdCard, tid: "nav-driver-registry", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/equipment", label: "Equipment · Yard", icon: TrailerIcon, tid: "nav-equipment", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/carrier-rates", label: "Carrier Rates & FSC", icon: DollarSign, tid: "nav-carrier-rates", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/specialty-carriers", label: "Specialty Carriers", icon: Award, tid: "nav-specialty-carriers", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/freight-pay", label: "Freight Audit & Pay", icon: Receipt, tid: "nav-freight-pay", roles: ["admin", "auditor"] },
  { to: "/claims", label: "Payments & Claims", icon: FileWarning, tid: "nav-claims", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/suppliers", label: "Supplier Sourcing", icon: Factory, tid: "nav-suppliers", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/trade-compliance", label: "Trade Compliance", icon: Globe, tid: "nav-trade-compliance", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/machines", label: "Machine Catalog", icon: Wrench, tid: "nav-machines", roles: ["admin", "auditor", "dispatcher", "driver", "carrier"] },
  { to: "/arcade", label: "Arcade · Tournaments", icon: Gamepad2, tid: "nav-arcade", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/carrier-onboarding", label: "Carrier Onboarding", icon: ShieldCheck, tid: "nav-carrier-onboarding", roles: ["admin", "dispatcher"] },
  { to: "/carrier-invites", label: "Carrier Invites", icon: UserPlus, tid: "nav-carrier-invites", roles: ["admin"] },
  { to: "/documents", label: "Documents", icon: FileText, tid: "nav-documents", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/routing-guide", label: "Routing Guide", icon: BookOpen, tid: "nav-routing-guide", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/vault", label: "Document Vault", icon: Archive, tid: "nav-vault", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/document-archive", label: "Document Archive (Legal Hold)", icon: ShieldCheck, tid: "nav-document-archive", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/hs-lookup", label: "HS Code Lookup", icon: Search, tid: "nav-hs-lookup", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/trailers", label: "Trailer Specs", icon: Truck, tid: "nav-trailers", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/integrations", label: "Integrations", icon: Plug, tid: "nav-integrations", roles: ["admin"] },
  { to: "/connections", label: "Connections · Keys", icon: KeyRound, tid: "nav-connections", roles: ["admin"] },
  { to: "/provider-outreach", label: "Provider Outreach", icon: Send, tid: "nav-provider-outreach", roles: ["admin"] },
  { to: "/investor-boardroom", label: "Investor Boardroom", icon: Briefcase, tid: "nav-investor-boardroom", roles: ["admin"] },
  { to: "/investor-invite-links", label: "Investor Invite Links", icon: Briefcase, tid: "nav-investor-invite-links", roles: ["admin"] },
  { to: "/marketing-pack", label: "Marketing Pack", icon: Megaphone, tid: "nav-marketing-pack", roles: ["admin"] },
  { to: "/sap-sync", label: "SAP S/4HANA", icon: Database, tid: "nav-sap-sync", roles: ["admin", "dispatcher"] },
  { to: "/powerbi", label: "Power BI", icon: PieChart, tid: "nav-powerbi", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/sharepoint", label: "SharePoint", icon: FolderOpen, tid: "nav-sharepoint", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/webex", label: "Cisco Webex", icon: Video, tid: "nav-webex", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/reports", label: "KPI Reports", icon: BarChart3, tid: "nav-reports", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/chat", label: "Team Chat", icon: MessagesSquare, tid: "nav-chat", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/links", label: "Quick Links", icon: ExternalLink, tid: "nav-links", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/promo", label: "Launch Promo", icon: Film, tid: "nav-promo", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/music", label: "Music · Focus", icon: MusicIcon, tid: "nav-music", roles: ["admin", "auditor", "dispatcher", "driver"] },
  { to: "/manual", label: "User Manual", icon: BookOpen, tid: "nav-manual", roles: ["admin", "auditor", "dispatcher"] },
  { to: "/admin", label: "Admin · Dashboard", icon: Activity, tid: "nav-admin-dashboard", roles: ["admin"] },
  { to: "/about", label: "About · Business Plan", icon: Award, tid: "nav-about", roles: ["admin", "auditor", "dispatcher", "carrier"] },
  { to: "/admin/users", label: "Admin · Users", icon: Users, tid: "nav-admin-users", roles: ["admin"] },
  { to: "/admin/settings", label: "Admin · Settings", icon: SettingsIcon, tid: "nav-admin-settings", roles: ["admin"] },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const [showChangePw, setShowChangePw] = React.useState(false);

  // Owners (founding partners) see everything except user administration —
  // authorization control stays with the primary admin.
  const canSee = (n) => {
    const role = user?.role || "dispatcher";
    if (role === "admin") return true;
    if (role === "owner") return n.to !== "/admin/users";
    return !n.roles || n.roles.includes(role);
  };

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
        {NAV.filter(canSee).map(({ to, label, icon: Icon, tid }) => (
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
              <div className="text-[10px] font-mono text-cyan-400 truncate uppercase tracking-wider" data-testid="sidebar-role">{user.role}</div>
            </div>
            <button
              onClick={() => setShowChangePw(true)}
              data-testid="change-password-btn"
              className="p-1.5 rounded text-slate-400 hover:text-amber-300 hover:bg-amber-500/10"
              title="Change password"
            >
              <KeyRound size={15} />
            </button>
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
        <ChangePasswordDialog open={showChangePw} onOpenChange={setShowChangePw} />
        <a href="https://mpls-automation-hub.emergent.host/"
           target="_blank" rel="noopener noreferrer"
           data-testid="sidebar-jadeos-link"
           className="mt-3 px-3 py-2 rounded border border-white/5 text-[10px] font-mono uppercase tracking-[0.15em] text-slate-500 hover:text-cyan-300 hover:border-cyan-500/30 flex items-center justify-between transition">
          <span>JadeOS family ↗</span>
          <span className="text-cyan-500/60">Stack</span>
        </a>
      </div>
    </aside>
  );
}
