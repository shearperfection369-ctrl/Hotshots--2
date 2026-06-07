"""routes.tms_invite_links — One-time-link gate for Hot Shot TMS VC pitch.

Lets the founder generate a unique, optionally-expiring URL per VC firm:
   /tms-investors?token=<token>

When that token loads the page:
  • Firm name + contact pre-populate in the hero + intro form.
  • Every PDF / ZIP download is automatically personalized for that firm
    (top-banner + diagonal CONFIDENTIAL watermark).
  • Every visit & download is audit-logged with IP, user-agent, scroll depth.
  • On first visit per token, an alert email goes to the founder via Resend
    (if Resend is configured in the Connections vault).

Admin endpoints (admin auth required):
  POST /api/investor/invite-links                  · create new link
  GET  /api/investor/invite-links                  · list all + visit stats
  POST /api/investor/invite-links/{token}/disable  · revoke a link
  DELETE /api/investor/invite-links/{token}        · delete a link

Public endpoints (no auth — VC opens link directly):
  GET  /api/public/tms-link/{token}                · validate token + payload
  POST /api/public/tms-link/{token}/visit          · log visit + download
"""
from __future__ import annotations

import io
import logging
import secrets
import zipfile
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from .orisei_docs import build_branded_markdown_pdf
from .tms_investor import (
    HOT_SHOT_BRAND,
    _hot_shot_deck_md,
    _hot_shot_one_pager_md,
)

logger = logging.getLogger("tennant_tms.tms_invite_links")
COLLECTION = "tms_investor_invite_links"


