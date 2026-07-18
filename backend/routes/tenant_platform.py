"""routes.tenant_platform — Hot Shot TMS multi-tenant white-label SaaS platform.

Isolation model: DATABASE-PER-TENANT. Each client lives in its own MongoDB
database `hs_tenant_{slug}` — users, loads, carriers, invoices, branding never
share a collection with another tenant or with the Orisei master TMS.

Endpoint groups:
  /api/hotshot/tenants/*   — master control (Orisei admin) — provision / monitor / suspend
  /api/hotshot/status      — PUBLIC uptime probe (point UptimeRobot here)
  /api/t/{slug}/*          — tenant-scoped portal APIs (own JWT auth)
  /api/payments/status/*   — payment status poll (unauthenticated, per Stripe playbook)
  /api/stripe/webhook      — Stripe webhook
"""
import base64
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import bcrypt
import jwt as pyjwt
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from routes.connections import get_connection_credentials
from routes.tenant_pdfs import build_invoice_pdf, build_ratecon_pdf

logger = logging.getLogger("orisei.tenant_platform")
JWT_ALG = "HS256"
BOOT_TS = time.time()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

PLANS = {
    "starter": {"name": "Starter", "lookup_key": "hotshot_starter_monthly", "monthly": 390},
    "growth": {"name": "Growth", "lookup_key": "hotshot_growth_monthly", "monthly": 975},
    "dwy": {"name": "Done-With-You", "lookup_key": "hotshot_dwy_monthly", "monthly": 2600},
}
TENANT_ROLES = ("admin", "dispatcher", "viewer")
LOAD_STATUSES = ("quoted", "booked", "in_transit", "delivered", "invoiced", "cancelled")

DEFAULT_BRANDING = {
    "company_name": "", "primary_color": "#F59E0B", "accent_color": "#22D3EE",
    "logo_b64": None, "tagline": "Powered by Hot Shot TMS",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def _jwt_secret() -> str:
    return os.environ["HS_JWT_SECRET"]


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:40] or uuid.uuid4().hex[:8]


# ---------- Pydantic ----------
class TenantCreate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field("", max_length=40)
    plan: str = Field("growth")
    admin_email: str = Field(..., max_length=200)
    admin_password: str = Field(..., min_length=8, max_length=100)
    admin_name: str = Field("", max_length=100)
    origin_url: str = Field("", max_length=300)
    send_welcome: bool = True


class SignupIn(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=200)
    password: str = Field(..., min_length=8, max_length=100)
    origin_url: str = Field("", max_length=300)
    website: str = Field("", max_length=100)  # honeypot


class LoginIn(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=100)


class TenantUserIn(BaseModel):
    email: str = Field(..., max_length=200)
    name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    role: str = Field("dispatcher")


class BrandingIn(BaseModel):
    company_name: str = Field("", max_length=100)
    primary_color: str = Field("#F59E0B", max_length=20)
    accent_color: str = Field("#22D3EE", max_length=20)
    tagline: str = Field("", max_length=140)
    logo_b64: Optional[str] = Field(None, max_length=700_000)


class LoadIn(BaseModel):
    origin: str = Field(..., min_length=2, max_length=120)
    destination: str = Field(..., min_length=2, max_length=120)
    pickup_date: str = Field("", max_length=30)
    equipment: str = Field("Dry Van", max_length=60)
    customer: str = Field("", max_length=120)
    carrier: str = Field("", max_length=120)
    customer_rate: float = Field(0, ge=0)
    carrier_rate: float = Field(0, ge=0)
    notes: str = Field("", max_length=1000)


class LoadPatch(BaseModel):
    status: Optional[str] = None
    carrier: Optional[str] = None
    customer_rate: Optional[float] = None
    carrier_rate: Optional[float] = None
    notes: Optional[str] = None


class CarrierIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    mc_number: str = Field("", max_length=30)
    contact: str = Field("", max_length=120)
    phone: str = Field("", max_length=40)
    equipment: str = Field("", max_length=100)


class CheckoutIn(BaseModel):
    lookup_key: str = Field(..., max_length=60)
    origin_url: str = Field(..., max_length=300)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


