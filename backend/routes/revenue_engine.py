"""routes.revenue_engine — ORISEI REVENUE STACK: the four automated revenue engines.

  1. Instant Quote Engine   — AI email-to-quote parsing + deterministic market
                              pricing (lane imbalance + seasonality + FSC) +
                              branded quote PDFs + send/queue via Resend.
  2. Shipper Acquisition    — prospect pipeline (manual/CSV/AI-researched) with
                              AI-written 3-touch personalized outreach sequences.
  3. Book-It-Now Marketplace— carriers self-book posted loads at a fixed price;
                              auto rate-con PDF; mirrors REAL bookings.
  4. QuickPay Spread        — same-day carrier pay at a fee; pure margin on flow.

Authed:  /api/revenue/*        Public: /api/public/revenue/*
"""

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from routes.sim_week import (
    CITIES, REGION_OF, REGION_MARKET, FSC_PER_MILE, DOE_DIESEL_AVG,
    _haversine_mi, _seasonal_multiplier,
)

logger = logging.getLogger("orisei.revenue_engine")

QUOTE_RPM = {"Van": 2.25, "Reefer": 2.70, "Flatbed": 2.58}   # midpoint market RPM
QUICKPAY_TIERS = {"same_day": 0.035, "two_day": 0.025, "five_day": 0.015}
QUOTE_VALID_HOURS = 72

STATE_REGION: Dict[str, str] = {
    "CA": "west", "NV": "west",
    "OR": "pnw", "WA": "pnw", "ID": "pnw",
    "CO": "mountain", "UT": "mountain", "NM": "mountain", "WY": "mountain", "MT": "mountain",
    "AZ": "southwest",
    "TX": "south_central", "OK": "south_central", "AR": "south_central", "LA": "south_central",
    "IL": "midwest", "WI": "midwest", "IN": "midwest", "OH": "midwest", "MI": "midwest",
    "MO": "midwest", "KY": "midwest",
    "MN": "plains", "ND": "plains", "SD": "plains", "IA": "plains", "NE": "plains", "KS": "plains",
    "GA": "southeast", "NC": "southeast", "SC": "southeast", "TN": "southeast",
    "AL": "southeast", "MS": "southeast", "VA": "southeast", "WV": "southeast",
    "FL": "florida",
    "NJ": "northeast", "PA": "northeast", "MA": "northeast", "NY": "northeast",
    "CT": "northeast", "RI": "northeast", "NH": "northeast", "VT": "northeast",
    "ME": "northeast", "MD": "northeast", "DE": "northeast",
}
STATE_CENTROID: Dict[str, tuple] = {
    "AL": (32.8, -86.8), "AR": (34.9, -92.4), "AZ": (34.3, -111.7), "CA": (36.5, -119.7),
    "CO": (39.0, -105.5), "CT": (41.6, -72.7), "DE": (39.0, -75.5), "FL": (28.6, -81.7),
    "GA": (32.6, -83.4), "IA": (42.0, -93.5), "ID": (44.4, -114.6), "IL": (40.0, -89.2),
    "IN": (39.9, -86.3), "KS": (38.5, -98.4), "KY": (37.5, -85.3), "LA": (31.1, -92.0),
    "MA": (42.3, -71.8), "MD": (39.0, -76.8), "ME": (45.4, -69.2), "MI": (44.3, -85.4),
    "MN": (46.3, -94.3), "MO": (38.4, -92.5), "MS": (32.7, -89.7), "MT": (47.0, -109.6),
    "NC": (35.5, -79.4), "ND": (47.4, -100.5), "NE": (41.5, -99.8), "NH": (43.7, -71.6),
    "NJ": (40.2, -74.7), "NM": (34.4, -106.1), "NV": (39.3, -116.6), "NY": (42.9, -75.5),
    "OH": (40.3, -82.8), "OK": (35.6, -97.5), "OR": (43.9, -120.6), "PA": (40.9, -77.8),
    "RI": (41.7, -71.6), "SC": (33.9, -80.9), "SD": (44.4, -100.2), "TN": (35.8, -86.3),
    "TX": (31.5, -99.3), "UT": (39.3, -111.7), "VA": (37.5, -78.9), "VT": (44.1, -72.7),
    "WA": (47.4, -120.4), "WI": (44.6, -89.7), "WV": (38.6, -80.6), "WY": (43.0, -107.6),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _resolve_place(text: str) -> Optional[Dict[str, Any]]:
    """Resolve 'City, ST' to coords + market region. Known metro > state centroid."""
    t = (text or "").strip()
    if not t:
        return None
    for name, (lat, lng) in CITIES.items():
        if name.lower() == t.lower() or name.split(",")[0].lower() == t.split(",")[0].lower():
            m = re.search(r",\s*([A-Za-z]{2})\s*$", t)
            if m and m.group(1).upper() != name.split(",")[1].strip():
                continue
            return {"name": name, "lat": lat, "lng": lng,
                    "region": REGION_OF[name], "precision": "metro"}
    m = re.search(r",\s*([A-Za-z]{2})\s*$", t)
    if m:
        st = m.group(1).upper()
        if st in STATE_CENTROID:
            lat, lng = STATE_CENTROID[st]
            return {"name": t.title() if t.islower() else t, "lat": lat, "lng": lng,
                    "region": STATE_REGION.get(st, "midwest"), "precision": "state"}
    return None


def _lane_mult_regions(o_region: str, d_region: str) -> float:
    o = REGION_MARKET[o_region]
    d = REGION_MARKET[d_region]
    return round(max(0.72, min(1.38, o["out"] * d["in"])), 3)


def price_lane(origin: str, destination: str, equipment: str = "Van",
               when: Optional[datetime] = None, margin_target: float = 0.15) -> Dict[str, Any]:
    """Deterministic market price for any US lane. Raises HTTP 422 on bad input."""
    o = _resolve_place(origin)
    d = _resolve_place(destination)
    if not o or not d:
        raise HTTPException(422, f"Could not resolve {'origin' if not o else 'destination'} — use 'City, ST' format")
    eq = equipment if equipment in QUOTE_RPM else "Van"
    when = when or _now()
    miles = max(120, round(_haversine_mi((o["lat"], o["lng"]), (d["lat"], d["lng"])) * 1.18))
    lane_mult = _lane_mult_regions(o["region"], d["region"])
    seas_mult = _seasonal_multiplier(when.month, eq, o["region"])
    rpm = round(QUOTE_RPM[eq] * lane_mult * seas_mult, 3)
    linehaul = round(rpm * miles, 2)
    fsc = round(FSC_PER_MILE * miles, 2)
    buy = round(linehaul + fsc, 2)
    headhaul = "headhaul" if lane_mult >= 1.08 else "backhaul" if lane_mult <= 0.92 else "balanced"
    margin = {"headhaul": max(0.10, margin_target - 0.03),
              "backhaul": margin_target + 0.05, "balanced": margin_target}[headhaul]
    sell = round(buy / (1 - margin), 2)
    return {
        "origin": o["name"], "destination": d["name"], "equipment": eq, "miles": miles,
        "linehaul_usd": linehaul, "fsc_usd": fsc, "fsc_per_mile": FSC_PER_MILE,
        "doe_diesel": DOE_DIESEL_AVG, "buy_usd": buy, "sell_usd": sell,
        "margin_usd": round(sell - buy, 2), "margin_pct": round(margin * 100, 1),
        "rpm_all_in": round(sell / miles, 2), "lane_mult": lane_mult,
        "seasonal_mult": seas_mult, "headhaul": headhaul,
        "o_region": o["region"], "d_region": d["region"],
        "confidence": "high" if o["precision"] == "metro" and d["precision"] == "metro" else "medium",
    }


async def _llm(session_id: str, system: str, prompt: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"), session_id=session_id,
                   system_message=system).with_model("anthropic", "claude-sonnet-4-5-20250929")
    return await chat.send_message(UserMessage(text=prompt))


def _json_from_llm(text: str) -> Any:
    t = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = t.find("[") if t.find("[") >= 0 and (t.find("{") < 0 or t.find("[") < t.find("{")) else t.find("{")
    end = max(t.rfind("]"), t.rfind("}"))
    return json.loads(t[start:end + 1])


async def _brand(db) -> Dict[str, Any]:
    return await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}


