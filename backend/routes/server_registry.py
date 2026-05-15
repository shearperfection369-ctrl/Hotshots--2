"""routes.server_registry — admin Server Registry endpoints.
Extracted from server.py as part of the conservative refactor."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


logger = logging.getLogger("tennant_tms.server_registry")


class ServerRegistryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    role: str = Field(..., min_length=1, max_length=40)
    hostname: str = Field(..., min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: Optional[str] = Field(default="https", max_length=20)
    region: Optional[str] = Field(default=None, max_length=60)
    environment: Optional[str] = Field(default="production", max_length=40)
    owner_email: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=2000)
    health_url: Optional[str] = Field(default=None, max_length=400)


class ServerRegistryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[str] = Field(default=None, min_length=1, max_length=40)
    hostname: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    protocol: Optional[str] = Field(default=None, max_length=20)
    region: Optional[str] = Field(default=None, max_length=60)
    environment: Optional[str] = Field(default=None, max_length=40)
    owner_email: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=2000)
    health_url: Optional[str] = Field(default=None, max_length=400)
    enabled: Optional[bool] = None


def build_server_registry_router(
    *,
    db,
    require_role: Callable,
    app_boot_at: datetime,
) -> APIRouter:
    router = APIRouter()

    async def _detect_system_servers() -> List[Dict[str, Any]]:
        """Live introspection of the actual servers the running pod talks to."""
        out: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        try:
            api_host = socket.gethostname()
            api_ip = socket.gethostbyname(api_host) if api_host else None
        except Exception:
            api_host, api_ip = "fastapi", None
        out.append({
            "id": "system::api",
            "name": "TMS Backend API",
            "role": "api",
            "hostname": api_host or "fastapi",
            "ip": api_ip,
            "port": 8001,
            "protocol": "http",
            "region": os.environ.get("REGION") or "kube-cluster",
            "environment": os.environ.get("ENV") or "production",
            "owner_email": "ops@tennantco.com",
            "system": True,
            "enabled": True,
            "health": "healthy",
            "uptime_seconds": int((now - app_boot_at).total_seconds()),
            "boot_at": app_boot_at.isoformat(),
            "version": "v2.4",
            "last_check_at": now.isoformat(),
            "notes": "FastAPI/uvicorn — request handler for every /api/* route.",
        })

        mongo_url = os.environ.get("MONGO_URL") or ""
        mongo_host = "mongo"
        try:
            from urllib.parse import urlparse
            u = urlparse(mongo_url)
            if u.hostname:
                mongo_host = u.hostname
        except Exception:
            pass
        mongo_ok, mongo_ms, mongo_meta = False, None, {}
        try:
            t0 = now
            info = await asyncio.wait_for(db.command("serverStatus"), timeout=2.0)
            mongo_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
            mongo_ok = True
            mongo_meta = {
                "version": info.get("version"),
                "connections": (info.get("connections") or {}).get("current"),
                "uptime_seconds": int(info.get("uptime") or 0),
            }
        except Exception as e:
            logger.warning("MongoDB serverStatus failed: %s", e)
        out.append({
            "id": "system::mongo",
            "name": "MongoDB Cluster",
            "role": "db",
            "hostname": mongo_host,
            "port": None,
            "protocol": "mongodb",
            "region": "kube-cluster",
            "environment": "production",
            "owner_email": "data@tennantco.com",
            "system": True,
            "enabled": True,
            "health": "healthy" if mongo_ok else "down",
            "ping_ms": mongo_ms,
            "version": mongo_meta.get("version"),
            "connections": mongo_meta.get("connections"),
            "uptime_seconds": mongo_meta.get("uptime_seconds"),
            "last_check_at": now.isoformat(),
            "notes": f"Database name: {os.environ.get('DB_NAME', '—')} · 29 indexed collections.",
        })

        llm_configured = bool(os.environ.get("EMERGENT_LLM_KEY"))
        out.append({
            "id": "system::llm",
            "name": "Emergent LLM Gateway",
            "role": "llm",
            "hostname": "integrations.emergentagent.com",
            "port": 443,
            "protocol": "https",
            "region": "us-east",
            "environment": "production",
            "owner_email": "platform@emergentagent.com",
            "system": True,
            "enabled": llm_configured,
            "health": "healthy" if llm_configured else "unconfigured",
            "last_check_at": now.isoformat(),
            "version": "claude-sonnet-4.5 · gpt-image-1 · nano-banana",
            "notes": "Powers HUDLINK chat, AI Brand Switcher, image gen.",
        })

        pub = os.environ.get("PUBLIC_APP_URL") or os.environ.get("REACT_APP_BACKEND_URL") or ""
        if pub:
            try:
                from urllib.parse import urlparse
                u = urlparse(pub)
                pub_host = u.hostname or "ingress"
                pub_port = u.port or (443 if (u.scheme or "https") == "https" else 80)
                pub_proto = u.scheme or "https"
            except Exception:
                pub_host, pub_port, pub_proto = "ingress", 443, "https"
            out.append({
                "id": "system::ingress",
                "name": "Kubernetes Ingress / Preview",
                "role": "edge",
                "hostname": pub_host,
                "port": pub_port,
                "protocol": pub_proto,
                "region": "kube-cluster",
                "environment": "production",
                "owner_email": "ops@tennantco.com",
                "system": True,
                "enabled": True,
                "health": "healthy",
                "last_check_at": now.isoformat(),
                "notes": "Edge proxy routing /api/* → backend:8001 and /* → frontend:3000.",
            })
        return out

    @router.get("/admin/servers")
    async def admin_list_servers(_=Depends(require_role("admin"))):
        """Return every attached server: auto-detected + custom registry."""
        system = await _detect_system_servers()
        custom = await db.servers_registry.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
        total = len(system) + len(custom)
        healthy = sum(1 for s in system if s.get("health") == "healthy") + sum(1 for c in custom if c.get("last_health") == "healthy")
        down = sum(1 for s in system if s.get("health") == "down") + sum(1 for c in custom if c.get("last_health") == "down")
        by_role: Dict[str, int] = {}
        for s in system + custom:
            r = s.get("role") or "other"
            by_role[r] = by_role.get(r, 0) + 1
        return {"system": system, "custom": custom,
                "totals": {"total": total, "healthy": healthy, "down": down, "by_role": by_role}}

    @router.post("/admin/servers")
    async def admin_create_server(payload: ServerRegistryCreate, admin=Depends(require_role("admin"))):
        doc = {
            "id": f"SRV-{uuid.uuid4().hex[:10].upper()}",
            "name": payload.name.strip(),
            "role": payload.role.strip(),
            "hostname": payload.hostname.strip(),
            "port": payload.port,
            "protocol": (payload.protocol or "https").strip(),
            "region": (payload.region or "").strip() or None,
            "environment": (payload.environment or "production").strip(),
            "owner_email": (payload.owner_email or "").strip() or None,
            "notes": (payload.notes or "").strip() or None,
            "health_url": (payload.health_url or "").strip() or None,
            "enabled": True,
            "system": False,
            "last_health": "unknown",
            "last_ping_ms": None,
            "last_check_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": admin.user_id,
            "created_by_name": admin.name,
        }
        await db.servers_registry.insert_one(dict(doc))
        return doc

    @router.patch("/admin/servers/{server_id}")
    async def admin_update_server(server_id: str, payload: ServerRegistryUpdate, admin=Depends(require_role("admin"))):
        if server_id.startswith("system::"):
            raise HTTPException(400, "System servers cannot be edited.")
        patch = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if not patch:
            raise HTTPException(400, "No fields to update.")
        patch["updated_at"] = datetime.now(timezone.utc).isoformat()
        patch["updated_by"] = admin.user_id
        r = await db.servers_registry.find_one_and_update(
            {"id": server_id}, {"$set": patch}, return_document=True, projection={"_id": 0},
        )
        if not r:
            raise HTTPException(404, "Server not found")
        return r

    @router.delete("/admin/servers/{server_id}")
    async def admin_delete_server(server_id: str, _=Depends(require_role("admin"))):
        if server_id.startswith("system::"):
            raise HTTPException(400, "System servers cannot be deleted.")
        r = await db.servers_registry.delete_one({"id": server_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Server not found")
        return {"ok": True}

    @router.post("/admin/servers/{server_id}/ping")
    async def admin_ping_server(server_id: str, _=Depends(require_role("admin"))):
        """Live health probe — HTTP if health_url provided, else TCP."""
        doc = await db.servers_registry.find_one({"id": server_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Server not found")
        now = datetime.now(timezone.utc)
        health, ping_ms, detail = "down", None, None
        try:
            if doc.get("health_url"):
                t0 = now
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as http:
                    resp = await http.get(doc["health_url"])
                    ping_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                    if 200 <= resp.status_code < 400:
                        health, detail = "healthy", f"HTTP {resp.status_code}"
                    else:
                        health, detail = "degraded", f"HTTP {resp.status_code}"
            elif doc.get("hostname") and doc.get("port"):
                t0 = now
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(doc["hostname"], int(doc["port"])),
                        timeout=3.0,
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    ping_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                    health, detail = "healthy", f"TCP {doc['hostname']}:{doc['port']} open"
                except asyncio.TimeoutError:
                    health, detail = "down", f"TCP {doc['hostname']}:{doc['port']} timed out after 3s"
            else:
                detail, health = "No health_url or hostname:port — nothing to probe.", "unknown"
        except Exception as e:
            detail, health = f"{type(e).__name__}: {e}", "down"
            logger.warning("Ping failed for %s: %s", server_id, detail)
        patch = {"last_health": health, "last_ping_ms": ping_ms,
                 "last_check_at": now.isoformat(), "last_detail": detail}
        await db.servers_registry.update_one({"id": server_id}, {"$set": patch})
        return {"ok": True, **patch}

    return router
