"""routes.truck_cleaning_fleet — carrier fleet unit registry, per-unit clean history/metrics,
AI efficiency schedule, and the AI offer engine that scrubs the client list."""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import resend
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routes.connections import get_connection_credentials
from routes.truck_cleaning import PRODUCT_IDS, UPSELL_META
from routes.truck_cleaning_field import _public_base

logger = logging.getLogger(__name__)
MODEL = ("anthropic", "claude-sonnet-4-5-20250929")
CADENCE_BY_PLAN = {"one_time": 30, "biweekly_sub": 14, "fleet_sub": 21}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - d).days)
    except ValueError:
        return None


class UnitIn(BaseModel):
    client_id: str
    unit_number: str = Field(..., min_length=1, max_length=40)
    make: str = Field("", max_length=60)
    model: str = Field("", max_length=60)
    year: str = Field("", max_length=8)
    cadence_days: int = Field(0, ge=0, le=120)  # 0 → derive from client plan
    notes: str = Field("", max_length=300)


class CleanIn(BaseModel):
    date: str = Field("", max_length=10)
    job_id: str = Field("", max_length=30)
    upsells: List[str] = Field(default_factory=list)


def _unit_metrics(u: Dict[str, Any]) -> Dict[str, Any]:
    hist = u.get("history") or []
    last = hist[-1]["date"] if hist else None
    ds = _days_since(f"{last}T00:00:00+00:00") if last else None
    cadence = u.get("cadence_days") or 21
    if ds is None:
        status, due_in = "never_cleaned", -999
    else:
        due_in = cadence - ds
        status = "overdue" if due_in < 0 else ("due_soon" if due_in <= 3 else "fresh")
    intervals = []
    for a, b in zip(hist, hist[1:]):
        try:
            intervals.append((datetime.strptime(b["date"], "%Y-%m-%d") - datetime.strptime(a["date"], "%Y-%m-%d")).days)
        except ValueError:
            pass
    return {"last_cleaned": last, "days_since": ds, "due_in_days": None if due_in == -999 else due_in,
            "status": status, "total_cleans": len(hist),
            "avg_interval_days": round(sum(intervals) / len(intervals), 1) if intervals else None,
            "cadence_days": cadence}


