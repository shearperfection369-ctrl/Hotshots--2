"""routes.orisei_auto_digest — Weekly per-shipper ops digest.

For each active Orisei customer with a primary contact email, compute their
previous-7-day KPIs (loads delivered, on-time %, A/R balance, lane spend) and
mail a branded one-page summary via Resend.

Endpoints (admin-only):
  POST /api/orisei/auto-digest/run        — execute for all eligible customers
  POST /api/orisei/auto-digest/preview    — render one customer's digest as HTML/PDF
  GET  /api/orisei/auto-digest/history    — recent runs

Cron hookup (outside the pod):
  curl -X POST -H "Authorization: Bearer <admin>" \\
       https://<host>/api/orisei/auto-digest/run

Set this as a Kubernetes CronJob, a Vercel cron, or a simple GH Actions
schedule that runs every Monday at 13:00 UTC (= 6 AM US Central).
"""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from .orisei_docs import build_branded_markdown_pdf

logger = logging.getLogger("tennant_tms.orisei_auto_digest")


# -------------------- helpers --------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.isoformat()


async def _resend_creds(db) -> Optional[Dict[str, str]]:
    try:
        from .connections import get_connection_credentials
        return await get_connection_credentials(db, "resend")
    except Exception:
        return None


async def _send_via_resend(creds: Dict[str, str], *, to: str, subject: str,
                            html: str, pdf_bytes: Optional[bytes] = None,
                            pdf_filename: Optional[str] = None,
                            extra_attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Send via Resend SDK. Returns {sent, message_id|None, error|None}."""
    if not creds or not creds.get("api_key"):
        return {"sent": False, "error": "no_resend_creds"}
    try:
        import asyncio
        import resend as _r
        _r.api_key = creds["api_key"]
        from_email = creds.get("from_email") or "onboarding@resend.dev"
        from_name = creds.get("from_name") or "Orisei Freight Solutions"
        payload: Dict[str, Any] = {
            "from": f"{from_name} <{from_email}>",
            "to": [to], "subject": subject, "html": html,
        }
        attachments: List[Dict[str, Any]] = []
        if pdf_bytes and pdf_filename:
            attachments.append({
                "filename": pdf_filename,
                "content": base64.b64encode(pdf_bytes).decode(),
            })
        for att in (extra_attachments or []):
            attachments.append({
                "filename": att["filename"],
                "content": base64.b64encode(att["content"]).decode(),
            })
        if attachments:
            payload["attachments"] = attachments
        result = await asyncio.to_thread(_r.Emails.send, payload)
        return {"sent": True, "message_id": (result or {}).get("id")}
    except Exception as exc:                                          # noqa: BLE001
        logger.warning("Resend send failed: %s", exc)
        return {"sent": False, "error": str(exc)[:300]}


def _digest_markdown(customer: Dict[str, Any],
                      kpis: Dict[str, Any],
                      bookings: List[Dict[str, Any]],
                      invoices: List[Dict[str, Any]],
                      week_start: datetime, week_end: datetime) -> str:
    """Render the per-shipper digest as branded Markdown for PDF generation."""
    delivered = [b for b in bookings if b.get("status") == "delivered"]
    in_transit = [b for b in bookings if b.get("status") in ("booked", "tendered", "in_transit")]
    outstanding = sum(float(i.get("amount_usd") or 0)
                        for i in invoices if i.get("status") == "issued")
    paid_this_week = sum(float(i.get("amount_usd") or 0)
                          for i in invoices if i.get("status") == "paid"
                          and (i.get("paid_at") or "") >= week_start.isoformat())
    on_time_pct = kpis.get("on_time_pct")
    on_time_str = f"{on_time_pct:.0f}%" if isinstance(on_time_pct, (int, float)) else "—"

    lane_lines = "\n".join(
        f"- {b.get('origin') or '—'} → {b.get('destination') or '—'} "
        f"· {b.get('carrier_name') or 'TBD'} · ${(b.get('rate_usd') or b.get('customer_rate_usd') or 0):,.0f}"
        for b in delivered[:6]
    ) or "_(No loads delivered this week.)_"

    return f"""# Weekly Freight Recap · {customer.get('name', 'Shipper')}

**Week of**: {week_start.date().isoformat()} → {(week_end - timedelta(days=1)).date().isoformat()}
**Prepared for**: {customer.get('primary_contact_name') or customer.get('name')}

---

## This Week at a Glance

| Metric | Value |
|---|---|
| Loads delivered | **{len(delivered)}** |
| Loads in transit | **{len(in_transit)}** |
| On-time delivery | **{on_time_str}** |
| Invoices paid this week | **${paid_this_week:,.2f}** |
| Outstanding A/R | **${outstanding:,.2f}** |

## Lanes We Moved For You
{lane_lines}

---

## What's Coming Up
- {len(in_transit)} active load(s) currently on dispatch
- Payment terms: **{customer.get('payment_terms', 'Net 30')}** from invoice issue date
- Need a same-day spot quote? Reply to this email — Oliver answers personally.

---

Thank you for trusting us with your freight.

**Oliver Cummins**
*Orisei Freight Solutions LLC*
Plymouth, Minnesota
oliver@oriseifreightsolutions.com
"""


def _digest_html(customer: Dict[str, Any], week_start: datetime,
                  week_end: datetime, kpis: Dict[str, Any]) -> str:
    """Inline-styled HTML for the email body (PDF is the attachment)."""
    name = customer.get("primary_contact_name") or customer.get("name")
    delivered = kpis.get("delivered_count", 0)
    on_time = kpis.get("on_time_pct")
    on_time_str = f"{on_time:.0f}%" if isinstance(on_time, (int, float)) else "—"
    return f"""
<table style="width:100%;max-width:560px;font-family:Arial,sans-serif;background:#0E3A6B;color:#fff;padding:24px;border-radius:8px;">
  <tr><td>
    <div style="font-size:11px;letter-spacing:2px;color:#C9A24A;text-transform:uppercase;">Orisei Freight Solutions · Weekly Recap</div>
    <h1 style="margin:8px 0 0 0;font-size:24px;">Hi {name},</h1>
    <p style="margin:16px 0;color:#E5E7EB;line-height:1.5;">
      Here's how your freight moved last week ({week_start.date()} → {(week_end - timedelta(days=1)).date()}):
    </p>
    <table style="width:100%;margin:16px 0;">
      <tr>
        <td style="padding:12px;background:rgba(255,255,255,0.08);border-radius:6px;text-align:center;">
          <div style="font-size:28px;font-weight:bold;color:#C9A24A;">{delivered}</div>
          <div style="font-size:11px;color:#E5E7EB;text-transform:uppercase;">Loads delivered</div>
        </td>
        <td style="width:8px;"></td>
        <td style="padding:12px;background:rgba(255,255,255,0.08);border-radius:6px;text-align:center;">
          <div style="font-size:28px;font-weight:bold;color:#C9A24A;">{on_time_str}</div>
          <div style="font-size:11px;color:#E5E7EB;text-transform:uppercase;">On-time delivery</div>
        </td>
      </tr>
    </table>
    <p style="color:#E5E7EB;font-size:13px;line-height:1.5;">
      Your full one-page recap is attached as a PDF. Reply to this email if anything
      needs attention — I respond personally within an hour.
    </p>
    <p style="margin-top:24px;color:#C9A24A;font-weight:bold;">— Oliver Cummins</p>
    <p style="color:#9CA3AF;font-size:11px;margin-top:24px;">
      Orisei Freight Solutions LLC · Plymouth, MN · oliver@oriseifreightsolutions.com
    </p>
  </td></tr>
</table>
"""


# -------------------- pydantic --------------------
class PreviewIn(BaseModel):
    customer_id: str


class RunIn(BaseModel):
    customer_ids: Optional[List[str]] = None     # if None, run for all eligible
    dry_run: bool = False
    week_start_iso: Optional[str] = None         # default: last Monday 00:00 UTC


# -------------------- main module --------------------
def build_auto_digest_router(
    api_router: APIRouter, *, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/orisei/auto-digest", tags=["orisei-auto-digest"])

    async def _compute_kpis(customer: Dict[str, Any],
                              week_start: datetime,
                              week_end: datetime) -> Dict[str, Any]:
        """Per-customer KPI math over the week window."""
        cust_id = customer["customer_id"]
        cust_name = customer.get("name")
        bookings = await db.brokerage_bookings.find(
            {"$or": [{"customer_id": cust_id}, {"customer_name": cust_name}]},
            {"_id": 0}).to_list(500)
        # Filter to delivered_at OR created_at within window
        in_window = [
            b for b in bookings
            if (b.get("delivered_at") or b.get("created_at") or "")[:10]
                >= week_start.date().isoformat()
            and (b.get("delivered_at") or b.get("created_at") or "")[:10]
                <  week_end.date().isoformat()
        ]
        delivered = [b for b in in_window if b.get("status") == "delivered"]
        on_time = None
        if delivered:
            on_time_count = sum(
                1 for b in delivered
                if not b.get("delivery_date") or not b.get("delivered_at")
                or b.get("delivered_at", "")[:10] <= b.get("delivery_date", "")
            )
            on_time = (on_time_count / len(delivered)) * 100
        invoices = await db.brokerage_invoices.find(
            {"$or": [{"customer_id": cust_id}, {"customer_name": cust_name}]},
            {"_id": 0}).to_list(500)
        return {
            "delivered_count": len(delivered),
            "in_window_total": len(in_window),
            "on_time_pct": on_time,
            "bookings": in_window,
            "invoices": invoices,
        }

    def _week_window(week_start_iso: Optional[str]) -> tuple[datetime, datetime]:
        if week_start_iso:
            ws = datetime.fromisoformat(week_start_iso.replace("Z", "+00:00"))
        else:
            now = _now()
            ws = (now - timedelta(days=now.weekday() + 7)).replace(
                hour=0, minute=0, second=0, microsecond=0)
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=timezone.utc)
        return ws, ws + timedelta(days=7)

    async def _ai_narrative(customer: Dict[str, Any], kpis: Dict[str, Any]) -> str:
        try:
            import os as _os
            import uuid as _uuid
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            key = _os.environ.get("EMERGENT_LLM_KEY")
            if not key:
                return ""
            chat = LlmChat(api_key=key, session_id=f"kpi-digest-{_uuid.uuid4().hex[:8]}",
                           system_message="You write 3-4 sentence weekly freight KPI narratives for shippers. "
                                          "Warm, factual, zero fluff, first person plural (we).").with_model(
                "anthropic", "claude-sonnet-4-5-20250929")
            summary = {k: v for k, v in kpis.items() if k not in ("bookings", "invoices")}
            reply = await chat.send_message(UserMessage(
                text=f"Weekly KPI narrative for {customer.get('name')}: {summary}"))
            return str(reply).strip()
        except Exception as exc:                                    # noqa: BLE001
            logger.warning("Digest AI narrative skipped: %s", exc)
            return ""

    async def _build_for_customer(customer: Dict[str, Any],
                                    week_start: datetime,
                                    week_end: datetime,
                                    brand: Dict[str, Any]) -> Dict[str, Any]:
        kpis = await _compute_kpis(customer, week_start, week_end)
        narrative = await _ai_narrative(customer, kpis)
        md = _digest_markdown(customer, kpis, kpis["bookings"],
                                kpis["invoices"], week_start, week_end)
        if narrative:
            md = f"> **Your week in review (AI):** {narrative}\n\n" + md
        pdf = build_branded_markdown_pdf(
            md, title="Weekly Freight Recap",
            subtitle=f"For {customer.get('name')}",
            brand=brand,
        )
        html = _digest_html(customer, week_start, week_end, kpis)
        return {"customer": customer, "kpis": kpis, "markdown": md,
                "pdf_bytes": pdf, "html": html}

    @router.post("/preview")
    async def preview_digest(payload: PreviewIn,
                              user=Depends(require_role("admin"))) -> Dict[str, Any]:
        customer = await db.orisei_customers.find_one(
            {"customer_id": payload.customer_id}, {"_id": 0})
        if not customer:
            raise HTTPException(404, "Customer not found")
        brand = await db.company_brand.find_one(
            {"is_active": True}, {"_id": 0}) or {}
        ws, we = _week_window(None)
        built = await _build_for_customer(customer, ws, we, brand)
        return {
            "customer_name": customer.get("name"),
            "week_start": _iso(ws), "week_end": _iso(we),
            "kpis": {k: v for k, v in built["kpis"].items()
                      if k in ("delivered_count", "in_window_total", "on_time_pct")},
            "email_html": built["html"],
            "pdf_size_bytes": len(built["pdf_bytes"]),
            "markdown": built["markdown"],
        }

    @router.post("/run")
    async def run_digest(payload: RunIn,
                          user=Depends(require_role("admin"))) -> Dict[str, Any]:
        ws, we = _week_window(payload.week_start_iso)
        q = {"active": True}
        if payload.customer_ids:
            q["customer_id"] = {"$in": payload.customer_ids}
        customers = await db.orisei_customers.find(q, {"_id": 0}).to_list(500)
        eligible = [c for c in customers
                     if (c.get("primary_contact_email") or c.get("ap_email"))]
        brand = await db.company_brand.find_one(
            {"is_active": True}, {"_id": 0}) or {}
        creds = await _resend_creds(db) if not payload.dry_run else None
        run_id = f"DIG-{uuid.uuid4().hex[:10].upper()}"
        run_started = _iso(_now())
        results: List[Dict[str, Any]] = []
        for c in eligible:
            to_email = (c.get("primary_contact_email") or c.get("ap_email"))
            try:
                built = await _build_for_customer(c, ws, we, brand)
            except Exception as exc:                                  # noqa: BLE001
                logger.exception("Digest render failed for %s", c.get("customer_id"))
                results.append({"customer_id": c["customer_id"],
                                "customer_name": c.get("name"),
                                "to": to_email,
                                "status": "render_failed",
                                "error": str(exc)[:200]})
                continue
            if payload.dry_run:
                results.append({"customer_id": c["customer_id"],
                                "customer_name": c.get("name"),
                                "to": to_email,
                                "status": "dry_run",
                                "pdf_size_bytes": len(built["pdf_bytes"]),
                                "delivered": built["kpis"]["delivered_count"]})
                continue
            send_res = await _send_via_resend(
                creds or {},
                to=to_email,
                subject=f"Your weekly freight recap · {c.get('name')} · {ws.date()}",
                html=built["html"], pdf_bytes=built["pdf_bytes"],
                pdf_filename=f"Orisei_Recap_{c['customer_id']}_{ws.date()}.pdf",
            )
            results.append({"customer_id": c["customer_id"],
                            "customer_name": c.get("name"),
                            "to": to_email,
                            "status": "sent" if send_res["sent"] else "failed",
                            "message_id": send_res.get("message_id"),
                            "error": send_res.get("error"),
                            "delivered": built["kpis"]["delivered_count"]})
        run_doc = {
            "run_id": run_id,
            "started_at": run_started,
            "completed_at": _iso(_now()),
            "week_start": _iso(ws), "week_end": _iso(we),
            "triggered_by": getattr(user, "name", "system"),
            "dry_run": payload.dry_run,
            "total_eligible": len(eligible),
            "sent": sum(1 for r in results if r["status"] == "sent"),
            "drafted": sum(1 for r in results if r["status"] in ("dry_run",)),
            "failed": sum(1 for r in results if r["status"] in ("failed", "render_failed")),
            "results": results,
        }
        await db.orisei_auto_digest_runs.insert_one(dict(run_doc))
        run_doc.pop("_id", None)
        return run_doc

    @router.get("/history")
    async def digest_history(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        rows = await db.orisei_auto_digest_runs.find(
            {}, {"_id": 0, "results": 0}     # exclude per-row details by default
        ).sort("started_at", -1).limit(30).to_list(30)
        return {"items": rows, "count": len(rows)}

    @router.get("/history/{run_id}")
    async def digest_history_detail(run_id: str,
                                      _=Depends(require_role("admin"))) -> Dict[str, Any]:
        row = await db.orisei_auto_digest_runs.find_one(
            {"run_id": run_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Run not found")
        return row

    api_router.include_router(router)

    async def _weekly_scheduler() -> None:
        """AI-handled weekly digest: auto-runs every Monday 07:00-08:00 CT."""
        await asyncio.sleep(45)
        while True:
            try:
                ct = _now() - timedelta(hours=6)
                if ct.weekday() == 0 and 7 <= ct.hour < 8:
                    wk = ct.strftime("%G-W%V")
                    state = await db.orisei_digest_state.find_one({"_id": "weekly"}) or {}
                    if state.get("last_week") != wk:
                        await run_digest.__wrapped__(RunIn(), None) if hasattr(run_digest, "__wrapped__") \
                            else await run_digest(RunIn(), None)
                        await db.orisei_digest_state.update_one(
                            {"_id": "weekly"}, {"$set": {"last_week": wk, "ran_at": _iso(_now())}},
                            upsert=True)
                        logger.info("Weekly shipper KPI digest auto-run complete (%s)", wk)
            except Exception as exc:                                # noqa: BLE001
                logger.warning("Weekly digest scheduler error: %s", exc)
            await asyncio.sleep(1800)

    return _weekly_scheduler
