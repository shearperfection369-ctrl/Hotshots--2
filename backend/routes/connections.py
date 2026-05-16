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
            {"key": "account_sid", "label": "Account SID", "secret": False, "required": True},
            {"key": "auth_token",  "label": "Auth Token",  "secret": True,  "required": True},
            {"key": "from_number", "label": "From Number", "secret": False, "required": True, "placeholder": "+16125550117"},
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


# ---------------- Router factory ----------------
def build_connections_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/connections")
    admin_only = require_role("admin")

    # ----- catalog (read for any admin) -----
    @router.get("/providers")
    async def list_providers(_=Depends(admin_only)):
        """Return the static provider catalog (id, name, category, fields)."""
        return {"providers": PROVIDERS}

    # ----- list all configured connections -----
    @router.get("")
    async def list_connections(_=Depends(admin_only)):
        out: List[Dict[str, Any]] = []
        cursor = db.connections.find({}, {"_id": 0})
        async for doc in cursor:
            out.append(_serialize_connection(doc))
        # Surface providers that have no doc yet as "unconfigured" rows.
        configured_ids = {c["provider_id"] for c in out}
        for prov in PROVIDERS:
            if prov["id"] not in configured_ids:
                out.append({
                    "provider_id": prov["id"],
                    "status": "unconfigured",
                    "enabled": False,
                    "fields": {f["key"]: "" for f in prov["fields"]},
                    "updated_at": None,
                    "updated_by": None,
                    "notes": None,
                })
        out.sort(key=lambda x: x["provider_id"])
        return {"connections": out, "providers": PROVIDERS}

    # ----- read one -----
    @router.get("/{provider_id}")
    async def get_connection(provider_id: str, _=Depends(admin_only)):
        if provider_id not in PROVIDERS_INDEX:
            raise HTTPException(404, "Unknown provider")
        doc = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        if not doc:
            prov = PROVIDERS_INDEX[provider_id]
            return {
                "provider_id": provider_id,
                "status": "unconfigured",
                "enabled": False,
                "fields": {f["key"]: "" for f in prov["fields"]},
                "updated_at": None,
                "updated_by": None,
                "notes": None,
            }
        return _serialize_connection(doc)

    # ----- upsert credentials -----
    @router.put("/{provider_id}")
    async def upsert_connection(provider_id: str, payload: ConnectionUpsertIn, user=Depends(admin_only)):
        if provider_id not in PROVIDERS_INDEX:
            raise HTTPException(404, "Unknown provider")
        prov = PROVIDERS_INDEX[provider_id]

        existing = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0}) or {}
        existing_fields = existing.get("fields", {}) or {}

        # Validate + merge
        merged: Dict[str, str] = {}
        for fdef in prov["fields"]:
            key = fdef["key"]
            new_val = payload.fields.get(key, None)
            # Empty-string for secret → keep existing (lets the UI re-save w/o re-typing secrets)
            if fdef.get("secret") and (new_val is None or new_val == ""):
                merged[key] = existing_fields.get(key, "")
            else:
                merged[key] = "" if new_val is None else str(new_val)
            if fdef.get("required") and not merged[key]:
                raise HTTPException(400, f"Field '{fdef['label']}' is required")

        # Encrypt secrets; store non-secrets in clear (so the UI can echo them).
        stored_fields: Dict[str, Dict[str, Any]] = {}
        for fdef in prov["fields"]:
            key = fdef["key"]
            val = merged[key]
            if fdef.get("secret"):
                stored_fields[key] = {"secret": True, "cipher": _encrypt(val) if val else ""}
            else:
                stored_fields[key] = {"secret": False, "value": val}

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
        saved = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        return _serialize_connection(saved)

    # ----- delete (disconnect) -----
    @router.delete("/{provider_id}")
    async def delete_connection(provider_id: str, _=Depends(admin_only)):
        if provider_id not in PROVIDERS_INDEX:
            raise HTTPException(404, "Unknown provider")
        await db.connections.delete_one({"provider_id": provider_id})
        return {"deleted": True, "provider_id": provider_id}

    # ----- test (placeholder for future per-provider checks) -----
    @router.post("/{provider_id}/test")
    async def test_connection(provider_id: str, _=Depends(admin_only)):
        if provider_id not in PROVIDERS_INDEX:
            raise HTTPException(404, "Unknown provider")
        doc = await db.connections.find_one({"provider_id": provider_id}, {"_id": 0})
        if not doc or not doc.get("enabled"):
            return {"ok": False, "message": "Not configured or disabled."}
        # Real per-provider auth-ping logic will land here once the customer
        # supplies keys. For now we just confirm the credentials decrypt cleanly.
        prov = PROVIDERS_INDEX[provider_id]
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
