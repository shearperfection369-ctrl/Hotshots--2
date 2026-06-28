"""routes.onboarding_checklist — Brokerage launch checklist.

Walks a freight-brokerage founder through every step required to legally
operate: MC filing, BOC-3, FMCSA bond, UCR, IFTA, insurance, and the
3rd-party API keys our TMS expects (Resend, FMCSA SAFER, R2, etc.).

State is per-brand and tracked in `onboarding_checklist_state`. Items are
static — only the `completed` boolean toggles per item.

Endpoints — all mounted under /api/onboarding/*:
  GET  /checklist                       · grouped items with current state
  POST /checklist/{item_id}/toggle      · flip completed (auth)
  POST /checklist/reset                 · admin: clear all completion state
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, Depends, HTTPException


# Comprehensive launch checklist for a US-based freight brokerage. Each
# item lives in one of the groups below; the UI groups them visually.
CHECKLIST: List[Dict[str, Any]] = [
    # ---- 1. Legal / Entity ----
    {"id": "entity-llc",          "group": "Legal / Entity", "title": "Form LLC (or chosen entity) with Sec of State",
        "instruction": "File articles of organization with your state. Most brokers use Wyoming, Delaware, or home state. Expect $50–$500 filing fee + $50/yr.",
        "link": "https://www.sba.gov/business-guide/launch-your-business/register-your-business", "priority": "P0"},
    {"id": "ein-irs",             "group": "Legal / Entity", "title": "Get EIN from IRS",
        "instruction": "Apply free online at irs.gov. Required for bank account, taxes, MC application. Takes ~15 minutes.",
        "link": "https://www.irs.gov/businesses/small-businesses-self-employed/apply-for-an-employer-identification-number-ein-online", "priority": "P0"},
    {"id": "ein-bank",            "group": "Legal / Entity", "title": "Open business bank account",
        "instruction": "Mercury, Relay, or local credit union. Need EIN + entity formation docs. Separate ops/payroll/factoring escrow accounts.",
        "link": "https://mercury.com", "priority": "P0"},

    # ---- 2. FMCSA / Authority ----
    {"id": "mc-application",      "group": "FMCSA Authority", "title": "File MC Authority (Form OP-1) with FMCSA",
        "instruction": "$300 non-refundable filing fee. Choose 'Property Broker'. Processing takes 4–6 weeks. Once issued, you'll get an MC number + USDOT number.",
        "link": "https://www.fmcsa.dot.gov/registration/get-mc-number-authority-operate", "priority": "P0"},
    {"id": "boc3",                "group": "FMCSA Authority", "title": "File BOC-3 process agent",
        "instruction": "Designate a process agent in every US state. Services like blanket BOC-3 ($25–50) handle all 50 in one filing.",
        "link": "https://www.fmcsa.dot.gov/registration/process-agents", "priority": "P0"},
    {"id": "fmcsa-bond-bmc-84",   "group": "FMCSA Authority", "title": "Secure $75,000 surety bond (BMC-84) or trust (BMC-85)",
        "instruction": "Required by FMCSA. Bond runs $900–$10,000+/yr depending on credit. Filed electronically by the surety.",
        "link": "https://www.fmcsa.dot.gov/registration/financial-responsibility", "priority": "P0"},
    {"id": "ucr",                 "group": "FMCSA Authority", "title": "Pay annual UCR (Unified Carrier Registration) fee",
        "instruction": "$76/yr base fee for brokers in 2026. Renew by Jan 1 every year.",
        "link": "https://www.ucr.gov", "priority": "P1"},

    # ---- 3. Insurance ----
    {"id": "ins-contingent-cargo","group": "Insurance",       "title": "Contingent Cargo coverage ($100K+ minimum)",
        "instruction": "Backstops carrier's primary cargo coverage. $1,200–$2,500/yr. Higher limits ($250K+) needed for high-value freight.",
        "link": "https://www.reliance-partners.com", "priority": "P0"},
    {"id": "ins-contingent-auto", "group": "Insurance",       "title": "Contingent Auto Liability ($1M)",
        "instruction": "Covers gaps if a carrier's auto policy fails. $400–$1,000/yr. Many shippers require this on the BPA.",
        "link": "https://www.reliance-partners.com", "priority": "P1"},
    {"id": "ins-e-o",             "group": "Insurance",       "title": "Errors & Omissions ($1M)",
        "instruction": "Protects against booking mistakes (wrong carrier, miscommunicated rate, etc.). $800–$2,500/yr.",
        "link": "https://www.reliance-partners.com", "priority": "P1"},
    {"id": "ins-general-liability","group": "Insurance",      "title": "General Liability ($1M / $2M aggregate)",
        "instruction": "Standard business policy. Bundles with E&O at most logistics insurance brokers.",
        "link": "https://www.thehartford.com", "priority": "P1"},

    # ---- 4. Tools / Subscriptions ----
    {"id": "loadboard-dat",       "group": "Tools & Subscriptions", "title": "DAT load board subscription (Power Broker tier)",
        "instruction": "Industry standard for finding loads + carriers. $295/mo for Power Broker tier. RateView analytics is worth the upgrade.",
        "link": "https://www.dat.com/loadboards", "priority": "P0"},
    {"id": "loadboard-truckstop","group": "Tools & Subscriptions", "title": "Truckstop.com subscription",
        "instruction": "Secondary load board. $150–$300/mo. Heavy in flatbed + reefer; good complement to DAT.",
        "link": "https://www.truckstop.com", "priority": "P1"},
    {"id": "carrier-vetting",     "group": "Tools & Subscriptions", "title": "Carrier vetting subscription (Highway / RMIS / Carrier411)",
        "instruction": "Real-time MC/insurance/safety + identity check. Highway ~$300/mo. Required for serious chargeback protection.",
        "link": "https://highway.com", "priority": "P1"},
    {"id": "factoring",           "group": "Tools & Subscriptions", "title": "Set up factoring or AR financing line",
        "instruction": "Triumph Business Capital, OTR Capital, or RTS. Typical 1.5–3% factoring fee. Improves cash flow from 30→1 day.",
        "link": "https://www.triumphbusinesscapital.com", "priority": "P1"},

    # ---- 5. API Keys / Integrations (for THIS TMS) ----
    {"id": "key-resend",          "group": "API Keys for TMS", "title": "Resend API key (transactional email)",
        "instruction": "Free up to 3K emails/mo, then $20/mo. Required for shipper intake emails, carrier rate-cons, BOL receipts.",
        "link": "https://resend.com/api-keys", "priority": "P0",
        "env_var": "RESEND_API_KEY"},
    {"id": "key-fmcsa-saferweb",  "group": "API Keys for TMS", "title": "FMCSA SAFER webKey (carrier verification)",
        "instruction": "Free. Lets the TMS auto-verify carrier safety ratings + insurance + authority status when you add a new carrier.",
        "link": "https://mobile.fmcsa.dot.gov/qc/services/safer-web-services-overview", "priority": "P0",
        "env_var": "FMCSA_SAFER_WEBKEY"},
    {"id": "key-cloudflare-r2",   "group": "API Keys for TMS", "title": "Cloudflare R2 access keys (immutable doc storage)",
        "instruction": "Pennies per GB. Stores BOL, POD, rate-con PDFs with 7-year retention for compliance. Currently using GridFS as fallback.",
        "link": "https://dash.cloudflare.com/?to=/:account/r2/api-tokens", "priority": "P1",
        "env_var": "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET"},
    {"id": "key-stripe",          "group": "API Keys for TMS", "title": "Stripe live keys (customer payment / ACH)",
        "instruction": "Required to accept ACH from shippers. Test keys are already wired; switch to live after KYC.",
        "link": "https://dashboard.stripe.com/apikeys", "priority": "P2",
        "env_var": "STRIPE_API_KEY"},
    {"id": "key-google-oauth",    "group": "API Keys for TMS", "title": "Google OAuth client (broker login)",
        "instruction": "Already wired via Emergent Auth — no action needed unless migrating to self-hosted client.",
        "link": "https://console.cloud.google.com/apis/credentials", "priority": "P2",
        "env_var": "GOOGLE_OAUTH_CLIENT_ID"},

    # ---- 6. Operational Setup ----
    {"id": "ops-phone",           "group": "Operational Setup", "title": "Dedicated business phone line (RingCentral / OpenPhone)",
        "instruction": "$15–25/mo. Carriers expect to reach a human 24/7. Forward to mobile + record calls for ELD disputes.",
        "link": "https://www.openphone.com", "priority": "P1"},
    {"id": "ops-website",         "group": "Operational Setup", "title": "Public website + carrier packet landing",
        "instruction": "Shippers Google you before sending a load. Bare minimum: home + carriers + contact. The TMS already has /landing.",
        "link": "https://oriseifreight.com", "priority": "P1"},
    {"id": "ops-carrier-packet",  "group": "Operational Setup", "title": "Carrier onboarding packet (W-9 + COI + carrier agreement)",
        "instruction": "Already wired via /carrier-onboarding in the TMS — confirm template + signature flow works end-to-end.",
        "link": "/carrier-onboarding", "priority": "P0"},
    {"id": "ops-shipper-rates",   "group": "Operational Setup", "title": "Shipper rate agreements / BPAs",
        "instruction": "Standard Broker-Shipper Agreement template — typically a 1-page MSA + per-load rate sheet. Templates in /documents.",
        "link": "/documents", "priority": "P0"},
    {"id": "ops-banking-factoring","group": "Operational Setup", "title": "Wire factoring deposit account into accounting",
        "instruction": "Once factoring is approved, all invoice deposits route to the factor's escrow. Set up in /factoring.",
        "link": "/factoring", "priority": "P1"},
]


def build_onboarding_router(
    api_router, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/onboarding", tags=["onboarding"])
    admin_dep = Depends(require_role("admin", "dispatcher"))

    async def _get_state() -> Dict[str, Any]:
        st = await db.onboarding_checklist_state.find_one(
            {"key": "default"}, {"_id": 0})
        if not st:
            st = {"key": "default", "completions": {},
                  "created_at": datetime.now(timezone.utc).isoformat()}
            await db.onboarding_checklist_state.insert_one(dict(st))
        return st

    @router.get("/checklist")
    async def get_checklist(_=Depends(get_current_user)) -> Dict[str, Any]:
        state = await _get_state()
        comps = state.get("completions") or {}
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in CHECKLIST:
            grp = item["group"]
            groups.setdefault(grp, []).append({
                **item,
                "completed": bool(comps.get(item["id"], {}).get("completed")),
                "completed_at": comps.get(item["id"], {}).get("at"),
                "completed_by": comps.get(item["id"], {}).get("by"),
            })
        total = len(CHECKLIST)
        done = sum(1 for i in CHECKLIST if comps.get(i["id"], {}).get("completed"))
        return {
            "groups": [{"name": g, "items": items} for g, items in groups.items()],
            "total": total,
            "completed": done,
            "percent": round(100.0 * done / max(1, total), 1),
        }

    @router.post("/checklist/{item_id}/toggle")
    async def toggle_item(item_id: str, user=admin_dep) -> Dict[str, Any]:
        if not any(i["id"] == item_id for i in CHECKLIST):
            raise HTTPException(404, f"Unknown checklist item '{item_id}'")
        state = await _get_state()
        comps = state.get("completions") or {}
        cur = bool(comps.get(item_id, {}).get("completed"))
        new = not cur
        comps[item_id] = {
            "completed": new,
            "at": datetime.now(timezone.utc).isoformat(),
            "by": getattr(user, "name", "system"),
        }
        await db.onboarding_checklist_state.update_one(
            {"key": "default"},
            {"$set": {"completions": comps,
                       "updated_at": datetime.now(timezone.utc).isoformat()}})
        return {"item_id": item_id, "completed": new}

    @router.post("/checklist/reset")
    async def reset_checklist(user=Depends(require_role("admin"))) -> Dict[str, Any]:
        await db.onboarding_checklist_state.update_one(
            {"key": "default"},
            {"$set": {"completions": {},
                       "reset_at": datetime.now(timezone.utc).isoformat(),
                       "reset_by": getattr(user, "name", "system")}})
        return {"ok": True}

    api_router.include_router(router)
