import React from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import DataStatusBanner from "./DataStatusBanner";
import OpsAlertOverlay from "./OpsAlertOverlay";

export default function Layout() {
  return (
    <div className="min-h-screen flex bg-[#0B0E14] text-slate-100 hud-grid-bg">
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col">
        <DataStatusBanner />
        <Outlet />
      </main>
      <OpsAlertOverlay />
    </div>
  );
}
