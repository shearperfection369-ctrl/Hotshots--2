import React from "react";
import "@/index.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import Login from "@/pages/Login";
import About from "@/pages/About";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Shipments from "@/pages/Shipments";
import BookLoad from "@/pages/BookLoad";
import Documents from "@/pages/Documents";
import Tracking from "@/pages/Tracking";
import HSLookup from "@/pages/HSLookup";
import Trailers from "@/pages/Trailers";
import Integrations from "@/pages/Integrations";
import Connections from "@/pages/Connections";
import ProviderOutreach from "@/pages/ProviderOutreach";
import InvestorBoardroom from "@/pages/InvestorBoardroom";
import MarketingPack from "@/pages/MarketingPack";
import Landing from "@/pages/Landing";
import Services from "@/pages/Services";
import Lanes from "@/pages/Lanes";
import Contact from "@/pages/Contact";
import PublicInvestors from "@/pages/PublicInvestors";
import TmsInvestors from "@/pages/TmsInvestors";
import TmsInviteLinks from "@/pages/TmsInviteLinks";
import MarginShield from "@/pages/MarginShield";
import BrokerageOpsKpis from "@/pages/BrokerageOpsKpis";
import OriseiOperations from "@/pages/OriseiOperations";
import CustomerPortal from "@/pages/CustomerPortal";
import CompetitiveTms from "@/pages/CompetitiveTms";
import PublicRfpBoard from "@/pages/PublicRfpBoard";
import DriverPwa from "@/pages/DriverPwa";
import Reports from "@/pages/Reports";
import Chat from "@/pages/Chat";
import QuickLinks from "@/pages/QuickLinks";
import FreightPay from "@/pages/FreightPay";
import CarrierOnboarding from "@/pages/CarrierOnboarding";
import DriverConsole from "@/pages/DriverConsole";
import DriverMobile from "@/pages/DriverMobile";
import AdminUsers from "@/pages/AdminUsers";
import SapSync from "@/pages/SapSync";
import AIAssistant from "@/pages/AIAssistant";
import Webex from "@/pages/Webex";
import PromoVideo from "@/pages/PromoVideo";
import Workbook from "@/pages/Workbook";
import CarrierRates from "@/pages/CarrierRates";
import Music from "@/pages/Music";
import Manual from "@/pages/Manual";
import Vault from "@/pages/Vault";
import Claims from "@/pages/Claims";
import CarrierInvites from "@/pages/CarrierInvites";
import AcceptInvite from "@/pages/AcceptInvite";
import TradeCompliance from "@/pages/TradeCompliance";
import SupplierSourcing from "@/pages/SupplierSourcing";
import Arcade from "@/pages/Arcade";
import Machines from "@/pages/Machines";
import Equipment from "@/pages/Equipment";
import RoutingGuide from "@/pages/RoutingGuide";
import MicrosoftCopilot from "@/pages/MicrosoftCopilot";
import PowerBI from "@/pages/PowerBI";
import SharePoint from "@/pages/SharePoint";
import AdminSettings from "@/pages/AdminSettings";
import AdminDashboard from "@/pages/AdminDashboard";
import Brokerage from "@/pages/Brokerage";
import SpecialtyCarriers from "@/pages/SpecialtyCarriers";
import DriverRegistry from "@/pages/DriverRegistry";
import WellnessNudges from "@/components/WellnessNudges";
import { ThemeProvider } from "@/lib/theme";
import { BrandingProvider } from "@/lib/branding";
import { MusicProvider } from "@/lib/music";
import MiniPlayer from "@/components/MiniPlayer";
import DeployHealthBanner from "@/components/DeployHealthBanner";

function RootRedirect() {
  // Public root: just show the Landing page. Authenticated operators have
  // /dashboard in the sidebar / can sign in via the nav. This way the public
  // root of the domain is the marketing site, exactly as a customer expects.
  return <Landing />;
}

