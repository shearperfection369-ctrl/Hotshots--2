"""routes.loadboard_gateway — Layer 3: direct load-board integrations with failover.

Five-board adapter layer (DAT, Truckstop, 123Loadboard, Convoy, Uber Freight):
normalized schema, OAuth/API-key auth, circuit breaker, 60s ingestion feed with
dedup, and an API-first booking channel with automatic email fallback + outbox.
Degrades gracefully to the internal sim board until credentials exist.
"""
import hashlib
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import resend

from routes.connections import get_connection_credentials

logger = logging.getLogger(__name__)

BOARDS: Dict[str, Dict[str, Any]] = {
    "dat": {"label": "DAT One", "provider_id": "dat", "auth": "bearer",
            "base": "https://api.dat.com/v1", "loads_path": "/loads", "accept_path": "/loads/{id}/accept",
            "docs": "https://developer.dat.com", "rate_limit": "100 req/min",
            "setup": "Apply for API access in your DAT One dashboard (approved in 24-48h)"},
    "truckstop": {"label": "Truckstop.com", "provider_id": "truckstop", "auth": "x_api_key",
                  "base": "https://api.truckstop.com/v2", "loads_path": "/loads", "accept_path": "/loads/{id}/accept",
                  "docs": "https://developer.truckstop.com", "rate_limit": "200 req/min",
                  "setup": "Request API credentials from Truckstop support (5-7 business days)"},
    "123loadboard": {"label": "123Loadboard", "provider_id": "loadboard_123", "auth": "bearer",
                     "base": "https://api.123loadboard.com/api/v2", "loads_path": "/loads",
                     "accept_path": "/loads/{id}/accept",
                     "docs": "https://api.123loadboard.com/docs", "rate_limit": "50 req/min",
                     "setup": "Generate an API key in your 123Loadboard dashboard (instant)"},
    "convoy": {"label": "Convoy", "provider_id": "convoy", "auth": "bearer",
               "base": "https://api.convoy.com/v1", "loads_path": "/shipments",
               "accept_path": "/shipments/{id}/accept",
               "docs": "https://developer.convoy.com", "rate_limit": "500 req/min",
               "setup": "Apply for API access in your Convoy account (1-2 days)"},
    "uberfreight": {"label": "Uber Freight", "provider_id": "uber_freight", "auth": "bearer",
                    "base": "https://api.uberfreight.com/v1", "loads_path": "/loads",
                    "accept_path": "/loads/{id}/accept",
                    "docs": "Contact Uber Freight partner support (limited public docs)",
                    "rate_limit": "100 req/min",
                    "setup": "Request access from your Uber Freight account manager (14-30 days, may require annual commitment)"},
}
LABEL_TO_BOARD = {v["label"]: k for k, v in BOARDS.items()}
LABEL_TO_BOARD.update({"DAT": "dat", "Truckstop": "truckstop", "123Loadboard": "123loadboard",
                       "Convoy": "convoy", "Uber Freight": "uberfreight"})
FAILOVER_ORDER = list(BOARDS.keys()) + ["internal_sim"]
BENCH_MINUTES = 5
FEED_FRESH_MINUTES = 5
FEED_STALE_MINUTES = 15
SIM_FEED_FLOOR = 20

LANES = [("Minneapolis, MN", "Chicago, IL", 408), ("Chicago, IL", "Dallas, TX", 967), ("Minneapolis, MN", "Denver, CO", 914),
         ("St. Paul, MN", "Kansas City, MO", 441), ("Milwaukee, WI", "Atlanta, GA", 809), ("Des Moines, IA", "Columbus, OH", 624),
         ("Fargo, ND", "Minneapolis, MN", 240), ("Omaha, NE", "St. Louis, MO", 438), ("Chicago, IL", "Nashville, TN", 472),
         ("Green Bay, WI", "Indianapolis, IN", 400)]
COMMODITIES = ["Packaged foods", "Auto parts", "Paper products", "Machinery", "Building materials",
               "Beverages", "Plastics", "Retail freight", "Ag equipment parts", "Electronics"]