def _quote_markdown(q: Dict[str, Any], brand: Dict[str, Any]) -> str:
    p = q["pricing"]
    lane = q["lane"]
    company = brand.get("company_name", "Orisei Freight Solutions")
    return f"""## Spot Rate Quote · {q['quote_id']}

- **Shipper**: {q['shipper'].get('company') or '—'}
- **Contact**: {q['shipper'].get('contact') or '—'}
- **Origin**: {p['origin']}
- **Destination**: {p['destination']}
- **Equipment**: {p['equipment']} · 53'
- **Commodity**: {lane.get('commodity') or 'FAK — general freight'}
- **Weight**: {f"{lane['weight_lbs']:,} lbs" if lane.get('weight_lbs') else 'Up to 45,000 lbs'}
- **Pickup**: {lane.get('pickup_date') or 'Per shipper schedule'}
- **Practical Miles**: {p['miles']:,}

## Rate Breakdown

- **Linehaul**: ${p['sell_usd'] - p['fsc_usd']:,.2f}
- **Fuel Surcharge**: ${p['fsc_usd']:,.2f} ({p['miles']:,} mi @ ${p['fsc_per_mile']}/mi · DOE ${p['doe_diesel']}/gal)

## Total All-In Rate: ${p['sell_usd']:,.2f}

- **Rate Per Mile**: ${p['rpm_all_in']}/mi all-in
- **Quote Valid Until**: {q['valid_until'][:16].replace('T', ' ')} UTC
- **Terms**: Rate includes full truckload, standard tarps/straps where applicable. Detention $65/hr after 2-hr grace. Subject to equipment availability at time of tender.

{company} moves your freight with vetted, insured carriers, live GPS tracking, and automated PODs. Reply to this quote or call to tender — we can have a truck assigned within the hour.
"""


def _ratecon_markdown(mb: Dict[str, Any], load: Dict[str, Any], brand: Dict[str, Any]) -> str:
    c = mb["carrier"]
    return f"""## Rate Confirmation · {mb['mb_id']}

- **Carrier**: {c.get('company')}
- **MC Number**: MC-{c.get('mc_number')}
- **Dispatcher**: {c.get('contact')} · {c.get('phone') or '—'} · {c.get('email')}
- **Load ID**: {load['mkt_id']}
- **Origin**: {load['origin']}
- **Destination**: {load['destination']}
- **Equipment**: {load['equipment']} · 53'
- **Commodity**: {load.get('commodity') or 'FAK'}
- **Weight**: {f"{load['weight_lbs']:,} lbs" if load.get('weight_lbs') else '—'}
- **Pickup**: {load.get('pickup_date') or 'TBD'}
- **Miles**: {load['miles']:,}

## Total Carrier Pay: ${load['book_now_usd']:,.2f}

- **Payment Terms**: Net 30 on clean POD · QuickPay available (same-day 3.5% / 48-hr 2.5% / 5-day 1.5%)
- **Booking Confirmation Code**: {mb['confirm_code']}
- **Requirements**: $1M auto liability + $100K cargo, active authority, Macropoint/GPS tracking accepted, POD within 24 hrs of delivery.

Booked electronically via the {brand.get('company_name', 'Orisei Freight Solutions')} Book-It-Now carrier marketplace on {mb['booked_at'][:16].replace('T', ' ')} UTC. This rate confirmation is binding upon carrier acceptance of load tender.
"""


