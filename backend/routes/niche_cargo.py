"""routes.niche_cargo — AI Niche Cargo Master.

Mines booking + strike data for consistent profitable lanes and niches,
and produces an AI capitalization advisory (cached 6h).
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger("tennant_tms.niche_cargo")

NICHE_LIBRARY = [
    {"niche": "Reefer produce & proteins", "who": "Pet food plants, meat processors, dairies (GLP-style shippers)", "why": "Reefer pays ~$3.45/mi vs $2.05 dry — 40-60% premium; spoilage risk keeps amateurs out"},
    {"niche": "Flatbed steel & building products", "who": "Fabricators, lumber mills, roofing distributors", "why": "Tarping/securement expertise = fewer competitors; ~$3.40/mi"},
    {"niche": "Medical & pharma (temp-controlled)", "who": "Device makers, wholesale pharma distributors", "why": "Compliance burden (validation, chain of custody) supports 18-22% margins"},
    {"niche": "Trade-show & event freight", "who": "Exhibit houses, AV companies", "why": "Hard deadlines + white-glove = 20%+ margins, repeat annual calendar"},
    {"niche": "Oversize/overweight permits", "who": "Ag equipment, generators, HVAC units", "why": "Permit knowledge is the moat; per-load fees $400-900 on top"},
    {"niche": "Final-mile liftgate B2B", "who": "Furniture, fitness equipment, kiosk installers", "why": "Accessorial-rich; lane notes (liftgate/no-dock) are the operating edge"},
]


def build_niche_cargo_router(*, db, get_current_user: Callable,
                             emergent_llm_key: Optional[str], LlmChat, UserMessage) -> APIRouter:  # noqa: N803
    router = APIRouter(prefix="/niche-cargo", tags=["niche-cargo"])

    async def _mine() -> Dict[str, Any]:
        lanes: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"loads": 0, "revenue": 0.0, "margin": 0.0, "equipment": "", "src": set()})
        for b in await db.brokerage_bookings.find({}, {"_id": 0}).to_list(3000):
            o, d = b.get("origin") or "?", b.get("destination") or "?"
            eq = (b.get("equipment") or "van").lower()
            k = f"{o} → {d} · {eq}"
            rate = float(b.get("forecast_rate_usd") or b.get("settled_rate_usd") or 0)
            m = float(b.get("forecast_margin_usd") or b.get("settled_margin_usd") or 0)
            L = lanes[k]
            L["loads"] += 1; L["revenue"] += rate; L["margin"] += m
            L["equipment"] = eq; L["origin"], L["destination"] = o, d
            L["src"].add(b.get("source") or "desk")
        rows = []
        for k, L in lanes.items():
            mp = (L["margin"] / L["revenue"] * 100) if L["revenue"] else 0
            rows.append({"lane": k, "origin": L.get("origin"), "destination": L.get("destination"),
                         "equipment": L["equipment"], "loads": L["loads"],
                         "revenue_usd": round(L["revenue"]), "margin_usd": round(L["margin"]),
                         "margin_pct": round(mp, 1), "sources": sorted(L["src"]),
                         "consistent_profitable": L["loads"] >= 3 and mp >= 12,
                         "verdict": ("PURSUE — consistent & profitable" if L["loads"] >= 3 and mp >= 12
                                     else "watch — needs volume" if mp >= 12
                                     else "margin thin — reprice or drop")})
        rows.sort(key=lambda r: (r["consistent_profitable"], r["margin_usd"]), reverse=True)
        return {"lanes": rows[:25],
                "pursue": [r for r in rows if r["consistent_profitable"]][:8],
                "niche_library": NICHE_LIBRARY}

    @router.get("/analysis")
    async def analysis(_=Depends(get_current_user)):
        return {**(await _mine()), "generated_at": datetime.now(timezone.utc).isoformat()}

    @router.post("/ai-advise")
    async def ai_advise(_=Depends(get_current_user)):
        cached = await db.niche_advice.find_one({"_id": "latest"}, {"_id": 0})
        if cached and cached.get("at", "") > (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat():
            return {**cached, "cached": True}
        if not emergent_llm_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
        data = await _mine()
        pursue = data["pursue"]
        prompt = (
            "You are the Niche Cargo Master for Orisei Freight Solutions, a Minneapolis brokerage. "
            "Given these consistent/profitable lanes from live desk data:\n"
            + "\n".join(f"- {r['lane']}: {r['loads']} loads, {r['margin_pct']}% margin, ${r['margin_usd']:,} total margin"
                        for r in pursue[:8])
            + "\n\nAdvise in under 350 words: (1) which 2-3 lanes to double down on and exactly how "
              "(dedicated capacity, 90-day fixed pricing, which shipper types to cold-call on those lanes); "
              "(2) which niche specializations fit these lanes (reefer, flatbed, medical, etc.) and what companies "
              "typically ship them; (3) one contrarian niche opportunity most brokers ignore. "
              "Blunt operator tone, bullet points, name real shipper archetypes."
        )
        try:
            chat = LlmChat(api_key=emergent_llm_key, session_id=f"niche-{uuid.uuid4().hex[:8]}",
                           system_message="Blunt freight-brokerage growth strategist. No fluff.").with_model(
                "anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=prompt))
        except Exception as e:                                       # noqa: BLE001
            raise HTTPException(502, f"AI provider error: {e}")
        doc = {"advice": reply, "at": datetime.now(timezone.utc).isoformat(),
               "based_on_lanes": [r["lane"] for r in pursue[:8]]}
        await db.niche_advice.update_one({"_id": "latest"}, {"$set": doc}, upsert=True)
        return {**doc, "cached": False}

    return router
