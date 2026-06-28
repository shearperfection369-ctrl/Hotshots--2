import React from "react";
import { Card } from "./ui/card";
import { Scale, AlertTriangle, ShieldAlert, Building2, FileWarning, BookOpen, Lock } from "lucide-react";
import { useBranding } from "../lib/branding";

/**
 * LegalCompliance — admin-only panel that surfaces the legal & compliance
 * implications of running the TMS against another company's brand and / or
 * ERP. The information below is general guidance — admins must consult
 * licensed counsel before using a third party's data in production.
 */
export default function LegalCompliance() {
  const { brand } = useBranding();
  const companyName = brand?.company_name || "Orisei Freight Solutions";
  const isDefault = brand?.is_default || brand?.brand_id === "orisei-freight";

  return (
    <Card className="hud-surface p-5" data-testid="admin-legal-compliance">
      <div className="flex items-center gap-2 mb-1">
        <Scale size={14} className="text-cyan-400" />
        <h3 className="font-display text-base font-bold text-white">Legal &amp; Compliance · ERP / Brand Data Use</h3>
        <span className="ml-2 px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider bg-yellow-500/10 text-yellow-300 border border-yellow-500/30">Informational · Not Legal Advice</span>
      </div>
      <p className="text-[11px] text-slate-400 leading-relaxed">
        Activating a non-built-in company brand (currently: <span className="text-cyan-300 font-mono">{companyName}</span>)
        introduces obligations around <em>data licensing, trademark use, privacy and ERP terms-of-service</em>.
        This panel summarizes the main risks so you can clear them with counsel before any production rollout.
      </p>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="legal-sections">

        <Section
          Icon={ShieldAlert}
          title="1 · Authorization to Use ERP Data"
          tone="red"
        >
          <p>
            Connecting to a customer&rsquo;s SAP, Oracle, Dynamics, NetSuite, Infor, Sage, Epicor, or IFS
            tenant <strong>requires a written agreement</strong> — typically a Master Services Agreement, Data Processing
            Addendum (GDPR / CCPA), and SAP / Oracle named-user license addendum for the integration account.
          </p>
          <Bullet>Cannot run ERP integrations against another company&rsquo;s production without their explicit consent.</Bullet>
          <Bullet>Sandbox / demo tenants are permitted only inside the vendor&rsquo;s developer license terms.</Bullet>
          <Bullet>The Emergent universal LLM key cannot be used to bypass enterprise SSO or data-residency controls.</Bullet>
        </Section>

        <Section
          Icon={Building2}
          title="2 · Trademark &amp; Brand Identity"
          tone="amber"
        >
          <p>
            The Company Theme generator surfaces <strong>publicly known facts</strong> (company name, color palette,
            flagship products) sourced from open data. Use of a third party&rsquo;s trademarked name, logo, or
            color trade-dress in a customer-facing build still requires written permission.
          </p>
          <Bullet>Internal demos / RFP responses · low risk if non-commercial and not distributed.</Bullet>
          <Bullet>External publication, marketing materials, or sales decks · written trademark license required.</Bullet>
          <Bullet>The generated profile is best-effort AI synthesis — verify any specific claim before quoting it.</Bullet>
        </Section>

        <Section
          Icon={FileWarning}
          title="3 · Data Privacy (GDPR, CCPA, PIPL, LGPD)"
          tone="amber"
        >
          <p>
            ERP records pulled into the TMS frequently include personal data
            (driver names, contact emails, signatures on PoDs). Treat the TMS as a <strong>Processor</strong>
            under GDPR Article 28 / CCPA Service-Provider rules and execute the matching DPA.
          </p>
          <Bullet>Retention limits, encryption-at-rest, breach notice within 72 hours.</Bullet>
          <Bullet>Cross-border transfers (US ↔ EU ↔ APAC) require SCCs or equivalent.</Bullet>
          <Bullet>Right-to-erasure: the TMS must honor delete requests within 30 days of receipt.</Bullet>
        </Section>

        <Section
          Icon={Lock}
          title="4 · ERP Vendor Terms (SAP, Oracle, MS, etc.)"
          tone="red"
        >
          <p>
            All major ERP vendors restrict <strong>indirect access</strong> — the use of a 3rd-party app
            (like this TMS) to read or write data on behalf of a human user.  Each vendor has a different metering model:
          </p>
          <Bullet><strong>SAP</strong> · Digital Access (document-based) since 2018. Each created sales order, delivery, or invoice may count toward a paid license.</Bullet>
          <Bullet><strong>Oracle</strong> · Application User vs. Application Read-Only license; integrations need a Restricted-Use license.</Bullet>
          <Bullet><strong>Microsoft D365</strong> · App User license required for non-interactive Dataverse access.</Bullet>
          <Bullet><strong>NetSuite, Infor, Sage</strong> · Integration users billed separately from named users.</Bullet>
        </Section>

        <Section
          Icon={AlertTriangle}
          title="5 · AI / LLM Disclosures"
          tone="amber"
        >
          <p>
            HUDLINK AI and the Company-Theme generator both send context to a hosted LLM (Claude Sonnet
            via Emergent). Most enterprise procurement teams now require an <strong>AI usage disclosure</strong>:
          </p>
          <Bullet>Inform users their prompts may be processed by a third-party LLM provider.</Bullet>
          <Bullet>Strip PII / trade secrets from prompts; do not paste raw HR or financial data.</Bullet>
          <Bullet>Log every LLM call for audit trail (the Admin Dashboard exposes the count).</Bullet>
        </Section>

        <Section
          Icon={BookOpen}
          title="6 · Recommended Workflow"
          tone="green"
        >
          <p>Before going live with a non-company brand against real customer ERP data:</p>
          <Bullet><strong>1.</strong> Customer signs an MSA + DPA with your organization.</Bullet>
          <Bullet><strong>2.</strong> Customer&rsquo;s IT issues a service account with read-only or scoped write permissions.</Bullet>
          <Bullet><strong>3.</strong> Customer&rsquo;s legal reviews your AI usage disclosure and trademark plan.</Bullet>
          <Bullet><strong>4.</strong> ERP integration tested in their sandbox tenant first, then promoted to PROD.</Bullet>
          <Bullet><strong>5.</strong> Quarterly access review &amp; key rotation; revoke on contract end.</Bullet>
        </Section>

      </div>

      {!isDefault && (
        <div className="mt-4 p-3 rounded-md border border-amber-500/30 bg-amber-500/5" data-testid="legal-active-brand-warning">
          <div className="flex items-center gap-2 text-amber-300 text-xs font-bold">
            <AlertTriangle size={12} /> Active Brand: {companyName}
          </div>
          <div className="text-[11px] text-slate-300 mt-1.5 leading-relaxed">
            You are currently themed as {companyName}. Confirm with counsel that you have a signed agreement
            covering data, trademark, and ERP indirect-access use before any external demo or production deployment.
          </div>
        </div>
      )}

      <div className="mt-3 text-[10px] font-mono text-slate-500 leading-relaxed">
        Source: SAP indirect-access licensing model (2018) · Oracle Master Agreement §B5 · Microsoft Customer Agreement §G2 ·
        GDPR Articles 28 &amp; 32 · CCPA / CPRA §1798.140 (Service Provider). This panel is informational and is not legal advice.
      </div>
    </Card>
  );
}

function Section({ Icon, title, tone, children }) {
  const tones = {
    red:    { border: "border-red-500/30",    bg: "bg-red-500/5",    icon: "text-red-300" },
    amber:  { border: "border-amber-500/30",  bg: "bg-amber-500/5",  icon: "text-amber-300" },
    green:  { border: "border-emerald-500/30", bg: "bg-emerald-500/5", icon: "text-emerald-300" },
  }[tone] || { border: "border-white/10", bg: "bg-white/[0.02]", icon: "text-cyan-300" };
  return (
    <div className={`p-3 rounded-md border ${tones.border} ${tones.bg}`}>
      <div className={`flex items-center gap-2 ${tones.icon} text-xs font-bold mb-1.5`}>
        <Icon size={12} /> {title}
      </div>
      <div className="text-[11px] text-slate-300 leading-relaxed space-y-1">{children}</div>
    </div>
  );
}

function Bullet({ children }) {
  return (
    <div className="flex gap-2 text-[11px] text-slate-300">
      <span className="text-cyan-400 shrink-0">·</span>
      <div className="leading-relaxed">{children}</div>
    </div>
  );
}
