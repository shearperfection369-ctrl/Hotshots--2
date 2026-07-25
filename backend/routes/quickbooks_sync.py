"""routes.quickbooks_sync — QuickBooks Online accounting sync.

OAuth2 connect flow + invoice/payment push per Intuit playbook.
Requires INTUIT_CLIENT_ID / INTUIT_CLIENT_SECRET / INTUIT_REDIRECT_URI in
backend/.env (from developer.intuit.com → app → Keys & OAuth).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import requests as rq
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

logger = logging.getLogger("tennant_tms.qbo")

BASE_URLS = {"sandbox": "https://sandbox-quickbooks.api.intuit.com",
             "production": "https://quickbooks.api.intuit.com"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env() -> Dict[str, Optional[str]]:
    return {"client_id": os.environ.get("INTUIT_CLIENT_ID"),
            "client_secret": os.environ.get("INTUIT_CLIENT_SECRET"),
            "redirect_uri": os.environ.get("INTUIT_REDIRECT_URI"),
            "environment": os.environ.get("INTUIT_ENVIRONMENT", "sandbox")}


def _auth_client():
    cfg = _env()
    if not (cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"]):
        return None
    from intuitlib.client import AuthClient
    return AuthClient(client_id=cfg["client_id"], client_secret=cfg["client_secret"],
                      redirect_uri=cfg["redirect_uri"], environment=cfg["environment"])


def build_quickbooks_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/qbo", tags=["quickbooks"])
    conns = db.qbo_connections

    async def _conn() -> Optional[Dict[str, Any]]:
        return await conns.find_one({"_id": "default"})

    async def _valid_token() -> Dict[str, Any]:
        conn = await _conn()
        if not conn or not conn.get("connected"):
            raise HTTPException(400, "QuickBooks not connected — run the Connect flow first")
        if conn.get("access_token_expires_at", "") <= _now_iso():
            ac = _auth_client()
            if not ac:
                raise HTTPException(400, "INTUIT credentials missing from backend/.env")
            ac.refresh_token = conn["refresh_token"]
            try:
                ac.refresh()
            except Exception as e:                                  # noqa: BLE001
                await conns.update_one({"_id": "default"}, {"$set": {"connected": False}})
                raise HTTPException(401, f"QuickBooks token refresh failed — reconnect required: {e}")
            conn["access_token"] = ac.access_token
            conn["refresh_token"] = ac.refresh_token
            await conns.update_one({"_id": "default"}, {"$set": {
                "access_token": ac.access_token, "refresh_token": ac.refresh_token,
                "access_token_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=ac.expires_in or 3500)).isoformat(),
                "updated_at": _now_iso()}})
        return conn

    def _base(conn) -> str:
        return BASE_URLS.get(conn.get("environment", "sandbox"), BASE_URLS["sandbox"])

    def _hdrs(conn) -> Dict[str, str]:
        return {"Authorization": f"Bearer {conn['access_token']}",
                "Accept": "application/json", "Content-Type": "application/json"}

    def _query(conn, q: str) -> list:
        r = rq.get(f"{_base(conn)}/v3/company/{conn['realm_id']}/query",
                   params={"query": q}, headers=_hdrs(conn), timeout=20)
        r.raise_for_status()
        return list(r.json().get("QueryResponse", {}).values())[0] if r.json().get("QueryResponse") else []

    def _ensure_customer(conn, name: str) -> str:
        safe = name.replace("'", "\\'")
        rows = _query(conn, f"select * from Customer where DisplayName = '{safe}'")
        if rows:
            return rows[0]["Id"]
        r = rq.post(f"{_base(conn)}/v3/company/{conn['realm_id']}/customer",
                    json={"DisplayName": name}, headers=_hdrs(conn), timeout=20)
        r.raise_for_status()
        return r.json()["Customer"]["Id"]

    def _ensure_item(conn) -> str:
        rows = _query(conn, "select * from Item where Name = 'Freight Services'")
        if rows:
            return rows[0]["Id"]
        accts = _query(conn, "select * from Account where AccountType = 'Income' maxresults 1")
        if not accts:
            raise HTTPException(502, "No income account found in QuickBooks company")
        r = rq.post(f"{_base(conn)}/v3/company/{conn['realm_id']}/item",
                    json={"Name": "Freight Services", "Type": "Service",
                          "IncomeAccountRef": {"value": accts[0]["Id"]}},
                    headers=_hdrs(conn), timeout=20)
        r.raise_for_status()
        return r.json()["Item"]["Id"]

    @router.get("/status")
    async def status(_=Depends(get_current_user)) -> Dict[str, Any]:
        cfg = _env()
        configured = bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])
        conn = await _conn()
        out = {"configured": configured, "environment": cfg["environment"],
               "connected": bool(conn and conn.get("connected")),
               "realm_id": conn.get("realm_id") if conn else None,
               "last_sync": conn.get("last_sync") if conn else None,
               "needs": [] if configured else [
                   "INTUIT_CLIENT_ID + INTUIT_CLIENT_SECRET — developer.intuit.com → your app → Keys & OAuth",
                   "INTUIT_REDIRECT_URI — must exactly match the redirect URI registered on the app",
                   "INTUIT_ENVIRONMENT — sandbox (default) or production"]}
        if out["connected"]:
            try:
                conn = await _valid_token()
                r = rq.get(f"{_base(conn)}/v3/company/{conn['realm_id']}/companyinfo/{conn['realm_id']}",
                           headers=_hdrs(conn), timeout=15)
                if r.status_code == 200:
                    out["company_name"] = r.json().get("CompanyInfo", {}).get("CompanyName")
                else:
                    out["connected"] = False
                    out["error"] = f"health check {r.status_code}"
            except HTTPException as e:
                out["connected"] = False
                out["error"] = e.detail
        return out

    @router.get("/authorize")
    async def authorize(_=Depends(get_current_user)) -> Dict[str, Any]:
        ac = _auth_client()
        if not ac:
            raise HTTPException(400, "INTUIT credentials missing — add INTUIT_CLIENT_ID, "
                                     "INTUIT_CLIENT_SECRET, INTUIT_REDIRECT_URI to backend/.env")
        from intuitlib.enums import Scopes
        return {"authorization_url": ac.get_authorization_url([Scopes.ACCOUNTING])}

    @router.get("/callback")
    async def callback(request: Request):
        code = request.query_params.get("code")
        realm_id = request.query_params.get("realmId")
        if not code or not realm_id:
            return HTMLResponse("<h3>QuickBooks connection failed — missing code/realmId.</h3>", status_code=400)
        ac = _auth_client()
        if not ac:
            return HTMLResponse("<h3>INTUIT credentials missing on the server.</h3>", status_code=400)
        try:
            ac.get_bearer_token(code, realm_id=realm_id)
        except Exception as e:                                      # noqa: BLE001
            return HTMLResponse(f"<h3>Token exchange failed: {e}</h3>", status_code=502)
        now = datetime.now(timezone.utc)
        await conns.update_one({"_id": "default"}, {"$set": {
            "realm_id": realm_id, "access_token": ac.access_token,
            "refresh_token": ac.refresh_token,
            "access_token_expires_at": (now + timedelta(seconds=ac.expires_in or 3500)).isoformat(),
            "refresh_token_expires_at": (now + timedelta(seconds=ac.x_refresh_token_expires_in or 8640000)).isoformat(),
            "environment": _env()["environment"], "connected": True,
            "updated_at": _now_iso()}}, upsert=True)
        return HTMLResponse("<h3>✅ QuickBooks connected. You can close this tab and return to the TMS.</h3>")

    @router.post("/disconnect")
    async def disconnect(_=Depends(get_current_user)) -> Dict[str, Any]:
        conn = await _conn()
        if conn and conn.get("refresh_token"):
            ac = _auth_client()
            if ac:
                try:
                    ac.revoke(token=conn["refresh_token"])
                except Exception:                                   # noqa: BLE001
                    pass
        await conns.update_one({"_id": "default"},
                               {"$set": {"connected": False, "updated_at": _now_iso()}}, upsert=True)
        return {"ok": True, "connected": False}

    @router.post("/sync/invoice/{booked_id}")
    async def sync_invoice(booked_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        conn = await _valid_token()
        b = await db.brokerage_bookings.find_one({"booked_id": booked_id}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Booking not found")
        existing = await db.qbo_invoice_map.find_one({"booked_id": booked_id}, {"_id": 0})
        if existing:
            return {"ok": True, "already_synced": True, **existing}
        cust_id = _ensure_customer(conn, b.get("customer_name") or "Unknown Shipper")
        item_id = _ensure_item(conn)
        amount = float(b.get("settled_rate_usd") or b.get("forecast_rate_usd") or 0)
        payload = {"CustomerRef": {"value": cust_id},
                   "Line": [{"DetailType": "SalesItemLineDetail", "Amount": amount,
                             "Description": f"Freight {b.get('origin')} → {b.get('destination')} · {b.get('load_id')}",
                             "SalesItemLineDetail": {"ItemRef": {"value": item_id}, "Qty": 1,
                                                      "UnitPrice": amount}}],
                   "PrivateNote": f"TMS booking {booked_id}"}
        r = rq.post(f"{_base(conn)}/v3/company/{conn['realm_id']}/invoice",
                    json=payload, headers=_hdrs(conn), timeout=20)
        if r.status_code >= 400:
            raise HTTPException(502, f"QBO invoice create failed: {r.text[:300]}")
        inv = r.json()["Invoice"]
        row = {"booked_id": booked_id, "qbo_invoice_id": inv["Id"],
               "qbo_doc_number": inv.get("DocNumber"), "qbo_customer_id": cust_id,
               "amount": amount, "balance": inv.get("Balance"), "synced_at": _now_iso()}
        await db.qbo_invoice_map.update_one({"booked_id": booked_id}, {"$set": row}, upsert=True)
        await conns.update_one({"_id": "default"}, {"$set": {"last_sync": _now_iso()}})
        return {"ok": True, **row}

    @router.post("/sync/payment/{booked_id}")
    async def sync_payment(booked_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        conn = await _valid_token()
        m = await db.qbo_invoice_map.find_one({"booked_id": booked_id}, {"_id": 0})
        if not m:
            raise HTTPException(404, "Invoice not synced to QuickBooks yet")
        payload = {"CustomerRef": {"value": m["qbo_customer_id"]},
                   "TotalAmt": m["amount"],
                   "Line": [{"Amount": m["amount"],
                             "LinkedTxn": [{"TxnId": m["qbo_invoice_id"], "TxnType": "Invoice"}]}]}
        r = rq.post(f"{_base(conn)}/v3/company/{conn['realm_id']}/payment",
                    json=payload, headers=_hdrs(conn), timeout=20)
        if r.status_code >= 400:
            raise HTTPException(502, f"QBO payment create failed: {r.text[:300]}")
        await db.qbo_invoice_map.update_one({"booked_id": booked_id},
                                            {"$set": {"paid_at": _now_iso(), "balance": 0}})
        return {"ok": True, "qbo_payment_id": r.json().get("Payment", {}).get("Id")}

    @router.post("/sync/recent-invoices")
    async def sync_recent(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _valid_token()
        rows = await db.brokerage_bookings.find(
            {"status": {"$in": ["booked", "delivered", "settled"]}},
            {"_id": 0, "booked_id": 1}).sort("booked_at", -1).to_list(5)
        results = []
        for b in rows:
            try:
                results.append(await sync_invoice(b["booked_id"]))
            except HTTPException as e:
                results.append({"booked_id": b["booked_id"], "ok": False, "error": e.detail})
        return {"ok": True, "results": results}

    return router