EQUIP = ["Dry Van", "Reefer", "Flatbed"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mins_ago(iso: Optional[str]) -> float:
    if not iso:
        return 1e9
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 60
    except Exception:  # noqa: BLE001
        return 1e9


def _valid_key(v: Optional[str]) -> bool:
    return bool(v and len(v.strip()) >= 10)


def _sim_loads(n: int = 14) -> List[Dict[str, Any]]:
    out = []
    for _ in range(n):
        origin, dest, miles = random.choice(LANES)
        rpm = round(random.uniform(2.05, 3.15), 2)
        out.append({"board_id": f"SIM-{uuid.uuid4().hex[:7].upper()}",
                    "board": random.choice(["DAT One", "Truckstop.com", "123Loadboard"]),
                    "origin": origin, "dest": dest, "miles": miles, "equipment": random.choice(EQUIP),
                    "commodity": random.choice(COMMODITIES), "weight_lbs": random.randint(12000, 44000),
                    "shipper_rate": round(miles * rpm, 0), "rpm": rpm, "simulated": True,
                    "pickup_date": (datetime.now(timezone.utc) + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d")})
    return out


def _normalize(board: str, x: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        origin = x.get("origin") or f"{x.get('originCity', x.get('pickup_city', ''))}, {x.get('originState', x.get('pickup_state', ''))}"
        dest = x.get("destination") or x.get("dest") or f"{x.get('destCity', x.get('delivery_city', ''))}, {x.get('destState', x.get('delivery_state', ''))}"
        miles = int(x.get("miles") or x.get("tripMiles") or x.get("distance_miles") or 0)
        rate = float(x.get("rate") or x.get("postedRate") or x.get("price") or 0)
        if len(origin.strip(", ")) < 4 or len(dest.strip(", ")) < 4 or not miles:
            return None
        return {"board_id": str(x.get("id") or x.get("loadId") or x.get("shipment_id") or uuid.uuid4().hex[:8].upper()),
                "board": BOARDS[board]["label"], "origin": origin, "dest": dest, "miles": miles,
                "equipment": x.get("equipmentType") or x.get("equipment") or "Dry Van",
                "commodity": x.get("commodity") or "General freight",
                "weight_lbs": int(x.get("weight") or x.get("weightLbs") or 30000),
                "shipper_rate": rate or round(miles * 2.5, 0),
                "rpm": round(rate / miles, 2) if rate and miles else 2.5,
                "pickup_date": str(x.get("pickupDate") or x.get("pickup_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:10],
                "simulated": False}
    except Exception:  # noqa: BLE001
        return None


async def _board_creds(db, board: str) -> Optional[Dict[str, str]]:
    return await get_connection_credentials(db, BOARDS[board]["provider_id"])


def _auth_headers(board: str, creds: Dict[str, str]) -> Optional[Dict[str, str]]:
    key = creds.get("api_key") or creds.get("client_secret") or ""
    if not _valid_key(key):
        return None
    if BOARDS[board]["auth"] == "x_api_key":
        return {"X-API-Key": key}
    return {"Authorization": f"Bearer {key}"}


async def _set_health(db, board: str, status: str, note: str = "", bench: bool = False):
    upd = {"board": board, "label": BOARDS.get(board, {}).get("label", board),
           "status": status, "note": note, "checked_at": _now()}
    if bench:
        upd["benched_until"] = (datetime.now(timezone.utc) + timedelta(minutes=BENCH_MINUTES)).isoformat()
    await db.loadboard_health.update_one({"board": board}, {"$set": upd,
                                                            "$inc": {"failures": 1 if bench else 0}}, upsert=True)


async def _is_benched(db, board: str) -> bool:
    h = await db.loadboard_health.find_one({"board": board}) or {}
    bu = h.get("benched_until")
    return bool(bu and datetime.fromisoformat(bu) > datetime.now(timezone.utc))


async def fetch_board_loads(db, board: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """One board fetch with credential check, retry and circuit breaker."""
    creds = await _board_creds(db, board)
    if not creds:
        await _set_health(db, board, "no_credentials")
        return None, "no_credentials"
    headers = _auth_headers(board, creds)
    if not headers:
        await _set_health(db, board, "no_credentials", "placeholder/blank key")
        return None, "no_credentials"
    if await _is_benched(db, board):
        return None, "benched"
    url = BOARDS[board]["base"] + BOARDS[board]["loads_path"]
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=8) as cx:
                r = await cx.get(url, headers=headers)
                r.raise_for_status()
                data = r.json()
                raw = data if isinstance(data, list) else data.get("loads") or data.get("shipments") or data.get("results") or []
                loads = [m for m in (_normalize(board, x) for x in raw[:40]) if m]
                await _set_health(db, board, "connected", f"{len(loads)} loads")
                return loads, "connected"
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                await _set_health(db, board, f"error: {type(e).__name__}", str(e)[:120], bench=True)
                return None, f"error: {type(e).__name__}"
    return None, "error"


# ---------------- booking channel: API-first, email fallback, outbox ----------------

def _booking_email_html(load: Dict[str, Any], action: str) -> Tuple[str, str]:
    drv = load.get("driver") or {}
    ca = load.get("carrier") or {}
    subject = (f"LOAD {action.upper()} — {load.get('board_id', load.get('load_id', ''))} · "
               f"{load['origin']} → {load['dest']} · PU {load.get('pickup_date', '')}")
    html = (f"<p>To the {load.get('board', 'load board')} posting desk,</p>"
            f"<p>Orisei Freight Solutions LLC (Broker) hereby <b>{action}s</b> the following posted load:</p>"
            f"<ul><li>Posting ref: <b>{load.get('board_id', '')}</b></li>"
            f"<li>Lane: <b>{load['origin']} → {load['dest']}</b> ({load.get('miles', '?')} mi)</li>"
            f"<li>Equipment: {load.get('equipment', '')} · {load.get('commodity', '')} · {load.get('weight_lbs', 0):,} lbs</li>"
            f"<li>Pickup: {load.get('pickup_date', '')}</li>"
            f"<li>Rate: <b>${float(load.get('shipper_rate', 0)):,.2f}</b></li>"
            f"<li>Assigned carrier: {ca.get('name', 'TBD')} (MC {ca.get('mc_number', 'TBD')})</li>"
            f"<li>Assigned driver: {drv.get('name', 'TBD')} (CDL {drv.get('cdl_number', 'TBD')})</li></ul>"
            f"<p>Please confirm by reply. Rate confirmation and shipping instructions issue immediately on confirmation.</p>"
            f"<p>— Orisei AI Broker Desk · dispatch@oriseifreight.com · Minneapolis, MN</p>")
    return subject, html


async def _send_or_queue_email(db, board: Optional[str], load: Dict[str, Any], action: str) -> str:
    to_email = None
    if board:
        creds = await _board_creds(db, board) or {}
        to_email = (creds.get("booking_email") or "").strip() or None
    subject, html = _booking_email_html(load, action)
    resend_creds = await get_connection_credentials(db, "resend") or {}
    if to_email and resend_creds.get("api_key"):
        try:
            resend.api_key = resend_creds["api_key"]
            resend.Emails.send({"from": resend_creds.get("from_email") or "Orisei Freight Dispatch <dispatch@oriseifreight.com>",
                                "to": [to_email], "subject": subject, "html": html})
            await db.board_actions.insert_one({"action_id": f"BA-{uuid.uuid4().hex[:6].upper()}",
                                               "load_id": load.get("load_id"), "board": board, "mode": "email",
                                               "detail": f"{action} email sent to {to_email}", "at": _now()})
            return "email"
        except Exception:  # noqa: BLE001
            logger.exception("board booking email failed")
    await db.loadboard_outbox.insert_one({"outbox_id": f"OB-{uuid.uuid4().hex[:6].upper()}", "board": board,
                                          "to_email": to_email, "subject": subject, "html": html,
                                          "load_id": load.get("load_id"), "action": action,
                                          "status": "queued", "created_at": _now(), "sent_at": None})
    await db.board_actions.insert_one({"action_id": f"BA-{uuid.uuid4().hex[:6].upper()}",
                                       "load_id": load.get("load_id"), "board": board, "mode": "queued",
                                       "detail": f"{action} email queued (missing {'booking email' if not to_email else 'Resend key'})",
                                       "at": _now()})
    return "queued"


async def book_on_board(db, load: Dict[str, Any], action: str = "accept") -> str:
    """API-first claim of a booked load on its source board; email fallback; outbox last."""
    board = LABEL_TO_BOARD.get(load.get("board", ""))
    if board:
        creds = await _board_creds(db, board)
        headers = _auth_headers(board, creds) if creds else None
        if headers and not await _is_benched(db, board) and not load.get("simulated"):
            url = BOARDS[board]["base"] + BOARDS[board]["accept_path"].format(id=load.get("board_id", ""))
            try:
                async with httpx.AsyncClient(timeout=8) as cx:
                    r = await cx.post(url, headers=headers, json={"broker": "Orisei Freight Solutions LLC"})
                    r.raise_for_status()
                await db.board_actions.insert_one({"action_id": f"BA-{uuid.uuid4().hex[:6].upper()}",
                                                   "load_id": load.get("load_id"), "board": board, "mode": "api",
                                                   "detail": f"POST {BOARDS[board]['accept_path'].format(id=load.get('board_id'))} OK",
                                                   "at": _now()})
                return "api"
            except Exception as e:  # noqa: BLE001
                await _set_health(db, board, f"error: {type(e).__name__}", "accept call failed", bench=True)
    return await _send_or_queue_email(db, board, load, action)


async def flush_outbox(db) -> int:
    resend_creds = await get_connection_credentials(db, "resend") or {}
    if not resend_creds.get("api_key"):
        return 0
    sent = 0
    items = await db.loadboard_outbox.find({"status": "queued"}).to_list(50)
    for it in items:
        to_email = it.get("to_email")
        if not to_email and it.get("board"):
            creds = await _board_creds(db, it["board"]) or {}
            to_email = (creds.get("booking_email") or "").strip() or None
        if not to_email:
            continue
        try:
            resend.api_key = resend_creds["api_key"]
            resend.Emails.send({"from": resend_creds.get("from_email") or "Orisei Freight Dispatch <dispatch@oriseifreight.com>",
                                "to": [to_email], "subject": it["subject"], "html": it["html"]})
            await db.loadboard_outbox.update_one({"outbox_id": it["outbox_id"]},
                                                 {"$set": {"status": "sent", "sent_at": _now(), "to_email": to_email}})
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("outbox flush failed for %s", it["outbox_id"])
    return sent


# ---------------- ingestion feed (60s poller, dedup) ----------------

def _fingerprint(ld: Dict[str, Any]) -> str:
    key = f"{ld['origin']}|{ld['dest']}|{ld['equipment']}|{ld['pickup_date']}|{int(ld['shipper_rate'] / 50)}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


async def ingest_tick(db) -> Dict[str, Any]:
    ingested, merged = 0, 0
    batches: List[Dict[str, Any]] = []
    for board in BOARDS:
        loads, status = await fetch_board_loads(db, board)
        if loads:
            batches.extend(loads)
    open_count = await db.board_loads.count_documents({"status": "open"})
    if not batches and open_count < SIM_FEED_FLOOR:
        batches = _sim_loads(10)
        await db.loadboard_health.update_one(
            {"board": "internal_sim"},
            {"$set": {"board": "internal_sim", "label": "Internal Sim Board", "status": "healthy",
                      "checked_at": _now()}}, upsert=True)
    for ld in batches:
        fp = _fingerprint(ld)
        existing = await db.board_loads.find_one({"fingerprint": fp})
        if existing:
            merged += 1
            upd = {"last_seen": _now()}
            if ld["shipper_rate"] > existing.get("shipper_rate", 0):
                upd.update({k: ld[k] for k in ("board", "board_id", "shipper_rate", "rpm")})
            await db.board_loads.update_one(
                {"fingerprint": fp},
                {"$set": upd, "$addToSet": {"sources": {"board": ld["board"], "board_id": ld["board_id"],
                                                        "shipper_rate": ld["shipper_rate"]}}})
        else:
            ingested += 1
            await db.board_loads.insert_one({**ld, "fingerprint": fp, "status": "open",
                                             "first_seen": _now(), "last_seen": _now(),
                                             "sources": [{"board": ld["board"], "board_id": ld["board_id"],
                                                          "shipper_rate": ld["shipper_rate"]}]})
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=FEED_STALE_MINUTES)).isoformat()
    expired = await db.board_loads.update_many({"status": "open", "last_seen": {"$lt": stale_cutoff}},
                                               {"$set": {"status": "expired"}})
    flushed = await flush_outbox(db)
    await db.loadboard_state.update_one(
        {"_id": "state"},
        {"$set": {"last_ingest_at": _now(), "last_ingested": ingested, "last_merged": merged,
                  "last_expired": expired.modified_count, "outbox_flushed": flushed},
         "$inc": {"ingest_ticks": 1}}, upsert=True)
    return {"ingested": ingested, "merged": merged, "expired": expired.modified_count, "outbox_flushed": flushed}


async def gateway_fetch_loads(db, n: int = 14) -> Dict[str, Any]:
    """Autopilot sourcing: prefer the fresh deduped feed, else live failover, else sim."""
    fresh_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=FEED_FRESH_MINUTES)).isoformat()
    feed = await db.board_loads.find({"status": "open", "last_seen": {"$gte": fresh_cutoff}},
                                     {"_id": 0}).sort("last_seen", -1).to_list(n)
    if feed:
        await db.loadboard_state.update_one({"_id": "state"},
                                            {"$set": {"last_fetch_at": _now(), "last_source": "ingestion_feed",
                                                      "loads_fetched": len(feed)},
                                             "$inc": {"total_fetches": 1}}, upsert=True)
        return {"source": "ingestion_feed", "source_label": "Deduped Ingestion Feed", "loads": feed}
    loads, source = None, "internal_sim"
    for board in BOARDS:
        result, _status = await fetch_board_loads(db, board)
        if result and loads is None:
            loads, source = result, board
    if loads is None:
        loads = _sim_loads(n)
    label = BOARDS.get(source, {}).get("label", "Internal Sim Board")
    await db.loadboard_state.update_one({"_id": "state"},
                                        {"$set": {"last_fetch_at": _now(), "last_source": source,
                                                  "loads_fetched": len(loads)},
                                         "$inc": {"total_fetches": 1}}, upsert=True)
    return {"source": source, "source_label": label, "loads": loads}


# ---------------- router ----------------

def build_loadboard_gateway_router(*, api_router, db, get_current_user):
    from fastapi import Depends, HTTPException

    @api_router.get("/loadboard-gateway/status")
    async def gateway_status(_=Depends(get_current_user)) -> Dict[str, Any]:
        health = await db.loadboard_health.find({}, {"_id": 0}).to_list(10)
        by_board = {h["board"]: h for h in health}
        state = await db.loadboard_state.find_one({"_id": "state"}, {"_id": 0}) or {}
        chain = []
        for b in FAILOVER_ORDER:
            label = BOARDS.get(b, {}).get("label", "Internal Sim Board")
            chain.append({"board": b, "label": label,
                          **(by_board.get(b) or {"status": "healthy" if b == "internal_sim" else "no_credentials",
                                                 "checked_at": None})})
        return {"failover_order": FAILOVER_ORDER, "chain": chain, "state": state,
                "note": "Real boards activate automatically once API keys are saved in Connections."}

    @api_router.post("/loadboard-gateway/fetch")
    async def gateway_fetch(_=Depends(get_current_user)) -> Dict[str, Any]:
        res = await gateway_fetch_loads(db)
        return {"ok": True, "source": res["source"], "source_label": res["source_label"],
                "count": len(res["loads"]), "sample": res["loads"][:6]}

    @api_router.get("/loadboard-gateway/boards")
    async def boards(_=Depends(get_current_user)) -> Dict[str, Any]:
        health = {h["board"]: h for h in await db.loadboard_health.find({}, {"_id": 0}).to_list(10)}
        out = []
        for bid, meta in BOARDS.items():
            creds = await _board_creds(db, bid)
            has_key = bool(creds and _auth_headers(bid, creds))
            out.append({"board": bid, "label": meta["label"], "provider_id": meta["provider_id"],
                        "docs": meta["docs"], "rate_limit": meta["rate_limit"], "setup": meta["setup"],
                        "has_api_key": has_key,
                        "booking_email": (creds or {}).get("booking_email", "") or "",
                        "health": health.get(bid, {"status": "no_credentials"})})
        return {"boards": out}

    @api_router.post("/loadboard-gateway/boards/{board_id}/test")
    async def test_board(board_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        if board_id not in BOARDS:
            raise HTTPException(status_code=404, detail="Unknown board")
        loads, status = await fetch_board_loads(db, board_id)
        return {"ok": status == "connected", "board": board_id, "status": status,
                "loads_found": len(loads or [])}

    @api_router.get("/loadboard-gateway/feed")
    async def feed(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.board_loads.find({"status": "open"}, {"_id": 0}).sort("last_seen", -1).to_list(50)
        state = await db.loadboard_state.find_one({"_id": "state"}, {"_id": 0}) or {}
        return {"loads": rows, "open_count": await db.board_loads.count_documents({"status": "open"}),
                "expired_count": await db.board_loads.count_documents({"status": "expired"}),
                "state": state}

    @api_router.get("/loadboard-gateway/outbox")
    async def outbox(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.loadboard_outbox.find({}, {"_id": 0, "html": 0}).sort("created_at", -1).to_list(50)
        return {"outbox": rows,
                "queued": await db.loadboard_outbox.count_documents({"status": "queued"}),
                "sent": await db.loadboard_outbox.count_documents({"status": "sent"})}

    @api_router.post("/loadboard-gateway/outbox/flush")
    async def outbox_flush(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"ok": True, "sent": await flush_outbox(db)}

    @api_router.get("/loadboard-gateway/actions")
    async def actions(_=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.board_actions.find({}, {"_id": 0}).sort("at", -1).to_list(50)
        return {"actions": rows}

    @api_router.post("/loadboard-gateway/ingest")
    async def manual_ingest(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"ok": True, **(await ingest_tick(db))}


async def ingestion_loop(db):
    import asyncio
    await asyncio.sleep(20)
    while True:
        try:
            await ingest_tick(db)
        except Exception:  # noqa: BLE001
            logger.exception("loadboard ingestion tick failed")
        await asyncio.sleep(60)
