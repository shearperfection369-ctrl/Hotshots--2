"""routes.provider_outreach — Automatic launch-day provider outreach.

Sends well-crafted intro emails to every API provider Orisei needs to
fully operate the platform, asking them for keys, sandbox credentials,
partner-program enrollment links, etc. Tracks who's been contacted,
who's responded, and which providers still have empty Connections-vault
credentials so the launch checklist is one-glance.

Email is sent via Resend (credentials pulled from the Connections vault).
If Resend isn't configured, requests dry-run successfully so the user
can still preview the email body.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from routes.connections import get_connection_credentials

logger = logging.getLogger("tennant_tms.provider_outreach")


# ---------- Provider catalog ----------
# Each entry says: who they are, what we need, where to email, and the
# default email body. The catalog stays in code so adding a provider is
# a one-line PR rather than a database migration.
PROVIDER_CATALOG: List[Dict[str, Any]] = [
    # -------- Load Boards --------
    {
        "id": "dat",
        "name": "DAT One",
        "category": "Load Board",
        "what_we_need": "DAT One Power API access · Production Bearer token · Postings + Search endpoints",
        "default_email": "developers@dat.com",
        "signup_url": "https://www.dat.com/load-boards/dat-one/api",
        "subject": "Orisei Freight Solutions — DAT One API access request",
        "body_md": (
            "Hi DAT team,\n\n"
            "I'm Oliver, founder of **Orisei Freight Solutions LLC** — a Twin Cities-based "
            "property freight brokerage launching our internal command deck. We have "
            "a paid DAT One subscription and would like to enable the Power API so we "
            "can pull lane postings programmatically into our margin-aware queue.\n\n"
            "Could you point me to the developer onboarding flow / production token "
            "request and any partner enrollment paperwork?\n\n"
            "Happy to share our use case in detail and sign whatever NDA / TOS is required.\n\n"
            "— Oliver, Orisei Freight Solutions LLC · MC pending · Saint Paul, MN"
        ),
    },
    {
        "id": "truckstop",
        "name": "Truckstop.com",
        "category": "Load Board",
        "what_we_need": "Truckstop Load Search API · OAuth client + sandbox token",
        "default_email": "apisupport@truckstop.com",
        "signup_url": "https://developer.truckstop.com",
        "subject": "Orisei Freight Solutions — Truckstop API onboarding",
        "body_md": (
            "Hi Truckstop API team,\n\n"
            "I'm Oliver at **Orisei Freight Solutions LLC**, a property freight brokerage "
            "in Saint Paul, MN. We're standing up our internal TMS and would like to "
            "integrate the Truckstop Load Search API into our aggregator feed.\n\n"
            "Could you send the partner onboarding packet, OAuth client credentials, "
            "and sandbox token request flow?\n\n"
            "Happy to provide W-9, MC docs, and a reference call.\n\n"
            "— Oliver, Orisei Freight Solutions LLC"
        ),
    },
    {
        "id": "convoy",
        "name": "Convoy / Flexport Trucking",
        "category": "Load Board",
        "what_we_need": "Flexport Trucking partner API · Loads endpoint · Bearer token",
        "default_email": "trucking-partners@flexport.com",
        "signup_url": "https://www.flexport.com/services/trucking",
        "subject": "Orisei Freight Solutions — Flexport Trucking partner API",
        "body_md": (
            "Hi Flexport Trucking team,\n\n"
            "I'm Oliver, founder of **Orisei Freight Solutions LLC** — a property "
            "freight brokerage launching in the Twin Cities. We'd like to integrate "
            "Flexport Trucking (formerly Convoy) loads into our internal aggregator.\n\n"
            "Could you share the partner-program docs, API onboarding steps, and "
            "any minimum volume / insurance requirements?\n\n"
            "— Oliver"
        ),
    },
    {
        "id": "uber_freight",
        "name": "Uber Freight",
        "category": "Load Board",
        "what_we_need": "Uber Freight Carrier API · Brokerage partner enrollment",
        "default_email": "partners@uberfreight.com",
        "signup_url": "https://www.uberfreight.com/api",
        "subject": "Orisei Freight Solutions — Uber Freight broker partnership",
        "body_md": (
            "Hi Uber Freight team,\n\n"
            "I'm reaching out from **Orisei Freight Solutions LLC**, a property "
            "freight brokerage launching in Saint Paul, MN. We'd like to discuss "
            "broker-partner integration so we can post and pull loads against the "
            "Uber Freight network.\n\n"
            "Could you share the integration brief and enrollment paperwork?\n\n"
            "— Oliver, Orisei Freight Solutions LLC"
        ),
    },
    {
        "id": "123loadboard",
        "name": "123Loadboard",
        "category": "Load Board",
        "what_we_need": "123Loadboard API access · Sandbox + production credentials",
        "default_email": "support@123loadboard.com",
        "signup_url": "https://www.123loadboard.com/api",
        "subject": "Orisei Freight Solutions — 123Loadboard API access",
        "body_md": (
            "Hi 123Loadboard team,\n\n"
            "I'm Oliver at **Orisei Freight Solutions LLC** in the Twin Cities. "
            "We have a paid 123Loadboard subscription and want to integrate the "
            "API into our brokerage TMS for programmatic posting + searching.\n\n"
            "Please point me to the API onboarding flow.\n\n"
            "— Oliver"
        ),
    },
    # -------- Factoring --------
    {
        "id": "triumph",
        "name": "Triumph Business Capital",
        "category": "Factoring",
        "what_we_need": "Broker factoring program · Quick-Pay API · NOA handling",
        "default_email": "broker@triumphbcap.com",
        "signup_url": "https://www.triumphbcap.com/freight-factoring/",
        "subject": "Orisei Freight Solutions — Broker factoring partnership",
        "body_md": (
            "Hi Triumph team,\n\n"
            "I'm Oliver, founder of **Orisei Freight Solutions LLC** — a freight "
            "brokerage launching in Saint Paul, MN. We're evaluating factoring "
            "partners for our cash-flow program.\n\n"
            "Could you share your broker rates, advance percentages, and any "
            "API / portal we can integrate with?\n\n"
            "— Oliver"
        ),
    },
    {
        "id": "apex_capital",
        "name": "Apex Capital",
        "category": "Factoring",
        "what_we_need": "Broker factoring · Fuel-card program · API",
        "default_email": "info@apexcapitalcorp.com",
        "signup_url": "https://www.apexcapitalcorp.com",
        "subject": "Orisei Freight Solutions — Factoring partnership inquiry",
        "body_md": (
            "Hi Apex team,\n\n"
            "I'm Oliver at **Orisei Freight Solutions LLC** — a freight brokerage "
            "launching in the Twin Cities. We'd like a factoring proposal "
            "including advance rates, fuel-card pricing, and any portal/API.\n\n"
            "— Oliver"
        ),
    },
    {
        "id": "otr",
        "name": "OTR Solutions",
        "category": "Factoring",
        "what_we_need": "Broker factoring rates + carrier monitoring API",
        "default_email": "info@otrsolutions.com",
        "signup_url": "https://otrsolutions.com",
        "subject": "Orisei Freight Solutions — OTR factoring proposal",
        "body_md": (
            "Hi OTR team,\n\n"
            "Orisei Freight Solutions LLC is launching a property brokerage in "
            "Saint Paul, MN. We're shopping factoring partners and would love a "
            "proposal + a walk-through of your broker tools / API.\n\n"
            "— Oliver"
        ),
    },
    # -------- Email / Communications --------
    {
        "id": "resend",
        "name": "Resend",
        "category": "Email Delivery",
        "what_we_need": "Production API key · Verified sending domain (oriseifreight.com)",
        "default_email": "support@resend.com",
        "signup_url": "https://resend.com/signup",
        "subject": "Orisei Freight Solutions — Resend domain verification + production limits",
        "body_md": (
            "Hi Resend team,\n\n"
            "I just signed up for Resend on behalf of **Orisei Freight Solutions LLC**. "
            "We send brokerage operational mail (BOLs, PODs, customer status updates) "
            "from `oriseifreight.com`.\n\n"
            "Could you (a) confirm production sending limits, (b) flag anything "
            "I should pre-warm before launch, and (c) give a heads-up on the "
            "DKIM / SPF / DMARC requirements?\n\n"
            "— Oliver"
        ),
    },
    # -------- Accounting --------
    {
        "id": "quickbooks",
        "name": "Intuit / QuickBooks Online",
        "category": "Accounting",
        "what_we_need": "Production OAuth client · Production redirect URI whitelist",
        "default_email": "developer@intuit.com",
        "signup_url": "https://developer.intuit.com",
        "subject": "Orisei Freight Solutions — QuickBooks production OAuth promotion",
        "body_md": (
            "Hi Intuit Developer team,\n\n"
            "I have a sandbox app on Intuit Developer and would like to promote it "
            "to production for **Orisei Freight Solutions LLC** (oriseifreight.com).\n\n"
            "Can you confirm what's needed (privacy policy, EULA, redirect URI "
            "whitelisting, app review screencast) so we can pass production review?\n\n"
            "— Oliver"
        ),
    },
    # -------- Compliance / Carrier vetting --------
    {
        "id": "rmis",
        "name": "RMIS / Highway Carrier Monitoring",
        "category": "Carrier Vetting",
        "what_we_need": "Carrier monitoring API · MC/DOT/CSA pulls",
        "default_email": "sales@rmis.com",
        "signup_url": "https://www.rmis.com",
        "subject": "Orisei Freight Solutions — Carrier monitoring proposal",
        "body_md": (
            "Hi RMIS team,\n\n"
            "Orisei Freight Solutions LLC is launching a property brokerage and we "
            "need a carrier-monitoring partner. Please send pricing for MC/DOT/CSA/"
            "insurance monitoring + API specs.\n\n"
            "— Oliver"
        ),
    },
    {
        "id": "saferwatch",
        "name": "SaferWatch / Carrier411",
        "category": "Carrier Vetting",
        "what_we_need": "Carrier history lookups · API or CSV exports",
        "default_email": "support@carrier411.com",
        "signup_url": "https://www.carrier411.com",
        "subject": "Orisei Freight Solutions — Carrier411 / SaferWatch subscription",
        "body_md": (
            "Hi team,\n\n"
            "I'm setting up the carrier vetting workflow for **Orisei Freight "
            "Solutions LLC** in Saint Paul. Please share subscription tiers and any "
            "API access for carrier history lookups.\n\n"
            "— Oliver"
        ),
    },
    {
        "id": "fmcsa",
        "name": "FMCSA — Authority + MC Number",
        "category": "Regulatory",
        "what_we_need": "Confirm MC# active · process bond / BMC-84 if needed",
        "default_email": "fmcsa.registration@dot.gov",
        "signup_url": "https://www.fmcsa.dot.gov/registration",
        "subject": "Orisei Freight Solutions — Property Broker authority status",
        "body_md": (
            "Hi FMCSA Registration team,\n\n"
            "Following up on the property broker authority application for "
            "**Orisei Freight Solutions LLC** in Saint Paul, MN. Could you confirm "
            "the MC# status and outstanding requirements (BMC-84 surety bond, "
            "BOC-3, UCR)?\n\n"
            "— Oliver"
        ),
    },
    # -------- Insurance --------
    {
        "id": "tivly",
        "name": "Tivly / Reliance / Other broker insurance",
        "category": "Insurance",
        "what_we_need": "Contingent cargo · Errors & Omissions · BMC-84 quote",
        "default_email": "sales@tivly.com",
        "signup_url": "https://www.tivly.com",
        "subject": "Orisei Freight Solutions — Broker insurance package quote",
        "body_md": (
            "Hi team,\n\n"
            "Orisei Freight Solutions LLC is launching a property brokerage and we "
            "need a quote covering BMC-84 surety, contingent cargo, and errors-and-"
            "omissions. Could you put together a proposal?\n\n"
            "— Oliver"
        ),
    },
]


# ---------- Pydantic models ----------
class ProviderSendIn(BaseModel):
    provider_ids: List[str] = Field(..., min_length=1)
    to_email_overrides: Optional[Dict[str, EmailStr]] = None     # {provider_id: email}
    note_appendix: Optional[str] = Field(None, max_length=2000)
    cc_email: Optional[EmailStr] = None
    dry_run: bool = False


def _md_to_html(md: str) -> str:
    """Tiny markdown-ish renderer (bold + paragraph) — keeps the email clean
    without pulling a full markdown library."""
    import html as _h
    import re as _re
    text = _h.escape(md.strip())
    text = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f'<p style="margin:0 0 12px 0;line-height:1.55;">{p.replace(chr(10), "<br>")}</p>'
                   for p in paragraphs)


def _email_html(provider: Dict[str, Any], body_md: str, note_appendix: Optional[str]) -> str:
    body_html = _md_to_html(body_md + ("\n\n" + note_appendix if note_appendix else ""))
    return f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#FBF8F0;padding:24px;color:#0B1320;">
  <div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E6CB85;border-radius:8px;overflow:hidden;">
    <div style="background:#0E3A6B;color:#fff;padding:22px 26px;border-bottom:3px solid #C9A24A;">
      <div style="font-size:11px;letter-spacing:.3em;color:#C9A24A;text-transform:uppercase;font-family:Courier,monospace;">Orisei Freight Solutions</div>
      <div style="font-size:18px;font-weight:800;margin-top:6px;">{provider["name"]} · {provider["category"]}</div>
    </div>
    <div style="padding:24px 26px;font-size:14px;color:#0B1320;">
      {body_html}
    </div>
    <div style="background:#FBF8F0;color:#94A3B8;font-size:10px;text-align:center;padding:10px;font-family:Courier,monospace;">
      ORISEI FREIGHT SOLUTIONS LLC · MINNEAPOLIS · SAINT PAUL · MN · oliver@oriseifreight.com
    </div>
  </div>
</body></html>"""


