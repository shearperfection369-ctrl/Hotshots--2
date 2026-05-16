"""routes.loadboard_adapters — pluggable real-API adapters for load boards.

Each adapter knows how to fetch loads from a real load-board API using the
credentials stored in the Connections vault. If credentials are missing or
the API call fails, callers fall back to the synthetic load feed already
defined in `routes.brokerage._gen_loads_for_board`.

This keeps the brokerage feed working out-of-the-box (synthetic loads) while
letting Orisei flip on real data the moment they paste API keys into the
Connections page — no code change required.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("tennant_tms.loadboard_adapters")


def _safe_origin_dest(s: str) -> tuple[str, str]:
    """Parse 'City, ST -> City, ST' format with a fallback."""
    parts = re.split(r"\s*(?:->|→|to)\s*", s, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return s.strip(), ""


def _to_load(raw: Dict[str, Any], board_id: str, *, origin: str, destination: str,
             rate_usd: float, miles: int, equipment: str = "Van",
             weight_lbs: int = 30000, post_age_h: int = 1,
             commodity: str = "General Freight") -> Dict[str, Any]:
    """Normalize a load from any adapter into the shape the frontend expects."""
    rpm = round(rate_usd / max(miles, 1), 2)
    forecast_margin_usd = round(rate_usd * 0.15, 2)
    margin_pct = 15.0
    return {
        "load_id": raw.get("id") or raw.get("load_id") or f"{board_id.upper()}-{uuid.uuid4().hex[:6].upper()}",
        "board_id": board_id,
        "origin": origin,
        "destination": destination,
        "miles": miles,
        "equipment": equipment,
        "commodity": commodity,
        "weight_lbs": weight_lbs,
        "pieces": raw.get("pieces") or 1,
        "rate_usd": round(rate_usd, 2),
        "rpm": rpm,
        "carrier_pay_usd": round(rate_usd * 0.85, 2),
        "forecast_margin_usd": forecast_margin_usd,
        "margin_pct": margin_pct,
        "post_age_h": post_age_h,
        "ai_score": 75,
        "ai_tags": ["live-feed"],
        "shipper": raw.get("shipper") or "Live Shipper",
        "live": True,
    }


# ---------- DAT One ----------
async def fetch_dat_loads(creds: Dict[str, Any], limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """Pull live loads from DAT One Power API.

    DAT requires a Bearer token obtained via their developer portal. When a
    valid token is present and the API responds 2xx, this returns normalized
    loads; otherwise returns None and the caller falls back to synthetic.
    """
    token = (creds or {}).get("api_key") or (creds or {}).get("access_token")
    if not token:
        return None
    base = "https://api.dat.com/load-board/v1/searches"  # public docs endpoint family
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                base,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                json={"limit": limit, "equipmentClass": "Van"},
            )
        if r.status_code >= 400:
            logger.info("DAT live-feed %s · falling back to synthetic", r.status_code)
            return None
        payload = r.json() if r.text else {}
        items = payload.get("matches") or payload.get("loads") or []
        out: List[Dict[str, Any]] = []
        for it in items[:limit]:
            o = (it.get("origin") or {}).get("city") or "—"
            os_ = (it.get("origin") or {}).get("stateProv") or ""
            d = (it.get("destination") or {}).get("city") or "—"
            ds = (it.get("destination") or {}).get("stateProv") or ""
            out.append(_to_load(
                it, "dat",
                origin=f"{o}, {os_}".strip(", "),
                destination=f"{d}, {ds}".strip(", "),
                rate_usd=float(it.get("rate") or it.get("amount") or 1800),
                miles=int(it.get("tripLength") or it.get("miles") or 600),
                equipment=it.get("equipmentType") or "Van",
                weight_lbs=int(it.get("weight") or 30000),
                post_age_h=int(it.get("ageHours") or 1),
            ))
        return out
    except httpx.RequestError as exc:
        logger.info("DAT live-feed network err %s · falling back to synthetic", exc)
        return None
    except Exception:                                                # noqa: BLE001
        logger.exception("DAT live-feed unexpected error")
        return None


# ---------- Truckstop ----------
async def fetch_truckstop_loads(creds: Dict[str, Any], limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """Truckstop.com Load Search API — OAuth 2.0 bearer token."""
    token = (creds or {}).get("access_token") or (creds or {}).get("api_key")
    if not token:
        return None
    base = "https://api.truckstop.com/v17/searches"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                base,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params={"pageSize": limit},
            )
        if r.status_code >= 400:
            logger.info("Truckstop live-feed %s · falling back to synthetic", r.status_code)
            return None
        payload = r.json() if r.text else {}
        items = payload.get("results") or payload.get("data") or []
        out: List[Dict[str, Any]] = []
        for it in items[:limit]:
            origin, dest = _safe_origin_dest(str(it.get("lane") or it.get("originDestination") or ""))
            out.append(_to_load(
                it, "truckstop",
                origin=origin or it.get("originCity", "—"),
                destination=dest or it.get("destinationCity", "—"),
                rate_usd=float(it.get("rate") or 1800),
                miles=int(it.get("miles") or 600),
                equipment=it.get("equipment") or "Van",
                weight_lbs=int(it.get("weight") or 30000),
            ))
        return out
    except httpx.RequestError as exc:
        logger.info("Truckstop live-feed network err %s · falling back to synthetic", exc)
        return None
    except Exception:                                                # noqa: BLE001
        logger.exception("Truckstop live-feed unexpected error")
        return None


# ---------- Convoy / Flexport Trucking ----------
async def fetch_convoy_loads(creds: Dict[str, Any], limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """Convoy was acquired and re-launched as part of Flexport Trucking.

    Pulls from Flexport Trucking API when a key is present. Most users will
    not have keys here, so this typically returns None and we use synthetic.
    """
    token = (creds or {}).get("api_key") or (creds or {}).get("access_token")
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://api.flexport.com/trucking/v1/loads",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": limit},
            )
        if r.status_code >= 400:
            return None
        payload = r.json() if r.text else {}
        items = payload.get("data") or []
        out: List[Dict[str, Any]] = []
        for it in items[:limit]:
            origin = (it.get("origin") or {}).get("city", "—")
            dest = (it.get("destination") or {}).get("city", "—")
            out.append(_to_load(
                it, "convoy",
                origin=origin, destination=dest,
                rate_usd=float(it.get("rate_cents", 0) / 100 or 1800),
                miles=int(it.get("miles") or 600),
                equipment=it.get("equipment_type") or "Van",
            ))
        return out
    except Exception:                                                # noqa: BLE001
        logger.exception("Convoy/Flexport live-feed error")
        return None


# Public registry — what live adapters do we know about?
ADAPTERS = {
    "dat":        ("quickbooks_or_dat", "dat",        fetch_dat_loads),
    "truckstop":  ("quickbooks_or_dat", "truckstop",  fetch_truckstop_loads),
    "convoy":     ("quickbooks_or_dat", "convoy",     fetch_convoy_loads),
}


async def try_fetch_live(board_id: str, creds: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Single entry point: returns live loads list or None.

    Caller pattern:
        creds = await get_connection_credentials(db, board_id)
        live = await try_fetch_live(board_id, creds)
        if live: return live
        # else fall through to synthetic
    """
    if board_id not in ADAPTERS or not creds:
        return None
    _, _, fetcher = ADAPTERS[board_id]
    try:
        return await asyncio.wait_for(fetcher(creds), timeout=10.0)
    except asyncio.TimeoutError:
        logger.info("%s live-feed timeout — falling back to synthetic", board_id)
        return None