def build_truck_cleaning_fleet_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/truck-cleaning", tags=["truck-cleaning-fleet"])
    guard = require_role("admin", "owner", "dispatcher")

    async def _seed_units():
        if await db.tc_units.count_documents({}) > 0:
            return
        clients = await db.tc_clients.find({}, {"_id": 0}).sort("created_at", -1).to_list(10)
        if not clients:
            return
        today = datetime.now(timezone.utc).date()
        specs = [("Freightliner", "Cascadia", "2021"), ("Peterbilt", "579", "2019"), ("Kenworth", "T680", "2022"),
                 ("Volvo", "VNL 860", "2020"), ("International", "LT625", "2018"), ("Mack", "Anthem", "2023")]
        i = 0
        for c in clients[:3]:
            cadence = CADENCE_BY_PLAN.get(c.get("plan", "fleet_sub"), 21)
            for n in range(min(c.get("cabs", 1), 3)):
                mk, md, yr = specs[i % len(specs)]
                ago = 5 + (i * 9) % 40
                hist = [{"date": (today - timedelta(days=ago + cadence)).isoformat(), "job_id": "", "upsells": []},
                        {"date": (today - timedelta(days=ago)).isoformat(), "job_id": "", "upsells": ["engine_bay"] if i % 3 == 0 else []}]
                await db.tc_units.insert_one({
                    "unit_id": f"UNIT-{uuid.uuid4().hex[:6].upper()}", "client_id": c["client_id"],
                    "company": c["company"], "unit_number": f"{c['company'].split()[0][:3].upper()}-{100 + i}",
                    "make": mk, "model": md, "year": yr, "cadence_days": cadence, "notes": "",
                    "history": hist, "is_sample": True, "created_at": _now()})
                i += 1

    # ================= FLEET UNIT REGISTRY =================
    @router.get("/units")
    async def units(client_id: str = "", _=Depends(guard)) -> Dict[str, Any]:
        await _seed_units()
        q = {"client_id": client_id} if client_id else {}
        rows = await db.tc_units.find(q, {"_id": 0}).sort("company", 1).to_list(1000)
        for u in rows:
            u["metrics"] = _unit_metrics(u)
        by_client: Dict[str, Dict[str, Any]] = {}
        for u in rows:
            g = by_client.setdefault(u["client_id"], {"client_id": u["client_id"], "company": u["company"],
                                                      "units": 0, "overdue": 0, "due_soon": 0, "total_cleans": 0})
            g["units"] += 1
            g["total_cleans"] += u["metrics"]["total_cleans"]
            if u["metrics"]["status"] in ("overdue", "never_cleaned"):
                g["overdue"] += 1
            elif u["metrics"]["status"] == "due_soon":
                g["due_soon"] += 1
        return {"units": rows, "fleets": sorted(by_client.values(), key=lambda x: -x["overdue"])}

    @router.post("/units")
    async def add_unit(payload: UnitIn, _=Depends(guard)) -> Dict[str, Any]:
        client = await db.tc_clients.find_one({"client_id": payload.client_id}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        cadence = payload.cadence_days or CADENCE_BY_PLAN.get(client.get("plan", "fleet_sub"), 21)
        row = {"unit_id": f"UNIT-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
               "company": client["company"], "cadence_days": cadence, "history": [],
               "is_sample": False, "created_at": _now()}
        await db.tc_units.insert_one(dict(row))
        row["metrics"] = _unit_metrics(row)
        return {"ok": True, "unit": row}

    @router.delete("/units/{unit_id}")
    async def del_unit(unit_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_units.delete_one({"unit_id": unit_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        return {"ok": True}

    @router.post("/units/{unit_id}/clean")
    async def mark_cleaned(unit_id: str, payload: CleanIn, _=Depends(guard)) -> Dict[str, Any]:
        u = await db.tc_units.find_one({"unit_id": unit_id}, {"_id": 0})
        if not u:
            raise HTTPException(status_code=404, detail="Unit not found")
        date = payload.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        entry = {"date": date, "job_id": payload.job_id, "upsells": payload.upsells, "logged_at": _now()}
        await db.tc_units.update_one({"unit_id": unit_id}, {"$push": {"history": entry}})
        u["history"] = (u.get("history") or []) + [entry]
        return {"ok": True, "metrics": _unit_metrics(u)}

    @router.post("/units/{unit_id}/cadence")
    async def set_cadence(unit_id: str, payload: Dict[str, int], _=Depends(guard)) -> Dict[str, Any]:
        days = int(payload.get("cadence_days", 0))
        if not 3 <= days <= 120:
            raise HTTPException(status_code=400, detail="cadence_days must be 3-120")
        r = await db.tc_units.update_one({"unit_id": unit_id}, {"$set": {"cadence_days": days}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Unit not found")
        return {"ok": True}

    # ================= AI EFFICIENCY SCHEDULE =================
    @router.get("/ai-schedule")
    async def ai_schedule(days: int = 7, ai: bool = True, _=Depends(guard)) -> Dict[str, Any]:
        await _seed_units()
        days = max(3, min(days, 14))
        rows = await db.tc_units.find({}, {"_id": 0}).to_list(1000)
        techs_n = max(1, await db.tc_techs.count_documents({"active": True}))
        capacity = techs_n * 9  # ~9 cabs per tech per day at 45 min + travel
        scored = []
        for u in rows:
            m = _unit_metrics(u)
            urgency = 999 if m["status"] == "never_cleaned" else -(m["due_in_days"] or 0)
            scored.append({"unit_id": u["unit_id"], "unit_number": u["unit_number"], "client_id": u["client_id"],
                           "company": u["company"], "make": u["make"], "model": u["model"],
                           "status": m["status"], "due_in_days": m["due_in_days"], "urgency": urgency})
        due = sorted([s for s in scored if s["urgency"] >= -3], key=lambda s: -s["urgency"])
        # pack into days, keeping each client's units on the same day (one yard trip)
        today = datetime.now(timezone.utc).date()
        plan = [{"date": (today + timedelta(days=i + 1)).isoformat(), "stops": [], "cabs": 0} for i in range(days)]
        by_client: Dict[str, List[Dict]] = {}
        for s in due:
            by_client.setdefault(s["client_id"], []).append(s)
        groups = sorted(by_client.values(), key=lambda g: -max(x["urgency"] for x in g))
        for g in groups:
            day = min(plan, key=lambda d: d["cabs"])
            if day["cabs"] + len(g) > capacity and day["cabs"] > 0:
                day = min(plan, key=lambda d: d["cabs"])
            day["stops"].append({"company": g[0]["company"], "client_id": g[0]["client_id"],
                                 "units": g, "cabs": len(g)})
            day["cabs"] += len(g)
        out = {"generated_at": _now(), "capacity_per_day": capacity, "techs": techs_n,
               "units_total": len(rows), "units_due": len(due),
               "overdue": sum(1 for s in scored if s["status"] in ("overdue", "never_cleaned")),
               "plan": plan}
        if ai and due:
            out["ai_notes"] = await _ai_notes(out)
        return out

    async def _ai_notes(sched: Dict[str, Any]) -> str:
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return ""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            brief = {"units_due": sched["units_due"], "overdue": sched["overdue"],
                     "capacity_per_day": sched["capacity_per_day"], "techs": sched["techs"],
                     "days": [{"date": d["date"], "cabs": d["cabs"],
                               "stops": [{"company": s["company"], "cabs": s["cabs"]} for s in d["stops"]]}
                              for d in sched["plan"] if d["stops"]]}
            chat = LlmChat(api_key=key, session_id=f"tc-sched-{uuid.uuid4().hex[:6]}",
                           system_message=("You are the Orisei Truck Cleaning dispatch optimizer. Given a proposed "
                                           "week plan, give 3-4 short bullet insights to maximize crew efficiency and "
                                           "revenue: route grouping, upsell opportunities on overdue units, capacity "
                                           "gaps to fill with marketing, subscription conversion angles. Plain bullets, "
                                           "no preamble, dollar-math where useful ($150/cab, $46 COGS).")).with_model(*MODEL)
            return str(await chat.send_message(UserMessage(text=json.dumps(brief))))
        except Exception:  # noqa: BLE001
            logger.exception("AI schedule notes failed")
            return ""

    # ================= AI OFFER ENGINE =================
    @router.post("/offers/scrub")
    async def scrub(_=Depends(guard)) -> Dict[str, Any]:
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            raise HTTPException(status_code=503, detail="EMERGENT_LLM_KEY not configured")
        clients = await db.tc_clients.find({}, {"_id": 0}).to_list(200)
        if not clients:
            raise HTTPException(status_code=400, detail="Client registry is empty — add clients first")
        jobs = await db.tc_jobs.find({}, {"_id": 0}).to_list(2000)
        profiles = []
        for c in clients:
            cj = sorted([j for j in jobs if j["client_id"] == c["client_id"]], key=lambda j: j["date"])
            last = cj[-1]["date"] if cj else None
            profiles.append({"client_id": c["client_id"], "company": c["company"], "plan": c["plan"],
                             "cabs": c["cabs"], "rate": c["rate"], "jobs_done": len(cj),
                             "last_job_date": last,
                             "days_since_last": _days_since(f"{last}T00:00:00+00:00") if last else None,
                             "lifetime_revenue": round(sum(j["price"] for j in cj), 2),
                             "has_used_upsells": any(j.get("upsells") for j in cj)})
        prompt = (
            "Scrub this truck-cab-cleaning client registry and produce ONE targeted email offer per client. "
            "Pricing: $150 one-time, $120/cab bi-weekly sub, $125/cab fleet (10+). Upsells: engine bay $25, tires $20, cabin filter $15. "
            "Pick the highest-value angle per client: win-back if inactive 30+ days, subscription upgrade for repeat one-timers, "
            "upsell bundle if never used upsells, referral ask for loyal subs, fleet-rate pitch if cabs>=10 and not on fleet plan. "
            "Return STRICT JSON array only, no markdown fences: "
            '[{"client_id":"...","offer_type":"win_back|sub_upgrade|upsell_bundle|referral|fleet_rate",'
            '"subject":"...","body":"2-4 short friendly paragraphs, blue-collar voice, one concrete offer with dollar math, '
            'sign off as Oliver Cummins, Orisei Truck Cleaning"}]. '
            f"Registry: {json.dumps(profiles)}")
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"tc-scrub-{uuid.uuid4().hex[:6]}",
                       system_message="You are a sharp direct-response copywriter for a mobile truck cleaning company. Output strict JSON only.").with_model(*MODEL)
        raw = str(await chat.send_message(UserMessage(text=prompt))).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("["):raw.rfind("]") + 1]
        try:
            offers = json.loads(raw)
            assert isinstance(offers, list)
        except Exception:
            logger.error("Offer scrub parse failed: %s", raw[:400])
            raise HTTPException(status_code=502, detail="AI returned unparseable offers — try again")
        cmap = {c["client_id"]: c for c in clients}
        created = []
        for o in offers:
            c = cmap.get(o.get("client_id"))
            if not c or not o.get("subject") or not o.get("body"):
                continue
            row = {"offer_id": f"OFF-{uuid.uuid4().hex[:6].upper()}", "client_id": c["client_id"],
                   "company": c["company"], "email": c.get("email", ""),
                   "offer_type": o.get("offer_type", "custom"), "subject": o["subject"][:180],
                   "body": o["body"][:4000], "status": "draft", "created_at": _now(), "sent_at": None}
            await db.tc_offers.delete_many({"client_id": c["client_id"], "status": "draft"})
            await db.tc_offers.insert_one(dict(row))
            created.append(row)
        return {"ok": True, "created": len(created), "offers": created}

    @router.get("/offers")
    async def offers(_=Depends(guard)) -> Dict[str, Any]:
        rows = await db.tc_offers.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
        creds = await get_connection_credentials(db, "resend") or {}
        return {"offers": rows, "resend_configured": bool(creds.get("api_key"))}

    @router.delete("/offers/{offer_id}")
    async def del_offer(offer_id: str, _=Depends(guard)) -> Dict[str, Any]:
        r = await db.tc_offers.delete_one({"offer_id": offer_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Offer not found")
        return {"ok": True}

    async def _send_offer(offer: Dict[str, Any], api_key: str, from_addr: str) -> Dict[str, Any]:
        to = offer.get("email")
        if not to:
            await db.tc_offers.update_one({"offer_id": offer["offer_id"]},
                                          {"$set": {"status": "skipped", "note": "client has no email"}})
            return {"offer_id": offer["offer_id"], "status": "skipped"}
        paras = "".join(f"<p>{p}</p>" for p in offer["body"].split("\n") if p.strip())
        html = f"""<!doctype html><html><body style="font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;background:#F8FAFC;padding:24px;color:#0D1117;">
<div style="max-width:620px;margin:0 auto;background:#fff;border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
  <div style="background:#0D1117;color:#fff;padding:20px 26px;border-bottom:4px solid #F59E0B;">
    <div style="font-size:11px;letter-spacing:.3em;color:#F59E0B;text-transform:uppercase;font-family:Courier,monospace;">Orisei Truck Cleaning</div>
  </div>
  <div style="padding:24px 26px;font-size:14px;line-height:1.65;">{paras}
    <p style="font-size:12px;color:#64748B;margin-top:22px;">Orisei Truck Cleaning Solutions · Minneapolis–St. Paul · (612) 555-0117 · reply STOP to opt out</p>
  </div></div></body></html>"""
        try:
            resend.api_key = api_key
            resp = resend.Emails.send({"from": from_addr, "to": [to],
                                       "subject": offer["subject"], "html": html})
            await db.tc_offers.update_one({"offer_id": offer["offer_id"]},
                                          {"$set": {"status": "sent", "sent_at": _now(),
                                                    "message_id": (resp or {}).get("id") if isinstance(resp, dict) else None}})
            return {"offer_id": offer["offer_id"], "status": "sent"}
        except Exception as exc:  # noqa: BLE001
            logger.exception("offer send failed")
            await db.tc_offers.update_one({"offer_id": offer["offer_id"]},
                                          {"$set": {"status": "failed", "note": str(exc)[:200]}})
            return {"offer_id": offer["offer_id"], "status": "failed"}

    @router.post("/offers/{offer_id}/send")
    async def send_offer(offer_id: str, _=Depends(guard)) -> Dict[str, Any]:
        offer = await db.tc_offers.find_one({"offer_id": offer_id}, {"_id": 0})
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        creds = await get_connection_credentials(db, "resend") or {}
        if not creds.get("api_key"):
            raise HTTPException(status_code=400, detail="Resend is not configured — add your Resend API key in Connections · Keys.")
        from_addr = creds.get("from_email") or "Orisei Truck Cleaning <oliver@oriseifreight.com>"
        return await _send_offer(offer, creds["api_key"], from_addr)

    @router.post("/offers/send-all")
    async def send_all(_=Depends(guard)) -> Dict[str, Any]:
        creds = await get_connection_credentials(db, "resend") or {}
        if not creds.get("api_key"):
            raise HTTPException(status_code=400, detail="Resend is not configured — add your Resend API key in Connections · Keys.")
        from_addr = creds.get("from_email") or "Orisei Truck Cleaning <oliver@oriseifreight.com>"
        drafts = await db.tc_offers.find({"status": "draft"}, {"_id": 0}).to_list(300)
        results = [await _send_offer(o, creds["api_key"], from_addr) for o in drafts]
        return {"ok": True, "results": results,
                "sent": sum(1 for r in results if r["status"] == "sent")}

    # ================= BEDDING & PRODUCT INVENTORY =================
    async def _seed_inventory():
        if await db.tc_inventory.count_documents({}) > 0:
            return
        meta = {u["id"]: u for u in UPSELL_META}
        for pid in PRODUCT_IDS:
            u = meta[pid]
            await db.tc_inventory.insert_one({"item_id": pid, "label": u["label"], "category": u["category"],
                                              "unit_price": u["price"], "stock": 10, "low_threshold": 4,
                                              "is_sample": True, "created_at": _now()})

    @router.get("/inventory")
    async def inventory(_=Depends(guard)) -> Dict[str, Any]:
        await _seed_inventory()
        rows = await db.tc_inventory.find({}, {"_id": 0}).sort("category", 1).to_list(100)
        pending = await db.tc_jobs.find({"status": "scheduled"}, {"_id": 0, "upsells": 1}).to_list(500)
        committed: Dict[str, int] = {}
        for j in pending:
            for u in j.get("upsells", []):
                if u in PRODUCT_IDS:
                    committed[u] = committed.get(u, 0) + 1
        for r in rows:
            r["committed"] = committed.get(r["item_id"], 0)
            r["available"] = r["stock"] - r["committed"]
            r["low"] = r["available"] <= r["low_threshold"]
        return {"items": rows, "low_count": sum(1 for r in rows if r["low"]),
                "retail_value": round(sum(r["stock"] * r["unit_price"] for r in rows), 2)}

    @router.post("/inventory/{item_id}/adjust")
    async def adjust_inventory(item_id: str, payload: Dict[str, int], _=Depends(guard)) -> Dict[str, Any]:
        delta = int(payload.get("delta", 0))
        if not delta or abs(delta) > 500:
            raise HTTPException(status_code=400, detail="delta must be non-zero, |delta| <= 500")
        item = await db.tc_inventory.find_one({"item_id": item_id})
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        new_stock = max(0, item["stock"] + delta)
        await db.tc_inventory.update_one({"item_id": item_id},
                                         {"$set": {"stock": new_stock, "updated_at": _now()}})
        return {"ok": True, "stock": new_stock}

    return router