function AppRouter() {
  const location = useLocation();
  // Synchronous check (before useEffects) — handle Emergent OAuth fragment
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<Login />} />
      <Route path="/home" element={<Landing />} />
      <Route path="/services" element={<Services />} />
      <Route path="/lanes" element={<Lanes />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/investors" element={<PublicInvestors />} />
      <Route path="/press" element={<PublicInvestors />} />
      <Route path="/exec-summary" element={<PublicInvestors />} />
      <Route path="/tms-investors" element={<TmsInvestors />} />
      <Route path="/tms-pitch" element={<TmsInvestors />} />
      <Route path="/demo" element={<TmsInvestors />} />
      <Route path="/about" element={<About />} />
      <Route path="/marketing" element={<About />} />
      <Route path="/landing" element={<About />} />
      <Route path="/accept-invite" element={<AcceptInvite />} />
      <Route path="/customer-portal" element={<CustomerPortal />} />
      <Route path="/rfp-board" element={<PublicRfpBoard />} />
      <Route path="/driver" element={<DriverPwa />} />
      {/* Driver mobile is auth-free */}
      <Route path="/driver" element={<DriverMobile />} />
      <Route path="/driver/:shipmentId" element={<DriverMobile />} />

      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/shipments" element={<Shipments />} />
        <Route path="/book-load" element={<BookLoad />} />
        <Route path="/brokerage" element={<Brokerage />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/tracking" element={<Tracking />} />
        <Route path="/live-tracking" element={<Tracking />} />
        <Route path="/hs-lookup" element={<HSLookup />} />
        <Route path="/trailers" element={<Trailers />} />
        <Route path="/integrations" element={<Integrations />} />
        <Route path="/connections" element={<Connections />} />
        <Route path="/provider-outreach" element={<ProviderOutreach />} />
        <Route path="/investor-boardroom" element={<InvestorBoardroom />} />
        <Route path="/investor-invite-links" element={<TmsInviteLinks />} />
        <Route path="/margin-shield" element={<MarginShield />} />
        <Route path="/brokerage-ops-kpis" element={<BrokerageOpsKpis />} />
        <Route path="/orisei-operations" element={<OriseiOperations />} />
        <Route path="/competitive-tms" element={<CompetitiveTms />} />
        <Route path="/marketing-pack" element={<MarketingPack />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/links" element={<QuickLinks />} />
        <Route path="/freight-pay" element={<FreightPay />} />
        <Route path="/carrier-onboarding" element={<CarrierOnboarding />} />
        <Route path="/driver-console" element={<DriverConsole />} />
        <Route path="/sap-sync" element={<SapSync />} />
        <Route path="/ai-assistant" element={<AIAssistant />} />
        <Route path="/hudlink" element={<AIAssistant />} />
        <Route path="/copilot" element={<MicrosoftCopilot />} />
        <Route path="/microsoft-copilot" element={<MicrosoftCopilot />} />
        <Route path="/routing-guide" element={<RoutingGuide />} />
        <Route path="/legacy-hudlink" element={<AIAssistant />} />
        <Route path="/powerbi" element={<PowerBI />} />
        <Route path="/sharepoint" element={<SharePoint />} />
        <Route path="/admin/settings" element={<AdminSettings />} />
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/specialty-carriers" element={<SpecialtyCarriers />} />
        <Route path="/driver-registry" element={<DriverRegistry />} />
        <Route path="/webex" element={<Webex />} />
        <Route path="/promo" element={<PromoVideo />} />
        <Route path="/workbook" element={<Workbook />} />
        <Route path="/carrier-rates" element={<CarrierRates />} />
        <Route path="/music" element={<Music />} />
        <Route path="/manual" element={<Manual />} />
        <Route path="/vault" element={<Vault />} />
        <Route path="/claims" element={<Claims />} />
        <Route path="/carrier-invites" element={<CarrierInvites />} />
        <Route path="/trade-compliance" element={<TradeCompliance />} />
        <Route path="/suppliers" element={<SupplierSourcing />} />
        <Route path="/machines" element={<Machines />} />
        <Route path="/equipment" element={<Equipment />} />
        <Route path="/arcade" element={<Arcade />} />
        <Route path="/admin/users" element={<AdminUsers />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <BrandingProvider>
            <MusicProvider>
              <DeployHealthBanner />
              <AppRouter />
              <MiniPlayer />
              <WellnessNudges />
              <Toaster
                theme="dark"
                position="bottom-right"
                toastOptions={{
                  style: { background: "#131821", border: "1px solid rgba(0,229,255,0.3)", color: "#F8FAFC" }
                }}
              />
            </MusicProvider>
          </BrandingProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
