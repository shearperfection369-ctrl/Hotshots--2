"""routes.readiness — Platform Readiness self-test engine.

Runs a DEEP FUNCTIONAL end-to-end flow on a throwaway tenant (provision → auth →
load → invoice → PDFs → branding → billing → teardown) plus LIVE PROBES against
every feature module advertised on the Hot Shot TMS landing page. Produces
pass/warn/fail per check with latency metrics, category scores, and a sell-ready verdict.
"""
import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Request

BASE = "http://localhost:8001/api"

# Landing-page capability map → API prefix probes
PROBE_CATEGORIES = [
    ("AI SUITE — THE MOAT", [
        ("AI Load Hunter", "/load-hunter"),
        ("AI Triage Engine", "/shipment-triage"),
        ("Dispatch Autopilot (ML)", "/dispatch/ml"),
        ("Auto-Match + Margin Shield", "/margin-shield"),
        ("AI Growth Copilot", "/copilot"),
        ("Agent Sentinel", "/sentinel"),
    ]),
    ("LIVE OPERATIONS", [
        ("Live GPS Ops Map", "/live-ops"),
        ("Route Optimizer", "/route-optimizer"),
        ("5-Board Load Aggregator", "/aggregator"),
        ("Driver Mobile PWA", "/driver-pwa"),
        ("Operational Sandbox", "/sim"),
        ("Telematics / GPS", "/telematics"),
    ]),
    ("MONEY & BACK OFFICE", [
        ("AR Aging + Collections", "/ar"),
        ("Factoring + Quick-Pay", "/factoring"),
        ("Cash Flow Console", "/cash-flow"),
        ("Connections (QuickBooks etc.)", "/connections"),
        ("Revenue Automation", "/revenue"),
    ]),
    ("PAPERWORK & COMPLIANCE", [
        ("Document Vault", "/doc-vault"),
        ("Claims Management (49 CFR 370)", "/claims"),
        ("EDI 204/210/214", "/edi"),
        ("FedEx / UPS Parcel Rating", "/parcel"),
        ("Live Weather / NWS Alerts", "/alerts"),
        ("BOC-3 / Authority", "/boc3"),
    ]),
    ("INTELLIGENCE & REPORTING", [
        ("Carrier Scorecards / Analytics", "/research-analytics"),
        ("Shipper CRM + Reports", "/shipper-relations"),
        ("QBR Studio", "/qbr-studio"),
        ("Freight Market News", "/freight-news"),
    ]),
]


