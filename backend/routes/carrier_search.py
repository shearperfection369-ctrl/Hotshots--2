"""FMCSA carrier lookup (free Socrata + optional QCMobile) + contact-enrichment slot."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

SOCRATA = "https://data.transportation.gov/resource/az4n-8mr2.json"
QC_BASE = "https://mobile.fmcsa.dot.gov/qc/services"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int(v: Any) -> Optional[int]:
    try:
        n = int(str(v).replace(",", "").strip())
        return n if n not in (0, 99999) else (0 if n == 0 else None)
    except (TypeError, ValueError):
        return None


CARGO_FIELDS = {
    "crgo_genfreight": "General Freight", "crgo_household": "Household Goods",
    "crgo_metalsheet": "Metal/Sheet", "crgo_motoveh": "Motor Vehicles",
    "crgo_drivetow": "Drive/Tow", "crgo_produce": "Produce", "crgo_livestock": "Livestock",
    "crgo_chem": "Chemicals", "crgo_drybulk": "Dry Bulk", "crgo_coldfood": "Refrigerated Food",
    "crgo_cargoothr": "Other",
}


def _norm_socrata(r: Dict[str, Any]) -> Dict[str, Any]:
    def y(k):
        return str(r.get(k, "")).strip().upper() in ("Y", "YES", "TRUE", "X")
    cargo = [label for f, label in CARGO_FIELDS.items() if y(f)]
    docket = ""
    if r.get("docket1"):
        docket = f"{r.get('docket1prefix', 'MC')}{r.get('docket1')}"
    addr = " ".join(str(r.get(k, "")).strip() for k in ("phy_street", "phy_city", "phy_state", "phy_zip") if r.get(k))
    mail = " ".join(str(r.get(k, "")).strip() for k in
                    ("carrier_mailing_street", "carrier_mailing_city", "carrier_mailing_state", "carrier_mailing_zip") if r.get(k))
    return {
        "dot_number": r.get("dot_number"), "docket": docket,
        "legal_name": (r.get("legal_name") or "").title() or r.get("legal_name"),
        "dba_name": (r.get("dba_name") or "").title() or None,
        "phone": r.get("phone"), "address": addr, "mailing_address": mail if mail != addr else "",
        "city": (r.get("phy_city") or "").title(), "state": r.get("phy_state"),
        "power_units": _int(r.get("power_units")), "drivers": _int(r.get("total_drivers")),
        "operation": r.get("carrier_operation"), "status": r.get("status_code"),
        "cargo": cargo, "source": "fmcsa_census", "retrieved_at": _now(),
    }


async def _socrata(where: str, limit: int = 25) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as cx:
        r = await cx.get(SOCRATA, params={"$where": where, "$limit": min(limit, 100),
                                          "$order": "power_units DESC"})
    if r.status_code >= 400:
        raise HTTPException(502, f"FMCSA data source error ({r.status_code})")
    return [_norm_socrata(x) for x in r.json()]


def _esc(s: str) -> str:
    return s.replace("'", "''")


def build_carrier_search_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/carrier-search", tags=["carrier-search"])
    guard = require_role("dispatcher", "auditor", "owner", "admin")

    @router.get("")
    async def search(q: str = Query(..., min_length=2), by: str = "auto",
                     state: str = "", min_units: int = 0, limit: int = 25, _=Depends(guard)):
        term = q.strip()
        digits = "".join(c for c in term if c.isdigit())
        if by == "dot" or (by == "auto" and term.upper().startswith("USDOT")) or (by == "auto" and digits == term):
            where = f"dot_number={digits}" if digits else "1=0"
        elif by == "mc" or term.upper().startswith("MC"):
            where = f"docket1='{_esc(digits)}'" if digits else "1=0"
        else:
            t = _esc(term.upper())
            where = f"(upper(legal_name) like '%{t}%' or upper(dba_name) like '%{t}%')"
        if state.strip():
            where += f" and upper(phy_state)='{_esc(state.strip().upper())}'"
        if min_units > 0:
            where += f" and power_units > {int(min_units)}"
        results = await _socrata(where, limit)
        return {"count": len(results), "results": results}

    @router.post("/add-prospect")
    async def add_prospect(payload: Dict[str, Any], _=Depends(guard)):
        name = str(payload.get("legal_name") or payload.get("dba_name") or "").strip()
        if len(name) < 2:
            raise HTTPException(400, "Carrier name required")
        existing = await db.tc_yard_prospects.find_one(
            {"$or": [{"dot_number": payload.get("dot_number")}, {"name": name}]}, {"_id": 0})
        if existing:
            return {"ok": True, "duplicate": True, "prospect_id": existing["prospect_id"],
                    "message": f"{name} is already in your hit list."}
        count = await db.tc_yard_prospects.count_documents({})
        pid = f"YP-{count + 1:02d}"
        units = payload.get("power_units") or 0
        doc = {
            "prospect_id": pid, "rank": count + 1, "name": name,
            "dba": payload.get("dba_name") or "", "dot_number": payload.get("dot_number"),
            "docket": payload.get("docket") or "", "phone": payload.get("phone") or "",
            "city": payload.get("city") or "", "state": payload.get("state") or "",
            "address": payload.get("address") or "", "trucks": units,
            "cargo": ", ".join(payload.get("cargo") or []),
            "tier": "A" if units and units <= 30 else ("B" if units and units <= 120 else "C"),
            "stage": "prospect", "source": "fmcsa", "email": "", "contact": "",
            "notes": f"Imported from FMCSA · {units or '?'} power units · {payload.get('operation', '')}".strip(),
            "created_at": _now(),
        }
        await db.tc_yard_prospects.insert_one(dict(doc))
        return {"ok": True, "prospect_id": pid, "message": f"{name} added to your hit list as {pid}."}

    @router.get("/enrichment-status")
    async def enrichment_status(_=Depends(guard)):
        providers = {"apollo": "APOLLO_API_KEY", "snov": "SNOV_API_KEY", "skrapp": "SKRAPP_API_KEY"}
        active = next((p for p, env in providers.items() if os.environ.get(env, "").strip()), None)
        return {"configured": bool(active), "provider": active,
                "message": ("Contact enrichment is live via " + active.title()) if active
                else "Contact enrichment not yet connected. Add an Apollo, Snov or Skrapp API key to enable work emails, direct dials and titles."}

    @router.post("/enrich")
    async def enrich(payload: Dict[str, Any], _=Depends(guard)):
        # Enrichment slot — activates automatically when a provider key is set.
        apollo = os.environ.get("APOLLO_API_KEY", "").strip()
        if not apollo:
            raise HTTPException(400, "Contact enrichment not configured. Add an Apollo/Snov/Skrapp API key first.")
        company = str(payload.get("company") or payload.get("legal_name") or "").strip()
        if not company:
            raise HTTPException(400, "Company name required")
        async with httpx.AsyncClient(timeout=20) as cx:
            r = await cx.post("https://api.apollo.io/api/v1/mixed_people/search",
                              headers={"X-Api-Key": apollo, "Content-Type": "application/json"},
                              json={"q_organization_name": company, "page": 1, "per_page": 5,
                                    "person_titles": payload.get("titles") or ["owner", "fleet manager", "operations"]})
        if r.status_code >= 400:
            raise HTTPException(502, f"Enrichment provider error ({r.status_code})")
        people = r.json().get("people", [])
        return {"company": company, "contacts": [
            {"name": p.get("name"), "title": p.get("title"), "email": p.get("email"),
             "phone": (p.get("phone_numbers") or [{}])[0].get("raw_number") if p.get("phone_numbers") else None,
             "linkedin": p.get("linkedin_url")} for p in people]}

    return router
