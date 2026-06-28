"""routes.sap — SAP S/4HANA OData mock connector.

Endpoints (all GET unless noted; all auth-required):
  GET  /sap/config           — current SAP system header
  GET  /sap/sales-orders     — branded sales-order list
  GET  /sap/purchase-orders  — branded purchase-order list
  POST /sap/sync             — kick off a mock sync, persist log
  GET  /sap/sync-logs        — recent sync history
"""

from __future__ import annotations

import random
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends


SAP_MOCK_CONFIG = {
    "system_id": "S4P",
    "host": "https://s4hana.tennantco.sap.com",
    "service": "/sap/opu/odata/sap/API_SALES_ORDER_SRV",
    "client": "100",
    "user": "TMS_SVC_ACCT",
    "auth_type": "OAuth 2.0 (SAML Bearer Assertion)",
}


def _gen_sap_sales_orders(n: int = 24) -> List[Dict[str, Any]]:
    """Deterministic-ish sales order data."""
    random.seed(42)
    customers = [
        ("CUST-100214", "Walmart Distribution — Bentonville"),
        ("CUST-100755", "Amazon Fulfillment — Phoenix"),
        ("CUST-100928", "FedEx Freight HQ — Memphis"),
        ("CUST-101044", "U.S. Postal Service — Washington DC"),
        ("CUST-101188", "Target Distribution — Minneapolis"),
        ("CUST-101332", "Costco Wholesale — Issaquah"),
        ("CUST-101501", "Boeing Everett Plant"),
        ("CUST-101677", "Ford F-150 Plant — Dearborn"),
    ]
    materials = [
        ("MAT-T16AMR", "T16 AMR Ride-On Scrubber", 38500.00),
        ("MAT-M30", "M30 Integrated Sweeper-Scrubber", 52000.00),
        ("MAT-S30", "S30 Industrial Sweeper", 41200.00),
        ("MAT-T7AMR", "T7 AMR Compact Robotic", 28900.00),
        ("MAT-M17", "M17 Mid-Size Sweeper-Scrubber", 33400.00),
        ("MAT-PARTS-BAT", "Lithium-Ion Battery Pack (Service Part)", 2150.00),
    ]
    plants = [("1010", "Golden Valley, MN"), ("1020", "Holland, MI"), ("1030", "Louisville, KY")]
    statuses = ["Open", "Open", "In Production", "Released to Shipping", "Confirmed", "Partial Delivery"]
    out = []
    for i in range(n):
        c = random.choice(customers)
        m = random.choice(materials)
        p = random.choice(plants)
        qty = random.randint(1, 6)
        net = round(m[2] * qty, 2)
        order_date = (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 45))).date().isoformat()
        req_date = (datetime.now(timezone.utc) + timedelta(days=random.randint(7, 60))).date().isoformat()
        out.append({
            "SalesOrder": f"SO-{500000 + i}",
            "SalesOrderType": "OR",
            "SoldToParty": c[0],
            "SoldToPartyName": c[1],
            "PurchaseOrderByCustomer": f"PO-{random.randint(70000, 99999)}",
            "Material": m[0],
            "MaterialDescription": m[1],
            "RequestedQuantity": qty,
            "NetAmount": net,
            "Currency": "USD",
            "Plant": p[0],
            "PlantName": p[1],
            "RequestedDeliveryDate": req_date,
            "CreationDate": order_date,
            "OverallStatus": random.choice(statuses),
            "IncoTerms": random.choice(["FCA", "DAP", "DDP", "EXW"]),
        })
    return out


def _gen_sap_purchase_orders(n: int = 16) -> List[Dict[str, Any]]:
    random.seed(7)
    vendors = [
        ("VEND-KNS", "Kuehne+Nagel Services (Import Logistics)"),
        ("VEND-MOTREX", "Motrex Co. Ltd — Drive Motors (KR)"),
        ("VEND-BATTCO", "BattCo Industries — Battery Cells (DE)"),
        ("VEND-PLASTIC", "Premier Polymers — Tank Bodies (US)"),
        ("VEND-STEEL", "Midwest Steel Frame Co (US)"),
        ("VEND-WIRING", "Yazaki Wiring Harness (JP)"),
    ]
    components = [
        ("CMP-DCMOT-750W", "DC Drive Motor 750W"),
        ("CMP-BATT-LI24V", "Li-ion Battery Module 24V 100Ah"),
        ("CMP-TANK-50G", "Solution Tank 50 Gallon — Molded"),
        ("CMP-FRAME-T16", "Chassis Frame Assy T16AMR"),
        ("CMP-HARNESS-S30", "Wiring Harness S30 Master Assy"),
        ("CMP-BRUSH-32", "Cylindrical Brush 32-inch"),
    ]
    plants = [("1010", "Golden Valley, MN"), ("1020", "Holland, MI"), ("1030", "Louisville, KY")]
    statuses = ["Open", "Released", "Goods Issued", "In Transit", "Partial GR", "Closed"]
    out = []
    for i in range(n):
        v = random.choice(vendors)
        c = random.choice(components)
        p = random.choice(plants)
        qty = random.randint(40, 800)
        unit_price = round(random.uniform(38, 1450), 2)
        net = round(unit_price * qty, 2)
        out.append({
            "PurchaseOrder": f"PO-{4500000 + i}",
            "Supplier": v[0],
            "SupplierName": v[1],
            "Material": c[0],
            "MaterialDescription": c[1],
            "OrderQuantity": qty,
            "NetPriceAmount": unit_price,
            "NetAmount": net,
            "Currency": "USD",
            "Plant": p[0],
            "PlantName": p[1],
            "CreationDate": (datetime.now(timezone.utc) - timedelta(days=random.randint(2, 30))).date().isoformat(),
            "DeliveryDate": (datetime.now(timezone.utc) + timedelta(days=random.randint(5, 45))).date().isoformat(),
            "OverallStatus": random.choice(statuses),
            "IncoTerms": random.choice(["FCA", "DAP", "DDP"]),
            "IsImport": v[0] == "VEND-KNS" or "(KR)" in v[1] or "(DE)" in v[1] or "(JP)" in v[1],
        })
    return out