# Some modules need a specific probe URL (query params / sample IDs)
PROBE_OVERRIDES = {
    "/route-optimizer": "/api/route-optimizer/geocode?q=Minneapolis,%20MN",
    "/driver-pwa": "/api/driver-pwa/booking/SELFTEST-PROBE",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Check:
    def __init__(self, name: str, kind: str = "functional"):
        self.name, self.kind = name, kind
        self.status, self.ms, self.evidence = "fail", 0, ""

    def done(self, ok: bool, ms: float, evidence: str, warn: bool = False):
        self.status = "pass" if ok else ("warn" if warn else "fail")
        self.ms = round(ms)
        self.evidence = evidence[:220]
        return self

    def as_dict(self):
        return {"name": self.name, "kind": self.kind, "status": self.status, "ms": self.ms, "evidence": self.evidence}


async def _timed(coro):
    t0 = time.perf_counter()
    resp = await coro
    return resp, (time.perf_counter() - t0) * 1000


def build_readiness_router(*, db, require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/hotshot/readiness", tags=["readiness"])

    async def _functional_flow(cx: httpx.AsyncClient, admin_headers: Dict[str, str]) -> List[Check]:
        checks: List[Check] = []
        slug = f"selftest-{uuid.uuid4().hex[:6]}"
        pw = f"SelfTest{uuid.uuid4().hex[:6]}!"
        email = f"admin@{slug}.local"
        tenant_token = None

        async def step(name, method, url, *, headers=None, json=None, expect=200, validate=None, kind="functional"):
            c = Check(name, kind)
            try:
                resp, ms = await _timed(cx.request(method, url, headers=headers, json=json, timeout=15))
                ok = resp.status_code == expect
                ev = f"HTTP {resp.status_code}"
                if ok and validate:
                    ok, extra = validate(resp)
                    ev += f" · {extra}"
                c.done(ok, ms, ev)
            except Exception as exc:  # noqa: BLE001
                c.done(False, 0, f"EXCEPTION: {str(exc)[:120]}")
            checks.append(c)
            return c, locals().get("resp")

        # 1 provision
        c, resp = await step("Provision isolated tenant workspace", "POST", f"{BASE}/hotshot/tenants",
                             headers=admin_headers,
                             json={"company_name": f"SelfTest {slug}", "slug": slug, "plan": "growth",
                                   "admin_email": email, "admin_password": pw, "send_welcome": False},
                             validate=lambda r: (r.json().get("ok") is True, f"slug={slug}"))
        if c.status != "pass":
            return checks
        # 2 login
        c, resp = await step("Tenant login (JWT issued)", "POST", f"{BASE}/t/{slug}/auth/login",
                             json={"email": email, "password": pw},
                             validate=lambda r: (bool(r.json().get("token")), "token issued"))
        if c.status == "pass":
            tenant_token = resp.json()["token"]
        th = {"Authorization": f"Bearer {tenant_token}"} if tenant_token else {}
        # 3 wrong password rejected
        await step("Wrong password rejected (401)", "POST", f"{BASE}/t/{slug}/auth/login",
                   json={"email": email, "password": "WrongPass1!"}, expect=401)
        # 4 book load + margin math
        c, resp = await step("Book a load — margin auto-computes", "POST", f"{BASE}/t/{slug}/loads",
                             headers=th, json={"origin": "Minneapolis, MN", "destination": "Dallas, TX",
                                               "customer": "SelfTest Shipper", "customer_rate": 2400, "carrier_rate": 1950},
                             validate=lambda r: (r.json()["load"]["margin"] == 450.0, "margin=$450 ✓"))
        load_id = resp.json()["load"]["load_id"] if c.status == "pass" else ""
        # 5 status update
        await step("Load status lifecycle update", "PATCH", f"{BASE}/t/{slug}/loads/{load_id}",
                   headers=th, json={"status": "delivered"})
        # 6 rate con PDF
        await step("Branded Rate Confirmation PDF", "GET", f"{BASE}/t/{slug}/loads/{load_id}/ratecon.pdf",
                   headers=th, validate=lambda r: (r.content[:4] == b"%PDF", f"{len(r.content)}b PDF"))
        # 7 invoice
        c, resp = await step("One-click invoice from delivered load", "POST", f"{BASE}/t/{slug}/loads/{load_id}/invoice",
                             headers=th, validate=lambda r: (r.json()["invoice"]["amount"] == 2400, "amount=$2,400 ✓"))
        inv_id = resp.json()["invoice"]["invoice_id"] if c.status == "pass" else ""
        # 8 invoice PDF
        await step("Branded Invoice PDF", "GET", f"{BASE}/t/{slug}/invoices/{inv_id}/pdf",
                   headers=th, validate=lambda r: (r.content[:4] == b"%PDF", f"{len(r.content)}b PDF"))
        # 9 dashboard KPIs
        await step("Dashboard KPIs accurate", "GET", f"{BASE}/t/{slug}/dashboard", headers=th,
                   validate=lambda r: (r.json()["kpis"]["gross_revenue"] == 2400 and r.json()["kpis"]["total_loads"] == 1,
                                       "revenue/load counts ✓"))
        # 10 branding
        await step("White-label branding update", "PUT", f"{BASE}/t/{slug}/branding", headers=th,
                   json={"company_name": f"SelfTest {slug}", "primary_color": "#10B981", "accent_color": "#22D3EE", "tagline": "readiness"})
        await step("Public branding reflects instantly", "GET", f"{BASE}/t/{slug}/branding/public",
                   validate=lambda r: (r.json().get("primary_color") == "#10B981", "color persisted ✓"))
        # 11 team + role gate
        c, resp = await step("Add dispatcher team member", "POST", f"{BASE}/t/{slug}/users", headers=th,
                             json={"email": f"dispatch@{slug}.local", "name": "Dispatcher D", "password": pw, "role": "dispatcher"})
        c2, resp2 = await step("Dispatcher login", "POST", f"{BASE}/t/{slug}/auth/login",
                               json={"email": f"dispatch@{slug}.local", "password": pw},
                               validate=lambda r: (bool(r.json().get("token")), "token issued"))
        if c2.status == "pass":
            dh = {"Authorization": f"Bearer {resp2.json()['token']}"}
            await step("Role gate: dispatcher blocked from billing (403)", "GET", f"{BASE}/t/{slug}/billing",
                       headers=dh, expect=403)
            await step("Cross-tenant isolation guard (403)", "GET", f"{BASE}/t/acme-freight-co/loads",
                       headers=dh, expect=403)
        # 12 billing
        await step("Stripe checkout session (subscription)", "POST", f"{BASE}/t/{slug}/billing/checkout", headers=th,
                   json={"lookup_key": "hotshot_growth_monthly", "origin_url": os.environ.get("PUBLIC_FRONTEND_URL", "http://localhost:3000")},
                   validate=lambda r: (r.json()["checkout_url"].startswith("https://checkout.stripe.com"), "stripe URL ✓"))
        # 13 platform status + collateral
        await step("Public uptime endpoint", "GET", f"{BASE}/hotshot/status",
                   validate=lambda r: (r.json().get("ok") is True, "db up ✓"))
        await step("Sales one-pager PDF", "GET", f"{BASE}/hotshot/one-pager.pdf",
                   validate=lambda r: (r.content[:4] == b"%PDF", f"{len(r.content)}b"))
        await step("Lead capture endpoint", "POST", f"{BASE}/hotshot/leads",
                   json={"name": "SELFTEST", "email": "selftest@readiness.local", "company": "Readiness Bot"})
        await db.hotshot_leads.delete_many({"email": "selftest@readiness.local"})
        # teardown
        await step("Teardown: tenant deleted, database dropped", "DELETE", f"{BASE}/hotshot/tenants/{slug}",
                   headers=admin_headers)
        return checks

    async def _probe(cx: httpx.AsyncClient, name: str, prefix: str, paths: Dict[str, Any],
                     headers: Dict[str, str], sem: asyncio.Semaphore) -> Check:
        c = Check(name, "probe")
        target: Optional[str] = None
        if prefix in PROBE_OVERRIDES:
            target = PROBE_OVERRIDES[prefix]
        else:
            candidates = sorted(p for p, methods in paths.items()
                                if p.startswith(f"/api{prefix}/") or p == f"/api{prefix}"
                                if "get" in methods and "{" not in p)
            if candidates:
                target = candidates[0]
        if not target:
            return c.done(False, 0, "no GET endpoint found", warn=True)
        async with sem:
            try:
                resp, ms = await _timed(cx.get(f"http://localhost:8001{target}", headers=headers, timeout=12))
                if resp.status_code < 300 or (resp.status_code in (404, 422) and prefix in PROBE_OVERRIDES):
                    c.done(True, ms, f"GET {target.split('?')[0]} → {resp.status_code}")
                elif resp.status_code < 500:
                    c.done(False, ms, f"GET {target} → {resp.status_code} (alive, guarded)", warn=True)
                else:
                    c.done(False, ms, f"GET {target} → {resp.status_code}")
            except Exception as exc:  # noqa: BLE001
                c.done(False, 0, f"EXCEPTION: {str(exc)[:100]}")
        return c

    @router.post("/run")
    async def run_readiness(request: Request, _=Depends(require_role("admin"))) -> Dict[str, Any]:
        started = time.perf_counter()
        admin_headers = {"Authorization": request.headers.get("Authorization", "")}
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        paths: Dict[str, set] = {}
        for r in request.app.routes:
            p = getattr(r, "path", "")
            methods = {m.lower() for m in (getattr(r, "methods", None) or set())}
            if p and methods:
                paths.setdefault(p, set()).update(methods)
        async with httpx.AsyncClient() as cx:
            sem = asyncio.Semaphore(8)
            functional_task = asyncio.create_task(_functional_flow(cx, admin_headers))
            probe_tasks = {cat: [ _probe(cx, n, p, paths, admin_headers, sem) for n, p in items ]
                           for cat, items in PROBE_CATEGORIES}
            probe_results = {cat: await asyncio.gather(*tasks) for cat, tasks in probe_tasks.items()}
            functional_checks = await functional_task

        categories = [{"name": "TENANT PLATFORM — DEEP FUNCTIONAL FLOW",
                       "checks": [c.as_dict() for c in functional_checks]}]
        categories += [{"name": cat, "checks": [c.as_dict() for c in res]} for cat, res in probe_results.items()]

        all_checks = [c for cat in categories for c in cat["checks"]]
        latencies = sorted(c["ms"] for c in all_checks if c["ms"] > 0)
        passed = sum(1 for c in all_checks if c["status"] == "pass")
        warned = sum(1 for c in all_checks if c["status"] == "warn")
        failed = sum(1 for c in all_checks if c["status"] == "fail")
        func_total = len(functional_checks)
        func_pass = sum(1 for c in functional_checks if c.status == "pass")
        pass_rate = round(100 * passed / max(1, len(all_checks)), 1)
        weighted = round(100 * (passed + 0.5 * warned) / max(1, len(all_checks)), 1)
        p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0
        avg = round(sum(latencies) / max(1, len(latencies)))
        critical_fail = any(c.status == "fail" for c in functional_checks)
        verdict = "READY_TO_SELL" if (not critical_fail and pass_rate >= 90) else ("NEEDS_ATTENTION" if not critical_fail else "NOT_READY")
        slowest = max(all_checks, key=lambda c: c["ms"]) if all_checks else None

        for cat in categories:
            cs = cat["checks"]
            cat["pass_rate"] = round(100 * sum(1 for c in cs if c["status"] == "pass") / max(1, len(cs)), 1)

        run = {
            "run_id": run_id, "started_at": _now(),
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "verdict": verdict, "score": weighted,
            "metrics": {
                "total_checks": len(all_checks), "passed": passed, "warned": warned, "failed": failed,
                "pass_rate": pass_rate, "functional_pass": f"{func_pass}/{func_total}",
                "avg_latency_ms": avg, "p95_latency_ms": p95,
                "slowest_check": {"name": slowest["name"], "ms": slowest["ms"]} if slowest else None,
            },
            "categories": categories,
        }
        await db.readiness_runs.insert_one(dict(run))
        run.pop("_id", None)
        return run

    @router.get("/runs")
    async def run_history(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        runs = await db.readiness_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(30)
        return {"runs": runs}

    @router.get("/latest")
    async def latest_run(_=Depends(require_role("admin"))) -> Dict[str, Any]:
        run = await db.readiness_runs.find_one({}, {"_id": 0}, sort=[("started_at", -1)])
        return {"run": run}

    return router