# ============================================================ router builder
def build_revenue_router(*, api_router: APIRouter, db,
                         get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/revenue", tags=["revenue-engine"])
    pub = APIRouter(prefix="/public/revenue", tags=["revenue-public"])

    async def _settings() -> Dict[str, Any]:
        return await db.revenue_settings.find_one({"_id": "settings"}) or {"margin_target": 0.15}

    async def _resend_send(*, to: str, subject: str, html: str,
                           pdf_bytes: Optional[bytes] = None, pdf_name: Optional[str] = None,
                           kind: str = "quote", ref: str = "") -> Dict[str, Any]:
        """Send now if Resend key exists, else queue for the moment it arrives."""
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        if creds and creds.get("api_key"):
            res = await _send_via_resend(creds, to=to, subject=subject, html=html,
                                         pdf_bytes=pdf_bytes, pdf_filename=pdf_name)
            status = "sent" if res.get("sent") else "failed"
        else:
            res, status = {"sent": False, "error": "no_resend_creds"}, "queued_awaiting_key"
        qid = f"OQ-{uuid.uuid4().hex[:8].upper()}"
        await db.outreach_queue.insert_one({
            "queue_id": qid, "type": kind, "ref": ref, "to_email": to, "subject": subject,
            "html": html, "has_pdf": bool(pdf_bytes), "pdf_name": pdf_name,
            "status": status, "error": res.get("error"), "created_at": _iso(_now()),
            "sent_at": _iso(_now()) if status == "sent" else None,
        })
        return {"status": status, "queue_id": qid}

    # ------------------------------------------------------------- dashboard
    @router.get("/dashboard")
    async def dashboard(_=Depends(get_current_user)) -> Dict[str, Any]:
        quotes = await db.revenue_quotes.find({}, {"_id": 0, "status": 1, "pricing": 1, "source": 1}).to_list(3000)
        won = [q for q in quotes if q["status"] == "won"]
        sent = [q for q in quotes if q["status"] in ("sent", "won", "lost")]
        prospects = await db.revenue_prospects.find({}, {"_id": 0, "stage": 1, "est_loads_week": 1}).to_list(3000)
        mkt_open = await db.marketplace_loads.count_documents({"status": "open"})
        mkt_booked = await db.marketplace_loads.count_documents({"status": "booked"})
        qps = await db.quickpay_requests.find({}, {"_id": 0, "fee_usd": 1, "status": 1}).to_list(2000)
        queue_waiting = await db.outreach_queue.count_documents({"status": "queued_awaiting_key"})
        avg_rev = 2400.0
        pipeline_value = sum((p.get("est_loads_week") or 2) * avg_rev * 4.33
                             for p in prospects if p["stage"] not in ("won", "lost"))
        return {
            "quotes": {"total": len(quotes), "sent": len(sent), "won": len(won),
                       "win_rate": round(len(won) / len(sent) * 100, 1) if sent else 0,
                       "won_revenue": round(sum(q["pricing"]["sell_usd"] for q in won), 2),
                       "won_margin": round(sum(q["pricing"]["margin_usd"] for q in won), 2)},
            "prospects": {"total": len(prospects),
                          "by_stage": {s: sum(1 for p in prospects if p["stage"] == s)
                                       for s in ["new", "sequenced", "replied", "discovery", "won", "lost"]},
                          "monthly_pipeline_usd": round(pipeline_value, 0)},
            "marketplace": {"open": mkt_open, "booked": mkt_booked},
            "quickpay": {"requests": len(qps),
                         "spread_earned": round(sum(q["fee_usd"] for q in qps), 2)},
            "outreach_queued_awaiting_key": queue_waiting,
            "resend_connected": bool(await _has_resend()),
        }

    async def _has_resend() -> bool:
        from routes.orisei_auto_digest import _resend_creds
        creds = await _resend_creds(db)
        return bool(creds and creds.get("api_key"))

    # ------------------------------------------------- 1) INSTANT QUOTE ENGINE
    class QuoteIn(BaseModel):
        origin: str
        destination: str
        equipment: str = "Van"
        company: str = ""
        contact: str = ""
        email: str = ""
        phone: str = ""
        commodity: str = ""
        weight_lbs: Optional[int] = None
        pickup_date: str = ""
        source: str = "manual"

    async def _create_quote(payload: QuoteIn, user_id: str) -> Dict[str, Any]:
        s = await _settings()
        pricing = price_lane(payload.origin, payload.destination, payload.equipment,
                             margin_target=float(s.get("margin_target", 0.15)))
        q = {
            "quote_id": f"Q-{uuid.uuid4().hex[:6].upper()}",
            "source": payload.source, "status": "draft",
            "shipper": {"company": payload.company, "contact": payload.contact,
                        "email": payload.email, "phone": payload.phone},
            "lane": {"origin": pricing["origin"], "destination": pricing["destination"],
                     "equipment": pricing["equipment"], "commodity": payload.commodity,
                     "weight_lbs": payload.weight_lbs, "pickup_date": payload.pickup_date},
            "pricing": pricing,
            "created_at": _iso(_now()), "created_by": user_id,
            "valid_until": _iso(_now() + timedelta(hours=QUOTE_VALID_HOURS)),
        }
        await db.revenue_quotes.insert_one(dict(q))
        return q

    @router.post("/quotes")
    async def create_quote(payload: QuoteIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        return await _create_quote(payload, getattr(user, "user_id", None))

    @router.post("/quotes/parse")
    async def parse_email(payload: Dict[str, Any], user=Depends(get_current_user)) -> Dict[str, Any]:
        """AI email-to-quote: paste any shipper email → structured, priced quote."""
        text = (payload.get("email_text") or "").strip()
        if len(text) < 15:
            raise HTTPException(400, "email_text required (paste the shipper's email)")
        try:
            raw = await _llm(
                f"quote-parse-{uuid.uuid4().hex[:8]}",
                "You extract freight quote requests from shipper emails. Return STRICT JSON only, "
                'no prose: {"company": str, "contact": str, "email": str, "phone": str, '
                '"origin": "City, ST", "destination": "City, ST", "equipment": "Van"|"Reefer"|"Flatbed", '
                '"commodity": str, "weight_lbs": int|null, "pickup_date": str, "notes": str}. '
                "Infer equipment from commodity (frozen/produce→Reefer, steel/lumber/machinery→Flatbed, "
                "else Van). Use empty string for unknown fields, null for unknown weight.",
                text)
            parsed = _json_from_llm(raw)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"AI parse failed: {e}")
        q = await _create_quote(QuoteIn(
            origin=parsed.get("origin") or "", destination=parsed.get("destination") or "",
            equipment=parsed.get("equipment") or "Van", company=parsed.get("company") or "",
            contact=parsed.get("contact") or "", email=parsed.get("email") or "",
            phone=parsed.get("phone") or "", commodity=parsed.get("commodity") or "",
            weight_lbs=parsed.get("weight_lbs"), pickup_date=parsed.get("pickup_date") or "",
            source="email"), getattr(user, "user_id", None))
        return {"parsed": parsed, "quote": q}

    @router.get("/quotes")
    async def list_quotes(status: Optional[str] = Query(None),
                          _=Depends(get_current_user)) -> Dict[str, Any]:
        f = {"status": status} if status else {}
        items = await db.revenue_quotes.find(f, {"_id": 0}).sort("created_at", -1).to_list(300)
        return {"items": items, "count": len(items)}

    @router.get("/quotes/{quote_id}/pdf")
    async def quote_pdf(quote_id: str, _=Depends(get_current_user)):
        q = await db.revenue_quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not q:
            raise HTTPException(404, "Quote not found")
        from routes.orisei_docs import build_branded_markdown_pdf
        brand = await _brand(db)
        pdf = build_branded_markdown_pdf(_quote_markdown(q, brand), title="Spot Rate Quote",
                                         subtitle=f"{q['pricing']['origin']} → {q['pricing']['destination']}",
                                         doc_id=quote_id, brand=brand)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{quote_id}.pdf"'})

    @router.post("/quotes/{quote_id}/send")
    async def send_quote(quote_id: str, payload: Dict[str, Any] = None,
                         user=Depends(get_current_user)) -> Dict[str, Any]:
        q = await db.revenue_quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not q:
            raise HTTPException(404, "Quote not found")
        to = (payload or {}).get("to_email") or q["shipper"].get("email")
        if not to:
            raise HTTPException(400, "No recipient email — provide to_email")
        brand = await _brand(db)
        p = q["pricing"]
        try:
            body = await _llm(
                f"quote-email-{quote_id}",
                f"You write short, confident freight-broker quote emails for "
                f"{brand.get('company_name', 'Orisei Freight Solutions')}. 90-130 words, no subject line, "
                "professional but human, end with a clear call to action to tender the load. Plain text.",
                f"Quote {quote_id}: {p['origin']} → {p['destination']}, {p['equipment']}, "
                f"{p['miles']} mi, all-in ${p['sell_usd']:,.2f} (${p['rpm_all_in']}/mi incl. FSC), "
                f"valid until {q['valid_until'][:10]}. Contact name: {q['shipper'].get('contact') or 'there'}.")
        except Exception:
            body = (f"Hi {q['shipper'].get('contact') or 'there'},\n\nHere is your all-in spot rate for "
                    f"{p['origin']} → {p['destination']} ({p['equipment']}, {p['miles']:,} practical miles): "
                    f"${p['sell_usd']:,.2f} — ${p['rpm_all_in']}/mi including fuel. Rate is valid until "
                    f"{q['valid_until'][:10]}. Vetted carrier, live GPS tracking, POD automation included.\n\n"
                    f"Reply to tender and we'll have a truck assigned within the hour.")
        html = "<div style='font-family:Arial,sans-serif;font-size:14px;line-height:1.6'>" + \
            body.replace("\n", "<br/>") + "</div>"
        from routes.orisei_docs import build_branded_markdown_pdf
        pdf = build_branded_markdown_pdf(_quote_markdown(q, brand), title="Spot Rate Quote",
                                         subtitle=f"{p['origin']} → {p['destination']}",
                                         doc_id=quote_id, brand=brand)
        res = await _resend_send(to=to, subject=f"Rate Quote {quote_id} · {p['origin']} → {p['destination']} · ${p['sell_usd']:,.0f} all-in",
                                 html=html, pdf_bytes=pdf, pdf_name=f"{quote_id}.pdf",
                                 kind="quote", ref=quote_id)
        await db.revenue_quotes.update_one({"quote_id": quote_id},
                                           {"$set": {"status": "sent", "sent_at": _iso(_now()),
                                                     "sent_to": to, "email_status": res["status"],
                                                     "email_body": body}})
        return {"ok": True, **res, "email_body": body}

    @router.post("/quotes/{quote_id}/status")
    async def set_quote_status(quote_id: str, payload: Dict[str, Any],
                               user=Depends(get_current_user)) -> Dict[str, Any]:
        status = payload.get("status")
        if status not in ("won", "lost", "sent", "draft", "expired"):
            raise HTTPException(400, "status must be won|lost|sent|draft|expired")
        q = await db.revenue_quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not q:
            raise HTTPException(404, "Quote not found")
        await db.revenue_quotes.update_one({"quote_id": quote_id},
                                           {"$set": {"status": status, f"{status}_at": _iso(_now())}})
        mkt = None
        if status == "won" and payload.get("post_to_marketplace", True):
            p, lane = q["pricing"], q["lane"]
            mkt = {
                "mkt_id": f"ML-{uuid.uuid4().hex[:6].upper()}",
                "origin": p["origin"], "destination": p["destination"],
                "equipment": p["equipment"], "miles": p["miles"],
                "commodity": lane.get("commodity") or "FAK", "weight_lbs": lane.get("weight_lbs"),
                "pickup_date": lane.get("pickup_date") or "",
                "book_now_usd": p["buy_usd"], "sell_usd": p["sell_usd"],
                "margin_usd": p["margin_usd"], "shipper": q["shipper"].get("company"),
                "quote_id": quote_id, "status": "open", "posted_at": _iso(_now()),
            }
            await db.marketplace_loads.insert_one(dict(mkt))
        return {"ok": True, "status": status,
                "marketplace_load": {k: v for k, v in (mkt or {}).items() if k != "sell_usd"} or None}

    @router.get("/settings")
    async def get_settings(_=Depends(get_current_user)) -> Dict[str, Any]:
        s = await _settings()
        s.pop("_id", None)
        return s

    @router.post("/settings")
    async def set_settings(payload: Dict[str, Any], _=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        mt = float(payload.get("margin_target", 0.15))
        if not 0.05 <= mt <= 0.40:
            raise HTTPException(400, "margin_target must be 0.05–0.40")
        await db.revenue_settings.update_one({"_id": "settings"},
                                             {"$set": {"margin_target": mt}}, upsert=True)
        return {"ok": True, "margin_target": mt}

    # ---------------------------------------------- 2) SHIPPER ACQUISITION
    class ProspectIn(BaseModel):
        company: str
        contact_name: str = ""
        email: str = ""
        phone: str = ""
        city_state: str = ""
        industry: str = ""
        est_loads_week: int = 2
        lanes: str = ""
        source: str = "manual"

    @router.post("/prospects")
    async def add_prospect(payload: ProspectIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        p = {"prospect_id": f"P-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
             "stage": "new", "score": min(100, 40 + payload.est_loads_week * 8),
             "created_at": _iso(_now()), "sequence": []}
        await db.revenue_prospects.insert_one(dict(p))
        return p

    @router.post("/prospects/import")
    async def import_prospects(payload: Dict[str, Any], user=Depends(get_current_user)) -> Dict[str, Any]:
        """CSV columns: company,contact_name,email,phone,city_state,industry,est_loads_week,lanes"""
        text = (payload.get("csv_text") or "").strip()
        if not text:
            raise HTTPException(400, "csv_text required")
        rows = list(csv.DictReader(io.StringIO(text)))
        created = []
        for r in rows[:500]:
            if not (r.get("company") or "").strip():
                continue
            try:
                est = int(r.get("est_loads_week") or 2)
            except ValueError:
                est = 2
            p = {"prospect_id": f"P-{uuid.uuid4().hex[:6].upper()}",
                 "company": r["company"].strip(), "contact_name": (r.get("contact_name") or "").strip(),
                 "email": (r.get("email") or "").strip(), "phone": (r.get("phone") or "").strip(),
                 "city_state": (r.get("city_state") or "").strip(),
                 "industry": (r.get("industry") or "").strip(), "est_loads_week": est,
                 "lanes": (r.get("lanes") or "").strip(), "source": "csv", "stage": "new",
                 "score": min(100, 40 + est * 8), "created_at": _iso(_now()), "sequence": []}
            await db.revenue_prospects.insert_one(dict(p))
            created.append(p["prospect_id"])
        return {"ok": True, "imported": len(created)}

    @router.post("/prospects/generate")
    async def generate_prospects(payload: Dict[str, Any], user=Depends(get_current_user)) -> Dict[str, Any]:
        """AI-researched target list. Marked source=ai_research — verify before outreach."""
        region = payload.get("region") or "Midwest"
        industry = payload.get("industry") or "food & beverage manufacturing"
        count = min(int(payload.get("count") or 8), 15)
        try:
            raw = await _llm(
                f"prospect-gen-{uuid.uuid4().hex[:8]}",
                "You are a freight brokerage sales researcher. Return STRICT JSON array only: "
                '[{"company": str, "city_state": "City, ST", "industry": str, '
                '"est_loads_week": int, "lanes": str, "why_target": str}]. '
                "List REAL, well-known shippers/manufacturers/distributors that actually ship "
                "truckload freight. lanes = their likely major outbound lanes.",
                f"List {count} truckload shipper targets in the {region} region, industry: {industry}. "
                "Prioritize companies with distribution centers that regularly buy spot/contract TL capacity.")
            targets = _json_from_llm(raw)
        except Exception as e:
            raise HTTPException(502, f"AI research failed: {e}")
        created = []
        for t in targets[:count]:
            est = int(t.get("est_loads_week") or 3)
            p = {"prospect_id": f"P-{uuid.uuid4().hex[:6].upper()}",
                 "company": t.get("company"), "contact_name": "", "email": "", "phone": "",
                 "city_state": t.get("city_state") or "", "industry": t.get("industry") or industry,
                 "est_loads_week": est, "lanes": t.get("lanes") or "",
                 "why_target": t.get("why_target") or "", "source": "ai_research",
                 "stage": "new", "score": min(100, 40 + est * 8),
                 "created_at": _iso(_now()), "sequence": []}
            await db.revenue_prospects.insert_one(dict(p))
            created.append({k: v for k, v in p.items()})
        return {"ok": True, "created": created,
                "note": "AI-researched targets — verify contact emails before sequencing."}

    @router.get("/prospects")
    async def list_prospects(_=Depends(get_current_user)) -> Dict[str, Any]:
        items = await db.revenue_prospects.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"items": items, "count": len(items)}

    @router.post("/prospects/{prospect_id}/sequence")
    async def build_sequence(prospect_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        p = await db.revenue_prospects.find_one({"prospect_id": prospect_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        brand = await _brand(db)
        company = brand.get("company_name", "Orisei Freight Solutions")
        try:
            raw = await _llm(
                f"sequence-{prospect_id}",
                f"You write cold outreach for {company}, a tech-forward freight brokerage with live GPS "
                "tracking, instant quoting, automated PODs/invoicing, and vetted carriers. Return STRICT "
                'JSON array of exactly 3 touches: [{"day": 0|3|7, "subject": str, "body": str}]. '
                "Touch 1: personalized opener referencing their industry/lanes, one clear value prop, "
                "soft CTA. Touch 2 (day 3): short bump with a specific capability (instant quote portal). "
                "Touch 3 (day 7): breakup email with a rate-check offer. 60-110 words each, plain text, "
                "no placeholders like [Name] — use the actual data given.",
                f"Prospect: {p['company']} · industry {p.get('industry') or 'general freight'} · "
                f"located {p.get('city_state') or 'US'} · likely lanes {p.get('lanes') or 'regional TL'} · "
                f"contact {p.get('contact_name') or 'Shipping Manager'}.")
            touches = _json_from_llm(raw)
        except Exception as e:
            raise HTTPException(502, f"AI sequence failed: {e}")
        now = _now()
        seq = []
        first_result = None
        for t in touches[:3]:
            day = int(t.get("day") or 0)
            item = {"day": day, "subject": t.get("subject"), "body": t.get("body"),
                    "scheduled_at": _iso(now + timedelta(days=day)), "status": "pending"}
            if p.get("email"):
                if day == 0:
                    html = "<div style='font-family:Arial,sans-serif;font-size:14px;line-height:1.6'>" + \
                        (t.get("body") or "").replace("\n", "<br/>") + "</div>"
                    res = await _resend_send(to=p["email"], subject=t.get("subject") or f"{company} — capacity",
                                             html=html, kind="prospect_touch", ref=prospect_id)
                    item["status"] = res["status"]
                    first_result = res
                else:
                    item["status"] = "scheduled"
            else:
                item["status"] = "needs_email"
            seq.append(item)
        await db.revenue_prospects.update_one(
            {"prospect_id": prospect_id},
            {"$set": {"sequence": seq, "stage": "sequenced", "sequenced_at": _iso(now)}})
        return {"ok": True, "sequence": seq, "first_touch": first_result,
                "note": None if p.get("email") else "Prospect has no email — sequence drafted, add an email to send."}

    @router.post("/prospects/{prospect_id}/stage")
    async def set_stage(prospect_id: str, payload: Dict[str, Any], _=Depends(get_current_user)) -> Dict[str, Any]:
        stage = payload.get("stage")
        if stage not in ("new", "sequenced", "replied", "discovery", "won", "lost"):
            raise HTTPException(400, "invalid stage")
        r = await db.revenue_prospects.update_one({"prospect_id": prospect_id},
                                                  {"$set": {"stage": stage}})
        if not r.matched_count:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True, "stage": stage}

    @router.get("/outreach/queue")
    async def outreach_queue(_=Depends(get_current_user)) -> Dict[str, Any]:
        items = await db.outreach_queue.find({}, {"_id": 0, "html": 0}).sort("created_at", -1).to_list(200)
        return {"items": items, "awaiting_key": sum(1 for i in items if i["status"] == "queued_awaiting_key"),
                "resend_connected": await _has_resend()}

    @router.post("/outreach/dispatch")
    async def dispatch_queue(_=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        """Flush queued emails once the Resend key is connected."""
        if not await _has_resend():
            raise HTTPException(409, "Resend key not connected — add it in Connections first")
        from routes.orisei_auto_digest import _resend_creds, _send_via_resend
        creds = await _resend_creds(db)
        pending = await db.outreach_queue.find({"status": "queued_awaiting_key"}).to_list(100)
        sent = failed = 0
        for item in pending:
            res = await _send_via_resend(creds, to=item["to_email"], subject=item["subject"],
                                         html=item["html"])
            new_status = "sent" if res.get("sent") else "failed"
            sent += res.get("sent", False)
            failed += not res.get("sent", False)
            await db.outreach_queue.update_one({"queue_id": item["queue_id"]},
                                               {"$set": {"status": new_status, "error": res.get("error"),
                                                         "sent_at": _iso(_now()) if res.get("sent") else None}})
        return {"ok": True, "sent": sent, "failed": failed}

    # ---------------------------------------------- 3) BOOK-IT-NOW MARKETPLACE
    class MktLoadIn(BaseModel):
        origin: str
        destination: str
        equipment: str = "Van"
        commodity: str = "FAK"
        weight_lbs: Optional[int] = None
        pickup_date: str = ""
        book_now_usd: Optional[float] = None
        margin_target: Optional[float] = None

    @router.post("/marketplace/loads")
    async def post_mkt_load(payload: MktLoadIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        s = await _settings()
        pricing = price_lane(payload.origin, payload.destination, payload.equipment,
                             margin_target=float(payload.margin_target or s.get("margin_target", 0.15)))
        book_now = round(float(payload.book_now_usd), 2) if payload.book_now_usd else pricing["buy_usd"]
        mkt = {"mkt_id": f"ML-{uuid.uuid4().hex[:6].upper()}",
               "origin": pricing["origin"], "destination": pricing["destination"],
               "equipment": pricing["equipment"], "miles": pricing["miles"],
               "commodity": payload.commodity, "weight_lbs": payload.weight_lbs,
               "pickup_date": payload.pickup_date, "book_now_usd": book_now,
               "sell_usd": pricing["sell_usd"], "margin_usd": round(pricing["sell_usd"] - book_now, 2),
               "status": "open", "posted_at": _iso(_now()),
               "posted_by": getattr(user, "user_id", None)}
        await db.marketplace_loads.insert_one(dict(mkt))
        return mkt

    @router.get("/marketplace/loads")
    async def list_mkt_loads(_=Depends(get_current_user)) -> Dict[str, Any]:
        items = await db.marketplace_loads.find({}, {"_id": 0}).sort("posted_at", -1).to_list(300)
        return {"items": items, "count": len(items)}

    @router.post("/marketplace/loads/{mkt_id}/close")
    async def close_mkt_load(mkt_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.marketplace_loads.update_one({"mkt_id": mkt_id, "status": "open"},
                                                  {"$set": {"status": "closed"}})
        if not r.matched_count:
            raise HTTPException(404, "Open load not found")
        return {"ok": True}

    # public carrier loadboard
    @pub.get("/loadboard")
    async def public_loadboard() -> Dict[str, Any]:
        items = await db.marketplace_loads.find(
            {"status": "open"},
            {"_id": 0, "sell_usd": 0, "margin_usd": 0, "posted_by": 0}).sort("posted_at", -1).to_list(100)
        for i in items:
            i["rpm"] = round(i["book_now_usd"] / max(i["miles"], 1), 2)
        return {"items": items, "count": len(items)}

    class BookIn(BaseModel):
        mc_number: str
        company: str
        contact: str
        email: str
        phone: str = ""

    @pub.post("/loadboard/{mkt_id}/book")
    async def public_book(mkt_id: str, payload: BookIn) -> Dict[str, Any]:
        if not re.fullmatch(r"\d{5,8}", payload.mc_number.strip().upper().replace("MC-", "").replace("MC", "")):
            raise HTTPException(422, "MC number must be 5-8 digits")
        mc = payload.mc_number.strip().upper().replace("MC-", "").replace("MC", "")
        load = await db.marketplace_loads.find_one({"mkt_id": mkt_id, "status": "open"}, {"_id": 0})
        if not load:
            raise HTTPException(409, "Load no longer available")
        mb = {"mb_id": f"MB-{uuid.uuid4().hex[:6].upper()}", "mkt_id": mkt_id,
              "carrier": {"company": payload.company.strip(), "mc_number": mc,
                          "contact": payload.contact.strip(), "email": payload.email.strip(),
                          "phone": payload.phone.strip()},
              "confirm_code": uuid.uuid4().hex[:8].upper(),
              "vetting": "pending_fmcsa_key",
              "booked_at": _iso(_now()), "status": "booked"}
        await db.marketplace_bookings.insert_one(dict(mb))
        await db.marketplace_loads.update_one({"mkt_id": mkt_id},
                                              {"$set": {"status": "booked", "booking": mb["mb_id"]}})
        booked_id = f"BK-MKT{uuid.uuid4().hex[:5].upper()}"
        await db.brokerage_bookings.insert_one({
            "booked_id": booked_id, "load_id": mkt_id, "board_id": "marketplace",
            "carrier_name": payload.company.strip(), "carrier_mc": mc,
            "customer_name": load.get("shipper") or "Marketplace Direct",
            "origin": load["origin"], "destination": load["destination"],
            "miles": load["miles"], "equipment": load["equipment"],
            "commodity": load.get("commodity") or "FAK", "weight_lbs": load.get("weight_lbs"),
            "customer_rate_usd": load.get("sell_usd") or load["book_now_usd"],
            "carrier_rate_usd": load["book_now_usd"],
            "pickup_date": load.get("pickup_date"), "status": "booked",
            "booked_at": _iso(_now()), "booked_by": "marketplace",
            "notes": f"Book-It-Now marketplace · {mb['mb_id']} · confirm {mb['confirm_code']} · FMCSA vetting pending key",
            "is_sample": False, "source": "marketplace",
        })
        await db.marketplace_bookings.update_one({"mb_id": mb["mb_id"]},
                                                 {"$set": {"booked_id": booked_id}})
        return {"ok": True, "mb_id": mb["mb_id"], "confirm_code": mb["confirm_code"],
                "ratecon_url": f"/api/public/revenue/bookings/{mb['mb_id']}/ratecon.pdf?code={mb['confirm_code']}",
                "message": "Load booked. Your rate confirmation is ready — dispatch will contact you within 15 minutes."}

    @pub.get("/bookings/{mb_id}/ratecon.pdf")
    async def public_ratecon(mb_id: str, code: str = Query(...)):
        mb = await db.marketplace_bookings.find_one({"mb_id": mb_id}, {"_id": 0})
        if not mb or mb.get("confirm_code") != code:
            raise HTTPException(403, "Invalid confirmation code")
        load = await db.marketplace_loads.find_one({"mkt_id": mb["mkt_id"]}, {"_id": 0})
        from routes.orisei_docs import build_branded_markdown_pdf
        brand = await _brand(db)
        pdf = build_branded_markdown_pdf(_ratecon_markdown(mb, load, brand),
                                         title="Rate Confirmation",
                                         subtitle=f"{load['origin']} → {load['destination']}",
                                         doc_id=mb_id, brand=brand)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{mb_id}-ratecon.pdf"'})

    # public shipper instant quote
    class PublicQuoteIn(BaseModel):
        company: str
        contact: str
        email: str
        phone: str = ""
        origin: str
        destination: str
        equipment: str = "Van"
        commodity: str = ""
        weight_lbs: Optional[int] = None
        pickup_date: str = ""

    @pub.post("/quote")
    async def public_quote(payload: PublicQuoteIn) -> Dict[str, Any]:
        q = await _create_quote(QuoteIn(**payload.model_dump(), source="portal"), "public-portal")
        p = q["pricing"]
        return {"ok": True, "quote_id": q["quote_id"], "valid_until": q["valid_until"],
                "origin": p["origin"], "destination": p["destination"],
                "equipment": p["equipment"], "miles": p["miles"],
                "all_in_rate_usd": p["sell_usd"], "rpm": p["rpm_all_in"],
                "fsc_included_usd": p["fsc_usd"],
                "message": "Rate locked for 72 hours. Our team will reach out within the hour — or reply to the confirmation email to tender now."}

    # ------------------------------------------------------- 4) QUICKPAY SPREAD
    @router.get("/quickpay/program")
    async def quickpay_program(_=Depends(get_current_user)) -> Dict[str, Any]:
        reqs = await db.quickpay_requests.find({}, {"_id": 0}).sort("requested_at", -1).to_list(300)
        eligible = await db.brokerage_bookings.find(
            {"status": {"$in": ["delivered", "booked", "in_transit"]}, "is_sample": {"$ne": True}},
            {"_id": 0, "booked_id": 1, "carrier_name": 1, "carrier_rate_usd": 1,
             "origin": 1, "destination": 1, "status": 1}).sort("booked_at", -1).to_list(100)
        taken = {r["booked_id"] for r in reqs}
        return {"tiers": {k: v * 100 for k, v in QUICKPAY_TIERS.items()},
                "requests": reqs,
                "spread_earned": round(sum(r["fee_usd"] for r in reqs), 2),
                "pending_payout": round(sum(r["net_pay_usd"] for r in reqs if r["status"] == "approved"), 2),
                "eligible_bookings": [b for b in eligible if b["booked_id"] not in taken]}

    @router.post("/quickpay/request")
    async def quickpay_request(payload: Dict[str, Any], user=Depends(get_current_user)) -> Dict[str, Any]:
        booked_id = payload.get("booked_id")
        tier = payload.get("tier", "two_day")
        if tier not in QUICKPAY_TIERS:
            raise HTTPException(400, f"tier must be one of {list(QUICKPAY_TIERS)}")
        b = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        if await db.quickpay_requests.find_one({"booked_id": booked_id}):
            raise HTTPException(409, "QuickPay already requested for this booking")
        pay = float(b.get("carrier_rate_usd") or 0)
        if pay <= 0:
            raise HTTPException(422, "Booking has no carrier rate")
        fee = round(pay * QUICKPAY_TIERS[tier], 2)
        qp = {"qp_id": f"QP-{uuid.uuid4().hex[:6].upper()}", "booked_id": booked_id,
              "carrier_name": b.get("carrier_name"), "carrier_pay_usd": pay,
              "tier": tier, "fee_pct": QUICKPAY_TIERS[tier] * 100, "fee_usd": fee,
              "net_pay_usd": round(pay - fee, 2), "status": "approved",
              "requested_at": _iso(_now()), "requested_by": getattr(user, "user_id", None)}
        await db.quickpay_requests.insert_one(dict(qp))
        return qp

    @router.post("/quickpay/{qp_id}/mark-paid")
    async def quickpay_paid(qp_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        r = await db.quickpay_requests.update_one(
            {"qp_id": qp_id, "status": "approved"},
            {"$set": {"status": "paid", "paid_at": _iso(_now())}})
        if not r.matched_count:
            raise HTTPException(404, "Approved request not found")
        return {"ok": True}

    api_router.include_router(router)
    api_router.include_router(pub)
    logger.info("Revenue Engine registered (/api/revenue + /api/public/revenue)")