# ---------- Router ----------
def build_provider_outreach_router(api_router: APIRouter, db, get_current_user, require_role) -> None:
    router = APIRouter(prefix="/provider-outreach", tags=["provider-outreach"])

    @router.get("/catalog")
    async def get_catalog(_=Depends(get_current_user)):
        """Return every provider we can email + Connection-vault status flag."""
        # Cross-reference Connections vault to know which still need keys
        conn_ids = set()
        async for c in db.connections.find({}, {"_id": 0, "provider_id": 1, "fields": 1}):
            if c.get("fields"):
                conn_ids.add(c["provider_id"])
        outreach_rows: Dict[str, Dict[str, Any]] = {}
        async for r in db.provider_outreach.find({}, {"_id": 0, "provider_id": 1, "status": 1, "sent_at": 1}):
            outreach_rows.setdefault(r["provider_id"], r)
        catalog = []
        for p in PROVIDER_CATALOG:
            o = outreach_rows.get(p["id"]) or {}
            catalog.append({
                **p,
                "has_credentials": p["id"] in conn_ids,
                "last_sent_at": o.get("sent_at"),
                "last_status": o.get("status"),
            })
        return {"providers": catalog, "count": len(catalog)}

    @router.post("/send")
    async def send_outreach(payload: ProviderSendIn, user=Depends(require_role("admin"))):
        """Email every selected provider in one batch.

        Pulls Resend creds from the Connections vault. Returns per-provider
        status (sent / dry_run / error). Persists each attempt to
        `db.provider_outreach` for the launch checklist.
        """
        provider_map = {p["id"]: p for p in PROVIDER_CATALOG}
        selected = [provider_map[pid] for pid in payload.provider_ids if pid in provider_map]
        if not selected:
            raise HTTPException(400, "No valid provider_ids selected")

        # Resolve Resend creds (skip when dry-run)
        api_key = None
        from_addr = "Orisei Freight <oliver@oriseifreight.com>"
        reply_to = "oliver@oriseifreight.com"
        if not payload.dry_run:
            creds = await get_connection_credentials(db, "resend") or {}
            api_key = creds.get("api_key")
            from_addr = creds.get("from_email") or from_addr
            reply_to = creds.get("reply_to") or reply_to
            if not api_key:
                raise HTTPException(
                    400,
                    "Resend not configured. Open Connections → Resend and paste an API key, "
                    "then retry. (Or pass dry_run=true to preview.)",
                )
            resend.api_key = api_key

        results: List[Dict[str, Any]] = []
        for prov in selected:
            to_email = ((payload.to_email_overrides or {}).get(prov["id"])
                        or prov["default_email"])
            html = _email_html(prov, prov["body_md"], payload.note_appendix)
            record = {
                "id": f"PO-{uuid.uuid4().hex[:10].upper()}",
                "provider_id": prov["id"],
                "provider_name": prov["name"],
                "to_email": to_email,
                "cc_email": payload.cc_email,
                "subject": prov["subject"],
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by": getattr(user, "user_id", None),
                "status": "pending",
            }
            if payload.dry_run:
                record["status"] = "dry_run"
                record["html_preview_bytes"] = len(html)
                await db.provider_outreach.insert_one(dict(record))
                results.append({**record, "html_preview": html})
                continue
            try:
                params = {
                    "from": from_addr, "to": [to_email],
                    "subject": prov["subject"], "html": html, "reply_to": reply_to,
                }
                if payload.cc_email:
                    params["cc"] = [payload.cc_email]
                resp = resend.Emails.send(params)
                record["status"] = "sent"
                record["message_id"] = (resp or {}).get("id") if isinstance(resp, dict) else None
            except Exception as exc:                                # noqa: BLE001
                logger.exception("Provider outreach send failed: %s", prov["id"])
                record["status"] = "error"
                record["error"] = str(exc)[:300]
            await db.provider_outreach.insert_one(dict(record))
            results.append(record)

        sent = sum(1 for r in results if r["status"] == "sent")
        return {
            "ok": True,
            "sent": sent,
            "dry_run_count": sum(1 for r in results if r["status"] == "dry_run"),
            "errors": sum(1 for r in results if r["status"] == "error"),
            "total": len(results),
            "results": results,
        }

    @router.get("/history")
    async def history(_=Depends(get_current_user)):
        rows = await db.provider_outreach.find({}, {"_id": 0}).sort("sent_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.put("/{outreach_id}/status")
    async def update_status(outreach_id: str, payload: Dict[str, Any], _=Depends(require_role("admin"))):
        """Manually mark an outreach row as 'replied' or 'closed' once the
        provider responds. Helpful for the launch-day checklist."""
        new_status = (payload or {}).get("status")
        if new_status not in {"replied", "closed", "sent", "error", "dry_run"}:
            raise HTTPException(400, "status must be one of: replied | closed | sent | error | dry_run")
        r = await db.provider_outreach.find_one_and_update(
            {"id": outreach_id},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
            return_document=True,
            projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Outreach record not found")
        return r

    api_router.include_router(router)
