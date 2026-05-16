"""routes.connections — admin-managed third-party connection credentials.

Stores credentials encrypted-at-rest (Fernet, symmetric). Each provider has a
strict field schema declared in `PROVIDERS`. Credentials are NEVER returned
to the client in plaintext — only a masked preview is exposed.

Designed so that future integrations (QuickBooks, DAT, Truckstop, Uber Freight,
123 Loadboard, Stripe, Resend, Twilio) can be wired without an .env edit:
admins paste credentials in the UI → encrypted blob lands in Mongo → wiring
code retrieves & decrypts on demand.
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


logger = logging.getLogger("tennant_tms.connections")


# ---------------- Provider catalog ----------------
# Each entry declares the human-readable name + required credential fields.
# `secret=True` fields are masked everywhere except during their original
# submission. Adding a provider here is the ONLY change needed to surface
# it in the admin Connections page.
PROVIDERS: List[Dict[str, Any]] = [
    {
        "id": "quickbooks",
        "name": "QuickBooks Online",
        "category": "Accounting",
        "description": "Sync invoices, expenses, and P&L from the Brokerage Command Deck.",
        "logo": "QB",
        "docs_url": "https://developer.intuit.com/app/developer/qbo/docs/get-started",
        "fields": [
            {"key": "client_id",     "label": "Client ID",     "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "secret": True,  "required": True},
            {"key": "environment",   "label": "Environment",   "secret": False, "required": True, "options": ["sandbox", "production"], "default": "sandbox"},
            {"key": "redirect_uri",  "label": "Redirect URI",  "secret": False, "required": True, "placeholder": "https://<host>/api/brokerage/quickbooks/callback"},
        ],
    },
    {
        "id": "dat",
        "name": "DAT One",
        "category": "Load Board",
        "description": "Premium loadboard postings, lane analytics, and credit scores.",
        "logo": "DAT",
        "docs_url": "https://www.dat.com/api",
        "fields": [
            {"key": "api_key",    "label": "API Key",  "secret": True, "required": True},
            {"key": "username",   "label": "Username", "secret": False, "required": True},
            {"key": "password",   "label": "Password", "secret": True,  "required": True},
            {"key": "service_id", "label": "Service Account ID", "secret": False, "required": False},
        ],
    },
    {
        "id": "truckstop",
        "name": "Truckstop",
        "category": "Load Board",
        "description": "Truckstop Premium loads, BookIt Now, and credit checks.",
        "logo": "TS",
        "docs_url": "https://developer.truckstop.com/",
        "fields": [
            {"key": "client_id",     "label": "Client ID",     "secret": False, "required": True},
            {"key": "client_secret", "label": "Client Secret", "secret": True,  "required": True},
            {"key": "integration_id","label": "Integration ID","secret": False, "required": True},
        ],
    },
    {
        "id": "uber_freight",
        "name": "Uber Freight",
        "category": "Load Board",
        "description": "Shipper API for digital tendering and tracking.",
        "logo": "UF",
        "docs_url": "https://www.uberfreight.com/api/",
        "fields": [
            {"key": "api_key",     "label": "API Key",     "secret": True, "required": True},
            {"key": "shipper_id",  "label": "Shipper ID",  "secret": False, "required": True},
        ],
    },
    {
        "id": "loadboard_123",
        "name": "123Loadboard",
        "category": "Load Board",
        "description": "Public REST API for spot freight postings and bid management.",
        "logo": "123",
        "docs_url": "https://www.123loadboard.com/api",
        "fields": [
            {"key": "api_key",    "label": "API Key", "secret": True, "required": True},
            {"key": "subscriber", "label": "Subscriber Email", "secret": False, "required": True},
        ],
    },
    {
        "id": "stripe",
        "name": "Stripe",
        "category": "Payments",
        "description": "Customer invoices, ACH, and card processing.",
        "logo": "S",
        "docs_url": "https://stripe.com/docs/keys",
        "fields": [
            {"key": "publishable_key", "label": "Publishable Key", "secret": False, "required": True},
            {"key": "secret_key",      "label": "Secret Key",      "secret": True,  "required": True},
            {"key": "webhook_secret",  "label": "Webhook Secret",  "secret": True,  "required": False},
        ],
    },
    {
        "id": "resend",
        "name": "Resend",
        "category": "Email",
        "description": "Transactional email for invoices, rate confirmations, and BOLs.",
        "logo": "R",
        "docs_url": "https://resend.com/docs",
        "fields": [
            {"key": "api_key",   "label": "API Key",   "secret": True,  "required": True},
            {"key": "from_email","label": "From Email","secret": False, "required": True, "placeholder": "ops@orisei.com"},
        ],
    },
    {
        "id": "twilio",
        "name": "Twilio SMS",
        "category": "Messaging",
        "description": "Driver check-in SMS, dispatch alerts, and 2FA codes.",
        "logo": "TW",
        "docs_url": "https://www.twilio.com/docs",
        "fields": [
            {"key": "account_sid",        "label": "Account SID",       "secret": False, "required": True},
            {"key": "auth_token",         "label": "Auth Token",        "secret": True,  "required": True},
            {"key": "from_number",        "label": "From Number",       "secret": False, "required": True, "placeholder": "+16125550117"},
            {"key": "monthly_sms_volume", "label": "Tuner · Est. monthly SMS volume", "secret": False, "required": False, "placeholder": "5000", "tuner": True, "hint": "Used to forecast monthly SMS spend on the Cost tab"},
        ],
    },
    {
        "id": "macropoint",
        "name": "Macropoint / Project44",
        "category": "Tracking",
        "description": "ELD + telematics aggregation for in-transit visibility.",
        "logo": "MP",
        "docs_url": "https://www.project44.com/",
        "fields": [
            {"key": "api_key",   "label": "API Key",   "secret": True, "required": True},
            {"key": "tenant_id", "label": "Tenant ID", "secret": False, "required": True},
        ],
    },
    {
        "id": "rmis",
        "name": "RMIS",
        "category": "Carrier Vetting",
        "description": "Carrier onboarding, insurance verification, COI repository.",
        "logo": "RM",
        "docs_url": "https://www.rmis.com/",
        "fields": [
            {"key": "api_key",    "label": "API Key",    "secret": True, "required": True},
            {"key": "broker_id",  "label": "Broker ID",  "secret": False, "required": True},
        ],
    },
    {
        "id": "apex_capital",
        "name": "Apex Capital",
        "category": "Factoring",
        "description": "Carrier-side factor. Verify factored carriers + send NOA-compliant payments.",
        "logo": "APX",
        "docs_url": "https://www.apexcapitalcorp.com/",
        "fields": [
            {"key": "api_key",            "label": "API Key",         "secret": True, "required": True},
            {"key": "broker_id",          "label": "Broker MC#",      "secret": False, "required": True},
            {"key": "ach_routing",        "label": "ACH Routing #",   "secret": True, "required": False},
            {"key": "ach_account",        "label": "ACH Account #",   "secret": True, "required": False},
            {"key": "factor_rate",        "label": "Negotiated Rate %", "secret": False, "required": False, "placeholder": "2.5"},
            {"key": "quick_pay_usage_pct", "label": "Tuner · % carriers using quick-pay", "secret": False, "required": False, "placeholder": "25", "tuner": True, "hint": "Calibrates MTD spend forecast on the Cost tab"},
        ],
    },
    {
        "id": "triumph",
        "name": "TriumphPay · Triumph Business Capital",
        "category": "Factoring",
        "description": "Carrier payments network + factoring. Quick-pay rails + carrier-of-record lookup.",
        "logo": "TPY",
        "docs_url": "https://triumphpay.com/developers",
        "fields": [
            {"key": "client_id",          "label": "Client ID",       "secret": False, "required": True},
            {"key": "client_secret",      "label": "Client Secret",   "secret": True,  "required": True},
            {"key": "environment",        "label": "Environment",     "secret": False, "required": True, "options": ["sandbox", "production"], "default": "sandbox"},
            {"key": "broker_mc",          "label": "Broker MC#",      "secret": False, "required": True},
            {"key": "factor_rate",        "label": "Negotiated Rate %", "secret": False, "required": False, "placeholder": "2.0"},
            {"key": "quick_pay_usage_pct", "label": "Tuner · % carriers using quick-pay", "secret": False, "required": False, "placeholder": "25", "tuner": True, "hint": "Calibrates MTD spend forecast on the Cost tab"},
        ],
    },
    {
        "id": "otr_capital",
        "name": "OTR Capital",
        "category": "Factoring",
        "description": "Carrier factoring + broker quick-pay financing line.",
        "logo": "OTR",
        "docs_url": "https://otrcapital.com/",
        "fields": [
            {"key": "api_key",            "label": "API Key",          "secret": True,  "required": True},
            {"key": "account_id",         "label": "Account ID",       "secret": False, "required": True},
            {"key": "factor_rate",        "label": "Negotiated Rate %","secret": False, "required": False, "placeholder": "2.5"},
            {"key": "quick_pay_usage_pct", "label": "Tuner · % carriers using quick-pay", "secret": False, "required": False, "placeholder": "25", "tuner": True, "hint": "Calibrates MTD spend forecast on the Cost tab"},
        ],
    },
    {
        "id": "rts_financial",
        "name": "RTS Financial",
        "category": "Factoring",
        "description": "Carrier factoring + fuel-card program. NOA verification API.",
        "logo": "RTS",
        "docs_url": "https://www.rtsinc.com/",
        "fields": [
            {"key": "api_key",            "label": "API Key",      "secret": True, "required": True},
            {"key": "broker_id",          "label": "Broker ID",    "secret": False, "required": True},
            {"key": "factor_rate",        "label": "Negotiated Rate %", "secret": False, "required": False, "placeholder": "2.5"},
            {"key": "quick_pay_usage_pct", "label": "Tuner · % carriers using quick-pay", "secret": False, "required": False, "placeholder": "25", "tuner": True, "hint": "Calibrates MTD spend forecast on the Cost tab"},
        ],
    },
]


PROVIDERS_INDEX: Dict[str, Dict[str, Any]] = {p["id"]: p for p in PROVIDERS}


# ---------------- Encryption helpers ----------------
def _load_or_create_fernet() -> Fernet:
    """Return a Fernet using `CONNECTIONS_ENCRYPTION_KEY`.

    If the env var is missing, generate a key, persist it to backend/.env,
    and use it from now on. This keeps the dev environment turnkey without
    forcing a manual key-gen step.
    """
    key = os.environ.get("CONNECTIONS_ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode("utf-8")
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        try:
            with open(env_path, "a", encoding="utf-8") as f:
                f.write(f"\nCONNECTIONS_ENCRYPTION_KEY={key}\n")
            os.environ["CONNECTIONS_ENCRYPTION_KEY"] = key
            logger.warning("Generated new CONNECTIONS_ENCRYPTION_KEY (persisted to backend/.env)")
        except OSError:
            logger.exception("Failed to persist CONNECTIONS_ENCRYPTION_KEY — running with in-memory key only")
            os.environ["CONNECTIONS_ENCRYPTION_KEY"] = key
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except (ValueError, TypeError):
        # Bad key shape — regenerate inline so the app keeps running.
        new_key = Fernet.generate_key()
        os.environ["CONNECTIONS_ENCRYPTION_KEY"] = new_key.decode("utf-8")
        logger.error("CONNECTIONS_ENCRYPTION_KEY was malformed; regenerated in-memory")
        return Fernet(new_key)


_FERNET = _load_or_create_fernet()


def _encrypt(plaintext: str) -> str:
    return _FERNET.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def _decrypt(token: str) -> str:
    try:
        return _FERNET.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("Failed to decrypt a connection credential — returning empty string")
        return ""


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "•" * len(value)
    return f"{value[:3]}{'•' * (len(value) - 6)}{value[-3:]}"


# ---------------- Pydantic models ----------------
class ConnectionUpsertIn(BaseModel):
    fields: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    notes: Optional[str] = None


class CustomFieldDef(BaseModel):
    key: str = Field(..., min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$")
    label: str = Field(..., min_length=1, max_length=60)
    secret: bool = False
    required: bool = True
    placeholder: Optional[str] = None


class CustomProviderIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=80)
    category: str = Field(..., min_length=1, max_length=40)
    description: Optional[str] = Field("", max_length=400)
    logo: Optional[str] = Field("•", max_length=4)
    docs_url: Optional[str] = Field(None, max_length=300)
    fields: List[CustomFieldDef] = Field(..., min_length=1, max_length=20)


# ---------------- Router factory ----------------
def build_connections_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/connections")
    admin_only = require_role("admin")

    # --- internal helpers bound to this DB handle ---
    async def _all_providers() -> List[Dict[str, Any]]:
        """Merge static catalog + admin-defined custom providers from Mongo."""
        out = [dict(p, builtin=True) for p in PROVIDERS]
        cursor = db.connection_providers_custom.find({}, {"_id": 0})
        async for doc in cursor:
            out.append({**doc, "builtin": False})
        return out

    async def _get_provider(provider_id: str) -> Optional[Dict[str, Any]]:
        if provider_id in PROVIDERS_INDEX:
            return {**PROVIDERS_INDEX[provider_id], "builtin": True}
        custom = await db.connection_providers_custom.find_one({"id": provider_id}, {"_id": 0})
        if custom:
            return {**custom, "builtin": False}
        return None

    async def _serialize_async(doc: Dict[str, Any]) -> Dict[str, Any]:
        prov = await _get_provider(doc["provider_id"]) or {}
        field_defs = {f["key"]: f for f in prov.get("fields", [])}
        clear = _decrypt_fields(doc.get("fields", {}))
        safe: Dict[str, Any] = {}
        for k, plain in clear.items():
            fdef = field_defs.get(k, {})
            if fdef.get("secret"):
                safe[k] = {"set": bool(plain), "preview": _mask(plain) if plain else ""}
            else:
                safe[k] = {"set": bool(plain), "value": plain}
        return {
            "provider_id": doc["provider_id"],
            "status": doc.get("status", "configured"),
            "enabled": bool(doc.get("enabled", True)),
            "fields": safe,
            "updated_at": doc.get("updated_at"),
            "updated_by": doc.get("updated_by"),
            "updated_by_name": doc.get("updated_by_name"),
            "notes": doc.get("notes"),
        }

    # ===================================================================
    #                  PROVIDER CATALOG (built-in + custom)
    # ===================================================================
    @router.get("/providers")
    async def list_providers(_=Depends(admin_only)):
        """Return the merged provider catalog (built-in + admin-defined custom)."""
        return {"providers": await _all_providers()}

    @router.post("/providers/custom")
    async def add_custom_provider(payload: CustomProviderIn, user=Depends(admin_only)):
        """Add a brand-new integration provider on the fly (no code change)."""
        if payload.id in PROVIDERS_INDEX:
            raise HTTPException(400, f"'{payload.id}' clashes with a built-in provider id")
        if await db.connection_providers_custom.find_one({"id": payload.id}, {"_id": 0}):
            raise HTTPException(400, f"Custom provider '{payload.id}' already exists")
        keys = [f.key for f in payload.fields]
        if len(set(keys)) != len(keys):
            raise HTTPException(400, "Duplicate field keys")
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": payload.id,
            "name": payload.name,
            "category": payload.category,
            "description": payload.description or "",
            "logo": (payload.logo or payload.name[:2]).upper(),
            "docs_url": payload.docs_url,
            "fields": [f.model_dump() for f in payload.fields],
            "created_at": now,
            "created_by": getattr(user, "user_id", None),
            "created_by_name": getattr(user, "name", None),
        }
        await db.connection_providers_custom.insert_one(dict(doc))
        return {**doc, "builtin": False}

    @router.delete("/providers/custom/{provider_id}")
    async def delete_custom_provider(provider_id: str, _=Depends(admin_only)):
        if provider_id in PROVIDERS_INDEX:
            raise HTTPException(400, "Built-in providers cannot be deleted")
        if not await db.connection_providers_custom.find_one({"id": provider_id}, {"_id": 0}):
            raise HTTPException(404, "Unknown custom provider")
        # Also delete the saved credentials for it
        await db.connections.delete_one({"provider_id": provider_id})
        await db.connection_providers_custom.delete_one({"id": provider_id})
        return {"deleted": True, "provider_id": provider_id}

    # ===================================================================
    #                  CONNECTION ROWS (credentials)
    # ===================================================================
    @router.get("")
    async def list_connections(_=Depends(admin_only)):
        providers = await _all_providers()
        out: List[Dict[str, Any]] = []
        cursor = db.connections.find({}, {"_id": 0})
        async for doc in cursor:
            out.append(await _serialize_async(doc))
        configured_ids = {c["provider_id"] for c in out}
        for prov in providers:
            if prov["id"] not in configured_ids:
                out.append({
                    "provider_id": prov["id"],
                    "status": "unconfigured",
                    "enabled": False,
                    "fields": {f["key"]: {"set": False, "value": ""} for f in prov["fields"]},
                    "updated_at": None,
                    "updated_by": None,
                    "notes": None,
                })
        out.sort(key=lambda x: x["provider_id"])
        return {"connections": out, "providers": providers}

    @router.get("/{provider_id}")
    async def get_connection(provider_id: str, _=Depends(admin_only)):
        prov = await _get_provider(provider_id)
        if not prov:
            raise HTTPException(404, "Unknown provider")
        doc = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        if not doc:
            return {
                "provider_id": provider_id,
                "status": "unconfigured",
                "enabled": False,
                "fields": {f["key"]: {"set": False, "value": ""} for f in prov["fields"]},
                "updated_at": None,
                "updated_by": None,
                "notes": None,
            }
        return await _serialize_async(doc)

    @router.put("/{provider_id}")
    async def upsert_connection(provider_id: str, payload: ConnectionUpsertIn, user=Depends(admin_only)):
        prov = await _get_provider(provider_id)
        if not prov:
            raise HTTPException(404, "Unknown provider")

        existing = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0}) or {}
        existing_stored: Dict[str, Any] = existing.get("fields", {}) or {}

        stored_fields: Dict[str, Dict[str, Any]] = {}
        for fdef in prov["fields"]:
            key = fdef["key"]
            new_val = payload.fields.get(key)
            if fdef.get("secret"):
                if new_val is None or new_val == "":
                    prev = existing_stored.get(key) or {}
                    cipher = prev.get("cipher") if isinstance(prev, dict) else ""
                    if fdef.get("required") and not cipher:
                        raise HTTPException(400, f"Field '{fdef['label']}' is required")
                    stored_fields[key] = {"secret": True, "cipher": cipher or ""}
                else:
                    stored_fields[key] = {"secret": True, "cipher": _encrypt(str(new_val))}
            else:
                text = "" if new_val is None else str(new_val)
                if fdef.get("required") and not text:
                    raise HTTPException(400, f"Field '{fdef['label']}' is required")
                stored_fields[key] = {"secret": False, "value": text}

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "provider_id": provider_id,
            "status": "configured" if payload.enabled else "disabled",
            "enabled": bool(payload.enabled),
            "fields": stored_fields,
            "updated_at": now,
            "updated_by": getattr(user, "user_id", None),
            "updated_by_name": getattr(user, "name", None),
            "notes": payload.notes,
        }
        await db.connections.update_one(
            {"provider_id": provider_id},
            {"$set": record, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        await db.connection_audit_log.insert_one({
            "provider_id": provider_id,
            "action": "upsert",
            "actor_id": getattr(user, "user_id", None),
            "actor_name": getattr(user, "name", None),
            "at": now,
            "status": record["status"],
            "field_keys": list(stored_fields.keys()),
        })
        saved = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        return await _serialize_async(saved)

    @router.delete("/{provider_id}")
    async def delete_connection(provider_id: str, user=Depends(admin_only)):
        prov = await _get_provider(provider_id)
        if not prov:
            raise HTTPException(404, "Unknown provider")
        await db.connections.delete_one({"provider_id": provider_id})
        await db.connection_audit_log.insert_one({
            "provider_id": provider_id,
            "action": "delete",
            "actor_id": getattr(user, "user_id", None),
            "actor_name": getattr(user, "name", None),
            "at": datetime.now(timezone.utc).isoformat(),
        })
        return {"deleted": True, "provider_id": provider_id}

    @router.post("/{provider_id}/test")
    async def test_connection(provider_id: str, _=Depends(admin_only)):
        prov = await _get_provider(provider_id)
        if not prov:
            raise HTTPException(404, "Unknown provider")
        doc = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        if not doc or not doc.get("enabled"):
            return {"ok": False, "message": "Not configured or disabled."}
        fields_clear = _decrypt_fields(doc.get("fields", {}))
        missing = [
            f["label"] for f in prov["fields"]
            if f.get("required") and not fields_clear.get(f["key"])
        ]
        if missing:
            return {"ok": False, "message": f"Missing required fields: {', '.join(missing)}"}
        return {
            "ok": True,
            "message": f"Credentials decrypt cleanly. (Live ping for {prov['name']} not yet implemented.)",
            "provider_id": provider_id,
        }

    return router


# ---------------- Internal helpers ----------------
def _decrypt_fields(stored: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    """Return {key: plaintext} for all fields (secrets decrypted)."""
    out: Dict[str, str] = {}
    for k, v in (stored or {}).items():
        if not isinstance(v, dict):
            out[k] = str(v) if v is not None else ""
            continue
        if v.get("secret"):
            cipher = v.get("cipher") or ""
            out[k] = _decrypt(cipher) if cipher else ""
        else:
            out[k] = str(v.get("value") or "")
    return out


def _serialize_connection(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a client-safe view of a connection record. Secrets are masked."""
    prov = PROVIDERS_INDEX.get(doc["provider_id"], {})
    clear = _decrypt_fields(doc.get("fields", {}))
    safe_fields: Dict[str, Any] = {}
    field_defs = {f["key"]: f for f in prov.get("fields", [])}
    for k, plain in clear.items():
        fdef = field_defs.get(k, {})
        if fdef.get("secret"):
            safe_fields[k] = {"set": bool(plain), "preview": _mask(plain) if plain else ""}
        else:
            safe_fields[k] = {"set": bool(plain), "value": plain}
    return {
        "provider_id": doc["provider_id"],
        "status": doc.get("status", "configured"),
        "enabled": bool(doc.get("enabled", True)),
        "fields": safe_fields,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
        "updated_by_name": doc.get("updated_by_name"),
        "notes": doc.get("notes"),
    }


# ---------------- Public helper for other route modules ----------------
async def get_connection_credentials(db, provider_id: str) -> Optional[Dict[str, str]]:
    """Public helper — other modules can call this to pull live credentials.

    Returns plaintext field map if the connection exists AND is enabled.
    Returns None otherwise. NEVER expose the dict to the network.
    """
    doc = await db.connections.find_one(
        {"provider_id": provider_id, "enabled": True},
        {"_id": 0},
    )
    if not doc:
        return None
    return _decrypt_fields(doc.get("fields", {}))
