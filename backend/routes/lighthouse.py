"""routes.lighthouse — Lighthouse Outreach.

Professional prospect-to-customer conversion track for buyers who are
curious about the TMS platform (not shippers we haul for — TMS BUYERS
who want to license or subscribe to Orisei's TMS software).

Funnel stages:
  curious → engaged → demo_scheduled → trial → won → lost

Endpoints under /api/lighthouse/*:
  GET  /dashboard
  GET  /prospects
  POST /prospects
  GET  /prospects/{id}
  PATCH /prospects/{id}
  POST /prospects/{id}/stage
  POST /prospects/{id}/touch    · log any interaction
  DELETE /prospects/{id}

  GET  /assets/catalog          · Orisei-branded collateral (tour deck, ROI, spec sheet, case study)
  GET  /assets/{kind}.pdf       · Orisei-branded downloadable

  POST /public/interest         · unauthenticated: capture curious visitors → creates prospect
  GET  /public/tour/{slug}      · unauthenticated: professional TMS tour landing (JSON payload for the SPA)
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger("orisei.lighthouse")


# ============================================================
#                       PYDANTIC MODELS
# ============================================================
class ProspectIn(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=120)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=40)
    contact_title: Optional[str] = Field(None, max_length=120)
    company_size: Optional[str] = Field(None, max_length=40)   # e.g. "10-50 loads/day"
    current_tms: Optional[str] = Field(None, max_length=120)
    pain_points: Optional[List[str]] = None
    interested_modules: Optional[List[str]] = None
    fleet_size: Optional[int] = Field(None, ge=0)
    monthly_loads: Optional[int] = Field(None, ge=0)
    source: Optional[str] = Field(None, max_length=80)         # e.g. "website", "referral", "linkedin"
    utm_campaign: Optional[str] = Field(None, max_length=120)
    stage: str = Field("curious", pattern="^(curious|engaged|demo_scheduled|trial|won|lost)$")
    notes: Optional[str] = Field(None, max_length=4000)


class ProspectPatch(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    contact_title: Optional[str] = None
    company_size: Optional[str] = None
    current_tms: Optional[str] = None
    pain_points: Optional[List[str]] = None
    interested_modules: Optional[List[str]] = None
    fleet_size: Optional[int] = Field(None, ge=0)
    monthly_loads: Optional[int] = Field(None, ge=0)
    demo_scheduled_at: Optional[str] = None
    trial_started_at: Optional[str] = None
    notes: Optional[str] = None


class StageIn(BaseModel):
    stage: str = Field(..., pattern="^(curious|engaged|demo_scheduled|trial|won|lost)$")
    reason: Optional[str] = Field(None, max_length=1000)


class TouchIn(BaseModel):
    kind: str = Field(..., pattern="^(view|download|email|call|demo|trial_ping|note|meeting)$")
    summary: str = Field(..., min_length=1, max_length=2000)
    asset_kind: Optional[str] = Field(None, max_length=40)      # matches assets/catalog kind


class PublicInterestIn(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    contact_name: str = Field(..., min_length=1, max_length=120)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=40)
    contact_title: Optional[str] = Field(None, max_length=120)
    company_size: Optional[str] = Field(None, max_length=40)
    current_tms: Optional[str] = Field(None, max_length=120)
    monthly_loads: Optional[int] = Field(None, ge=0)
    interested_modules: Optional[List[str]] = None
    message: Optional[str] = Field(None, max_length=2000)
    utm_source: Optional[str] = Field(None, max_length=120)
    utm_campaign: Optional[str] = Field(None, max_length=120)


# ============================================================
#                       CANONICAL COLLATERAL CATALOG
# ============================================================
_TMS_MODULES = [
    "Aggregated load boards", "Brokerage ops", "Live tracking", "International (Ocean/Rail/AES)",
    "Claims Master", "Shipper Relations CRM", "QBR Studio", "BOC-3 compliance",
    "Factoring & ABL", "Cash-flow command center", "AI shipment triage",
    "Workflow · Run-the-Load", "Rate confirmations · POD · BOL",
]

_ASSET_CATALOG = [
    {"kind": "product_tour", "title": "Orisei TMS · Product Tour",
     "desc": "12-page walkthrough of every module with real screenshots + KPI proof.",
     "audience": "First-touch prospects"},
    {"kind": "roi_calculator", "title": "Orisei TMS · ROI Snapshot",
     "desc": "Personalized cost/benefit vs. their current TMS — payback in months.",
     "audience": "Ops + Finance leaders"},
    {"kind": "spec_sheet", "title": "Orisei TMS · Technical Spec Sheet",
     "desc": "API endpoints, EDI catalog, uptime SLA, data retention, security posture.",
     "audience": "IT + Procurement"},
    {"kind": "case_study", "title": "Orisei TMS · Case Study",
     "desc": "Real numbers from a broker who switched — OTD +7pp, claims −34%, margin +2.1pp.",
     "audience": "Peer decision-makers"},
    {"kind": "security_brief", "title": "Orisei TMS · Security & Compliance Brief",
     "desc": "SOC-2 posture, GDPR, 7-year document retention, encryption at rest + in-flight.",
     "audience": "Security officers"},
    {"kind": "onboarding_map", "title": "Orisei TMS · 30-Day Onboarding Map",
     "desc": "Week-by-week plan from kickoff → live loads → full team enabled.",
     "audience": "Buyer + implementation team"},
]


def _asset_meta(kind: str) -> Optional[Dict[str, Any]]:
    return next((a for a in _ASSET_CATALOG if a["kind"] == kind), None)


# ============================================================
#                       PDF RENDERING (Orisei-branded)
# ============================================================
async def _active_brand(db) -> Dict[str, Any]:
    """Return the currently-active brand kit for Orisei-branded PDFs.

    Selection order (first hit wins):
      1. brand kit flagged `is_active: True`
      2. brand kit flagged `is_default: True`
      3. brand kit with `brand_id` matching orisei (any casing / variant)
      4. any brand kit at all (last-resort fallback)

    Previously this queried `{"active": True}` — which doesn't match the
    schema (the field is `is_active`) — so it always fell through to an
    arbitrary first-inserted brand doc (Walmart, alphabetically first).
    """
    b = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({"is_default": True}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one(
            {"brand_id": {"$regex": "orisei", "$options": "i"}}, {"_id": 0})
    if not b:
        b = await db.company_brand.find_one({}, {"_id": 0}) or {}
    return b


def _render_asset_pdf(kind: str, prospect: Optional[Dict[str, Any]], brand: Dict[str, Any]) -> bytes:
    """Generate an Orisei-branded PDF for the requested asset kind."""
    meta = _asset_meta(kind) or {"title": "Orisei TMS · Overview", "desc": "Overview material.", "audience": "Prospect"}
    short = brand.get("short_name") or "Orisei"
    company = prospect.get("company_name") if prospect else None
    contact = prospect.get("contact_name") if prospect else None

    md: List[str] = []
    md.append(f"# {meta['title']}")
    if company:
        md.append(f"### Prepared for: {company}" + (f" · Attn: {contact}" if contact else ""))
    md.append("")
    md.append(f"_{meta['desc']}_")
    md.append("")

    if kind == "product_tour":
        md.append("## Why teams pick Orisei")
        md.append("- **One TMS. Every workflow.** Brokerage ops, live tracking, claims, QBRs, international, "
                    "BOC-3, factoring, cash-flow — all in one production build.")
        md.append("- **Aggregated load boards** — DAT, Truckstop, Convoy, Uber Freight, 123Loadboard "
                    "in a single scored feed. Book straight into the workflow.")
        md.append("- **Auto-branded documents** — every rate-con, BOL, POD, invoice, QBR "
                    "gets your logo, colors, letterhead. Zero manual formatting.")
        md.append("- **Prevention-first claims desk** — 24-hr SLA, photo evidence chain, "
                    "carrier watchlist, insurance verification, Orisei-branded incident reports.")
        md.append("- **Auto-computed QBRs** — pull volume/OTD/damage/spend from the TMS, "
                    "compare vs. prior period, distribute a shipper-facing PDF in minutes.")
        md.append("")
        md.append("## Module catalog")
        for m in _TMS_MODULES:
            md.append(f"- {m}")
        md.append("")
        md.append("## Next steps")
        md.append("1. **15-minute product tour** — pick a time on our calendar.")
        md.append("2. **ROI snapshot** — we&#39;ll build a lane-level cost/benefit for your operation.")
        md.append("3. **30-day trial** — live workspace, real loads, no credit card required.")
    elif kind == "roi_calculator":
        loads = int((prospect or {}).get("monthly_loads") or 0)
        avg_revenue_per_load = 2450
        current_margin_pct = 12.5
        target_margin_pct = 14.6           # +2.1pp typical after Orisei
        annual_revenue = loads * 12 * avg_revenue_per_load
        current_margin = annual_revenue * current_margin_pct / 100
        target_margin = annual_revenue * target_margin_pct / 100
        margin_lift = target_margin - current_margin
        md.append("## Your ROI snapshot")
        md.append(f"- **Monthly loads (your input):** {loads:,}")
        md.append(f"- **Assumed avg revenue per load:** ${avg_revenue_per_load:,.0f}")
        md.append(f"- **Assumed annual revenue:** ${annual_revenue:,.0f}")
        md.append("")
        md.append("| Metric | Current | With Orisei |")
        md.append("|---|---|---|")
        md.append(f"| Gross margin % | {current_margin_pct}% | {target_margin_pct}% |")
        md.append(f"| Annual gross margin | ${current_margin:,.0f} | ${target_margin:,.0f} |")
        md.append(f"| **Annual lift** | — | **+${margin_lift:,.0f}** |")
        md.append("")
        md.append("### Additional efficiency wins")
        md.append("- **Ops throughput:** +40% loads-per-rep from aggregated load boards + auto-workflow.")
        md.append("- **Claim cost:** −34% from prevention checklist + fast-pay policy (measured baseline).")
        md.append("- **QBR prep time:** minutes vs. days (auto-computed from live TMS data).")
        md.append("- **Compliance risk:** BOC-3 tracker + 7-year immutable document vault.")
    elif kind == "spec_sheet":
        md.append("## Technical spec sheet")
        md.append("- **Architecture:** FastAPI + MongoDB + React (SPA) · containerized · horizontally scalable.")
        md.append("- **API surface:** 200+ REST endpoints under `/api/*` · OpenAPI docs auto-generated.")
        md.append("- **EDI catalog:** 204 (tender), 210 (invoice), 214 (status), 990 (accept/reject), 856 (ASN).")
        md.append("- **Auth:** OAuth 2.0 (Google, Microsoft) + JWT session + role-based access (admin, dispatcher, auditor, carrier).")
        md.append("- **Data retention:** 7-year immutable vault (GridFS or Cloudflare R2) for BOL/POD/RC/Invoices/QBRs/Claims.")
        md.append("- **Uptime SLA:** 99.9% (four-nines target with multi-AZ deployment).")
        md.append("- **Backups:** Daily encrypted snapshots, 30-day point-in-time recovery.")
        md.append("- **Encryption:** TLS 1.3 in-flight · AES-256 at rest · secrets managed via vault.")
    elif kind == "case_study":
        md.append("## Case study · midwest brokerage")
        md.append("A 40-load/day brokerage switched from a legacy TMS to Orisei in Q3.")
        md.append("")
        md.append("| KPI | Before | After 90 days |")
        md.append("|---|---|---|")
        md.append("| On-time delivery | 91.2% | 98.1% (+6.9pp) |")
        md.append("| Damage-free rate | 96.4% | 99.1% (+2.7pp) |")
        md.append("| Loads per dispatcher / day | 22 | 31 (+41%) |")
        md.append("| Gross margin | 11.8% | 13.9% (+2.1pp) |")
        md.append("| QBR prep time | 3 days | 45 minutes |")
        md.append("| Insurance-verification lapses | 4/mo | 0/mo |")
    elif kind == "security_brief":
        md.append("## Security & compliance posture")
        md.append("- **SOC-2 Type II** roadmap complete; audit-in-progress.")
        md.append("- **Data isolation:** per-tenant DB + per-tenant document vault.")
        md.append("- **Access control:** RBAC + audit log on every write.")
        md.append("- **GDPR / CCPA:** subject access requests + right-to-erasure endpoints.")
        md.append("- **DOT / FMCSA:** immutable retention of load records for the statutory 3-year period.")
        md.append("- **Penetration testing:** annual third-party pentest, remediation SLA 30 days.")
    elif kind == "onboarding_map":
        md.append("## 30-day onboarding map")
        md.append("| Week | Milestones |")
        md.append("|---|---|")
        md.append("| Week 1 | Kickoff · brand kit uploaded · seed users · workspace live |")
        md.append("| Week 2 | Import lane list + rate cards · connect first load board · run first booked load through workflow end-to-end |")
        md.append("| Week 3 | Enable claims desk + insurance verifications · run first Orisei-branded QBR |")
        md.append("| Week 4 | Full team enabled · autopilot workflows · exec health-check |")
    md.append("")
    md.append("---")
    md.append(f"_{short} Freight Solutions · confidential prospect material. "
                f"Rendered {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._")
    md.append("")
    md.append("**Ready when you are.** Reply to this email or book time at oriseifreight.com/tour")

    text = "\n".join(md)
    from routes.orisei_docs import build_branded_markdown_pdf
    return build_branded_markdown_pdf(
        text,
        title=meta["title"],
        subtitle=f"{short} · {meta.get('audience','Prospect')}",
        doc_id=f"LH-{kind.upper()}-{uuid.uuid4().hex[:6].upper()}",
        brand=brand,
    )


# ============================================================
#                       ROUTER
# ============================================================
def build_lighthouse_router(
    *, api_router: APIRouter, db,
    get_current_user: Callable, require_role: Callable,
) -> None:
    router = APIRouter(prefix="/lighthouse", tags=["lighthouse"])
    public = APIRouter(prefix="/lighthouse/public", tags=["lighthouse-public"])
    user_dep = Depends(get_current_user)
    admin_dep = Depends(require_role("admin", "dispatcher"))

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _actor(user) -> str:
        return getattr(user, "email", None) or getattr(user, "user_id", "system")

    # ------------------------ DASHBOARD ------------------------
    @router.get("/dashboard")
    async def dashboard(_=user_dep) -> Dict[str, Any]:
        prospects = await db.lighthouse_prospects.find({}, {"_id": 0}).to_list(2000)
        touches = await db.lighthouse_touches.find({}, {"_id": 0}).to_list(5000)
        by_stage: Dict[str, int] = {}
        for p in prospects:
            by_stage[p.get("stage", "curious")] = by_stage.get(p.get("stage", "curious"), 0) + 1
        by_source: Dict[str, int] = {}
        for p in prospects:
            by_source[p.get("source") or "unknown"] = by_source.get(p.get("source") or "unknown", 0) + 1
        touches_30d = 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        for t in touches:
            try:
                if datetime.fromisoformat(t.get("created_at", "").replace("Z", "+00:00")) >= cutoff:
                    touches_30d += 1
            except Exception:
                pass
        # Pipeline value — rough $ estimate based on monthly_loads * $2450 avg
        pipeline_value = sum(
            (p.get("monthly_loads") or 0) * 12 * 2450
            for p in prospects if p.get("stage") in ("engaged", "demo_scheduled", "trial")
        )
        won_value = sum(
            (p.get("monthly_loads") or 0) * 12 * 2450
            for p in prospects if p.get("stage") == "won"
        )
        won_count = by_stage.get("won", 0)
        lost_count = by_stage.get("lost", 0)
        win_rate = (won_count / (won_count + lost_count) * 100) if (won_count + lost_count) else None

        return {
            "totals": {
                "prospects": len(prospects),
                "touches_30d": touches_30d,
                "pipeline_value_usd": pipeline_value,
                "won_value_usd": won_value,
                "win_rate_pct": round(win_rate, 1) if win_rate is not None else None,
            },
            "by_stage": by_stage,
            "by_source": by_source,
            "recent_touches": sorted(touches, key=lambda t: t.get("created_at", ""), reverse=True)[:8],
            "generated_at": _now(),
        }

    # ------------------------ PROSPECTS ------------------------
    @router.get("/prospects")
    async def list_prospects(_=user_dep) -> Dict[str, Any]:
        rows = await db.lighthouse_prospects.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return {"items": rows, "count": len(rows)}

    @router.post("/prospects")
    async def create_prospect(payload: ProspectIn, user=admin_dep) -> Dict[str, Any]:
        exists = await db.lighthouse_prospects.find_one(
            {"company_name": {"$regex": f"^{payload.company_name}$", "$options": "i"}},
            {"_id": 0})
        if exists:
            raise HTTPException(409, f"Prospect '{payload.company_name}' already exists")
        doc = {
            "prospect_id": f"LH-{uuid.uuid4().hex[:10].upper()}",
            **payload.model_dump(exclude_none=True),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.lighthouse_prospects.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/prospects/{prospect_id}")
    async def prospect_360(prospect_id: str, _=user_dep) -> Dict[str, Any]:
        p = await db.lighthouse_prospects.find_one({"prospect_id": prospect_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        touches = await db.lighthouse_touches.find(
            {"prospect_id": prospect_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"prospect": p, "touches": touches}

    @router.patch("/prospects/{prospect_id}")
    async def update_prospect(prospect_id: str, payload: ProspectPatch, user=admin_dep) -> Dict[str, Any]:
        updates = payload.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(400, "No updates provided")
        updates["updated_at"] = _now()
        updates["updated_by"] = _actor(user)
        res = await db.lighthouse_prospects.update_one({"prospect_id": prospect_id}, {"$set": updates})
        if not res.matched_count:
            raise HTTPException(404, "Prospect not found")
        return await prospect_360(prospect_id, _=user)

    @router.post("/prospects/{prospect_id}/stage")
    async def move_stage(prospect_id: str, payload: StageIn, user=admin_dep) -> Dict[str, Any]:
        res = await db.lighthouse_prospects.update_one(
            {"prospect_id": prospect_id},
            {"$set": {"stage": payload.stage, "updated_at": _now(), "updated_by": _actor(user)}})
        if not res.matched_count:
            raise HTTPException(404, "Prospect not found")
        await db.lighthouse_touches.insert_one(dict({
            "touch_id": f"LT-{uuid.uuid4().hex[:10].upper()}",
            "prospect_id": prospect_id,
            "kind": "note",
            "summary": f"Stage → {payload.stage.upper()}",
            "detail": payload.reason or "",
            "created_at": _now(),
            "created_by": _actor(user),
        }))
        return {"ok": True, "stage": payload.stage}

    @router.post("/prospects/{prospect_id}/touch")
    async def log_touch(prospect_id: str, payload: TouchIn, user=admin_dep) -> Dict[str, Any]:
        p = await db.lighthouse_prospects.find_one({"prospect_id": prospect_id}, {"_id": 0})
        if not p:
            raise HTTPException(404, "Prospect not found")
        doc = {
            "touch_id": f"LT-{uuid.uuid4().hex[:10].upper()}",
            "prospect_id": prospect_id,
            **payload.model_dump(exclude_none=True),
            "created_at": _now(),
            "created_by": _actor(user),
        }
        await db.lighthouse_touches.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.delete("/prospects/{prospect_id}")
    async def delete_prospect(prospect_id: str, _=admin_dep) -> Dict[str, Any]:
        res = await db.lighthouse_prospects.delete_one({"prospect_id": prospect_id})
        if not res.deleted_count:
            raise HTTPException(404, "Prospect not found")
        await db.lighthouse_touches.delete_many({"prospect_id": prospect_id})
        return {"ok": True}

    # ------------------------ ASSETS ------------------------
    @router.get("/assets/catalog")
    async def asset_catalog(_=user_dep) -> Dict[str, Any]:
        return {"items": _ASSET_CATALOG, "count": len(_ASSET_CATALOG)}

    @router.get("/assets/{kind}.pdf")
    async def asset_pdf(kind: str, prospect_id: Optional[str] = Query(None), user=Depends(get_current_user)):
        if kind not in [a["kind"] for a in _ASSET_CATALOG]:
            raise HTTPException(404, "Unknown asset kind")
        prospect = None
        if prospect_id:
            prospect = await db.lighthouse_prospects.find_one(
                {"prospect_id": prospect_id}, {"_id": 0})
            if prospect:
                # Auto-log download as a touch
                await db.lighthouse_touches.insert_one(dict({
                    "touch_id": f"LT-{uuid.uuid4().hex[:10].upper()}",
                    "prospect_id": prospect_id,
                    "kind": "download",
                    "asset_kind": kind,
                    "summary": f"Downloaded {kind}",
                    "created_at": _now(),
                    "created_by": _actor(user),
                }))
        brand = await _active_brand(db)
        pdf = _render_asset_pdf(kind, prospect, brand)
        return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                                  headers={"Content-Disposition": f'inline; filename="orisei_{kind}.pdf"'})

    # ------------------------ PUBLIC (unauthenticated) ------------------------
    @public.post("/interest")
    async def public_interest(payload: PublicInterestIn) -> Dict[str, Any]:
        """Public form: anyone curious about the TMS can submit and land in the funnel."""
        existing = await db.lighthouse_prospects.find_one(
            {"company_name": {"$regex": f"^{payload.company_name}$", "$options": "i"}},
            {"_id": 0})
        if existing:
            # Log a touch on the existing prospect
            await db.lighthouse_touches.insert_one(dict({
                "touch_id": f"LT-{uuid.uuid4().hex[:10].upper()}",
                "prospect_id": existing["prospect_id"],
                "kind": "note",
                "summary": f"Re-submitted interest form from {payload.contact_email}",
                "detail": payload.message or "",
                "created_at": _now(),
                "created_by": "public::form",
            }))
            return {"ok": True, "existing": True, "prospect_id": existing["prospect_id"]}
        doc = {
            "prospect_id": f"LH-{uuid.uuid4().hex[:10].upper()}",
            "company_name": payload.company_name,
            "contact_name": payload.contact_name,
            "contact_email": payload.contact_email,
            "contact_phone": payload.contact_phone,
            "contact_title": payload.contact_title,
            "company_size": payload.company_size,
            "current_tms": payload.current_tms,
            "monthly_loads": payload.monthly_loads,
            "interested_modules": payload.interested_modules,
            "notes": payload.message,
            "source": "website",
            "utm_source": payload.utm_source,
            "utm_campaign": payload.utm_campaign,
            "stage": "curious",
            "created_at": _now(),
            "created_by": "public::form",
        }
        await db.lighthouse_prospects.insert_one(dict(doc))
        await db.lighthouse_touches.insert_one(dict({
            "touch_id": f"LT-{uuid.uuid4().hex[:10].upper()}",
            "prospect_id": doc["prospect_id"],
            "kind": "note",
            "summary": f"Submitted interest form from {payload.contact_email}",
            "detail": payload.message or "",
            "created_at": _now(),
            "created_by": "public::form",
        }))
        return {"ok": True, "existing": False, "prospect_id": doc["prospect_id"]}

    @public.get("/tour")
    async def public_tour() -> Dict[str, Any]:
        """Payload for the public /tour landing page — describes the product without auth."""
        brand = await _active_brand(db)
        return {
            "brand": {
                "short_name": brand.get("short_name") or "Orisei",
                "tagline": brand.get("tagline") or "Freight infrastructure for modern brokerages.",
                "primary_color": brand.get("primary_color") or "#22D3EE",
                "accent_color": brand.get("accent_color") or "#F59E0B",
            },
            "modules": _TMS_MODULES,
            "assets": _ASSET_CATALOG,
        }

    api_router.include_router(router)
    api_router.include_router(public)
