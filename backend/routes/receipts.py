"""routes.receipts — Orisei official capital/payment receipts.

Sequential receipt register (ORI-RCT-####) with branded PDF output.
Seeds the two founding capital contributions (Daniel $2,500 · Doug $300).

Endpoints — /api/receipts/*
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("orisei.receipts")

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
        "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
        "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _words_under_1000(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{ONES[n // 100]} Hundred")
        n %= 100
    if n >= 20:
        parts.append(TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else ""))
    elif n:
        parts.append(ONES[n])
    return " ".join(parts)


def amount_in_words(amount: float) -> str:
    dollars = int(amount)
    cents = round((amount - dollars) * 100)
    if dollars == 0:
        w = "Zero"
    else:
        chunks = []
        for div, label in ((1_000_000, "Million"), (1_000, "Thousand"), (1, "")):
            if dollars >= div:
                chunks.append(f"{_words_under_1000(dollars // div)} {label}".strip())
                dollars %= div
        w = " ".join(chunks)
    return f"{w} and {cents:02d}/100 Dollars"


def _receipt_markdown(r: Dict[str, Any], brand: Dict[str, Any]) -> str:
    company = brand.get("company_name", "Orisei Freight Solutions LLC")
    capital_clause = (" and the payer's capital account has been credited accordingly per "
                      "Article II of the Partnership Agreement"
                      if "capital" in r["purpose"].lower() else "")
    notes_line = f"**Notes**: {r['notes']}" if r.get("notes") else ""
    return f"""## OFFICIAL RECEIPT · {r['receipt_no']}

- **Date Received**: {r['received_at'][:10]}
- **Received From**: {r['received_from']}
- **Amount**: **${r['amount_usd']:,.2f}**
- **Amount in Words**: {amount_in_words(r['amount_usd'])}
- **Payment Method**: {r['method']}
- **Purpose**: {r['purpose']}
- **Credited To**: {r['credited_to']}

## Acknowledgment

{company} hereby acknowledges receipt of the amount stated above in immediately available funds. This receipt is entered in the Company's official receipt register{capital_clause}.

{notes_line}

| | |
| --- | --- |
| Issued By: **{r.get('issued_by_name') or 'Oliver Cummins — Operator / Principal Broker'}** | Signature: ______________________ |
| Receipt No: {r['receipt_no']} | Register Entry: {r['received_at'][:16].replace('T', ' ')} UTC |

