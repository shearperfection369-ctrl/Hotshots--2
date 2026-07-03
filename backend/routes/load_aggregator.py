"""routes.load_aggregator — Unified live feed across every load board.

Solves the "load-swapping" problem: when a broker uses DAT + Truckstop +
Direct EDI + spot rate boards, they toggle between tabs and miss loads.
This module fans out queries in parallel across every configured board,
merges + de-dupes + scores the feed by user preferences, and hands back
one ranked pipeline.

Also tracks per-board data-retention compliance (DAT keeps 24 months of
match audit trail, Truckstop keeps 7yr for TLM records, ELD-derived
records need 6 months FMCSA hold, etc.).

Endpoints — under /api/aggregator/*:
  GET  /feed              · unified live feed (all boards, filterable)
  GET  /boards            · registered boards + retention policy per board
  POST /prefs             · save operator preferences (equipment, lanes,
                            min rate/mile, saved-filters)
  GET  /prefs             · read current prefs
  POST /pin               · pin a load across boards for revisit
  GET  /pins              · list pinned loads
  DELETE /pins/{load_id}
  GET  /retention/policy  · full data-retention reference (per board)
  GET  /retention/audit   · compliance snapshot per board
  POST /retention/attest  · record an attestation event
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.aggregator")


def _tdelta_minutes(m: int) -> timedelta:
    return timedelta(minutes=int(m or 0))


# Data-retention reference — each entry documents what the load board
# expects for record retention + our current compliance posture. Used by
# the retention audit + attestation flow.
BOARD_RETENTION_POLICY: List[Dict[str, Any]] = [
    {
        "board_id": "dat",
        "board_name": "DAT One (DAT freight exchange)",
        "retention_months": 24,
        "record_types": [
            "Load match audit trail (broker + carrier + rate + booking timestamp)",
            "RateView benchmark queries (auditable snapshot)",
            "Carrier onboarding docs referenced from CarrierWatchCTPAT feed",
        ],
        "citations": ["DAT Solutions Data Use Agreement §7.2 — retention"],
        "storage_requirements": "Encrypted at rest, restore within 5 business days on subpoena.",
    },
    {
        "board_id": "truckstop",
        "board_name": "Truckstop.com (Truckstop / RMIS)",
        "retention_months": 84,  # 7 years for TLM
        "record_types": [
            "Truckstop Load Match (TLM) audit trail — 7-year hold",
            "Carrier vetting decisions from RMIS integration — 3-year hold",
            "Rate-Confirmation counter-signature copies",
        ],
        "citations": ["Truckstop TOS §12 · TLM Record Retention"],
        "storage_requirements": "Immutable snapshot per booking. Downloadable audit log within 10 business days.",
    },
    {
        "board_id": "direct_edi",
        "board_name": "Direct EDI (Shipper 204/990/214)",
        "retention_months": 84,  # SPS Commerce standard
        "record_types": [
            "EDI 204 tender + 990 response",
            "EDI 214 status codes across shipment lifecycle",
            "EDI 210 invoice + 820 remittance",
        ],
        "citations": ["SPS Commerce data retention agreement · Shipper contract SLAs"],
        "storage_requirements": "GS1 EPCIS event history. 7 years minimum. Chain-of-custody preserved.",
    },
    {
        "board_id": "spot_rate",
        "board_name": "Spot Rate Market (aggregated 3rd-party feeds)",
        "retention_months": 12,
        "record_types": [
            "Rate snapshot at booking time (lane + equipment + weight)",
            "Board source attribution",
        ],
        "citations": ["Internal SLA — spot-rate audit"],
        "storage_requirements": "Warm storage. Aggregate anonymized after 12 months.",
    },
    {
        "board_id": "smartway",
        "board_name": "SmartWay Carrier Registry (EPA)",
        "retention_months": 36,
        "record_types": [
            "Registry snapshot per carrier at time of booking",
            "SmartWay tier + fuel-efficiency profile",
        ],
        "citations": ["EPA SmartWay Data Sharing Agreement"],
        "storage_requirements": "Retained 3 years for EPA sustainability reporting.",
    },
    {
        "board_id": "eld",
        "board_name": "ELD-derived tracking events",
        "retention_months": 6,  # FMCSA minimum for supporting docs
        "record_types": [
            "HOS supporting documents referenced by tracking events",
            "Geofence enter/exit for pickup/delivery confirmation",
        ],
        "citations": ["49 CFR §395.11 — Supporting document retention"],
        "storage_requirements": "6-month minimum FMCSA hold. Extend to 12 months if disputed.",
    },
]


class PrefsIn(BaseModel):
    equipment: Optional[List[str]] = None
    min_rate_per_mile: Optional[float] = Field(None, ge=0)
    origin_states: Optional[List[str]] = None
    dest_states: Optional[List[str]] = None
    max_weight_lbs: Optional[float] = Field(None, ge=0)
    exclude_hazmat: bool = False
    preferred_boards: Optional[List[str]] = None
    saved_filter_name: Optional[str] = Field(None, max_length=80)


class PinIn(BaseModel):
    load_id: str
    board_id: str
    reason: Optional[str] = Field(None, max_length=500)


class AttestIn(BaseModel):
    board_id: str
    attester_name: Optional[str] = Field(None, max_length=120)
    finding: str = Field(..., max_length=1000)
    is_compliant: bool = True


def _score_load(load: Dict[str, Any], prefs: Dict[str, Any]) -> int:
    """Return a 0-100 score for how well this load matches the user's prefs.
    Simple heuristic — the UI displays it as a colored bar."""
    score = 50
    equip = prefs.get("equipment") or []
    if equip and load.get("equipment") in equip:
        score += 15
    elif equip:
        score -= 10
    rpm = load.get("rate_per_mile")
    min_rpm = prefs.get("min_rate_per_mile")
    if min_rpm is not None and rpm is not None:
        score += 20 if rpm >= min_rpm else -20
    if prefs.get("exclude_hazmat") and load.get("hazmat"):
        score -= 40
    origin = (load.get("origin") or "")
    dest = (load.get("destination") or "")
    for st in (prefs.get("origin_states") or []):
        if f", {st}" in origin.upper():
            score += 10
    for st in (prefs.get("dest_states") or []):
        if f", {st}" in dest.upper():
            score += 10
    return max(0, min(100, score))


def build_aggregator_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/aggregator", tags=["aggregator"])

    async def _all_boards() -> List[Dict[str, Any]]:
        # The brokerage module owns the primary board list — reuse it so
        # every consumer sees the same catalog with the same colors.
        try:
            from routes.brokerage import LOAD_BOARDS  # type: ignore
            return [dict(b) for b in LOAD_BOARDS]
        except Exception:                                          # noqa: BLE001
            return [{"id": b["board_id"], "name": b["board_name"],
                     "color": "#0EA5E9"} for b in BOARD_RETENTION_POLICY[:4]]

    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce a brokerage-style load into the aggregator's contract:
        expose `rate_per_mile` (mirrors `rpm`), guarantee `margin_usd` /
        `margin_pct` (derived from carrier_pay when a board doesn't post
        them directly), and a synthetic ISO `posted_at` for sortability."""
        rpm = row.get("rate_per_mile", row.get("rpm"))
        if rpm is not None and "rate_per_mile" not in row:
            row["rate_per_mile"] = rpm
        if "posted_at" not in row:
            mins = row.get("posted_minutes_ago") or 0
            row["posted_at"] = (
                datetime.now(timezone.utc) - _tdelta_minutes(mins)
            ).isoformat()
        # Broker margin — every load in the aggregator surfaces the
        # forecast $ margin and %. If the source board didn't provide
        # them, derive from rate_usd - carrier_pay_usd.
        rate = float(row.get("rate_usd") or 0)
        cpay = row.get("carrier_pay_usd")
        margin_usd = row.get("margin_usd")
        if margin_usd is None:
            margin_usd = row.get("forecast_margin_usd")
        if margin_usd is None and cpay is not None:
            margin_usd = round(rate - float(cpay), 2)
        if margin_usd is not None:
            row["margin_usd"] = round(float(margin_usd), 2)
            if not row.get("margin_pct") and rate > 0:
                row["margin_pct"] = round((float(margin_usd) / rate) * 100, 1)
        return row

    async def _fetch_board(bid: str) -> List[Dict[str, Any]]:
        """Fetch loads from a board by reusing whatever's persisted +
        generated by the brokerage module. This keeps the aggregator
        real-data driven without duplicating fetch logic."""
        try:
            rows = await db.brokerage_loads.find(
                {"board_id": bid}, {"_id": 0}).to_list(50)
            if not rows:
                from routes.brokerage import _gen_loads_for_board  # type: ignore
                rows = _gen_loads_for_board(bid, count=12)
            return [_normalize(dict(r)) for r in rows]
        except Exception as e:                                    # noqa: BLE001
            logger.warning("Board fetch failed for %s: %s", bid, e)
            return []

    @router.get("/boards")
    async def boards(_=Depends(get_current_user)) -> Dict[str, Any]:
        bs = await _all_boards()
        # Attach retention info per board
        retention_by_id = {r["board_id"]: r for r in BOARD_RETENTION_POLICY}
        for b in bs:
            r = retention_by_id.get(b.get("id"))
            if r:
                b["retention_months"] = r["retention_months"]
                b["retention_summary"] = f"{r['retention_months']} months"
        return {"items": bs, "count": len(bs)}

    @router.get("/feed")
    async def feed(equipment: Optional[str] = None,
                    origin_state: Optional[str] = None,
                    dest_state: Optional[str] = None,
                    min_rate_per_mile: Optional[float] = None,
                    max_weight_lbs: Optional[float] = None,
                    exclude_hazmat: bool = False,
                    boards_csv: Optional[str] = None,
                    sort_by: str = Query("score", enum=["score", "posted_at", "rate_per_mile", "rate_usd", "margin_usd", "margin_pct"]),
                    limit: int = Query(200, ge=1, le=500),
                    user=Depends(get_current_user)) -> Dict[str, Any]:
        """Unified feed across every configured board with client-supplied
        or persisted preference filters. Loads are annotated with a
        `score` (0-100) computed from user prefs + a `board_id` tag."""
        all_boards = await _all_boards()
        wanted = set(boards_csv.split(",")) if boards_csv else {b["id"] for b in all_boards}
        board_ids = [b["id"] for b in all_boards if b["id"] in wanted]

        prefs = await db.aggregator_prefs.find_one(
            {"user_id": getattr(user, "user_id", "default")}, {"_id": 0}) or {}
        # Merge query filters over persisted prefs
        merged: Dict[str, Any] = {
            "equipment": [equipment] if equipment else prefs.get("equipment"),
            "min_rate_per_mile": min_rate_per_mile if min_rate_per_mile is not None else prefs.get("min_rate_per_mile"),
            "origin_states": [origin_state] if origin_state else prefs.get("origin_states"),
            "dest_states": [dest_state] if dest_state else prefs.get("dest_states"),
            "max_weight_lbs": max_weight_lbs if max_weight_lbs is not None else prefs.get("max_weight_lbs"),
            "exclude_hazmat": bool(exclude_hazmat or prefs.get("exclude_hazmat")),
        }

        # Fan-out board fetches in parallel — this is the aggregator's
        # magic. Each board query is independent so we `gather`.
        results = await asyncio.gather(*[_fetch_board(bid) for bid in board_ids],
                                          return_exceptions=True)
        merged_rows: List[Dict[str, Any]] = []
        board_by_id = {b["id"]: b for b in all_boards}
        for bid, res in zip(board_ids, results):
            if isinstance(res, Exception):
                continue
            for r in res:
                r["board_id"] = bid
                r["board_name"] = board_by_id.get(bid, {}).get("name", bid.upper())
                r["board_color"] = board_by_id.get(bid, {}).get("color", "#0EA5E9")
                r["score"] = _score_load(r, merged)
                merged_rows.append(r)

        # Client-side filters (applied post-merge for consistency)
        def keep(r: Dict[str, Any]) -> bool:
            if merged.get("equipment") and r.get("equipment") not in merged["equipment"]:
                return False
            if merged.get("min_rate_per_mile") is not None and (r.get("rate_per_mile") or 0) < merged["min_rate_per_mile"]:
                return False
            if merged.get("max_weight_lbs") is not None and (r.get("weight_lbs") or 0) > merged["max_weight_lbs"]:
                return False
            if merged.get("exclude_hazmat") and r.get("hazmat"):
                return False
            if merged.get("origin_states"):
                if not any(f", {s}" in (r.get("origin") or "").upper() for s in merged["origin_states"]):
                    return False
            if merged.get("dest_states"):
                if not any(f", {s}" in (r.get("destination") or "").upper() for s in merged["dest_states"]):
                    return False
            return True

        filtered = [r for r in merged_rows if keep(r)]
        # De-dupe on (origin, destination, pickup_date, rate_usd) since a
        # single load can appear on multiple boards via cross-listing.
        seen = {}
        for r in filtered:
            k = (r.get("origin"), r.get("destination"), r.get("pickup_date"), r.get("rate_usd"))
            if k in seen:
                # Merge board sources — surface as list on the row
                seen[k].setdefault("also_on", []).append(r["board_id"])
            else:
                seen[k] = r
        deduped = list(seen.values())

        # Sort
        key_fn = {
            "score": lambda x: -(x.get("score") or 0),
            "posted_at": lambda x: x.get("posted_at") or "",
            "rate_per_mile": lambda x: -(x.get("rate_per_mile") or 0),
            "rate_usd": lambda x: -(x.get("rate_usd") or 0),
            "margin_usd": lambda x: -(x.get("margin_usd") or 0),
            "margin_pct": lambda x: -(x.get("margin_pct") or 0),
        }[sort_by]
        deduped.sort(key=key_fn)

        return {
            "items": deduped[:limit],
            "total": len(deduped),
            "boards_polled": board_ids,
            "applied_prefs": merged,
            "margin_summary": {
                "total_margin_usd": round(sum(float(r.get("margin_usd") or 0) for r in deduped), 2),
                "avg_margin_usd": round(
                    (sum(float(r.get("margin_usd") or 0) for r in deduped) / len(deduped))
                    if deduped else 0, 2),
                "avg_margin_pct": round(
                    (sum(float(r.get("margin_pct") or 0) for r in deduped) / len(deduped))
                    if deduped else 0, 1),
                "high_margin_count": sum(1 for r in deduped if (r.get("margin_pct") or 0) >= 18),
            },
        }

    @router.get("/prefs")
    async def get_prefs(user=Depends(get_current_user)) -> Dict[str, Any]:
        p = await db.aggregator_prefs.find_one(
            {"user_id": getattr(user, "user_id", "default")}, {"_id": 0}) or {}
        p.pop("user_id", None)
        return p

    @router.post("/prefs")
    async def save_prefs(payload: PrefsIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        p = payload.model_dump(exclude_none=True)
        p["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.aggregator_prefs.update_one(
            {"user_id": getattr(user, "user_id", "default")},
            {"$set": p, "$setOnInsert": {"user_id": getattr(user, "user_id", "default")}},
            upsert=True,
        )
        return {"ok": True, **p}

    @router.post("/pin")
    async def pin_load(payload: PinIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        doc = {
            "pin_id": f"PIN-{uuid.uuid4().hex[:10].upper()}",
            "user_id": getattr(user, "user_id", "default"),
            "pinned_at": datetime.now(timezone.utc).isoformat(),
            **payload.model_dump(),
        }
        await db.aggregator_pins.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/pins")
    async def list_pins(user=Depends(get_current_user)) -> Dict[str, Any]:
        rows = await db.aggregator_pins.find(
            {"user_id": getattr(user, "user_id", "default")},
            {"_id": 0}).sort("pinned_at", -1).to_list(200)
        return {"items": rows, "count": len(rows)}

    @router.delete("/pins/{pin_id}")
    async def unpin(pin_id: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        await db.aggregator_pins.delete_one(
            {"pin_id": pin_id, "user_id": getattr(user, "user_id", "default")})
        return {"ok": True}

    # -------- RETENTION COMPLIANCE --------
    @router.get("/retention/policy")
    async def retention_policy(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"items": BOARD_RETENTION_POLICY, "count": len(BOARD_RETENTION_POLICY)}

    @router.get("/retention/audit")
    async def retention_audit(_=Depends(get_current_user)) -> Dict[str, Any]:
        """Snapshot compliance per board — join policy vs latest attestation."""
        attests = await db.aggregator_retention_attestations.find(
            {}, {"_id": 0}).sort("attested_at", -1).to_list(200)
        latest_by_board: Dict[str, Dict[str, Any]] = {}
        for a in attests:
            if a["board_id"] not in latest_by_board:
                latest_by_board[a["board_id"]] = a
        rows: List[Dict[str, Any]] = []
        for r in BOARD_RETENTION_POLICY:
            latest = latest_by_board.get(r["board_id"])
            status = "UNATTESTED"
            if latest:
                status = "COMPLIANT" if latest.get("is_compliant") else "NON_COMPLIANT"
                # Stale if >180 days
                try:
                    when = datetime.fromisoformat(latest["attested_at"].replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - when).days > 180:
                        status = "STALE"
                except Exception:                                       # noqa: BLE001
                    pass
            rows.append({
                **r,
                "status": status,
                "latest_attestation": latest,
            })
        return {"items": rows, "compliant": sum(1 for r in rows if r["status"] == "COMPLIANT"),
                "stale": sum(1 for r in rows if r["status"] == "STALE"),
                "non_compliant": sum(1 for r in rows if r["status"] == "NON_COMPLIANT"),
                "unattested": sum(1 for r in rows if r["status"] == "UNATTESTED")}

    @router.post("/retention/attest")
    async def attest(payload: AttestIn,
                       user=Depends(require_role("admin", "auditor"))) -> Dict[str, Any]:
        if not any(r["board_id"] == payload.board_id for r in BOARD_RETENTION_POLICY):
            raise HTTPException(400, f"Unknown board_id '{payload.board_id}'")
        doc = {
            "attest_id": f"ATT-{uuid.uuid4().hex[:10].upper()}",
            "attested_at": datetime.now(timezone.utc).isoformat(),
            "attester_id": getattr(user, "user_id", None),
            "attester_role": getattr(user, "role", None),
            **payload.model_dump(),
        }
        if not doc.get("attester_name"):
            doc["attester_name"] = getattr(user, "name", "system")
        await db.aggregator_retention_attestations.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    api_router.include_router(router)
