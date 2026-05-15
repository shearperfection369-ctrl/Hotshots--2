"""routes.branding — multi-tenant brand management.

Endpoints:
  GET    /branding              · active brand (or default Tennant)
  GET    /branding/all          · admin: list every generated brand
  POST   /branding/generate     · admin: Claude generates full brand profile
  POST   /branding/manual       · admin: paste manual brand fields
  GET    /branding/template     · admin: blank template the UI pre-fills
  POST   /branding/activate     · admin: switch active brand
  DELETE /branding/{brand_id}   · admin: delete (Tennant default protected)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


logger = logging.getLogger("tennant_tms.branding")


DEFAULT_BRAND = {
    "brand_id": "tennant",
    "company_name": "Tennant Companies",
    "short_name": "Tennant",
    "tagline": "Mission-control TMS · Built for the team's day",
    "industry": "Industrial cleaning equipment manufacturer",
    "headquarters": "Golden Valley, MN",
    "primary_color": "#00E5FF",
    "secondary_color": "#06B6D4",
    "accent_color": "#10B981",
    "logo_letter": "T",
    "sample_products": ["T16 AMR Scrubber", "T350 LPG Scrubber", "S30 Sweeper", "M30 Combo", "X4 ROVR"],
    "sample_suppliers": ["Samsung SDI", "Trojan Battery", "Honda Power Equipment", "Premier Polymers", "Midwest Steel"],
    "sample_lanes": ["Golden Valley → Holland MI", "Holland MI → Louisville KY", "Busan KR → Long Beach CA", "Yokohama JP → Tacoma WA"],
    "catalog_label": "Machine Catalog",
    "is_default": True,
}


class BrandGenerateIn(BaseModel):
    company_name: str
    activate: bool = True


class BrandManualIn(BaseModel):
    company_name: str
    short_name: Optional[str] = None
    tagline: Optional[str] = ""
    industry: Optional[str] = ""
    headquarters: Optional[str] = ""
    primary_color: Optional[str] = "#00E5FF"
    secondary_color: Optional[str] = "#06B6D4"
    accent_color: Optional[str] = "#10B981"
    logo_letter: Optional[str] = None
    catalog_label: Optional[str] = "Product Catalog"
    sample_products: Optional[List[str]] = []
    sample_suppliers: Optional[List[str]] = []
    sample_lanes: Optional[List[str]] = []
    facilities: Optional[List[Dict[str, str]]] = []
    promo_video_ids: Optional[List[str]] = []
    activate: bool = True


class BrandActivateIn(BaseModel):
    brand_id: str


def build_branding_router(
    *,
    db,
    get_current_user: Callable,
    require_role: Callable,
    emergent_llm_key: Optional[str],
    LlmChat,                       # noqa: N803 — injected class
    UserMessage,                   # noqa: N803 — injected class
) -> APIRouter:
    router = APIRouter()

    async def _ensure_brand_erp_stub(brand: Dict[str, Any]):
        """When a brand is activated, ensure there's an ERP connection labeled
        for that brand. Becomes active only if no real ERP is already set."""
        short = brand.get("short_name") or brand.get("company_name") or "Brand"
        slug = re.sub(r"[^a-z0-9]+", "", short.lower())[:20] or "brand"
        conn_id = f"sap-{slug}-auto"
        existing = await db.erp_config.find_one({"connection_id": conn_id})
        doc = {
            "connection_id": conn_id,
            "erp_key": "sap_s4hana",
            "erp_name": "SAP S/4HANA",
            "label": f"{short} · S/4HANA (auto)",
            "auth_mode": "oauth2_client_credentials",
            "config": {"base_url": f"https://my-s4.{slug}.com", "client": "100"},
            "auto_stub": True,
            "brand_id": brand.get("brand_id"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if not existing:
            doc["created_at"] = doc["updated_at"]
        await db.erp_config.update_one({"connection_id": conn_id}, {"$set": doc}, upsert=True)
        cur = await db.erp_config.find_one({"is_active": True}, {"_id": 0})
        if not cur or cur.get("auto_stub"):
            await db.erp_config.update_many({}, {"$set": {"is_active": False}})
            await db.erp_config.update_one({"connection_id": conn_id}, {"$set": {"is_active": True}})

    @router.get("/branding")
    async def branding_active(_=Depends(get_current_user)):
        """Returns the currently active company brand."""
        active = await db.company_brand.find_one({"is_active": True}, {"_id": 0})
        if not active:
            return {"brand": DEFAULT_BRAND}
        return {"brand": active}

    @router.get("/branding/all")
    async def branding_list(_=Depends(require_role("admin"))):
        """List every brand the admin has generated."""
        rows = await db.company_brand.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return {"brands": rows, "default": DEFAULT_BRAND}

    @router.post("/branding/generate")
    async def branding_generate(payload: BrandGenerateIn, user=Depends(require_role("admin"))):
        """Generate a full company brand from just a name via Claude Sonnet."""
        name = (payload.company_name or "").strip()
        if not name:
            raise HTTPException(400, "company_name is required")
        if not emergent_llm_key:
            raise HTTPException(500, "EMERGENT_LLM_KEY not configured")

        system = (
            "You generate company brand profiles + realistic operational sample "
            "data for a Transportation Management System (TMS) so it can be "
            "re-themed for any company. Reply with STRICT JSON ONLY — no prose, "
            "no markdown fences. Use realistic, public data (no proprietary info). "
            "Schema:\n"
            "{\n"
            '  "company_name": "Full legal name",\n'
            '  "short_name": "One-word brand",\n'
            '  "tagline": "8-12 word descriptor",\n'
            '  "industry": "primary industry",\n'
            '  "headquarters": "City, ST",\n'
            '  "primary_color": "#RRGGBB hex (their actual brand color)",\n'
            '  "secondary_color": "#RRGGBB hex (complementary)",\n'
            '  "accent_color": "#RRGGBB hex (success / highlight)",\n'
            '  "logo_letter": "single uppercase letter from their name",\n'
            '  "sample_products": ["6 real flagship products (just names)"],\n'
            '  "sample_suppliers": ["8 plausible Tier-1 suppliers (just names)"],\n'
            '  "sample_lanes": ["6 plausible transportation lanes: City ST -> City ST"],\n'
            '  "catalog_label": "what they call their catalog",\n'
            '  "facilities": [\n'
            '    {"name": "HQ Distribution Center", "city": "City, ST"},\n'
            '    {"name": "Regional DC", "city": "City, ST"},\n'
            '    {"name": "Manufacturing Plant", "city": "City, ST"},\n'
            '    {"name": "Port Inbound", "city": "City, ST"}\n'
            '  ],\n'
            '  "shipments": [\n'
            '    {"reference": "<COMPANY_PREFIX>-12345", "mode": "TL|LTL|Ocean|Air|Rail|Parcel", "carrier": "real carrier name", "status": "in_transit|delayed|delivered|pending|at_origin|at_dest", "origin_city": "City, ST", "destination_city": "City, ST", "commodity": "plausible item being shipped", "progress": 0.0-1.0}\n'
            '  ]\n'
            "}"
        )
        prompt = f"Generate the brand profile for: {name}"
        try:
            chat = LlmChat(
                api_key=emergent_llm_key,
                session_id=f"brand-{uuid.uuid4().hex[:8]}",
                system_message=system,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            reply = await chat.send_message(UserMessage(text=prompt))
        except Exception as e:
            logger.exception("Brand LLM failed")
            raise HTTPException(502, f"AI provider error: {e}")

        raw = (reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
        try:
            profile = json.loads(raw)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                raise HTTPException(502, "AI returned non-JSON brand profile")
            try:
                profile = json.loads(m.group(0))
            except Exception:
                raise HTTPException(502, "AI returned malformed brand profile JSON")

        for f in ("company_name", "short_name", "primary_color"):
            if not profile.get(f):
                raise HTTPException(502, f"AI profile missing '{f}'")
        brand_id = re.sub(r"[^a-z0-9]+", "-", profile["short_name"].lower()).strip("-") or uuid.uuid4().hex[:6]

        doc = {
            "brand_id": brand_id,
            "company_name": profile.get("company_name", name),
            "short_name": profile.get("short_name", name),
            "tagline": profile.get("tagline", ""),
            "industry": profile.get("industry", ""),
            "headquarters": profile.get("headquarters", ""),
            "primary_color": profile.get("primary_color", "#00E5FF"),
            "secondary_color": profile.get("secondary_color", "#06B6D4"),
            "accent_color": profile.get("accent_color", "#10B981"),
            "logo_letter": (profile.get("logo_letter") or profile.get("short_name", name)[:1]).upper()[:1],
            "sample_products": profile.get("sample_products", [])[:8],
            "sample_suppliers": profile.get("sample_suppliers", [])[:8],
            "sample_lanes": profile.get("sample_lanes", [])[:8],
            "catalog_label": profile.get("catalog_label", "Product Catalog"),
            "facilities": profile.get("facilities", [])[:6],
            "shipments": profile.get("shipments", [])[:20],
            "is_default": False,
            "is_active": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.user_id,
            "created_by_name": user.name,
        }
        await db.company_brand.update_one({"brand_id": brand_id}, {"$set": doc}, upsert=True)

        if payload.activate:
            await db.company_brand.update_many({}, {"$set": {"is_active": False}})
            await db.company_brand.update_one({"brand_id": brand_id}, {"$set": {"is_active": True}})
            doc["is_active"] = True
            await _ensure_brand_erp_stub(doc)

        return {"ok": True, "brand": doc}

    @router.post("/branding/manual")
    async def branding_manual(payload: BrandManualIn, user=Depends(require_role("admin"))):
        """Create a brand from manual fields — no AI required."""
        name = (payload.company_name or "").strip()
        if not name:
            raise HTTPException(400, "company_name is required")
        short = (payload.short_name or name.split()[0]).strip()
        brand_id = re.sub(r"[^a-z0-9]+", "-", short.lower()).strip("-") or uuid.uuid4().hex[:6]

        raw_facs = payload.facilities or []
        facilities: List[Dict[str, str]] = []
        for f in raw_facs:
            if isinstance(f, str):
                facilities.append({"name": f, "city": f})
            elif isinstance(f, dict):
                facilities.append({"name": f.get("name") or f.get("city") or "", "city": f.get("city") or ""})

        doc = {
            "brand_id": brand_id,
            "company_name": name,
            "short_name": short,
            "tagline": payload.tagline or "",
            "industry": payload.industry or "",
            "headquarters": payload.headquarters or "",
            "primary_color": payload.primary_color or "#00E5FF",
            "secondary_color": payload.secondary_color or "#06B6D4",
            "accent_color": payload.accent_color or "#10B981",
            "logo_letter": (payload.logo_letter or short[:1] or "B").upper()[:1],
            "sample_products": [p for p in (payload.sample_products or []) if p][:8],
            "sample_suppliers": [s for s in (payload.sample_suppliers or []) if s][:8],
            "sample_lanes": [l for l in (payload.sample_lanes or []) if l][:8],
            "catalog_label": payload.catalog_label or "Product Catalog",
            "facilities": facilities[:6],
            "promo_video_ids": [v.strip() for v in (payload.promo_video_ids or []) if v and v.strip()][:6],
            "shipments": [],
            "is_default": False,
            "is_active": False,
            "is_manual": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user.user_id,
            "created_by_name": user.name,
        }
        await db.company_brand.update_one({"brand_id": brand_id}, {"$set": doc}, upsert=True)

        if payload.activate:
            await db.company_brand.update_many({}, {"$set": {"is_active": False}})
            await db.company_brand.update_one({"brand_id": brand_id}, {"$set": {"is_active": True}})
            doc["is_active"] = True
            await _ensure_brand_erp_stub(doc)

        return {"ok": True, "brand": doc}

    @router.get("/branding/template")
    async def branding_template(_=Depends(require_role("admin"))):
        """Returns a blank/empty brand template the UI pre-fills."""
        return {
            "company_name": "",
            "short_name": "",
            "tagline": "",
            "industry": "",
            "headquarters": "",
            "primary_color": "#00E5FF",
            "secondary_color": "#06B6D4",
            "accent_color": "#10B981",
            "logo_letter": "",
            "catalog_label": "Product Catalog",
            "sample_products": ["", "", "", "", "", ""],
            "sample_suppliers": ["", "", "", "", "", "", "", ""],
            "sample_lanes": ["", "", "", "", "", ""],
            "facilities": [
                {"name": "", "city": ""},
                {"name": "", "city": ""},
                {"name": "", "city": ""},
            ],
            "promo_video_ids": ["", "", ""],
        }

    @router.post("/branding/activate")
    async def branding_activate(payload: BrandActivateIn, _=Depends(require_role("admin"))):
        """Switch the active brand. Pass brand_id='tennant' to restore default."""
        if payload.brand_id == "tennant":
            await db.company_brand.update_many({}, {"$set": {"is_active": False}})
            await _ensure_brand_erp_stub({"brand_id": "tennant", "short_name": "Tennant"})
            return {"ok": True, "brand": DEFAULT_BRAND}
        found = await db.company_brand.find_one({"brand_id": payload.brand_id})
        if not found:
            raise HTTPException(404, "brand_id not found")
        await db.company_brand.update_many({}, {"$set": {"is_active": False}})
        await db.company_brand.update_one({"brand_id": payload.brand_id}, {"$set": {"is_active": True}})
        found.pop("_id", None)
        found["is_active"] = True
        await _ensure_brand_erp_stub(found)
        return {"ok": True, "brand": found}

    @router.delete("/branding/{brand_id}")
    async def branding_delete(brand_id: str, _=Depends(require_role("admin"))):
        """Delete a generated brand. Cannot delete the Tennant default."""
        if brand_id == "tennant":
            raise HTTPException(400, "Cannot delete the built-in default")
        r = await db.company_brand.delete_one({"brand_id": brand_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Brand not found")
        return {"ok": True}

    # Expose the ensure_brand_erp_stub helper so callers (admin dashboard,
    # SAP module) can re-use the same activation side-effect.
    router._ensure_brand_erp_stub = _ensure_brand_erp_stub  # type: ignore[attr-defined]
    return router