def build_sap_router(
    *,
    db,
    get_current_user: Callable,
    require_role: Callable,
    brand_swap: Callable,
    active_brand_doc: Callable,
) -> APIRouter:
    router = APIRouter()

    async def _brand_sap_config() -> Dict[str, Any]:
        cfg = dict(SAP_MOCK_CONFIG)
        brand = await active_brand_doc()
        if brand and brand.get("brand_id") != "orisei-freight":
            short = brand.get("short_name") or "Brand"
            slug = re.sub(r"[^a-z0-9]+", "", short.lower())[:20] or "brand"
            prefix = re.sub(r"[^A-Z0-9]+", "", short.upper())[:6] or "BRND"
            cfg["host"] = f"https://s4hana.{slug}.sap.com"
            cfg["user"] = f"{prefix}_TMS_SVC"
        return cfg

    async def _overlay_sap_records(rows: List[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
        brand = await active_brand_doc()
        if not brand or brand.get("brand_id") == "orisei-freight":
            return rows
        products = brand.get("sample_products") or []
        suppliers = brand.get("sample_suppliers") or []
        short = brand.get("short_name") or "Brand"
        prefix = re.sub(r"[^A-Z0-9]+", "", short.upper())[:4] or "BRND"
        facilities = brand.get("facilities") or []
        out = []
        for i, r in enumerate(rows):
            d = dict(r)
            if products:
                desc = products[i % len(products)]
                slug = re.sub(r"[^A-Z0-9]+", "", desc.upper())[:6] or f"P{i:03d}"
                d["Material"] = f"{prefix}-{slug}"
                d["MaterialDescription"] = desc
            if kind == "purchase" and suppliers:
                sup_name = suppliers[i % len(suppliers)]
                sup_code = "VEND-" + re.sub(r"[^A-Z0-9]+", "", sup_name.upper())[:6]
                d["Supplier"] = sup_code
                d["SupplierName"] = sup_name
            if facilities:
                f = facilities[i % len(facilities)]
                fname = f.get("name") or f.get("city") or short
                d["PlantName"] = fname
            out.append(d)
        return out

    @router.get("/sap/config")
    async def sap_config(_=Depends(get_current_user)):
        cfg = await _brand_sap_config()
        return await brand_swap(cfg)

    @router.get("/sap/sales-orders")
    async def sap_sales_orders(_=Depends(get_current_user),
                               plant: Optional[str] = None,
                               status: Optional[str] = None):
        orders = _gen_sap_sales_orders()
        if plant: orders = [o for o in orders if o["Plant"] == plant]
        if status: orders = [o for o in orders if o["OverallStatus"] == status]
        orders = await _overlay_sap_records(orders, "sales")
        cfg = await _brand_sap_config()
        return await brand_swap({
            "value": orders,
            "@odata.count": len(orders),
            "source": cfg["host"] + cfg["service"],
        })

    @router.get("/sap/purchase-orders")
    async def sap_purchase_orders(_=Depends(get_current_user),
                                  plant: Optional[str] = None,
                                  only_imports: bool = False):
        orders = _gen_sap_purchase_orders()
        if plant: orders = [o for o in orders if o["Plant"] == plant]
        if only_imports: orders = [o for o in orders if o["IsImport"]]
        orders = await _overlay_sap_records(orders, "purchase")
        cfg = await _brand_sap_config()
        return await brand_swap({
            "value": orders,
            "@odata.count": len(orders),
            "source": cfg["host"] + "/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV",
        })

    @router.post("/sap/sync")
    async def sap_sync(_=Depends(require_role("admin", "dispatcher"))):
        """Trigger a mock OData sync and persist a log row."""
        sales = _gen_sap_sales_orders()
        purch = _gen_sap_purchase_orders()
        log = {
            "log_id": f"SYNC-{uuid.uuid4().hex[:8].upper()}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "sales_count": len(sales),
            "purchase_count": len(purch),
            "duration_ms": random.randint(820, 1850),
            "status": "success",
        }
        await db.sap_sync_logs.insert_one(dict(log))
        return await brand_swap(log)

    @router.get("/sap/sync-logs")
    async def sap_sync_logs(_=Depends(get_current_user)):
        docs = await db.sap_sync_logs.find({}, {"_id": 0}).sort("started_at", -1).limit(30).to_list(30)
        return await brand_swap(docs)

    return router
