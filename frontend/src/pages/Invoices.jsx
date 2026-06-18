import React from "react";
import Topbar from "@/components/Topbar";
import { Card } from "@/components/ui/card";
import { FileText, ShieldCheck, ExternalLink } from "lucide-react";
import { InvoicesTab } from "./BrokerSettings";

/**
 * /invoices — dedicated top-level Invoice Generator page.
 *
 * Surfaces the InvoicesTab that previously lived only inside Broker Settings,
 * so the founder can find the invoice generator with one click from the
 * sidebar instead of two-deep through a settings tab.
 */
export default function Invoices() {
  return (
    <>
      <Topbar
        title="Invoices"
        subtitle="Branded invoice generator · multi-load consolidated billing · auto-archived to legal vault"
      />
      <div className="p-4 md:p-6 space-y-5">
        {/* Onboarding banner */}
        <Card className="p-4 bg-gradient-to-br from-cyan-950/40 via-slate-950 to-slate-950 border-cyan-400/30">
          <div className="flex items-start gap-3">
            <FileText className="text-cyan-300 shrink-0 mt-0.5" size={26} />
            <div className="flex-1">
              <div className="text-sm font-semibold text-cyan-100">
                Generate branded invoices in 30 seconds
              </div>
              <div className="text-xs text-slate-400 mt-1">
                Click <b className="text-cyan-300">New Branded Invoice</b>, pick a customer,
                check the bookings to consolidate, set payment terms, save. The PDF is auto-stamped
                with your active brand (Orisei + Califia), auto-archived to the immutable 7-year
                Document Vault, and ready to email or factor.
              </div>
              <div className="text-[11px] text-slate-500 mt-2 flex items-center gap-3 flex-wrap">
                <span className="inline-flex items-center gap-1 text-emerald-300"><ShieldCheck size={11}/> Immutable copy retained for 7 yrs</span>
                <a href="/document-archive?doc_type=COMMERCIAL_INVOICE"
                   className="inline-flex items-center gap-1 text-amber-300 hover:underline">
                  <ExternalLink size={11}/> View invoice version history
                </a>
              </div>
            </div>
          </div>
        </Card>
        <InvoicesTab />
      </div>
    </>
  );
}
