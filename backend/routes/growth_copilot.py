"""routes.growth_copilot — AI GROWTH COPILOT.

The AI develops and follows a plan to take Orisei to ≥ $20,000/week NET
margin after all expenses, assists in real time with all business goals,
and guards a comprehensive freight-brokerage compliance registry so no
responsibility is ever missed.

Endpoints — /api/copilot/*
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("orisei.growth_copilot")

GOAL_WEEKLY_NET = 20000.0
MODEL = ("anthropic", "claude-sonnet-4-5-20250929")

# Weekly fixed overhead of the real business (mirrors sandbox OVERHEAD_DAILY × 7)
WEEKLY_OVERHEAD = {
    "Contingent cargo + GL insurance": 196.0,
    "BMC-84 $75k surety bond": 29.0,
    "Load board subscriptions (DAT/Truckstop)": 84.0,
    "TMS / software / tracking data": 70.0,
    "Office, phone, misc": 49.0,
    "UCR / BOC-3 / filings amortized": 8.4,
    "Operator draw": 1000.0,
    "Carrier vetting service (MCP/Highway)": 35.0,
    "Carrier COI monitoring": 14.0,
    "Shipper credit checks": 12.0,
    "Bookkeeping + CPA": 46.0,
    "Website + marketing": 23.0,
    "Bank fees + legal reserve": 21.0,
}
WEEKLY_OVERHEAD_TOTAL = round(sum(WEEKLY_OVERHEAD.values()), 2)

# ---------------------------------------------------------------- compliance
# Complete freight-brokerage compliance registry — nothing gets missed.
COMPLIANCE_ITEMS = [
    ("authority", "FMCSA Broker Authority (MC number) active", "Verify MC operating authority shows ACTIVE on SAFER/Licensing & Insurance. Re-check monthly.", "critical"),
    ("authority", "BOC-3 process agents filed (all 50 states)", "Blanket process-agent designation on file with FMCSA. Confirm agent company invoice is current.", "critical"),
    ("financial", "BMC-84 surety bond ($75,000) in force", "MAP-21 requirement. Confirm bond premium paid and surety shows on FMCSA L&I. Lapse = automatic revocation after 30 days.", "critical"),
    ("authority", "UCR (Unified Carrier Registration) current year paid", "Annual UCR fee for brokers. Renew every fall for the following year.", "high"),
    ("insurance", "Contingent cargo insurance ($100k) active", "Not legally required but demanded by shippers. Keep COI current and on letterhead.", "high"),
    ("insurance", "General liability policy active", "Standard $1M GL for contracts and shipper onboarding packets.", "high"),
    ("insurance", "Errors & Omissions coverage evaluated", "E&O protects against mis-brokering claims. Review annually.", "medium"),
    ("carrier_vetting", "Carrier vetting SOP enforced on every booking", "Verify authority ACTIVE, ≥$1M auto / $100k cargo insurance with cert direct from producer, safety rating not UNSATISFACTORY, no chameleon-carrier flags, W-9 on file.", "critical"),
    ("carrier_vetting", "Carrier insurance certificate monitoring", "Track expirations; auto-suspend carriers with lapsed certs. Use insurance monitoring on every active carrier.", "critical"),
    ("carrier_vetting", "Broker-carrier agreements signed before first load", "Signed master agreement incl. no-back-solicitation, payment terms, indemnification.", "critical"),
    ("contracts", "Shipper-broker agreements + credit checks", "Signed shipper agreement and credit check (Ansonia/credit report) before extending Net terms.", "high"),
    ("records", "Transaction records retained 3 years (49 CFR 371.3)", "Keep every rate con, BOL, invoice, and carrier file for at least 3 years — shippers/carriers may request transaction records.", "critical"),
    ("claims", "Cargo claims handled per 49 CFR 370", "Acknowledge claims within 30 days, pay/decline/compromise within 120 days. Maintain OS&D file per incident.", "critical"),
    ("tax", "W-9s collected · 1099-NEC filed for carriers (if applicable)", "Collect W-9 from every carrier at onboarding; confirm 1099 obligations with CPA each January.", "high"),
    ("tax", "MN state registration, taxes & annual renewal", "MN LLC annual renewal (free, due Dec 31), state income/sales tax obligations reviewed with CPA quarterly.", "high"),
    ("financial", "Separate business bank account + capital ledger", "No commingling. Capital accounts ledger current for all three members.", "high"),
    ("operations", "Load tracking + proactive shipper updates", "Every load tracked (check calls or ELD/GPS). Late-risk loads escalated before the receiver calls.", "medium"),
    ("operations", "Double-brokering prevention checks", "Match dispatch phone/email to carrier's FMCSA record; verify truck at pickup; no re-brokering clause enforced.", "critical"),
    ("marketing", "Website, brand, quote funnel live", "Public get-quote page connected to sales pipeline — every inquiry answered < 1 hr.", "medium"),
    ("hr", "Partner roles, operating agreement & payroll draws documented", "Operating agreement executed; member draws tracked against capital accounts.", "medium"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _extract_json(text: str) -> Any:
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    raw = m.group(1) if m else text
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(raw[start:end + 1])


async def _llm(system: str, prompt: str, session_id: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="EMERGENT_LLM_KEY not configured")
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system).with_model(*MODEL)
    return str(await chat.send_message(UserMessage(text=prompt)))


class ChatIn(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=80)
    message: str = Field(..., min_length=1, max_length=4000)


class ComplianceStatusIn(BaseModel):
    status: str = Field(..., pattern="^(met|in_progress|action_needed)$")


def build_growth_copilot_router(*, db, get_current_user: Callable,
                                require_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/copilot", tags=["growth-copilot"])

    # ---------------------------------------------------------- live state
    async def _business_state() -> Dict[str, Any]:
        week_ago = _iso(_now() - timedelta(days=7))
        rev = margin = loads_wk = 0.0
        async for b in db.brokerage_bookings.find(
                {"is_sample": {"$ne": True}, "booked_at": {"$gte": week_ago}}, {"_id": 0}):
            rev += b.get("customer_rate_usd") or 0
            margin += (b.get("customer_rate_usd") or 0) - (b.get("carrier_rate_usd") or 0)
            loads_wk += 1
        ar_open = 0.0
        async for inv in db.brokerage_invoices.find(
                {"is_sample": {"$ne": True}, "status": {"$in": ["issued", "overdue"]}}, {"_id": 0}):
            ar_open += inv.get("total_usd") or 0
        prospects = await db.revenue_prospects.count_documents({})
        shippers = await db.shipper_accounts.count_documents({})
        # last completed sandbox week (training signal)
        last_sim = await db.sim_state.find_one({"status": "complete"}, {"_id": 0}, sort=[("started_at", -1)])
        sim_net = None
        if last_sim:
            led = last_sim.get("ledger", {})
            sim_net = round(led.get("revenue", 0) - led.get("carrier_pay", 0)
                            - led.get("factoring_fees", 0) - led.get("exception_costs", 0)
                            - led.get("overhead", 0) - led.get("claims", 0)
                            - led.get("bad_debt", 0) + led.get("quickpay_income", 0), 2)
        net_wk = round(margin - WEEKLY_OVERHEAD_TOTAL, 2)
        avg_margin = round(margin / loads_wk, 2) if loads_wk else 0
        loads_needed = None
        if avg_margin > 0:
            loads_needed = int((GOAL_WEEKLY_NET + WEEKLY_OVERHEAD_TOTAL) / avg_margin + 0.999)
        compliance_gaps = await db.copilot_compliance.count_documents({"status": {"$ne": "met"}})
        active_alerts = await db.sentinel_alerts.count_documents({"status": {"$in": ["active", "acked"]}})
        return {
            "goal_weekly_net": GOAL_WEEKLY_NET,
            "week": {"revenue": round(rev, 2), "gross_margin": round(margin, 2),
                     "overhead": WEEKLY_OVERHEAD_TOTAL, "net_margin": net_wk,
                     "loads": int(loads_wk), "avg_margin_per_load": avg_margin},
            "progress_pct": round(max(0.0, net_wk) / GOAL_WEEKLY_NET * 100, 1),
            "gap_to_goal": round(GOAL_WEEKLY_NET - net_wk, 2),
            "loads_needed_per_week": loads_needed,
            "pipeline": {"prospects": prospects, "shipper_accounts": shippers,
                         "open_ar": round(ar_open, 2)},
            "sandbox_last_week_net": sim_net,
            "compliance_gaps": compliance_gaps,
            "sentinel_active_alerts": active_alerts,
            "overhead_breakdown": WEEKLY_OVERHEAD,
            "computed_at": _iso(_now()),
        }

    async def _ensure_compliance_seed():
        if await db.copilot_compliance.count_documents({}) == 0:
            for cat, title, detail, sev in COMPLIANCE_ITEMS:
                await db.copilot_compliance.insert_one({
                    "item_id": f"CMP-{uuid.uuid4().hex[:6].upper()}", "category": cat,
                    "title": title, "detail": detail, "severity": sev,
                    "status": "action_needed", "updated_at": _iso(_now())})

    def _state_brief(s: Dict[str, Any]) -> str:
        return (f"GOAL: ${GOAL_WEEKLY_NET:,.0f}/week NET margin after ALL expenses.\n"
                f"CURRENT WEEK: revenue ${s['week']['revenue']:,.0f}, gross margin ${s['week']['gross_margin']:,.0f}, "
                f"fixed overhead ${s['week']['overhead']:,.0f}/wk, NET ${s['week']['net_margin']:,.0f} "
                f"({s['progress_pct']}% of goal, gap ${s['gap_to_goal']:,.0f}). "
                f"{s['week']['loads']} real loads booked this week, avg margin/load ${s['week']['avg_margin_per_load']:,.0f}.\n"
                f"PIPELINE: {s['pipeline']['prospects']} prospects, {s['pipeline']['shipper_accounts']} shipper accounts, "
                f"open AR ${s['pipeline']['open_ar']:,.0f}.\n"
                f"SANDBOX (simulated training week) last net: {s['sandbox_last_week_net']}.\n"
                f"COMPLIANCE ITEMS NOT YET MET: {s['compliance_gaps']}. Sentinel active alerts: {s['sentinel_active_alerts']}.\n"
                f"Overhead stack: " + ", ".join(f"{k} ${v:,.0f}" for k, v in WEEKLY_OVERHEAD.items()))

    SYSTEM = (
        "You are the ORISEI GROWTH COPILOT — a world-class freight brokerage operator, "
        "revenue strategist and compliance officer for Orisei Freight Solutions LLC "
        "(3-member Minnesota brokerage: Oliver Cummins — principal broker/ops, Daniel W. Karsor — "
        "technology/brand/capital, Doug Graham — capacity/carrier relations, 12-yr CDL owner-operator). "
        "Your mandate: develop and relentlessly follow a plan to reach at least $20,000/week NET margin "
        "after all expenses, then push beyond. Be professional, specific, and numeric — talk like a "
        "seasoned brokerage GM: lanes, RPM, margins, carrier costs, DSO, factoring, detention, claims. "
        "You must never miss a compliance responsibility (FMCSA authority, BMC-84 bond, BOC-3, UCR, "
        "49 CFR 371.3 records, 49 CFR 370 claims, carrier vetting, double-brokering prevention, W-9/1099, "
        "MN state obligations) or any freight activity that drives success (prospecting, quoting, "
        "carrier network building, AR collection, cash-flow management). Always ground advice in the "
        "live business data provided. Keep answers tight and actionable.")

    # ------------------------------------------------------------ endpoints
    @router.get("/state")
    async def state(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _ensure_compliance_seed()
        return await _business_state()

    @router.post("/plan/generate")
    async def generate_plan(user=Depends(require_role("owner", "dispatcher"))) -> Dict[str, Any]:
        await _ensure_compliance_seed()
        s = await _business_state()
        prompt = (
            _state_brief(s) +
            "\n\nBuild the master growth plan to $20,000/week net margin and beyond. "
            "Return STRICT JSON only:\n"
            '{"summary": "2-3 sentence professional overview of the road to $20k/wk net", '
            '"phases": [{"name": "...", "target_weekly_net": 2500, "timeframe": "Weeks 1-4", '
            '"focus": "one-line theme", "tasks": [{"title": "...", "detail": "specific, numeric action", '
            '"category": "sales|carriers|ops|compliance|finance"}]}]}\n'
            "Rules: 4 phases (ramp to ~$2.5k, $7.5k, $14k, $20k+/wk net). 5-7 tasks per phase. "
            "Include the math (loads/week × avg margin needed at each phase, assuming ~$275-450 margin/load "
            "growing with lane density). Include compliance and cash-flow tasks — nothing may be missed.")
        raw = await _llm(SYSTEM, prompt, f"copilot-plan-{uuid.uuid4().hex[:8]}")
        try:
            plan = _extract_json(raw)
        except Exception:
            raise HTTPException(status_code=502, detail="AI returned an unparseable plan — try again")
        for p in plan.get("phases", []):
            for t in p.get("tasks", []):
                t["task_id"] = f"GT-{uuid.uuid4().hex[:6].upper()}"
                t["done"] = False
        doc = {"plan_id": f"PLAN-{uuid.uuid4().hex[:6].upper()}", "goal_weekly_net": GOAL_WEEKLY_NET,
               "summary": plan.get("summary", ""), "phases": plan.get("phases", []),
               "generated_at": _iso(_now()), "generated_by": user.email,
               "state_at_generation": s, "active": True}
        await db.copilot_plans.update_many({"active": True}, {"$set": {"active": False}})
        await db.copilot_plans.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/plan")
    async def get_plan(_=Depends(get_current_user)) -> Dict[str, Any]:
        plan = await db.copilot_plans.find_one({"active": True}, {"_id": 0})
        return {"plan": plan}

    @router.post("/plan/tasks/{task_id}/toggle")
    async def toggle_task(task_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        plan = await db.copilot_plans.find_one({"active": True})
        if not plan:
            raise HTTPException(status_code=404, detail="No active plan")
        found = False
        for p in plan["phases"]:
            for t in p["tasks"]:
                if t["task_id"] == task_id:
                    t["done"] = not t.get("done", False)
                    found = True
        if not found:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.copilot_plans.update_one({"plan_id": plan["plan_id"]},
                                          {"$set": {"phases": plan["phases"]}})
        return {"ok": True}

    @router.post("/briefing")
    async def briefing(user=Depends(get_current_user)) -> Dict[str, Any]:
        await _ensure_compliance_seed()
        s = await _business_state()
        plan = await db.copilot_plans.find_one({"active": True}, {"_id": 0})
        gaps = await db.copilot_compliance.find(
            {"status": {"$ne": "met"}}, {"_id": 0}).sort("severity", 1).to_list(25)
        plan_ctx = ""
        if plan:
            open_tasks = [t["title"] for p in plan["phases"] for t in p["tasks"] if not t.get("done")][:12]
            plan_ctx = "OPEN PLAN TASKS: " + "; ".join(open_tasks)
        prompt = (_state_brief(s) + "\n" + plan_ctx +
                  "\nUNMET COMPLIANCE: " + "; ".join(g["title"] for g in gaps[:12]) +
                  "\n\nWrite this week's action briefing (max 320 words, markdown): "
                  "1) Where we stand vs the $20k/wk goal (numbers). "
                  "2) The 5 highest-leverage actions THIS WEEK (specific, numeric). "
                  "3) Compliance red flags to close immediately. "
                  "4) One risk you're watching. Professional, direct, encouraging.")
        text = await _llm(SYSTEM, prompt, f"copilot-brief-{uuid.uuid4().hex[:8]}")
        doc = {"briefing_id": f"BRF-{uuid.uuid4().hex[:6].upper()}", "text": text,
               "state": s, "created_at": _iso(_now()), "created_by": user.email}
        await db.copilot_briefings.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    @router.get("/briefing/latest")
    async def latest_briefing(_=Depends(get_current_user)) -> Dict[str, Any]:
        b = await db.copilot_briefings.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        return {"briefing": b}

    @router.post("/chat")
    async def chat(payload: ChatIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        await _ensure_compliance_seed()
        s = await _business_state()
        history = await db.copilot_chat.find(
            {"session_id": payload.session_id}, {"_id": 0}).sort("at", -1).to_list(12)
        history.reverse()
        hist_txt = "\n".join(f"{m['role'].upper()}: {m['content'][:600]}" for m in history)
        prompt = (f"LIVE BUSINESS DATA:\n{_state_brief(s)}\n\n"
                  + (f"CONVERSATION SO FAR:\n{hist_txt}\n\n" if hist_txt else "")
                  + f"PARTNER ({user.name}): {payload.message}")
        reply = await _llm(SYSTEM, prompt, f"copilot-chat-{payload.session_id}")
        now = _iso(_now())
        await db.copilot_chat.insert_many([
            {"session_id": payload.session_id, "role": "user", "content": payload.message,
             "user": user.email, "at": now},
            {"session_id": payload.session_id, "role": "assistant", "content": reply, "at": now}])
        return {"reply": reply, "session_id": payload.session_id}

    @router.get("/chat/{session_id}")
    async def chat_history(session_id: str, _=Depends(get_current_user)) -> Dict[str, Any]:
        msgs = await db.copilot_chat.find({"session_id": session_id}, {"_id": 0}) \
            .sort("at", 1).to_list(100)
        return {"messages": msgs}

    @router.get("/compliance")
    async def compliance(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _ensure_compliance_seed()
        items = await db.copilot_compliance.find({}, {"_id": 0}).to_list(50)
        order = {"critical": 0, "high": 1, "medium": 2}
        items.sort(key=lambda x: (x["status"] == "met", order.get(x["severity"], 3)))
        met = sum(1 for i in items if i["status"] == "met")
        return {"items": items, "met": met, "total": len(items)}

    @router.post("/compliance/{item_id}/status")
    async def set_compliance(item_id: str, payload: ComplianceStatusIn,
                             user=Depends(require_role("owner", "dispatcher"))) -> Dict[str, Any]:
        r = await db.copilot_compliance.update_one(
            {"item_id": item_id},
            {"$set": {"status": payload.status, "updated_at": _iso(_now()), "updated_by": user.email}})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Compliance item not found")
        return {"ok": True}

    return router