*This is an official financial record of {company}. Retain for tax and capital-account purposes.*
"""


class ReceiptIn(BaseModel):
    received_from: str
    amount_usd: float
    method: str = "Cash / Direct Transfer"
    purpose: str = "Capital contribution"
    credited_to: str = "Company operating account"
    notes: str = ""


class CapitalEntryIn(BaseModel):
    member: str
    entry_type: str  # contribution | holdback | withdrawal
    amount_usd: float
    notes: str = ""


CAPITAL_MEMBERS = [
    {"member": "Oliver Cummins", "role": "Operator / Principal Broker",
     "commitment_usd": 10000.0, "in_kind": "Orisei Command Deck platform IP + regulatory work product"},
    {"member": "Daniel W. Karsor", "role": "Finance & Growth",
     "commitment_usd": 10000.0, "in_kind": None},
    {"member": "Doug Graham", "role": "Capacity & Carrier Relations",
     "commitment_usd": 10000.0, "in_kind": "12 years CDL owner/operator expertise + carrier network"},
]
ENTRY_TYPES = ("contribution", "holdback", "withdrawal")


def build_receipts_router(*, api_router: APIRouter, db,
                          get_current_user: Callable, require_role: Callable) -> None:
    router = APIRouter(prefix="/receipts", tags=["receipts"])

    async def _next_no() -> str:
        last = await db.capital_receipts.find({}, {"_id": 0, "receipt_no": 1}).sort("receipt_no", -1).to_list(1)
        n = int(last[0]["receipt_no"].rsplit("-", 1)[1]) if last else 0
        return f"ORI-RCT-{n + 1:04d}"

    async def _seed():
        if await db.capital_receipts.count_documents({"receipt_no": "ORI-RCT-0001"}) > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        seeds = [
            {"receipt_no": "ORI-RCT-0001", "received_from": "Daniel W. Karsor",
             "amount_usd": 2500.00, "method": "Cash / Direct Transfer",
             "purpose": "Founding capital contribution — Partnership Agreement §2.2",
             "credited_to": "Member capital account — D. W. Karsor (33⅓% interest)",
             "notes": "Launch capital per Business Plan Use of Funds.",
             "received_at": now, "issued_by_name": "Oliver Cummins — Operator / Principal Broker"},
            {"receipt_no": "ORI-RCT-0002", "received_from": "Doug Graham",
             "amount_usd": 1300.00, "method": "Cash / Direct Transfer",
             "purpose": "Founding capital contribution — Partnership Agreement §2.3",
             "credited_to": "Member capital account — D. Graham (33⅓% interest)",
             "notes": "Accompanies in-kind contribution: 12 years CDL owner/operator expertise (§2.5).",
             "received_at": now, "issued_by_name": "Oliver Cummins — Operator / Principal Broker"},
            {"receipt_no": "ORI-RCT-0003", "received_from": "Oliver Cummins",
             "amount_usd": 10000.00, "method": "In-kind — agreed value (unanimous consent)",
             "purpose": "Capital contribution — commitment PAID IN FULL in-kind (Agreement §2.4)",
             "credited_to": "Member capital account — O. Cummins (33⅓% interest)",
             "notes": "Software design & development of the Orisei Command Deck, business structuring & formation work, and payment of all Company expenses to date from personal funds.",
             "received_at": now, "issued_by_name": "Oliver Cummins — Operator / Principal Broker"},
        ]
        for s in seeds:
            await db.capital_receipts.update_one({"receipt_no": s["receipt_no"]},
                                                 {"$setOnInsert": s}, upsert=True)
        logger.info("Seeded founding capital receipts (Karsor $2,500 · Graham $300)")

    @router.get("")
    async def list_receipts(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _seed()
        items = await db.capital_receipts.find({}, {"_id": 0}).sort("receipt_no", -1).to_list(200)
        return {"items": items,
                "total_received": round(sum(i["amount_usd"] for i in items), 2)}

    @router.post("")
    async def create_receipt(payload: ReceiptIn,
                             user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        await _seed()
        if payload.amount_usd <= 0:
            raise HTTPException(422, "amount_usd must be positive")
        if not payload.received_from.strip():
            raise HTTPException(422, "received_from is required")
        r = {**payload.model_dump(), "receipt_no": await _next_no(),
             "received_at": datetime.now(timezone.utc).isoformat(),
             "issued_by_name": "Oliver Cummins — Operator / Principal Broker",
             "issued_by": getattr(user, "user_id", None)}
        await db.capital_receipts.insert_one(dict(r))
        r.pop("_id", None)
        r.pop("issued_by", None)
        return r

    @router.get("/{receipt_no}/pdf")
    async def receipt_pdf(receipt_no: str, _=Depends(get_current_user)):
        await _seed()
        r = await db.capital_receipts.find_one({"receipt_no": receipt_no}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Receipt not found")
        from routes.orisei_docs import build_branded_markdown_pdf
        brand = await db.company_brand.find_one({"is_active": True}, {"_id": 0}) or {}
        pdf = build_branded_markdown_pdf(
            _receipt_markdown(r, brand), title="Official Receipt",
            subtitle=f"{r['receipt_no']} · ${r['amount_usd']:,.2f} · {r['received_from']}",
            doc_id=r["receipt_no"], brand=brand)
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{r["receipt_no"]}.pdf"'})

    # -------------------------------------------------- capital accounts ledger
    cap = APIRouter(prefix="/capital", tags=["capital-accounts"])

    @cap.get("/accounts")
    async def capital_accounts(_=Depends(get_current_user)) -> Dict[str, Any]:
        await _seed()
        receipts = await db.capital_receipts.find({}, {"_id": 0}).to_list(500)
        entries = await db.capital_ledger.find({}, {"_id": 0}).sort("at", -1).to_list(1000)
        members = []
        for m in CAPITAL_MEMBERS:
            contributed = round(sum(
                r["amount_usd"] for r in receipts
                if r["received_from"] == m["member"] and "capital" in r["purpose"].lower()), 2)
            holdbacks = round(sum(e["amount_usd"] for e in entries
                                  if e["member"] == m["member"] and e["entry_type"] == "holdback"), 2)
            withdrawals = round(sum(e["amount_usd"] for e in entries
                                    if e["member"] == m["member"] and e["entry_type"] == "withdrawal"), 2)
            members.append({
                **m, "contributed_usd": contributed,
                "remaining_commitment_usd": round(max(0, m["commitment_usd"] - contributed), 2),
                "holdbacks_usd": holdbacks, "withdrawals_usd": withdrawals,
                "balance_usd": round(contributed + holdbacks - withdrawals, 2),
            })
        return {"members": members,
                "total_committed": round(sum(m["commitment_usd"] for m in CAPITAL_MEMBERS), 2),
                "total_paid_in": round(sum(m["contributed_usd"] for m in members), 2),
                "total_balance": round(sum(m["balance_usd"] for m in members), 2),
                "ledger": entries[:50]}

    @cap.post("/entries")
    async def add_capital_entry(payload: CapitalEntryIn,
                                user=Depends(require_role("admin", "dispatcher"))) -> Dict[str, Any]:
        names = [m["member"] for m in CAPITAL_MEMBERS]
        if payload.member not in names:
            raise HTTPException(422, f"member must be one of {names}")
        if payload.entry_type not in ENTRY_TYPES:
            raise HTTPException(422, f"entry_type must be one of {list(ENTRY_TYPES)}")
        if payload.amount_usd <= 0:
            raise HTTPException(422, "amount_usd must be positive")
        receipt_no = None
        if payload.entry_type == "contribution":
            r = {"received_from": payload.member, "amount_usd": round(payload.amount_usd, 2),
                 "method": "Cash / Direct Transfer",
                 "purpose": "Capital contribution — commitment installment (Agreement §2.1)",
                 "credited_to": f"Member capital account — {payload.member} (33⅓% interest)",
                 "notes": payload.notes, "receipt_no": await _next_no(),
                 "received_at": datetime.now(timezone.utc).isoformat(),
                 "issued_by_name": "Oliver Cummins — Operator / Principal Broker",
                 "issued_by": getattr(user, "user_id", None)}
            await db.capital_receipts.insert_one(dict(r))
            receipt_no = r["receipt_no"]
        elif payload.entry_type == "withdrawal":
            acct = await capital_accounts()
            member = next(m for m in acct["members"] if m["member"] == payload.member)
            if payload.amount_usd > member["balance_usd"]:
                raise HTTPException(409, f"Withdrawal exceeds {payload.member}'s capital balance "
                                         f"(${member['balance_usd']:,.2f}) — unanimous consent + Agreement §3.4 limits apply")
        entry = {"entry_id": f"CAP-{datetime.now(timezone.utc).strftime('%y%m%d%H%M%S')}",
                 "at": datetime.now(timezone.utc).isoformat(), "member": payload.member,
                 "entry_type": payload.entry_type, "amount_usd": round(payload.amount_usd, 2),
                 "notes": payload.notes, "receipt_no": receipt_no,
                 "by": getattr(user, "user_id", None)}
        await db.capital_ledger.insert_one(dict(entry))
        entry.pop("_id", None)
        return {"ok": True, **entry}

    api_router.include_router(router)
    api_router.include_router(cap)
    logger.info("Receipts register + Capital Accounts registered (/api/receipts, /api/capital)")
