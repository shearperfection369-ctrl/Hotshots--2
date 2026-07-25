"""routes.quotes — branded freight quote builder.

CRUD quotes with lane line-items, deterministic DAT-style market benchmark
per lane, and a branded one-page quote PDF.
"""
from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("tennant_tms.quotes")

STATUSES = ["draft", "sent", "accepted", "declined", "expired"]
EQUIPMENT_BASE = {"van": 2.05, "reefer": 2.55, "flatbed": 2.48, "stepdeck": 2.62, "power-only": 1.80}


def market_per_mile(origin: str, dest: str, equipment: str) -> float:
    base = EQUIPMENT_BASE.get((equipment or "van").strip().lower(), 2.10)
    key = f"{(origin or '').strip().lower()}|{(dest or '').strip().lower()}|{(equipment or '').strip().lower()}"
    h = int(hashlib.md5(key.encode()).hexdigest()[:6], 16)
    jitter = (h % 61 - 30) / 100
    return round(base + jitter, 2)


class LineItem(BaseModel):
    origin: str
    destination: str
    equipment: str = "van"
    miles: int = 0
    rate_usd: float = 0
    fuel_pct: float = 0
    accessorials_usd: float = 0
    notes: str = ""


class QuoteIn(BaseModel):
    shipper: str
    contact_name: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    valid_days: int = 14
    status: str = "draft"
    notes: str = ""
    lines: List[LineItem] = Field(default_factory=list)


class QuotePatch(BaseModel):
    shipper: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    valid_days: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    lines: Optional[List[LineItem]] = None


class BenchmarkIn(BaseModel):
    lines: List[LineItem]


def _enrich_lines(lines: List[dict]) -> List[dict]:
    out = []
    for ln in lines:
        bpm = market_per_mile(ln["origin"], ln["destination"], ln["equipment"])
        miles = ln.get("miles") or 0
        rate = ln.get("rate_usd") or 0
        line_total = round(rate * (1 + (ln.get("fuel_pct") or 0) / 100) + (ln.get("accessorials_usd") or 0), 2)
        out.append({**ln,
                    "market_per_mile": bpm,
                    "market_total": round(bpm * miles, 2) if miles else None,
                    "line_total": line_total})
    return out


def _totals(lines: List[dict]) -> dict:
    total = round(sum(l["line_total"] for l in lines), 2)
    market = round(sum(l["market_total"] or 0 for l in lines), 2)
    return {"total_usd": total, "market_total_usd": market,
            "vs_market_usd": round(market - total, 2) if market else None}


def build_quotes_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/freight-quotes")
    col = db.freight_quotes

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _next_number() -> str:
        year = datetime.now(timezone.utc).year
        n = await col.count_documents({}) + 1
        return f"ORQ-{year}-{n:04d}"

    @router.get("")
    async def list_quotes(_=Depends(get_current_user)):
        rows = await col.find({}, {"_id": 0}).sort("updated_at", -1).to_list(300)
        return {"quotes": rows,
                "counts": {s: sum(1 for r in rows if r.get("status") == s) for s in STATUSES}}

    @router.post("")
    async def create_quote(payload: QuoteIn, _=Depends(get_current_user)):
        if payload.status not in STATUSES:
            raise HTTPException(400, "Invalid status")
        lines = _enrich_lines([l.model_dump() for l in payload.lines])
        doc = {**payload.model_dump(exclude={"lines"}),
               "id": await _next_number(), "lines": lines, **_totals(lines),
               "valid_until": (datetime.now(timezone.utc) + timedelta(days=payload.valid_days)).date().isoformat(),
               "created_at": _now(), "updated_at": _now()}
        await col.insert_one({**doc})
        doc.pop("_id", None)
        return {"ok": True, "quote": doc}

    @router.get("/{qid}")
    async def get_quote(qid: str, _=Depends(get_current_user)):
        doc = await col.find_one({"id": qid}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Quote not found")
        return doc

    @router.patch("/{qid}")
    async def update_quote(qid: str, payload: QuotePatch, _=Depends(get_current_user)):
        existing = await col.find_one({"id": qid}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Quote not found")
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if "status" in updates and updates["status"] not in STATUSES:
            raise HTTPException(400, "Invalid status")
        if "lines" in updates:
            lines = _enrich_lines([l if isinstance(l, dict) else l for l in updates["lines"]])
            updates["lines"] = lines
            updates.update(_totals(lines))
        if "valid_days" in updates:
            updates["valid_until"] = (datetime.now(timezone.utc) + timedelta(days=updates["valid_days"])).date().isoformat()
        updates["updated_at"] = _now()
        await col.update_one({"id": qid}, {"$set": updates})
        doc = await col.find_one({"id": qid}, {"_id": 0})
        return {"ok": True, "quote": doc}

    @router.delete("/{qid}")
    async def delete_quote(qid: str, _=Depends(get_current_user)):
        res = await col.delete_one({"id": qid})
        if res.deleted_count == 0:
            raise HTTPException(404, "Quote not found")
        return {"ok": True}

    @router.post("/benchmark")
    async def benchmark(payload: BenchmarkIn, _=Depends(get_current_user)):
        lines = _enrich_lines([l.model_dump() for l in payload.lines])
        return {"lines": lines, **_totals(lines)}

    @router.get("/{qid}/pdf")
    async def quote_pdf(qid: str, _=Depends(get_current_user)):
        doc = await col.find_one({"id": qid}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Quote not found")
        from .quote_pdf import build_quote_pdf
        pdf_bytes = build_quote_pdf(doc)
        return StreamingResponse(
            io.BytesIO(pdf_bytes), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="Orisei_Quote_{qid}.pdf"'})

    return router
