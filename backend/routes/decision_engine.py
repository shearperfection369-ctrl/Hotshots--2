"""routes.decision_engine — Layer: standalone load-matching microservice.

Pure, deterministic input->output matching over the carrier + driver registry.
No AI dependency: this endpoint answers whether or not any LLM layer is online.
"""
from typing import Any, Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field

ENGINE_VERSION = "orisei-match/1.0"
WEIGHTS = {"lane_origin": 30, "lane_dest": 10, "equipment": 30, "weight": 5,
           "reliability": 15, "availability": 6, "driver_ready": 4}
EQUIP_MAP = {"Dry Van": "Van", "Reefer": "Reefer", "Flatbed": "Flatbed"}


class MatchIn(BaseModel):
    origin: str = Field(..., min_length=2, max_length=80)
    dest: str = Field(..., min_length=2, max_length=80)
    equipment: str = "Dry Van"
    weight_lbs: int = Field(30000, ge=1, le=80000)
    miles: Optional[int] = Field(None, ge=1, le=4000)
    shipper_rate: Optional[float] = Field(None, ge=0, le=50000)


def build_decision_engine_router(*, api_router, db, get_current_user):

    @api_router.get("/decision-engine/info")
    async def engine_info(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"engine": ENGINE_VERSION, "standalone": True, "weights": WEIGHTS,
                "description": "Deterministic carrier-matching over the local carrier/driver registry. "
                               "Runs with zero AI dependency — callable by the autopilot, the UI, "
                               "an external system, or a human with curl."}

    @api_router.post("/decision-engine/match")
    async def match(payload: MatchIn, _=Depends(get_current_user)) -> Dict[str, Any]:
        o_state = payload.origin.split(",")[-1].strip()
        d_state = payload.dest.split(",")[-1].strip()
        want_eq = EQUIP_MAP.get(payload.equipment, payload.equipment)
        carriers = await db.dispatch_carriers.find({"is_active": True}, {"_id": 0}).to_list(200)
        ranked: List[Dict[str, Any]] = []
        for ca in carriers:
            states = ca.get("service_states") or []
            eqs = [str(e).lower() for e in (ca.get("equipment_types") or [])]
            drivers = await db.dispatch_drivers.count_documents(
                {"is_active": True, "$or": [{"carrier_id": ca.get("carrier_id")},
                                            {"mc_number": ca.get("mc_number", "")}]})
            comp = {
                "lane_origin": WEIGHTS["lane_origin"] if o_state in states else 0,
                "lane_dest": WEIGHTS["lane_dest"] if d_state in states else 0,
                "equipment": WEIGHTS["equipment"] if want_eq.lower() in eqs else 0,
                "weight": WEIGHTS["weight"] if payload.weight_lbs <= ca.get("max_weight_lbs", 48000) else 0,
                "reliability": round(float(ca.get("on_time_pct", 85)) / 100 * WEIGHTS["reliability"], 1),
                "availability": min(WEIGHTS["availability"], float(ca.get("days_idle", 0))),
                "driver_ready": WEIGHTS["driver_ready"] if drivers > 0 else 0,
            }
            score = round(sum(comp.values()), 1)
            est_rate = round(payload.miles * float(ca.get("rate_expectation_per_mile", 2.3)), 0) if payload.miles else None
            margin = round(payload.shipper_rate - est_rate, 2) if (payload.shipper_rate and est_rate) else None
            ranked.append({"carrier_id": ca.get("carrier_id"), "name": ca.get("legal_name"),
                           "mc_number": ca.get("mc_number"), "score": score, "components": comp,
                           "drivers_available": drivers, "qualified": comp["equipment"] > 0 and comp["weight"] > 0,
                           "est_carrier_rate": est_rate, "est_margin": margin,
                           "on_time_pct": ca.get("on_time_pct"), "home_base_state": ca.get("home_base_state")})
        ranked.sort(key=lambda x: -x["score"])
        recommended = next((r for r in ranked if r["qualified"] and r["drivers_available"] > 0), None)
        return {"engine": ENGINE_VERSION, "input": payload.model_dump(),
                "ranked": ranked[:15], "recommended": recommended,
                "carriers_evaluated": len(ranked)}