def build_tenant_platform_router(*, db, client, require_role: Callable) -> APIRouter:
    router = APIRouter(tags=["tenant-platform"])

    def tdb(slug: str):
        return client[f"hs_tenant_{slug}"]

    async def _log(slug: str, kind: str, message: str, level: str = "info"):
        await db.tenant_activity.insert_one({
            "slug": slug, "kind": kind, "level": level, "message": message, "at": _now()})

    async def _tenant_doc(slug: str) -> Dict[str, Any]:
        doc = await db.tenants.find_one({"slug": slug}, {"_id": 0})
        if not doc:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return doc

    # ---------- tenant auth dependency ----------
    async def tenant_user(request: Request, slug: str) -> Dict[str, Any]:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            payload = pyjwt.decode(auth[7:], _jwt_secret(), algorithms=[JWT_ALG])
        except pyjwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Session expired — log in again")
        except pyjwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        if payload.get("tenant") != slug:
            raise HTTPException(status_code=403, detail="Token is for a different workspace")
        tenant = await _tenant_doc(slug)
        if tenant.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="This workspace is suspended — contact support")
        user = await tdb(slug).users.find_one({"user_id": payload.get("sub")}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if payload.get("imp"):
            user["impersonated"] = True
        return user

    def require_tenant_role(*roles):
        async def dep(request: Request, slug: str):
            user = await tenant_user(request, slug)
            if user.get("role") not in roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return user
        return dep

    # ================= PUBLIC STATUS (UptimeRobot) =================
    @router.get("/hotshot/status")
    async def platform_status() -> Dict[str, Any]:
        try:
            await db.command("ping")
            db_ok = True
        except Exception:
            db_ok = False
        tenants = await db.tenants.count_documents({}) if db_ok else -1
        return {"ok": db_ok, "service": "hotshot-tms", "db": "up" if db_ok else "down",
                "uptime_seconds": int(time.time() - BOOT_TS), "tenants": tenants, "checked_at": _now()}

    # ================= MASTER: TENANT PROVISIONING =================
    def _welcome_html(company: str, admin_name: str, login_url: str, primary: str = "#F59E0B") -> str:
        steps = [
            ("Book your first load", "Loads → New Load. Enter the lane and rates — margin computes automatically."),
            ("Invoice in one click", "When a load delivers, hit the invoice icon. Track open A/R on your dashboard."),
            ("Add your team", "Team tab — admins, dispatchers, and read-only viewers."),
            ("Make it yours", "Settings → Branding. Upload your logo and colors — the portal re-skins instantly."),
        ]
        rows = "".join(
            f'<tr><td style="padding:10px 0;border-bottom:1px solid #F1F5F9;"><b style="color:#0D1117;">{i+1}. {t}</b><br>'
            f'<span style="color:#64748B;font-size:13px;">{d}</span></td></tr>' for i, (t, d) in enumerate(steps))
        return f"""<!doctype html><html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#F8FAFC;padding:24px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #E2E8F0;">
<div style="background:#0D1117;padding:26px 30px;border-bottom:4px solid {primary};">
<div style="color:{primary};font-size:11px;letter-spacing:.25em;font-family:Courier,monospace;">HOT SHOT TMS</div>
<div style="color:#fff;font-size:22px;font-weight:800;margin-top:6px;">Welcome aboard, {company}!</div></div>
<div style="padding:26px 30px;font-size:14px;line-height:1.6;color:#1E293B;">
<p>Hi {admin_name or 'there'},</p>
<p>Your isolated workspace is live. Your data sits in its own database — nobody else's freight ever touches it.</p>
<p style="text-align:center;margin:26px 0;"><a href="{login_url}" style="background:{primary};color:#000;font-weight:800;padding:13px 34px;border-radius:999px;text-decoration:none;">Open your workspace</a></p>
<p style="font-size:12px;color:#64748B;text-align:center;">Login: <a href="{login_url}">{login_url}</a></p>
<table style="width:100%;border-collapse:collapse;margin-top:8px;">{rows}</table>
<p style="margin-top:22px;">Questions? Just reply — you'll hear back within one business day.<br>— Oliver Cummins, Hot Shot TMS</p>
</div></div></body></html>"""

    async def _send_welcome(slug: str, company: str, admin_email: str, admin_name: str, origin: str) -> Dict[str, Any]:
        login_url = f"{(origin or os.environ.get('PUBLIC_FRONTEND_URL', '')).rstrip('/')}/t/{slug}/login"
        html = _welcome_html(company, admin_name, login_url)
        subject = f"Your {company} workspace on Hot Shot TMS is live"
        record = {"id": f"WEL-{uuid.uuid4().hex[:8].upper()}", "slug": slug, "to_email": admin_email,
                  "subject": subject, "html": html, "login_url": login_url, "created_at": _now()}
        creds = await get_connection_credentials(db, "resend") or {}
        api_key = creds.get("api_key")
        if not api_key:
            record["status"] = "queued_no_resend"
            await db.tenant_emails.insert_one(dict(record))
            await _log(slug, "email", f"Welcome email QUEUED for {admin_email} (Resend key missing)", level="warn")
            return {"sent": False, "status": "queued_no_resend", "login_url": login_url,
                    "reason": "Resend key missing — email queued. Add your Resend key in Connections to send automatically."}
        try:
            import resend
            resend.api_key = api_key
            resp = resend.Emails.send({
                "from": creds.get("from_email") or "Hot Shot TMS <oliver@oriseifreight.com>",
                "to": [admin_email], "subject": subject, "html": html,
                "reply_to": creds.get("reply_to") or "oliver@oriseifreight.com"})
            record["status"] = "sent"
            record["message_id"] = (resp or {}).get("id") if isinstance(resp, dict) else None
            await db.tenant_emails.insert_one(dict(record))
            await _log(slug, "email", f"Welcome email SENT to {admin_email}")
            return {"sent": True, "status": "sent", "login_url": login_url}
        except Exception as exc:  # noqa: BLE001
            record["status"] = "failed"
            record["error"] = str(exc)[:200]
            await db.tenant_emails.insert_one(dict(record))
            await _log(slug, "email", f"Welcome email FAILED for {admin_email}: {str(exc)[:120]}", level="warn")
            return {"sent": False, "status": "failed", "login_url": login_url, "reason": str(exc)[:200]}

    async def _provision(company_name: str, slug_hint: str, plan: str, admin_email: str,
                         admin_password: str, admin_name: str, source: str) -> Dict[str, Any]:
        slug = _slugify(slug_hint or company_name)
        if await db.tenants.find_one({"slug": slug}):
            raise HTTPException(status_code=400, detail=f"Workspace name '{slug}' is already taken — try another")
        email = admin_email.strip().lower()
        if not EMAIL_RE.match(email):
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        tenant = {
            "slug": slug, "company_name": company_name, "plan": plan,
            "status": "active", "source": source, "created_at": _now(), "admin_email": email,
            "billing": {"status": "trial", "plan": plan, "subscription_id": None, "last_payment_at": None},
        }
        await db.tenants.insert_one(dict(tenant))
        t = tdb(slug)
        await t.users.create_index("email", unique=True)
        await t.users.insert_one({
            "user_id": f"TU-{uuid.uuid4().hex[:8].upper()}", "email": email,
            "name": admin_name or company_name + " Admin",
            "role": "admin", "password_hash": _hash_pw(admin_password),
            "created_at": _now(), "last_login_at": None,
        })
        await t.branding.insert_one({**DEFAULT_BRANDING, "company_name": company_name, "_singleton": True})
        await _log(slug, "provision", f"Tenant '{company_name}' provisioned on {plan} plan ({source})")
        logger.info("Tenant provisioned: %s (%s, %s)", slug, plan, source)
        return tenant

    @router.post("/hotshot/tenants")
    async def create_tenant(payload: TenantCreate, _=Depends(require_role("admin"))) -> Dict[str, Any]:
        if payload.plan not in PLANS:
            raise HTTPException(status_code=400, detail="Invalid plan")
        tenant = await _provision(payload.company_name, payload.slug, payload.plan,
                                  payload.admin_email, payload.admin_password, payload.admin_name, "manual")
        welcome = None
        if payload.send_welcome:
            welcome = await _send_welcome(tenant["slug"], payload.company_name,
                                          tenant["admin_email"], payload.admin_name, payload.origin_url)
        return {"ok": True, "tenant": tenant, "login_path": f"/t/{tenant['slug']}/login", "welcome_email": welcome}

    @router.post("/hotshot/signup")  # PUBLIC — self-serve trial from the landing page
    async def self_serve_signup(payload: SignupIn, request: Request) -> Dict[str, Any]:
        if payload.website:  # honeypot — silently accept
            return {"ok": True, "login_path": "/hotshot"}
        ip = request.client.host if request.client else "x"
        recent = await db.tenants.count_documents({
            "source": "self_serve", "signup_ip": ip,
            "created_at": {"$gt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
        if recent >= 3:
            raise HTTPException(status_code=429, detail="Too many signups from this network — try again later")
        tenant = await _provision(payload.company_name, "", "growth",
                                  payload.email, payload.password, payload.name, "self_serve")
        await db.tenants.update_one({"slug": tenant["slug"]}, {"$set": {"signup_ip": ip}})
        await _send_welcome(tenant["slug"], payload.company_name, tenant["admin_email"], payload.name, payload.origin_url)
        user = await tdb(tenant["slug"]).users.find_one({"email": tenant["admin_email"]})
        token = pyjwt.encode({
            "sub": user["user_id"], "email": tenant["admin_email"], "role": "admin", "tenant": tenant["slug"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access",
        }, _jwt_secret(), algorithm=JWT_ALG)
        return {"ok": True, "slug": tenant["slug"], "login_path": f"/t/{tenant['slug']}/login", "token": token}


    @router.get("/hotshot/tenants")
    async def list_tenants(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        tenants = await db.tenants.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        out = []
        for tn in tenants:
            t = tdb(tn["slug"])
            users = await t.users.count_documents({})
            loads = await t.loads.count_documents({})
            invoices = await t.invoices.count_documents({})
            last_user = await t.users.find_one({"last_login_at": {"$ne": None}}, {"_id": 0, "last_login_at": 1},
                                               sort=[("last_login_at", -1)])
            out.append({**tn, "usage": {"users": users, "loads": loads, "invoices": invoices,
                                        "last_login_at": (last_user or {}).get("last_login_at")}})
        return {"tenants": out, "count": len(out)}

    @router.post("/hotshot/tenants/{slug}/status")
    async def set_tenant_status(slug: str, payload: Dict[str, str], _=Depends(require_role("admin"))) -> Dict[str, Any]:
        status = payload.get("status", "")
        if status not in ("active", "suspended"):
            raise HTTPException(status_code=400, detail="status must be active|suspended")
        r = await db.tenants.update_one({"slug": slug}, {"$set": {"status": status}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tenant not found")
        await _log(slug, "status", f"Tenant {status}", level="warn" if status == "suspended" else "info")
        return {"ok": True, "status": status}

    @router.delete("/hotshot/tenants/{slug}")
    async def delete_tenant(slug: str, _=Depends(require_role("admin"))) -> Dict[str, Any]:
        await _tenant_doc(slug)
        await client.drop_database(f"hs_tenant_{slug}")
        await db.tenants.delete_one({"slug": slug})
        await _log(slug, "delete", "Tenant deleted and database dropped", level="warn")
        return {"ok": True}

    @router.post("/hotshot/tenants/{slug}/impersonate")
    async def impersonate_tenant(slug: str, _=Depends(require_role("admin"))) -> Dict[str, Any]:
        tenant = await _tenant_doc(slug)
        user = await tdb(slug).users.find_one({"role": "admin"}, sort=[("created_at", 1)])
        if not user:
            raise HTTPException(status_code=404, detail="Tenant has no admin user")
        token = pyjwt.encode({
            "sub": user["user_id"], "email": user["email"], "role": user["role"], "tenant": slug,
            "imp": True, "exp": datetime.now(timezone.utc) + timedelta(hours=2), "type": "access",
        }, _jwt_secret(), algorithm=JWT_ALG)
        await _log(slug, "impersonate", f"Platform owner opened client view for {tenant['company_name']}")
        return {"token": token, "portal_path": f"/t/{slug}/app", "expires_in_hours": 2}

    @router.get("/hotshot/tenants/{slug}/activity")
    async def tenant_activity(slug: str, _=Depends(require_role("admin"))) -> Dict[str, Any]:
        rows = await db.tenant_activity.find({"slug": slug}, {"_id": 0}).sort("at", -1).to_list(100)
        return {"activity": rows}

    @router.get("/hotshot/activity")
    async def all_activity(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        rows = await db.tenant_activity.find({}, {"_id": 0}).sort("at", -1).to_list(100)
        return {"activity": rows}

    # ================= TENANT: AUTH =================
    @router.get("/t/{slug}/branding/public")
    async def public_branding(slug: str) -> Dict[str, Any]:
        tenant = await _tenant_doc(slug)
        brand = await tdb(slug).branding.find_one({"_singleton": True}, {"_id": 0, "_singleton": 0}) or dict(DEFAULT_BRANDING)
        return {**brand, "tenant_status": tenant.get("status"), "company_name": brand.get("company_name") or tenant["company_name"]}

    @router.post("/t/{slug}/auth/login")
    async def tenant_login(slug: str, payload: LoginIn, request: Request) -> Dict[str, Any]:
        tenant = await _tenant_doc(slug)
        if tenant.get("status") == "suspended":
            raise HTTPException(status_code=403, detail="This workspace is suspended — contact support")
        email = payload.email.strip().lower()
        ident = f"{slug}:{email}"
        attempt = await db.hs_login_attempts.find_one({"identifier": ident})
        if attempt and attempt.get("count", 0) >= 5:
            locked_at = datetime.fromisoformat(attempt["last_at"])
            if datetime.now(timezone.utc) - locked_at < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many failed attempts — try again in 15 minutes")
            await db.hs_login_attempts.delete_one({"identifier": ident})
        user = await tdb(slug).users.find_one({"email": email})
        if not user or not _check_pw(payload.password, user.get("password_hash", "")):
            await db.hs_login_attempts.update_one(
                {"identifier": ident}, {"$inc": {"count": 1}, "$set": {"last_at": _now()}}, upsert=True)
            await _log(slug, "auth", f"Failed login for {email}", level="warn")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        await db.hs_login_attempts.delete_one({"identifier": ident})
        await tdb(slug).users.update_one({"user_id": user["user_id"]}, {"$set": {"last_login_at": _now()}})
        token = pyjwt.encode({
            "sub": user["user_id"], "email": email, "role": user["role"], "tenant": slug,
            "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access",
        }, _jwt_secret(), algorithm=JWT_ALG)
        await _log(slug, "auth", f"{user['name']} logged in")
        return {"token": token, "user": {k: user[k] for k in ("user_id", "email", "name", "role")}}

    @router.get("/t/{slug}/auth/me")
    async def tenant_me(request: Request, slug: str) -> Dict[str, Any]:
        return await tenant_user(request, slug)

    @router.post("/t/{slug}/auth/change-password")
    async def tenant_change_pw(slug: str, payload: PasswordChange, request: Request) -> Dict[str, Any]:
        user = await tenant_user(request, slug)
        full = await tdb(slug).users.find_one({"user_id": user["user_id"]})
        if not _check_pw(payload.current_password, full.get("password_hash", "")):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        await tdb(slug).users.update_one({"user_id": user["user_id"]},
                                         {"$set": {"password_hash": _hash_pw(payload.new_password)}})
        return {"ok": True}

    # ================= TENANT: TEAM =================
    @router.get("/t/{slug}/users")
    async def tenant_users(slug: str, user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Dict[str, Any]:
        rows = await tdb(slug).users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(100)
        return {"users": rows}

    @router.post("/t/{slug}/users")
    async def tenant_add_user(slug: str, payload: TenantUserIn, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        if payload.role not in TENANT_ROLES:
            raise HTTPException(status_code=400, detail=f"Role must be one of {TENANT_ROLES}")
        email = payload.email.strip().lower()
        if await tdb(slug).users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="A user with that email already exists")
        new_user = {"user_id": f"TU-{uuid.uuid4().hex[:8].upper()}", "email": email, "name": payload.name,
                    "role": payload.role, "password_hash": _hash_pw(payload.password),
                    "created_at": _now(), "last_login_at": None}
        await tdb(slug).users.insert_one(dict(new_user))
        await _log(slug, "team", f"{user['name']} added {payload.name} ({payload.role})")
        return {"ok": True, "user": {k: new_user[k] for k in ("user_id", "email", "name", "role")}}

    @router.delete("/t/{slug}/users/{user_id}")
    async def tenant_del_user(slug: str, user_id: str, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        if user_id == user["user_id"]:
            raise HTTPException(status_code=400, detail="You can't remove yourself")
        r = await tdb(slug).users.delete_one({"user_id": user_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        await _log(slug, "team", f"{user['name']} removed user {user_id}")
        return {"ok": True}

    # ================= TENANT: BRANDING =================
    @router.put("/t/{slug}/branding")
    async def tenant_set_branding(slug: str, payload: BrandingIn, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        if payload.logo_b64:
            raw = payload.logo_b64.split(",")[-1]
            try:
                blob = base64.b64decode(raw)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid logo image data")
            if len(blob) > 400_000:
                raise HTTPException(status_code=400, detail="Logo too large — keep it under 400KB")
        update = payload.model_dump(exclude_none=False)
        if payload.logo_b64 is None:
            update.pop("logo_b64")
        await tdb(slug).branding.update_one({"_singleton": True}, {"$set": update}, upsert=True)
        await _log(slug, "branding", f"{user['name']} updated branding")
        return {"ok": True}

    @router.delete("/t/{slug}/branding/logo")
    async def tenant_del_logo(slug: str, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        await tdb(slug).branding.update_one({"_singleton": True}, {"$set": {"logo_b64": None}})
        return {"ok": True}

    # ================= TENANT: LOADS =================
    @router.get("/t/{slug}/loads")
    async def tenant_loads(slug: str, user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Dict[str, Any]:
        rows = await tdb(slug).loads.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"loads": rows}

    @router.post("/t/{slug}/loads")
    async def tenant_add_load(slug: str, payload: LoadIn, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        load = {"load_id": f"HS-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(),
                "status": "booked", "margin": round(payload.customer_rate - payload.carrier_rate, 2),
                "created_by": user["name"], "created_at": _now(), "updated_at": _now()}
        await tdb(slug).loads.insert_one(dict(load))
        return {"ok": True, "load": load}

    @router.patch("/t/{slug}/loads/{load_id}")
    async def tenant_patch_load(slug: str, load_id: str, payload: LoadPatch,
                                user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        update = {k: v for k, v in payload.model_dump().items() if v is not None}
        if "status" in update and update["status"] not in LOAD_STATUSES:
            raise HTTPException(status_code=400, detail=f"Status must be one of {LOAD_STATUSES}")
        existing = await tdb(slug).loads.find_one({"load_id": load_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Load not found")
        cr = update.get("customer_rate", existing.get("customer_rate", 0))
        xr = update.get("carrier_rate", existing.get("carrier_rate", 0))
        update["margin"] = round(cr - xr, 2)
        update["updated_at"] = _now()
        await tdb(slug).loads.update_one({"load_id": load_id}, {"$set": update})
        return {"ok": True}

    @router.delete("/t/{slug}/loads/{load_id}")
    async def tenant_del_load(slug: str, load_id: str, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await tdb(slug).loads.delete_one({"load_id": load_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Load not found")
        return {"ok": True}

    # ================= TENANT: CARRIERS =================
    @router.get("/t/{slug}/carriers")
    async def tenant_carriers(slug: str, user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Dict[str, Any]:
        rows = await tdb(slug).carriers.find({}, {"_id": 0}).sort("name", 1).to_list(300)
        return {"carriers": rows}

    @router.post("/t/{slug}/carriers")
    async def tenant_add_carrier(slug: str, payload: CarrierIn, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        carrier = {"carrier_id": f"HC-{uuid.uuid4().hex[:6].upper()}", **payload.model_dump(), "created_at": _now()}
        await tdb(slug).carriers.insert_one(dict(carrier))
        return {"ok": True, "carrier": carrier}

    @router.delete("/t/{slug}/carriers/{carrier_id}")
    async def tenant_del_carrier(slug: str, carrier_id: str, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await tdb(slug).carriers.delete_one({"carrier_id": carrier_id})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Carrier not found")
        return {"ok": True}

    # ================= TENANT: INVOICES =================
    @router.get("/t/{slug}/invoices")
    async def tenant_invoices(slug: str, user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Dict[str, Any]:
        rows = await tdb(slug).invoices.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
        return {"invoices": rows}

    @router.post("/t/{slug}/loads/{load_id}/invoice")
    async def tenant_invoice_load(slug: str, load_id: str, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        load = await tdb(slug).loads.find_one({"load_id": load_id}, {"_id": 0})
        if not load:
            raise HTTPException(status_code=404, detail="Load not found")
        existing = await tdb(slug).invoices.find_one({"load_id": load_id}, {"_id": 0})
        if existing:
            return {"ok": True, "invoice": existing, "already_invoiced": True}
        inv = {"invoice_id": f"INV-{uuid.uuid4().hex[:6].upper()}", "load_id": load_id,
               "customer": load.get("customer", ""), "amount": load.get("customer_rate", 0),
               "status": "open", "created_at": _now(), "paid_at": None}
        await tdb(slug).invoices.insert_one(dict(inv))
        await tdb(slug).loads.update_one({"load_id": load_id}, {"$set": {"status": "invoiced", "updated_at": _now()}})
        return {"ok": True, "invoice": inv}

    @router.post("/t/{slug}/invoices/{invoice_id}/paid")
    async def tenant_invoice_paid(slug: str, invoice_id: str, user=Depends(require_tenant_role("admin", "dispatcher"))) -> Dict[str, Any]:
        r = await tdb(slug).invoices.update_one({"invoice_id": invoice_id},
                                                {"$set": {"status": "paid", "paid_at": _now()}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return {"ok": True}

    # ================= TENANT: BRANDED PDFS =================
    @router.get("/t/{slug}/loads/{load_id}/ratecon.pdf")
    async def load_ratecon_pdf(slug: str, load_id: str,
                               user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Response:
        load = await tdb(slug).loads.find_one({"load_id": load_id}, {"_id": 0})
        if not load:
            raise HTTPException(status_code=404, detail="Load not found")
        brand = await tdb(slug).branding.find_one({"_singleton": True}, {"_id": 0}) or dict(DEFAULT_BRANDING)
        pdf = build_ratecon_pdf(brand, load)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="RateCon_{load_id}.pdf"'})

    @router.get("/t/{slug}/invoices/{invoice_id}/pdf")
    async def invoice_pdf(slug: str, invoice_id: str,
                          user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Response:
        inv = await tdb(slug).invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        load = await tdb(slug).loads.find_one({"load_id": inv.get("load_id", "")}, {"_id": 0})
        brand = await tdb(slug).branding.find_one({"_singleton": True}, {"_id": 0}) or dict(DEFAULT_BRANDING)
        pdf = build_invoice_pdf(brand, inv, load)
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="Invoice_{invoice_id}.pdf"'})

    # ================= TENANT: DASHBOARD =================
    @router.get("/t/{slug}/dashboard")
    async def tenant_dashboard(slug: str, user=Depends(require_tenant_role("admin", "dispatcher", "viewer"))) -> Dict[str, Any]:
        t = tdb(slug)
        loads = await t.loads.find({}, {"_id": 0}).to_list(1000)
        invoices = await t.invoices.find({}, {"_id": 0}).to_list(1000)
        active = [l for l in loads if l.get("status") in ("booked", "in_transit")]
        revenue = sum(l.get("customer_rate", 0) for l in loads if l.get("status") != "cancelled")
        margin = sum(l.get("margin", 0) for l in loads if l.get("status") != "cancelled")
        open_ar = sum(i.get("amount", 0) for i in invoices if i.get("status") == "open")
        by_status: Dict[str, int] = {}
        for l in loads:
            by_status[l.get("status", "?")] = by_status.get(l.get("status", "?"), 0) + 1
        return {"kpis": {"total_loads": len(loads), "active_loads": len(active),
                         "gross_revenue": round(revenue, 2), "gross_margin": round(margin, 2),
                         "open_ar": round(open_ar, 2), "carriers": await t.carriers.count_documents({}),
                         "team": await t.users.count_documents({})},
                "by_status": by_status,
                "recent_loads": sorted(loads, key=lambda x: x.get("created_at", ""), reverse=True)[:8]}

    # ================= BILLING (Stripe — Flow A, SMP w/ fallback) =================
    @router.get("/t/{slug}/billing")
    async def tenant_billing(slug: str, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        tenant = await _tenant_doc(slug)
        return {"billing": tenant.get("billing", {}), "plan": tenant.get("plan"),
                "plans": {k: {"name": v["name"], "monthly": v["monthly"], "lookup_key": v["lookup_key"]} for k, v in PLANS.items()}}

    @router.post("/t/{slug}/billing/checkout")
    async def tenant_checkout(slug: str, payload: CheckoutIn, user=Depends(require_tenant_role("admin"))) -> Dict[str, Any]:
        plan_key = next((k for k, v in PLANS.items() if v["lookup_key"] == payload.lookup_key), None)
        if not plan_key:
            raise HTTPException(status_code=400, detail="Unknown plan")
        prices = stripe.Price.list(lookup_keys=[payload.lookup_key], active=True, limit=1).data
        if not prices:
            raise HTTPException(status_code=500, detail=f"Price not found: {payload.lookup_key}")
        price = prices[0]
        kwargs = dict(
            line_items=[{"price": price.id, "quantity": 1}],
            mode="subscription",
            success_url=f"{payload.origin_url}/t/{slug}/app/settings?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{payload.origin_url}/t/{slug}/app/settings?checkout=cancelled",
            metadata={"tenant_slug": slug, "plan": plan_key, "lookup_key": payload.lookup_key},
        )
        try:
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or "").lower()
            if "managed payments" in msg or "ineligible" in msg:
                session = stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True},
                                                         billing_address_collection="required")
            else:
                raise
        await db.hs_payment_transactions.insert_one({
            "session_id": session.id, "tenant_slug": slug, "plan": plan_key,
            "lookup_key": payload.lookup_key, "amount": (price.unit_amount or 0),
            "currency": price.currency, "status": "initiated", "payment_status": "pending",
            "created_at": _now(), "updated_at": _now()})
        await _log(slug, "billing", f"{user['name']} started checkout for {PLANS[plan_key]['name']}")
        return {"checkout_url": session.url, "session_id": session.id}

    async def _mark_paid(session_id: str, subscription_id: Optional[str] = None):
        rec = await db.hs_payment_transactions.find_one({"session_id": session_id})
        if not rec or rec.get("payment_status") == "paid":
            return
        await db.hs_payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": "paid",
                      "stripe_subscription_id": subscription_id, "updated_at": _now()}})
        await db.tenants.update_one({"slug": rec["tenant_slug"]}, {"$set": {
            "plan": rec["plan"],
            "billing": {"status": "active", "plan": rec["plan"], "subscription_id": subscription_id,
                        "last_payment_at": _now()}}})
        await _log(rec["tenant_slug"], "billing", f"Subscription ACTIVE on {PLANS[rec['plan']]['name']} plan")

    @router.get("/payments/status/{session_id}")
    async def payment_status(session_id: str) -> Dict[str, Any]:
        record = await db.hs_payment_transactions.find_one({"session_id": session_id})
        if not record:
            raise HTTPException(status_code=404, detail="Transaction not found")
        if record.get("payment_status") != "paid":
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await _mark_paid(session_id, s.subscription)
                    record = await db.hs_payment_transactions.find_one({"session_id": session_id})
            except stripe.error.StripeError:
                pass
        return {"session_id": record["session_id"], "status": record["status"],
                "payment_status": record["payment_status"]}

    @router.post("/stripe/webhook")
    async def stripe_webhook(request: Request) -> Dict[str, Any]:
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")
        obj, t = event["data"]["object"], event["type"]
        if t == "checkout.session.completed":
            await _mark_paid(obj["id"], obj.get("subscription"))
        elif t == "checkout.session.expired":
            await db.hs_payment_transactions.update_one(
                {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
                {"$set": {"status": "expired", "payment_status": "expired", "updated_at": _now()}})
        return {"status": "ok"}

    # ================= TENANT: HELP GUIDE =================
    @router.get("/t/{slug}/help")
    async def tenant_help(slug: str) -> Dict[str, Any]:
        brand = await tdb(slug).branding.find_one({"_singleton": True}, {"_id": 0}) or DEFAULT_BRANDING
        name = brand.get("company_name") or "your brokerage"
        return {"sections": [
            {"title": "1 · Your first load in 2 minutes", "body": f"Go to Loads → New Load. Enter origin, destination, customer rate and carrier rate — {name}'s margin computes automatically. Update the status as it moves: booked → in transit → delivered."},
            {"title": "2 · Invoice with one click", "body": "When a load is delivered, hit Invoice on the load row. It lands in Invoices with an open balance. Mark it paid when the money hits."},
            {"title": "3 · Add your team", "body": "Team tab → Add User. Admins manage everything; dispatchers book and update loads; viewers get read-only access — perfect for accountants."},
            {"title": "4 · Make it yours", "body": "Settings → Branding. Upload your logo and set your colors — the whole portal re-skins instantly for everyone on your team."},
            {"title": "5 · Billing", "body": "Settings → Billing shows your plan. Card payments run through Stripe — you can upgrade any time and it prorates automatically."},
            {"title": "Need help?", "body": "Email oliver@oriseifreight.com — you'll hear back within one business day. Growth and Done-With-You plans get priority support."},
        ]}

    return router
