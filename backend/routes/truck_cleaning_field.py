"""routes.truck_cleaning_field — SMS reminders w/ one-tap reschedule + before/after photo proof."""
import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import resend
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from PIL import Image
from pydantic import BaseModel, Field

from routes.connections import get_connection_credentials
from routes.truck_cleaning import UPSELLS, UPSELL_META, SCENT_MENU

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_base() -> str:
    for k in ("PUBLIC_APP_URL", "FRONTEND_PUBLIC_URL", "REACT_APP_BACKEND_URL"):
        v = (os.environ.get(k) or "").rstrip("/")
        if v:
            return v
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except OSError:
        pass
    return ""


class RescheduleIn(BaseModel):
    new_date: str = Field(..., min_length=10, max_length=10)  # YYYY-MM-DD


class ProofSendIn(BaseModel):
    to_email: str = Field(..., min_length=5, max_length=200)
    message: str = Field("", max_length=600)


async def _send_sms(db, to: str, body: str, *, job_id: str = "", kind: str = "reminder") -> Dict[str, Any]:
    """Send via Twilio (Connections vault). No creds → queue the message so nothing is lost."""
    creds = await get_connection_credentials(db, "twilio") or {}
    row = {"sms_id": f"SMS-{uuid.uuid4().hex[:8].upper()}", "to": to, "body": body,
           "job_id": job_id, "kind": kind, "created_at": _now()}
    if not (creds.get("account_sid") and creds.get("auth_token") and creds.get("from_number")):
        row["status"] = "queued"
        row["note"] = "Twilio not configured — will send once keys are added in Connections"
        await db.tc_sms_log.insert_one(dict(row))
        return row
    try:
        from twilio.rest import Client
        client = Client(creds["account_sid"], creds["auth_token"])
        msg = await asyncio.to_thread(client.messages.create, to=to, from_=creds["from_number"], body=body)
        row["status"] = "sent"
        row["twilio_sid"] = msg.sid
    except Exception as exc:  # noqa: BLE001
        logger.exception("Twilio send failed")
        row["status"] = "failed"
        row["note"] = str(exc)[:200]
    await db.tc_sms_log.insert_one(dict(row))
    return row


async def _remind_job(db, job: Dict[str, Any]) -> Dict[str, Any]:
    client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
    phone = (client.get("phone") or "").strip()
    if not phone:
        return {"job_id": job["job_id"], "status": "skipped", "note": "client has no phone on file"}
    token = job.get("reschedule_token") or uuid.uuid4().hex
    scent_token = job.get("scent_card_token") or uuid.uuid4().hex
    await db.tc_jobs.update_one({"job_id": job["job_id"]},
                                {"$set": {"reschedule_token": token, "scent_card_token": scent_token}})
    link = f"{_public_base()}/tc/reschedule/{token}"
    scent_link = f"{_public_base()}/tc/scent/{scent_token}"
    body = (f"Orisei Truck Cleaning: confirming your cleaning for {job['company']} on {job['date']} "
            f"({job['cabs']} cab{'s' if job['cabs'] != 1 else ''}). Need a different day? "
            f"One tap: {link} | Pick your scent + bunk upgrades: {scent_link}")
    sms = await _send_sms(db, phone, body, job_id=job["job_id"], kind="reminder")
    await db.tc_jobs.update_one({"job_id": job["job_id"]},
                                {"$set": {"reminder_status": sms["status"], "reminder_sent_at": _now(),
                                          "reminder_for_date": job["date"]}})
    return {"job_id": job["job_id"], "status": sms["status"], "to": phone, "note": sms.get("note")}


async def run_tomorrow_reminders(db) -> Dict[str, Any]:
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    jobs = await db.tc_jobs.find({"date": tomorrow, "status": "scheduled"}, {"_id": 0}).to_list(300)
    results = []
    for j in jobs:
        if j.get("reminder_for_date") == tomorrow:
            continue  # already reminded for this window
        results.append(await _remind_job(db, j))
    return {"target_date": tomorrow, "eligible": len(jobs), "processed": results}


async def reminders_autorun_loop(db):
    """Fires every 6 hours; sends each job's tomorrow-reminder exactly once."""
    while True:
        try:
            out = await run_tomorrow_reminders(db)
            if out["processed"]:
                logger.info("TC reminders autorun: %s", out)
        except Exception:  # noqa: BLE001
            logger.exception("TC reminders autorun failed")
        await asyncio.sleep(6 * 3600)