# -------------------- Pydantic --------------------
class InviteLinkCreate(BaseModel):
    firm_name: str = Field(..., min_length=1, max_length=120)
    contact_name: Optional[str] = Field(None, max_length=120)
    contact_email: Optional[EmailStr] = None
    note: Optional[str] = Field(None, max_length=500,
                                description="Internal note · who introduced, etc.")
    max_visits: Optional[int] = Field(None, ge=1, le=10_000)
    days_valid: Optional[int] = Field(None, ge=1, le=365,
                                       description="Auto-expire after N days")

    # Whitespace-only firm names sneak past min_length=1 — reject them.
    @classmethod
    def _validate_firm(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("firm_name cannot be blank")
        return v

    def __init__(self, **data):  # noqa: D401
        if "firm_name" in data:
            data["firm_name"] = self._validate_firm(data["firm_name"])
        super().__init__(**data)


class VisitIn(BaseModel):
    event: str = Field("page_view", description="page_view · deck · one-pager · zip · scroll")
    scroll_depth_pct: Optional[int] = Field(None, ge=0, le=100)
    referrer: Optional[str] = None


# -------------------- Helpers --------------------
def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo _id and surface visit count + last visit for list views."""
    out = {k: v for k, v in doc.items() if k != "_id"}
    visits = doc.get("visits") or []
    out["visit_count"] = len(visits)
    out["unique_ip_count"] = len({(v.get("ip") or "") for v in visits})
    out["last_visit_at"] = visits[-1]["at"] if visits else None
    out["download_counts"] = {
        "deck":      sum(1 for v in visits if v.get("event") == "deck"),
        "one-pager": sum(1 for v in visits if v.get("event") == "one-pager"),
        "zip":       sum(1 for v in visits if v.get("event") == "zip"),
    }
    return out


import os

# Unified investor deck URL that showcases all three products (JadeOS Quantum AI,
# JadeOS-Agent Suite, Hot Shot TMS) on one page with links to each. Pre-token
# email invites now point here instead of the single-product /tms-investors
# page. The token is still appended as ?ref=<token> so visits can be tracked.
UNIFIED_DECK_URL = os.environ.get(
    "INVESTOR_UNIFIED_DECK_URL",
    "https://mpls-automation-hub.emergent.host/deck")


def _link_share_url(base: str, token: str) -> str:
    """Unified three-product deck URL (default share link)."""
    sep = "&" if "?" in UNIFIED_DECK_URL else "?"
    return f"{UNIFIED_DECK_URL}{sep}ref={token}"


def _link_tms_only_share_url(base: str, token: str) -> str:
    """Original Hot Shot TMS-only gated landing URL."""
    return f"{base.rstrip('/')}/tms-investors?token={token}"


def _resolve_origin(request: Request) -> str:
    """Derive the public origin (scheme + host) preferring browser-set
    Origin/Referer headers over the in-cluster base_url.
    """
    # Highest priority: explicit env var pinning the public origin
    env_origin = os.environ.get("HOT_SHOT_PUBLIC_ORIGIN")
    if env_origin:
        return env_origin.rstrip("/")
    origin = request.headers.get("origin") or ""
    if not origin:
        ref = request.headers.get("referer") or ""
        if ref:
            from urllib.parse import urlparse
            p = urlparse(ref)
            if p.scheme and p.netloc:
                origin = f"{p.scheme}://{p.netloc}"
    if not origin:
        # Fall back to base_url (Kubernetes internal — last resort)
        origin = str(request.base_url).rstrip("/")
        if origin.endswith("/api"):
            origin = origin[: -len("/api")]
    return origin.rstrip("/")


def _check_active(doc: Dict[str, Any]) -> None:
    """Raise 410 / 423 / 429 if the link is no longer usable."""
    if doc.get("status") == "disabled":
        raise HTTPException(status_code=410, detail="This invite link has been disabled.")
    exp = doc.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp_dt:
                raise HTTPException(status_code=410, detail="This invite link has expired.")
        except ValueError:
            pass  # malformed date, ignore
    max_visits = doc.get("max_visits")
    if max_visits and len(doc.get("visits") or []) >= max_visits:
        raise HTTPException(status_code=423,
                            detail=f"This invite link has reached its visit cap ({max_visits}).")


def _personalization_from(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Build the personalization dict consumed by build_branded_markdown_pdf."""
    return {
        "firm_name": doc["firm_name"],
        "contact_name": doc.get("contact_name") or None,
        "prepared_date": datetime.now(timezone.utc).strftime("%d %b %Y"),
    }


def _safe_slug(s: str) -> str:
    import re as _re
    return _re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_") or "VC"


async def _maybe_notify_founder(db, doc: Dict[str, Any], request: Request,
                                event: str) -> None:
    """Fire-and-forget Resend email to founder on first visit per token."""
    visits = doc.get("visits") or []
    is_first_visit_of_kind = sum(1 for v in visits if v.get("event") == event) == 0
    if not is_first_visit_of_kind:
        return  # we already alerted for this event-type on this token

    try:
        from .connections import get_connection_credentials
        creds = await get_connection_credentials(db, "resend")
    except Exception:
        creds = None
    if not creds or not creds.get("api_key"):
        return

    to_email = "shearperfection369@gmail.com"
    from_email = creds.get("from_email") or "onboarding@resend.dev"
    from_name = creds.get("from_name") or "Hot Shot TMS"
    firm = doc.get("firm_name") or "Unknown firm"
    contact = doc.get("contact_name") or "—"
    ip = (request.client.host if request.client else "—") or "—"
    ua = request.headers.get("user-agent", "—")[:200]
    event_label = {
        "page_view": "opened the data room",
        "deck":      "downloaded the pitch deck",
        "one-pager": "downloaded the one-pager",
        "zip":       "downloaded the FULL data room",
    }.get(event, f"event={event}")
    subject = f"[Hot Shot TMS] {firm} just {event_label}"
    text = (
        f"{firm} just {event_label}.\n\n"
        f"Token: {doc['token']}\n"
        f"Contact on file: {contact}\n"
        f"IP: {ip}\n"
        f"User-Agent: {ua}\n"
        f"At: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S UTC}\n"
    )
    try:
        import asyncio
        import resend as _resend
        _resend.api_key = creds["api_key"]
        await asyncio.to_thread(_resend.Emails.send, {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": text,
        })
        logger.info("Founder alerted: %s · %s", firm, event)
    except Exception as exc:  # pragma: no cover
        logger.warning("Founder Resend alert failed: %s", exc)


# -------------------- ROUTER --------------------
def build_tms_invite_links_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    """Wire admin + public endpoints into the main api_router."""

    admin_dep = Depends(require_role("admin"))
    router = APIRouter(prefix="/investor", tags=["tms-invite-links"])

    # ---------- ADMIN: CREATE ----------
    @router.post("/invite-links")
    async def create_invite_link(payload: InviteLinkCreate, request: Request,
                                 _: Any = admin_dep) -> Dict[str, Any]:
        token = secrets.token_urlsafe(16)
        now = datetime.now(timezone.utc)
        expires_at: Optional[str] = None
        if payload.days_valid:
            from datetime import timedelta
            expires_at = (now + timedelta(days=payload.days_valid)).isoformat()
        doc = {
            "token": token,
            "firm_name": payload.firm_name.strip(),
            "contact_name": (payload.contact_name or "").strip() or None,
            "contact_email": payload.contact_email,
            "note": (payload.note or "").strip() or None,
            "max_visits": payload.max_visits,
            "days_valid": payload.days_valid,
            "created_at": now.isoformat(),
            "expires_at": expires_at,
            "status": "active",
            "visits": [],
        }
        await db[COLLECTION].insert_one(dict(doc))
        origin = _resolve_origin(request)
        return {**_serialize(doc),
                "share_url": _link_share_url(origin, token),
                "tms_only_share_url": _link_tms_only_share_url(origin, token)}

    # ---------- ADMIN: LIST ----------
    @router.get("/invite-links")
    async def list_invite_links(request: Request, _: Any = admin_dep) -> Dict[str, Any]:
        rows = await db[COLLECTION].find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        origin = _resolve_origin(request)
        items = []
        for r in rows:
            ser = _serialize(r)
            ser["share_url"] = _link_share_url(origin, r["token"])
            ser["tms_only_share_url"] = _link_tms_only_share_url(origin, r["token"])
            items.append(ser)
        return {"items": items, "count": len(items)}

    # ---------- ADMIN: DISABLE ----------
    @router.post("/invite-links/{token}/disable")
    async def disable_invite_link(token: str, _: Any = admin_dep) -> Dict[str, str]:
        res = await db[COLLECTION].update_one({"token": token},
                                              {"$set": {"status": "disabled"}})
        if res.matched_count == 0:
            raise HTTPException(404, "Invite link not found")
        return {"status": "disabled"}

    # ---------- ADMIN: DELETE ----------
    @router.delete("/invite-links/{token}")
    async def delete_invite_link(token: str, _: Any = admin_dep) -> Dict[str, str]:
        res = await db[COLLECTION].delete_one({"token": token})
        if res.deleted_count == 0:
            raise HTTPException(404, "Invite link not found")
        return {"status": "deleted"}

    api_router.include_router(router)

    # ---------- PUBLIC: VALIDATE + PAYLOAD ----------
    public = APIRouter(prefix="/public", tags=["tms-invite-links", "public"])

    @public.get("/tms-link/{token}")
    async def tms_link_summary(token: str, request: Request) -> Dict[str, Any]:
        doc = await db[COLLECTION].find_one({"token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Invite link not found")
        _check_active(doc)
        # Light personalization payload (no PII other than firm + contact)
        return {
            "firm_name": doc["firm_name"],
            "contact_name": doc.get("contact_name"),
            "status": doc.get("status"),
            "expires_at": doc.get("expires_at"),
            "max_visits": doc.get("max_visits"),
            "visits_used": len(doc.get("visits") or []),
        }

    @public.post("/tms-link/{token}/visit")
    async def tms_link_log_visit(token: str, payload: VisitIn,
                                  request: Request) -> Dict[str, str]:
        doc = await db[COLLECTION].find_one({"token": token}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Invite link not found")
        _check_active(doc)
        visit = {
            "at": datetime.now(timezone.utc).isoformat(),
            "event": payload.event,
            "ip": (request.client.host if request.client else None),
            "ua": request.headers.get("user-agent", "")[:300],
            "scroll_depth_pct": payload.scroll_depth_pct,
            "referrer": payload.referrer,
        }
        await db[COLLECTION].update_one({"token": token},
                                        {"$push": {"visits": visit}})
        # Founder alert (fire-and-forget; never fail the call)
        try:
            await _maybe_notify_founder(db, doc, request, payload.event)
        except Exception:  # pragma: no cover
            pass
        return {"status": "logged"}

    # ---------- PUBLIC: PERSONALIZED PDF DOWNLOADS ----------
    @public.get("/tms-link/{token}/deck.pdf")
    async def tms_link_deck_pdf(token: str, request: Request) -> StreamingResponse:
        doc = await db[COLLECTION].find_one({"token": token}, {"_id": 0})
        if not doc: raise HTTPException(404, "Invite link not found")
        _check_active(doc)
        await db[COLLECTION].update_one({"token": token},
            {"$push": {"visits": {"at": datetime.now(timezone.utc).isoformat(),
                                  "event": "deck",
                                  "ip": (request.client.host if request.client else None),
                                  "ua": request.headers.get("user-agent", "")[:300]}}})
        try: await _maybe_notify_founder(db, doc, request, "deck")
        except Exception: pass
        firm_slug = _safe_slug(doc["firm_name"])
        pdf = build_branded_markdown_pdf(
            _hot_shot_deck_md(),
            title="Hot Shot TMS · VC Pitch Deck",
            subtitle=f"Prepared for {doc['firm_name']} · Confidential",
            brand=HOT_SHOT_BRAND,
            personalization=_personalization_from(doc),
        )
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Hot_Shot_TMS_Pitch_Deck_for_{firm_slug}.pdf"'})

    @public.get("/tms-link/{token}/one-pager.pdf")
    async def tms_link_one_pager_pdf(token: str, request: Request) -> StreamingResponse:
        doc = await db[COLLECTION].find_one({"token": token}, {"_id": 0})
        if not doc: raise HTTPException(404, "Invite link not found")
        _check_active(doc)
        await db[COLLECTION].update_one({"token": token},
            {"$push": {"visits": {"at": datetime.now(timezone.utc).isoformat(),
                                  "event": "one-pager",
                                  "ip": (request.client.host if request.client else None),
                                  "ua": request.headers.get("user-agent", "")[:300]}}})
        try: await _maybe_notify_founder(db, doc, request, "one-pager")
        except Exception: pass
        firm_slug = _safe_slug(doc["firm_name"])
        pdf = build_branded_markdown_pdf(
            _hot_shot_one_pager_md(),
            title="Hot Shot TMS · Investor One-Pager",
            subtitle=f"Prepared for {doc['firm_name']} · Confidential",
            brand=HOT_SHOT_BRAND,
            personalization=_personalization_from(doc),
        )
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition":
                f'attachment; filename="Hot_Shot_TMS_One_Pager_for_{firm_slug}.pdf"'})

    @public.get("/tms-link/{token}/data-room.zip")
    async def tms_link_data_room_zip(token: str, request: Request) -> StreamingResponse:
        doc = await db[COLLECTION].find_one({"token": token}, {"_id": 0})
        if not doc: raise HTTPException(404, "Invite link not found")
        _check_active(doc)
        await db[COLLECTION].update_one({"token": token},
            {"$push": {"visits": {"at": datetime.now(timezone.utc).isoformat(),
                                  "event": "zip",
                                  "ip": (request.client.host if request.client else None),
                                  "ua": request.headers.get("user-agent", "")[:300]}}})
        try: await _maybe_notify_founder(db, doc, request, "zip")
        except Exception: pass
        firm_slug = _safe_slug(doc["firm_name"])
        personalization = _personalization_from(doc)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"01_Hot_Shot_TMS_Pitch_Deck_for_{firm_slug}.pdf",
                        build_branded_markdown_pdf(
                            _hot_shot_deck_md(),
                            title="Hot Shot TMS · VC Pitch Deck",
                            subtitle=f"Prepared for {doc['firm_name']} · Confidential",
                            brand=HOT_SHOT_BRAND,
                            personalization=personalization))
            zf.writestr(f"02_Hot_Shot_TMS_One_Pager_for_{firm_slug}.pdf",
                        build_branded_markdown_pdf(
                            _hot_shot_one_pager_md(),
                            title="Hot Shot TMS · Investor One-Pager",
                            subtitle=f"Prepared for {doc['firm_name']} · Confidential",
                            brand=HOT_SHOT_BRAND,
                            personalization=personalization))
            zf.writestr("README.txt",
                        "Hot Shot TMS · VC Data Room\n"
                        f"Prepared for: {doc['firm_name']}\n"
                        + (f"Attn: {doc['contact_name']}\n" if doc.get("contact_name") else "")
                        + f"Token: {doc['token']}\n"
                        f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"
                        f"\nFounder: Oliver Cummins · shearperfection369@gmail.com\n"
                        f"HQ: Plymouth, Minnesota\n"
                        f"\nThis package is confidential and intended solely\n"
                        f"for {doc['firm_name']}. Please do not forward without\n"
                        f"prior written consent.\n")
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/zip",
            headers={"Content-Disposition":
                f'attachment; filename="Hot_Shot_TMS_Data_Room_for_{firm_slug}.zip"'})

    api_router.include_router(public)
