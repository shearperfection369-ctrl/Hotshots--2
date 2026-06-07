import React from "react";
import { Button } from "../components/ui/button";
import { TennantLogo } from "../components/TennantLogo";
import { Truck, Plane, Ship, Package, Train, MapPinned } from "lucide-react";
import { TENNANT_LOGO_URL } from "../lib/api";

export default function Login() {
  const handleSignIn = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] text-white grid lg:grid-cols-2 hud-grid-bg" data-testid="login-page">
      {/* Left visual panel */}
      <div className="hidden lg:flex relative items-center justify-center p-12 overflow-hidden border-r border-white/5">
        <div className="absolute inset-0 opacity-30">
          <img
            src={TENNANT_LOGO_URL}
            alt="Tennant equipment"
            className="w-full h-full object-cover"
          />
        </div>
        <div className="absolute inset-0 bg-gradient-to-br from-[#0B0E14]/95 via-[#0B0E14]/85 to-cyan-950/40"></div>
        <div className="relative z-10 max-w-md">
          <TennantLogo size="lg" />
          <h1 className="font-display text-5xl font-black mt-8 leading-none tracking-tighter">
            Mission-Control<br />
            <span className="text-cyan-400">Transportation</span>
          </h1>
          <p className="text-slate-400 mt-6 leading-relaxed">
            A unified command center for Tennant Companies. Track every load — TL, LTL, parcel, ocean, air, rail — across Louisville, Holland, and Golden Valley.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-4">
            {[
              { Icon: Truck, label: "TL / LTL" },
              { Icon: Plane, label: "Air Freight" },
              { Icon: Ship, label: "Ocean K+N" },
              { Icon: Package, label: "Parcel" },
              { Icon: Train, label: "Rail" },
              { Icon: MapPinned, label: "Live Map" },
            ].map(({ Icon, label }) => (
              <div key={label} className="flex flex-col items-center gap-2 p-3 rounded-md border border-white/5 bg-white/[0.02]">
                <Icon size={20} className="text-cyan-400" strokeWidth={1.5} />
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right login panel */}
      <div className="flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex justify-center mb-8">
            <TennantLogo size="lg" />
          </div>
          <div className="text-[10px] font-mono text-cyan-400 tracking-[0.3em] uppercase mb-3">Secure Access</div>
          <h2 className="font-display text-3xl font-bold tracking-tight">Sign in to TMS</h2>
          <p className="text-sm text-slate-400 mt-3">
            Authorized Tennant Companies personnel only. Sign in with your Google account.
          </p>

          <Button
            onClick={handleSignIn}
            data-testid="google-signin-btn"
            className="w-full mt-8 bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_24px_rgba(0,229,255,0.35)] hover:shadow-[0_0_36px_rgba(0,229,255,0.55)] transition-all py-6 text-base"
          >
            <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
              <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </Button>

          <div className="mt-6 text-[11px] text-slate-500 font-mono leading-relaxed">
            By signing in, you agree to Tennant&apos;s acceptable-use policy.
            Sessions are encrypted and expire after 7 days of inactivity.
          </div>

          <div className="mt-12 pt-6 border-t border-white/5">
            <div className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.2em] mb-3">Capacity</div>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>250 users · 3 facilities · 6 modes</span>
              <span className="text-cyan-400 mono">v1.0</span>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-white/5 text-[10px] font-mono text-slate-500 flex items-center justify-between"
               data-testid="login-jadeos-ribbon">
            <span>Part of the <span className="text-cyan-400">JadeOS</span> stack</span>
            <a href="https://mpls-automation-hub.emergent.host/"
               target="_blank" rel="noopener noreferrer"
               data-testid="login-jadeos-link"
               className="text-cyan-400 hover:underline tracking-wider">
              See the full thesis →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