def build_truck_cleaning_field_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-field"])
    guard = require_role("admin", "owner", "dispatcher")
    photos = AsyncIOMotorGridFSBucket(db, bucket_name="tc_photos")

    # ================= SMS REMINDERS =================
    @router.post("/jobs/{job_id}/remind")
    async def remind(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return await _remind_job(db, job)

    @router.post("/reminders/run")
    async def reminders_run(_=Depends(guard)) -> Dict[str, Any]:
        return await run_tomorrow_reminders(db)

    @router.get("/sms-log")
    async def sms_log(_=Depends(guard)) -> Dict[str, Any]:
        creds = await get_connection_credentials(db, "twilio") or {}
        rows = await db.tc_sms_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"twilio_configured": bool(creds.get("account_sid")), "log": rows,
                "queued": sum(1 for r in rows if r["status"] == "queued")}

    # -------- public one-tap reschedule --------
    @router.get("/reschedule/{token}")
    async def reschedule_info(token: str) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"reschedule_token": token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Reschedule link not found")
        return {k: job.get(k) for k in ("job_id", "company", "date", "cabs", "status")}

    @router.post("/reschedule/{token}")
    async def reschedule(token: str, payload: RescheduleIn) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"reschedule_token": token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Reschedule link not found")
        if job["status"] != "scheduled":
            raise HTTPException(status_code=400, detail="This job is already completed — call us to book a new one")
        try:
            nd = datetime.strptime(payload.new_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD")
        if nd <= datetime.now(timezone.utc).date():
            raise HTTPException(status_code=400, detail="Pick a future date")
        await db.tc_jobs.update_one({"reschedule_token": token},
                                    {"$set": {"date": payload.new_date, "rescheduled_from": job["date"],
                                              "rescheduled_at": _now(), "reminder_for_date": None}})
        client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
        if client.get("phone"):
            await _send_sms(db, client["phone"],
                            f"Orisei Truck Cleaning: your cleaning is rescheduled to {payload.new_date}. "
                            f"We'll confirm the window 24h before. Thanks!",
                            job_id=job["job_id"], kind="reschedule_confirm")
        return {"ok": True, "new_date": payload.new_date}

    # ================= PHOTO PROOF =================
    @router.post("/jobs/{job_id}/photos")
    async def upload_photo(job_id: str, file: UploadFile = File(...), kind: str = Form("before"),
                           caption: str = Form(""), _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if kind not in ("before", "after"):
            raise HTTPException(status_code=400, detail="kind must be before|after")
        existing = await db["tc_photos.files"].count_documents({"metadata.job_id": job_id})
        if existing >= 8:
            raise HTTPException(status_code=400, detail="Max 8 photos per job")
        raw = await file.read()
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            raise HTTPException(status_code=400, detail="Not a valid image")
        im.thumbnail((1280, 1280))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82)
        data = buf.getvalue()
        proof_token = job.get("proof_token") or uuid.uuid4().hex
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"proof_token": proof_token}})
        fid = await photos.upload_from_stream(f"{job_id}_{kind}.jpg", data, metadata={
            "job_id": job_id, "kind": kind, "caption": caption[:200],
            "size_bytes": len(data), "uploaded_at": _now()})
        return {"ok": True, "photo_id": str(fid), "kind": kind, "proof_token": proof_token}

    async def _job_photos(job_id: str):
        rows = await db["tc_photos.files"].find({"metadata.job_id": job_id}).sort("uploadDate", 1).to_list(20)
        return [{"photo_id": str(f["_id"]), "kind": (f.get("metadata") or {}).get("kind"),
                 "caption": (f.get("metadata") or {}).get("caption", "")} for f in rows]

    @router.get("/jobs/{job_id}/photos")
    async def list_photos(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"photos": await _job_photos(job_id), "proof_token": job.get("proof_token")}

    @router.delete("/photos/{photo_id}")
    async def delete_photo(photo_id: str, _=Depends(guard)) -> Dict[str, Any]:
        try:
            await photos.delete(ObjectId(photo_id))
        except Exception:
            raise HTTPException(status_code=404, detail="Photo not found")
        return {"ok": True}

    @router.post("/jobs/{job_id}/proof/send")
    async def send_proof(job_id: str, payload: ProofSendIn, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        plist = await _job_photos(job_id)
        if not plist:
            raise HTTPException(status_code=400, detail="Upload at least one photo first")
        proof_token = job.get("proof_token")
        proof_url = f"{_public_base()}/tc/proof/{proof_token}"
        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        if not api_key:
            raise HTTPException(status_code=400,
                                detail=f"Resend is not configured — copy the proof link instead: {proof_url}")
        base_api = f"{_public_base()}/api/truck-cleaning/proof/{proof_token}/photo"
        before = [p for p in plist if p["kind"] == "before"][:2]
        after = [p for p in plist if p["kind"] == "after"][:2]
        img_row = "".join(
            f'<td style="padding:4px;"><div style="font-size:10px;letter-spacing:.2em;color:#64748B;font-family:Courier,monospace;text-transform:uppercase;margin-bottom:4px;">{p["kind"]}</div>'
            f'<img src="{base_api}/{p["photo_id"]}" width="260" style="border-radius:8px;display:block;" /></td>'
            for p in (before + after))
        msg = f'<p style="background:#FFF8EB;border-left:3px solid #F59E0B;padding:10px 14px;">{payload.message}</p>' if payload.message else ""
        html = f"""<!doctype html><html><body style="font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#F8FAFC;padding:24px;color:#0D1117;">
<div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
  <div style="background:#0D1117;color:#fff;padding:22px 26px;border-bottom:4px solid #F59E0B;">
    <div style="font-size:11px;letter-spacing:.3em;color:#F59E0B;text-transform:uppercase;font-family:Courier,monospace;">Orisei Truck Cleaning</div>
    <div style="font-size:22px;font-weight:800;margin-top:6px;">Your photo proof — {job['date']}</div>
  </div>
  <div style="padding:24px 26px;font-size:14px;line-height:1.6;">
    <p>Hi {job.get('company', 'Team')},</p>
    <p>Job complete — {job['cabs']} cab(s) cleaned to the 45-minute showroom spec. Here's the proof:</p>
    {msg}
    <table style="width:100%;border-collapse:collapse;"><tr>{img_row}</tr></table>
    <p style="text-align:center;margin:22px 0;">
      <a href="{proof_url}" style="background:#F59E0B;color:#0D1117;font-weight:800;padding:12px 28px;border-radius:999px;text-decoration:none;">VIEW FULL GALLERY</a>
    </p>
    <p style="margin-top:20px;">— Oliver Cummins<br><b>Orisei Truck Cleaning Solutions</b><br>oliver@oriseifreightsolutions.com · (763) 443-4459</p>
  </div></div></body></html>"""
        try:
            resend.api_key = api_key
            resp = resend.Emails.send({
                "from": creds.get("from_email") or "Orisei Truck Cleaning <oliver@oriseifreightsolutions.com>",
                "to": [payload.to_email],
                "subject": f"Photo proof — {job['company']} cab cleaning {job['date']}",
                "html": html})
        except Exception as exc:  # noqa: BLE001
            logger.exception("TC proof email failed")
            raise HTTPException(status_code=502, detail=f"Resend send failed: {str(exc)[:180]}")
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"proof_sent_at": _now(), "proof_sent_to": payload.to_email}})
        review = await _request_review(job)
        return {"ok": True, "proof_url": proof_url, "review_request": review,
                "message_id": (resp or {}).get("id") if isinstance(resp, dict) else None}

    # -------- public proof gallery --------
    @router.get("/proof/{proof_token}")
    async def public_proof(proof_token: str) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"proof_token": proof_token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Proof link not found")
        return {"company": job["company"], "date": job["date"], "cabs": job["cabs"],
                "status": job["status"], "photos": await _job_photos(job["job_id"])}

    @router.get("/proof/{proof_token}/photo/{photo_id}")
    async def public_proof_photo(proof_token: str, photo_id: str) -> Response:
        job = await db.tc_jobs.find_one({"proof_token": proof_token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Proof link not found")
        try:
            grid_out = await photos.open_download_stream(ObjectId(photo_id))
        except Exception:
            raise HTTPException(status_code=404, detail="Photo not found")
        if (grid_out.metadata or {}).get("job_id") != job["job_id"]:
            raise HTTPException(status_code=404, detail="Photo not found")
        data = await grid_out.read()
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400"})

    # ================= REVIEW ENGINE =================
    async def _request_review(job: Dict[str, Any]) -> Dict[str, Any]:
        settings = await db.tc_settings.find_one({"_id": "truck_cleaning"}) or {}
        review_url = settings.get("google_review_url", "")
        if not review_url:
            return {"status": "skipped", "note": "no review link set — add it in AI Offers · Review Engine"}
        if job.get("review_requested_at"):
            return {"status": "skipped", "note": "already requested"}
        client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
        phone = (client.get("phone") or "").strip()
        if not phone:
            return {"status": "skipped", "note": "client has no phone"}
        sms = await _send_sms(db, phone,
                              f"Thanks for trusting Orisei Truck Cleaning with your cabs, {job['company']}! "
                              f"Your before/after photos just landed. If we earned it, a 5-star review takes 20 seconds "
                              f"and means the world to our crew: {review_url}",
                              job_id=job["job_id"], kind="review_request")
        await db.tc_jobs.update_one({"job_id": job["job_id"]},
                                    {"$set": {"review_requested_at": _now(), "review_sms_status": sms["status"]}})
        return {"status": sms["status"]}

    @router.post("/jobs/{job_id}/review-request")
    async def manual_review_request(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job.pop("review_requested_at", None)
        return await _request_review(job)

    @router.get("/settings")
    async def get_settings(_=Depends(guard)) -> Dict[str, Any]:
        s = await db.tc_settings.find_one({"_id": "truck_cleaning"}) or {}
        reviews = await db.tc_jobs.count_documents({"review_requested_at": {"$ne": None}})
        return {"google_review_url": s.get("google_review_url", ""), "review_requests_sent": reviews}

    @router.post("/settings")
    async def set_settings(payload: Dict[str, str], _=Depends(guard)) -> Dict[str, Any]:
        url = (payload.get("google_review_url") or "").strip()[:400]
        await db.tc_settings.update_one({"_id": "truck_cleaning"},
                                        {"$set": {"google_review_url": url, "updated_at": _now()}}, upsert=True)
        return {"ok": True, "google_review_url": url}

    # ================= DRIVER SCENT CARD =================
    @router.post("/jobs/{job_id}/scent-card")
    async def make_scent_card(job_id: str, _=Depends(guard)) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        token = job.get("scent_card_token") or uuid.uuid4().hex
        await db.tc_jobs.update_one({"job_id": job_id}, {"$set": {"scent_card_token": token}})
        return {"ok": True, "link_path": f"/tc/scent/{token}"}

    @router.get("/scent/{token}")
    async def scent_card_info(token: str) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"scent_card_token": token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Scent card not found")
        options = [u for u in UPSELL_META if u["category"] in ("freshener", "bedding")]
        return {"company": job["company"], "date": job["date"], "cabs": job["cabs"], "status": job["status"],
                "scents": SCENT_MENU, "upgrades": options,
                "current": job.get("driver_prefs") or {"scent": "", "upsell_ids": []},
                "locked": job["status"] != "scheduled"}

    @router.post("/scent/{token}")
    async def scent_card_submit(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        job = await db.tc_jobs.find_one({"scent_card_token": token}, {"_id": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Scent card not found")
        if job["status"] != "scheduled":
            raise HTTPException(status_code=400, detail="This job is already done — picks apply to your next visit, call us!")
        scent = str(payload.get("scent") or "")[:60]
        if scent and scent not in SCENT_MENU:
            raise HTTPException(status_code=400, detail="Pick a scent from the menu")
        valid_ids = {u["id"] for u in UPSELL_META if u["category"] in ("freshener", "bedding")}
        picks = [u for u in (payload.get("upsell_ids") or []) if u in valid_ids][:10]
        ups = sorted(set([u for u in job.get("upsells", []) if u not in valid_ids] + picks))
        client = await db.tc_clients.find_one({"client_id": job["client_id"]}, {"_id": 0}) or {}
        price = round(job["cabs"] * client.get("rate", 175) + sum(UPSELLS[u] for u in ups), 2)
        await db.tc_jobs.update_one({"scent_card_token": token},
                                    {"$set": {"upsells": ups, "price": price,
                                              "driver_prefs": {"scent": scent, "upsell_ids": picks,
                                                               "submitted_at": _now()}}})
        added = round(sum(UPSELLS[u] for u in picks), 2)
        return {"ok": True, "scent": scent, "added_total": added,
                "message": "Locked in — the crew will have it on the truck."}

    return router
