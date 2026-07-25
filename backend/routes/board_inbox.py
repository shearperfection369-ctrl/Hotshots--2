"""routes.board_inbox — reads booking-confirmation replies from load boards.

Inbound webhook (email provider forwards replies here) + manual log + sim mode.
Confirmed bookings auto-advance the load; rejections flag it for re-booking.
"""
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Body, Depends, HTTPException

logger = logging.getLogger(__name__)

CONFIRM_WORDS = ["confirm", "confirmed", "accepted", "approved", "booked", "all set",
                 "good to go", "you are covered", "you're covered", "load is yours"]
REJECT_WORDS = ["reject", "rejected", "declined", "cancel", "cancelled", "unavailable",
                "no longer available", "covered by another", "already booked", "gone"]
REF_RE = re.compile(r"\b(AP|BH|SIM|DAT|OB)-[A-Z0-9]{5,9}\b", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_board_inbox_router(*, api_router, db, get_current_user, require_role):

    async def _webhook_token() -> str:
        cfg = await db.board_inbox_config.find_one({"_id": "cfg"})
        if not cfg:
            cfg = {"_id": "cfg", "token": uuid.uuid4().hex}
            await db.board_inbox_config.insert_one(cfg)
        return cfg["token"]

    async def process_reply(from_email: str, subject: str, body: str, source: str) -> Dict[str, Any]:
        text = f"{subject}\n{body}"
        refs = list({m.group(0).upper() for m in REF_RE.finditer(text)})
        load: Optional[Dict[str, Any]] = None
        for ref in refs:
            load = await db.autopilot_loads.find_one({"$or": [{"load_id": ref}, {"board_id": ref}]}, {"_id": 0})
            if load:
                break
        lower = text.lower()
        classification = ("confirmation" if any(w in lower for w in CONFIRM_WORDS)
                          else "rejection" if any(w in lower for w in REJECT_WORDS) else "unclear")
        action, status = "reply logged — no load reference matched", "unmatched"
        if load:
            status = "matched"
            if classification == "confirmation":
                upd: Dict[str, Any] = {"board_confirmed": True, "board_confirmed_at": _now()}
                if load["stage"] == "carrier_matched":
                    upd["stage_at"] = "2020-01-01T00:00:00+00:00"
                    action = "board CONFIRMED — load auto-advanced, rate con issues next cycle"
                else:
                    action = "board CONFIRMED — confirmation recorded on the load"
                await db.autopilot_loads.update_one(
                    {"load_id": load["load_id"]},
                    {"$set": upd, "$push": {"timeline": {"at": _now(), "stage": load["stage"],
                                                         "note": f"Board reply from {from_email}: {action}"}}})
            elif classification == "rejection":
                action = "board REJECTED — load flagged for dispatcher re-booking"
                await db.autopilot_loads.update_one(
                    {"load_id": load["load_id"]},
                    {"$set": {"board_rejected": True, "board_rejected_at": _now()},
                     "$push": {"timeline": {"at": _now(), "stage": load["stage"],
                                            "note": f"Board reply from {from_email}: {action}"}}})
            else:
                action = "reply matched to load but intent unclear — needs a human read"
                await db.autopilot_loads.update_one(
                    {"load_id": load["load_id"]},
                    {"$push": {"timeline": {"at": _now(), "stage": load["stage"],
                                            "note": f"Board reply from {from_email} (unclear intent) — see inbox"}}})
            await db.loadboard_outbox.update_many(
                {"load_id": load["load_id"], "status": {"$in": ["queued", "sent"]}},
                {"$set": {"status": "answered", "answered_at": _now()}})
        doc = {"inbox_id": f"IN-{uuid.uuid4().hex[:6].upper()}", "from_email": from_email,
               "subject": subject[:180], "body_excerpt": body[:300], "refs": refs,
               "load_id": load["load_id"] if load else None, "classification": classification,
               "action": action, "status": status, "source": source, "received_at": _now()}
        await db.board_inbox.insert_one(dict(doc))
        return doc

    @api_router.get("/board-inbox")
    async def inbox(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.board_inbox.find({}, {"_id": 0}).sort("received_at", -1).to_list(50)
        token = await _webhook_token()
        return {"replies": rows,
                "stats": {"total": await db.board_inbox.count_documents({}),
                          "confirmations": await db.board_inbox.count_documents({"classification": "confirmation"}),
                          "rejections": await db.board_inbox.count_documents({"classification": "rejection"}),
                          "unmatched": await db.board_inbox.count_documents({"status": "unmatched"})},
                "webhook": {"path": f"/api/board-inbox/inbound?token={token}",
                            "note": "Point your email provider's inbound-parse webhook (Resend/SendGrid/Mailgun) here; "
                                    "POST JSON {from, subject, body}."}}

    @api_router.post("/board-inbox/inbound")
    async def inbound(token: str = "", payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        if token != await _webhook_token():
            raise HTTPException(status_code=401, detail="Invalid inbox token")
        doc = await process_reply(str(payload.get("from") or payload.get("from_email") or "unknown"),
                                  str(payload.get("subject") or ""),
                                  str(payload.get("body") or payload.get("text") or payload.get("html") or ""),
                                  "webhook")
        return {"ok": True, "inbox_id": doc["inbox_id"], "classification": doc["classification"],
                "action": doc["action"]}

    @api_router.post("/board-inbox/log")
    async def manual_log(payload: Dict[str, Any] = Body(...),
                         _=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        doc = await process_reply(str(payload.get("from_email") or "manual entry"),
                                  str(payload.get("subject") or ""), str(payload.get("body") or ""), "manual")
        return {"ok": True, "reply": doc}

    @api_router.post("/board-inbox/simulate")
    async def simulate(_=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        answered = await db.board_inbox.distinct("load_id")
        item = await db.loadboard_outbox.find_one(
            {"status": {"$in": ["queued", "sent"]}, "load_id": {"$nin": [x for x in answered if x]}},
            sort=[("created_at", 1)])
        if not item:
            raise HTTPException(status_code=404, detail="No unanswered booking emails to simulate a reply for")
        board = (item.get("board") or "board").upper()
        confirm = random.random() < 0.85
        if confirm:
            body = (f"This confirms your acceptance of posting {item['load_id']}. The load is yours — "
                    f"booked to Orisei Freight Solutions. Please proceed with carrier dispatch. — {board} posting desk")
            subject = f"RE: {item['subject']} — CONFIRMED"
        else:
            body = (f"Unfortunately posting referenced in {item['load_id']} is no longer available; "
                    f"it was covered by another broker this morning. — {board} posting desk")
            subject = f"RE: {item['subject']} — load no longer available"
        doc = await process_reply(f"posting-desk@{(item.get('board') or 'board')}.example.com",
                                  subject, body, "simulated")
        return {"ok": True, "reply": doc}
