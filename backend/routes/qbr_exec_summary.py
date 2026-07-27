"""routes.qbr_exec_summary — AI executive-summary PDF for QBR Studio."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from .plan_brochure import AZURE, GOLD, GOLD_LIGHT, INK, PAPER, SLATE, WHITE, _para
from .orisei_docs import LOGO_PATH
from .qbr_studio import _compute_metrics, _quarter_bounds

W, H = letter


def build_qbr_exec_router(*, db, get_current_user: Callable,
                          emergent_llm_key: Optional[str], LlmChat, UserMessage) -> APIRouter:  # noqa: N803
    router = APIRouter(prefix="/qbr-studio", tags=["qbr-exec"])

    @router.get("/exec-summary/{shipper_name}/pdf")
    async def exec_summary_pdf(shipper_name: str, period: str, _=Depends(get_current_user)):
        bounds = _quarter_bounds(period)
        if not bounds:
            raise HTTPException(400, "period must look like Q1-2026")
        start, end, label = bounds
        m = await _compute_metrics(db, shipper_name, start, end)
        if not emergent_llm_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
        prompt = (
            f"Write a freight QBR executive summary (240-300 words) for shipper '{shipper_name}', period {label}. "
            f"Computed data: {m}. Structure: 1) headline performance verdict, 2) what the numbers say "
            "(on-time, volume, margin/claims if present), 3) risks to watch, 4) three concrete recommendations "
            "for next quarter. Confident advisory tone, plain language, no markdown headers — short paragraphs "
            "and dash bullets only."
        )
        try:
            chat = LlmChat(api_key=emergent_llm_key, session_id=f"qbr-exec-{uuid.uuid4().hex[:8]}",
                           system_message="Senior freight-brokerage account strategist writing for a shipper's executives.").with_model(
                "anthropic", "claude-sonnet-4-5-20250929")
            narrative = await chat.send_message(UserMessage(text=prompt))
        except Exception as e:                                       # noqa: BLE001
            raise HTTPException(502, f"AI provider error: {e}")

        buf = io.BytesIO()
        c = Canvas(buf, pagesize=letter)
        c.setTitle(f"QBR Executive Summary · {shipper_name} · {label}")
        c.setFillColor(PAPER); c.rect(0, 0, W, H, fill=1, stroke=0)
        c.setFillColor(AZURE); c.rect(0, H - 96, W, 96, fill=1, stroke=0)
        c.setFillColor(GOLD); c.rect(0, H - 102, W, 6, fill=1, stroke=0)
        try:
            c.drawImage(str(LOGO_PATH), 40, H - 84, width=56, height=56,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
        c.setFont("Helvetica-Bold", 18); c.setFillColor(WHITE)
        c.drawString(110, H - 50, "EXECUTIVE SUMMARY — QUARTERLY BUSINESS REVIEW")
        c.setFont("Helvetica", 9.5); c.setFillColor(GOLD_LIGHT)
        c.drawString(110, H - 68, f"{shipper_name} · {label} · AI-computed from live desk data · Orisei Freight Solutions")
        y = H - 130
        kpis = [("Loads", m.get("volume_loads")), ("Revenue", m.get("revenue_usd")),
                ("OTP %", m.get("otp_pct")), ("OTD %", m.get("otd_pct")),
                ("Damage-free %", m.get("damage_free_pct")), ("Avg margin %", m.get("margin_pct"))]
        x = 40
        c.setFont("Helvetica-Bold", 8)
        for lab, val in kpis:
            c.setFillColor(SLATE); c.drawString(x, y, lab.upper())
            c.setFillColor(AZURE); c.setFont("Helvetica-Bold", 13)
            disp = "—" if val is None else (f"${val:,.0f}" if lab == "Revenue" else f"{val:g}")
            c.drawString(x, y - 16, disp)
            c.setFont("Helvetica-Bold", 8)
            x += 88
        yy = y - 48
        for para in [p for p in str(narrative).split("\n") if p.strip()]:
            yy = _para(c, para.strip(), 40, yy, "Helvetica", 9.5, W - 80, INK, leading=13.5) - 8
            if yy < 80:
                break
        c.setFillColor(GOLD); c.rect(0, 26, W, 2.5, fill=1, stroke=0)
        c.setFont("Helvetica", 7); c.setFillColor(SLATE)
        c.drawString(40, 14, "Orisei Freight Solutions LLC · oliver@oriseifreightsolutions.com")
        c.drawRightString(W - 40, 14, f"Generated {datetime.now(timezone.utc).date().isoformat()}")
        c.save()
        return StreamingResponse(io.BytesIO(buf.getvalue()), media_type="application/pdf",
                                 headers={"Content-Disposition": f'attachment; filename="QBR_Exec_Summary_{label}.pdf"'})

    return router
