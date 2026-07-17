"""routes.launch_blast — Launch announcement email blast.

Turns the Queen Califia launch card into a ready-to-send HTML announcement
email for the shipper prospect list (revenue_prospects + lighthouse_prospects
+ shipper_accounts, deduped). Sends via Resend when the key is connected,
otherwise queues in outreach_queue as queued_awaiting_key.

Endpoints — /api/launch-blast/*
"""
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger("orisei.launch_blast")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_url() -> str:
    return (os.environ.get("PUBLIC_FRONTEND_URL") or "").rstrip("/")


def _email_html(contact_name: str) -> str:
    base = _public_url()
    first = (contact_name or "there").split(" ")[0]
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0B1320;font-family:Georgia,'Times New Roman',serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0B1320;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#0B1320;border:1px solid #C9A24A;border-radius:8px;overflow:hidden;">
  <tr><td>
    <img src="{base}/brand/pack/launch_card_wide.png" alt="Orisei Freight Solutions — We're Live" width="600" style="display:block;width:100%;height:auto;" />
  </td></tr>
  <tr><td style="padding:32px 40px 8px;">
    <div style="color:#E6CB85;font-size:22px;font-weight:bold;letter-spacing:1px;">Hi {first} — the Queen rides.</div>
  </td></tr>
  <tr><td style="padding:8px 40px;color:#D7E1EE;font-size:15px;line-height:1.65;">
    <p style="margin:0 0 14px;">Orisei Freight Solutions is officially <b style="color:#E6CB85;">live and booking freight</b>.
    We're a Minnesota-built, operator-owned brokerage — 13 years of supply-chain experience, a CDL owner-operator vetting
    every carrier, and our own real-time TMS (the Orisei Command Deck) tracking every load from tender to delivery.</p>
    <p style="margin:0 0 14px;">What that means for your dock:</p>
    <table role="presentation" cellpadding="0" cellspacing="0" style="color:#D7E1EE;font-size:14px;line-height:1.7;">
      <tr><td style="color:#C9A24A;padding-right:10px;vertical-align:top;">&#9670;</td><td>Instant quotes on TL, LTL, and specialized — answered by a broker who has actually run the lane</td></tr>
      <tr><td style="color:#C9A24A;padding-right:10px;vertical-align:top;">&#9670;</td><td>Live GPS tracking + proactive check calls — you see what we see</td></tr>
      <tr><td style="color:#C9A24A;padding-right:10px;vertical-align:top;">&#9670;</td><td>Carriers vetted by a 12-year owner-operator — equipment, insurance, and honesty checked</td></tr>
    </table>
  </td></tr>
  <tr><td align="center" style="padding:24px 40px 8px;">
    <a href="{base}/get-quote" style="display:inline-block;background:#C9A24A;color:#0B1320;font-weight:bold;font-size:15px;text-decoration:none;padding:14px 36px;border-radius:6px;letter-spacing:0.5px;">GET AN INSTANT QUOTE &rarr;</a>
  </td></tr>
  <tr><td style="padding:16px 40px 8px;color:#8FA3BC;font-size:13px;line-height:1.6;text-align:center;">
    Or simply reply to this email with an origin, destination, and commodity — we'll have a rate back to you within the hour.
  </td></tr>
  <tr><td style="padding:20px 40px 28px;border-top:1px solid rgba(201,162,74,0.3);color:#8FA3BC;font-size:11px;line-height:1.6;text-align:center;">
    <b style="color:#E6CB85;">ORISEI FREIGHT SOLUTIONS LLC</b><br/>
    Oliver Cummins &middot; Daniel W. Karsor &middot; Doug Graham<br/>
    Minneapolis &middot; Saint Paul &middot; Brooklyn Park &middot; Minnesota<br/>
    <a href="{base}" style="color:#C9A24A;">{base.replace('https://', '')}</a>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


SUBJECT = "We're live — Orisei Freight Solutions is now booking freight"


async def _recipients(db) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}

    def _add(email: Optional[str], contact: str, company: str, source: str):
        e = (email or "").strip().lower()
        if not e or not EMAIL_RE.match(e) or e in seen:
            return
        seen[e] = {"email": e, "contact_name": contact or "", "company": company or "", "source": source}

    async for p in db.revenue_prospects.find({}, {"_id": 0}):
        _add(p.get("email"), p.get("contact_name"), p.get("company"), "Revenue Prospects")
    async for p in db.lighthouse_prospects.find({}, {"_id": 0}):
        _add(p.get("contact_email"), p.get("contact_name"), p.get("company_name"), "Lighthouse")
    async for p in db.shipper_accounts.find({}, {"_id": 0}):
        _add(p.get("contact_email"), p.get("contact_name") or "", p.get("company_name"), "Shipper Accounts")
    return sorted(seen.values(), key=lambda r: r["company"].lower())


class SendIn(BaseModel):
    emails: Optional[List[str]] = None   # subset; None/empty → all
    test_to: Optional[str] = None        # single test send


def build_launch_blast_router(*, db, get_current_user: Callable,
                              require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/launch-blast", tags=["launch-blast"])

    @router.get("/preview")
    async def preview(_=Depends(get_current_user)) -> Dict[str, Any]:
        recips = await _recipients(db)
        return {"subject": SUBJECT, "html": _email_html("Alex Shipman"),
                "recipient_count": len(recips),
                "card_url": f"{_public_url()}/brand/pack/launch_card_wide.png"}

    @router.get("/recipients")
    async def recipients(_=Depends(get_current_user)) -> Dict[str, Any]:
        recips = await _recipients(db)
        return {"recipients": recips, "count": len(recips)}

    @router.post("/send")
    async def send(payload: SendIn, user=Depends(require_role("owner"))) -> Dict[str, Any]:
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        has_key = bool(creds and creds.get("api_key"))

        if payload.test_to:
            targets = [{"email": payload.test_to.strip().lower(),
                        "contact_name": user.name, "company": "TEST", "source": "test"}]
        else:
            all_r = await _recipients(db)
            wanted = {e.strip().lower() for e in (payload.emails or [])}
            targets = [r for r in all_r if not wanted or r["email"] in wanted]

        sent = queued = failed = 0
        for r in targets:
            html = _email_html(r["contact_name"])
            status, error = "queued_awaiting_key", None
            if has_key:
                res = await _send_via_resend(creds, to=r["email"], subject=SUBJECT, html=html)
                status = "sent" if res.get("sent") else "failed"
                error = res.get("error")
            await db.outreach_queue.insert_one({
                "queue_id": f"OQ-{uuid.uuid4().hex[:8].upper()}", "type": "launch_blast",
                "ref": r["company"], "to_email": r["email"], "subject": SUBJECT,
                "html": html, "has_pdf": False, "status": status, "error": error,
                "created_at": _now_iso(),
                "sent_at": _now_iso() if status == "sent" else None})
            if status == "sent":
                sent += 1
            elif status == "queued_awaiting_key":
                queued += 1
            else:
                failed += 1
        logger.info("Launch blast: %d sent, %d queued, %d failed (%d targets)",
                    sent, queued, failed, len(targets))
        return {"total": len(targets), "sent": sent, "queued_awaiting_key": queued,
                "failed": failed, "resend_connected": has_key}

    return router
