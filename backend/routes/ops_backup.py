"""routes.ops_backup — automated MongoDB backups + log-collection pruning."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
BACKUP_DIR = Path("/app/backups")
KEEP = 4
BACKUP_EVERY_DAYS = 7
LOG_CAPS = {"sim_events": 5000, "hunter_audit": 5000, "sentinel_repairs": 3000,
            "sentinel_checks": 3000, "tenant_activity": 5000, "user_sessions": 5000,
            "dispatch_ml_training": 5000}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_days(iso: str) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400
    except Exception:  # noqa: BLE001
        return 1e9


def build_ops_backup_router(*, api_router, db, get_current_user, require_role):
    BACKUP_DIR.mkdir(exist_ok=True)

    async def run_backup() -> Dict[str, Any]:
        name = f"orisei_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.gz"
        path = BACKUP_DIR / name
        cmd = ["mongodump", "--uri", os.environ["MONGO_URL"], "--db", os.environ["DB_NAME"],
               f"--archive={path}", "--gzip"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(status_code=500, detail=f"mongodump failed: {err.decode()[:300]}")
        size = path.stat().st_size
        for old in sorted(BACKUP_DIR.glob("orisei_backup_*.gz"))[:-KEEP]:
            old.unlink()
        await db.ops_maintenance.update_one(
            {"_id": "state"},
            {"$set": {"last_backup_at": _now(), "last_backup_name": name, "last_backup_size": size},
             "$inc": {"backups_run": 1}}, upsert=True)
        return {"name": name, "size_bytes": size, "at": _now()}

    async def run_prune() -> Dict[str, Any]:
        pruned: Dict[str, int] = {}
        for coll, cap in LOG_CAPS.items():
            n = await db[coll].estimated_document_count()
            if n > cap:
                overflow = n - cap
                rows = await db[coll].find({}, {"_id": 1}).sort("_id", 1).skip(overflow - 1).limit(1).to_list(1)
                if rows:
                    res = await db[coll].delete_many({"_id": {"$lte": rows[0]["_id"]}})
                    pruned[coll] = res.deleted_count
        await db.ops_maintenance.update_one(
            {"_id": "state"}, {"$set": {"last_prune_at": _now(), "last_prune": pruned}}, upsert=True)
        return {"pruned": pruned}

    @api_router.get("/ops-backups")
    async def list_backups(_=Depends(get_current_user)) -> Dict[str, Any]:
        files = []
        for p in sorted(BACKUP_DIR.glob("orisei_backup_*.gz"), reverse=True):
            st = p.stat()
            files.append({"name": p.name, "size_bytes": st.st_size,
                          "at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()})
        state = await db.ops_maintenance.find_one({"_id": "state"}, {"_id": 0}) or {}
        return {"backups": files, "state": state, "keep": KEEP, "cadence_days": BACKUP_EVERY_DAYS,
                "log_caps": LOG_CAPS}

    @api_router.post("/ops-backups/run")
    async def trigger_backup(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        return {"ok": True, "backup": await run_backup()}

    @api_router.post("/ops-backups/prune")
    async def trigger_prune(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        return {"ok": True, **(await run_prune())}

    @api_router.get("/ops-backups/{name}/download")
    async def download_backup(name: str, _=Depends(get_current_user)):
        if "/" in name or ".." in name or not name.startswith("orisei_backup_"):
            raise HTTPException(status_code=400, detail="Invalid backup name")
        path = BACKUP_DIR / name
        if not path.exists():
            raise HTTPException(status_code=404, detail="Backup not found")
        return FileResponse(path, media_type="application/gzip", filename=name)

    async def maintenance_tick():
        state = await db.ops_maintenance.find_one({"_id": "state"}) or {}
        if _age_days(state.get("last_backup_at", "")) >= BACKUP_EVERY_DAYS:
            await run_backup()
        if _age_days(state.get("last_prune_at", "")) >= 1:
            await run_prune()

    return maintenance_tick


async def backup_loop(maintenance_tick):
    await asyncio.sleep(60)
    while True:
        try:
            await maintenance_tick()
        except Exception:  # noqa: BLE001
            logger.exception("ops backup maintenance failed")
        await asyncio.sleep(6 * 3600)
