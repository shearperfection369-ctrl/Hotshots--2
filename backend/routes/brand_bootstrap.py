"""
Bootstrap the active company brand row.

Every PDF generator pulls the active brand from db.company_brand via
_get_active_brand() — if the collection is empty, PDFs fall back to
hard-coded defaults and lose the correct logo / color / contact info.

Run on every backend startup (idempotent — only inserts if missing).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

log = logging.getLogger("orisei.brand_bootstrap")

ORISEI_BRAND: Dict[str, Any] = {
    "brand_id":          "orisei-freight",
    "name":              "Orisei Freight Solutions",
    "company_name":      "Orisei Freight Solutions LLC",
    "short_name":        "ORISEI",
    "logo_letter":       "O",
    "primary_color":     "#0E3A6B",   # navy
    "accent_color":      "#C9A24A",   # gold
    "secondary_color":   "#E5E7EB",
    "founder_name":      "Oliver Cummins",
    "founder_title":     "Founder",
    "contact_email":     "oliver@oriseifreightsolutions.com",
    "contact_emails": {
        "sales":     "oliver@oriseifreightsolutions.com",
        "ops":       "oliver@oriseifreightsolutions.com",
        "billing":   "oliver@oriseifreightsolutions.com",
        "carrier":   "oliver@oriseifreightsolutions.com",
        "general":   "oliver@oriseifreightsolutions.com",
    },
    "phone":             "(763) 443-4459",
    "hq_city":           "Minneapolis, MN",
    "headquarters":      "Minneapolis · Saint Paul, MN",
    "website":           "oriseifreight.com",
    "site_url":          "https://oriseifreight.com",
    "tagline":           "The spirit of Califia, the power of modern freight.",
    "mc_number":         None,       # filed but pending — show "pending" on docs
    "bond_amount_usd":   75_000,
    "cargo_insurance_usd":   100_000,
    "auto_insurance_usd": 1_000_000,
    "gl_insurance_usd":   1_000_000,
    "logo_local_path":     "/app/frontend/public/brand/orisei_logo.png",
    "wordmark_local_path": "/app/frontend/public/brand/orisei_wordmark.png",
    "logo_pdf_path":       "/app/backend/routes/_orisei_logo_pdf.png",
    "wordmark_pdf_path":   "/app/backend/routes/_orisei_wordmark_pdf.png",
    "is_active":           True,
    "is_sample":           False,
}


async def ensure_active_brand(db) -> None:
    """Insert ORISEI_BRAND if no active brand row exists, else update missing
    fields without overwriting any user-customised values."""
    existing = await db.company_brand.find_one({"is_active": True})
    if not existing:
        await db.company_brand.update_one(
            {"brand_id": ORISEI_BRAND["brand_id"]},
            {"$set": ORISEI_BRAND}, upsert=True,
        )
        log.info("Seeded active Orisei brand row in db.company_brand")
        return
    # Patch in any new fields that didn't exist before, but never overwrite
    missing = {k: v for k, v in ORISEI_BRAND.items()
                if k not in existing or existing.get(k) in (None, "")}
    if missing:
        await db.company_brand.update_one(
            {"_id": existing["_id"]}, {"$set": missing})
        log.info("Patched %d missing brand fields onto existing active brand",
                  len(missing))
