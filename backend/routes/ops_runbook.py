"""routes.ops_runbook — Layer 5: manual ops safety net.

Branded, downloadable runbook for running the brokerage with ALL automation down,
plus printable load sheets and a live emergency carrier contact list.
"""
import io
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen.canvas import Canvas

from routes.orisei_docs import build_branded_markdown_pdf

RUNBOOK_MD = """# Orisei Manual Operations Runbook

**Purpose.** If every automation layer is down — the AI broker desk, the backhaul hunter,
the load-board gateway, even this TMS — this document keeps freight moving. Print it.
Keep a copy in the office and one in each dispatcher's truck bag.

## Layer map (what fails, what takes over)

| Layer | Normal | If it's down |
| --- | --- | --- |
| AI Broker Autopilot | Sources, books & runs loads | Dispatchers work loads manually per §2 |
| Backhaul Hunter | Books returns automatically | Dispatcher calls boards for return loads per §3 |
| Load Board Gateway | DAT → Truckstop → Convoy → sim | Log in to board websites directly per §2.1 |
| Decision Engine | Ranks carriers by API | Use the printed carrier table + §4 checklist |
| This TMS | System of record | Paper load sheets (print weekly) + phone dispatch |

## 1 · Declare manual mode
1. Confirm outage: refresh the Command Center twice, 2 minutes apart.
2. Call the Operator (Oliver Cummins) — he declares MANUAL MODE.
3. Print the latest **Load Sheets PDF** (or use the last weekly printout).
4. Assign one dispatcher as **Board Watcher**, one as **Carrier Caller**.

## 2 · Manual load sourcing
### 2.1 Board logins (browser, not API)
- DAT One: power.dat.com — company login in the office password book.
- Truckstop: main.truckstop.com — same password book.
- Sort by origin state, filter equipment, target lanes from the printed lane table.

### 2.2 Qualify a load (60-second check)
- Rate ≥ lane minimum on the printed profit-per-lane table.
- Margin after carrier pay ≥ $150 (or Operator waiver).
- Pickup window achievable for an available driver.

## 3 · Manual carrier match & dispatch
1. Pull the printed **Emergency Carrier Contact List** (appended to this PDF).
2. Match: origin state in carrier's service states → equipment fits → weight under max.
3. Call the dispatcher; confirm driver name, CDL, cell, and ETA to shipper.
4. **Every load gets a driver on the BOL. No driver name, no dispatch.**
5. Fill a paper rate con (pad in the office safe) — load ID, lane, rate, driver — both parties sign by photo/text.

## 4 · Tracking & delivery (phone cadence)
- Driver texts photo of signed BOL at pickup — Carrier Caller logs time on the load sheet.
- Check calls every 4 hours in transit; note city + ETA on the sheet.
- POD photo within 2 hours of delivery; staple to the load sheet.
- Invoice manually from the POD (invoice pad, sequential numbers, copy to the ledger).

## 5 · Escalation ladder
1. Driver unreachable 2+ hours → call carrier dispatcher → call shipper with revised ETA.
2. Carrier no-show → next carrier on the printed match list; note the failure for scorecards.
3. Rate dispute → Operator only; nobody else negotiates.
4. Systems restored → back-enter every paper load into the TMS the same day.

## 6 · Weekly drill
Every Friday, print fresh load sheets and the contact list, and file last week's set.
Fifteen minutes of printing is the difference between an outage and a shutdown.
"""


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def build_ops_runbook_router(*, api_router, db, get_current_user):

    async def _contacts_md() -> str:
        rows = await db.dispatch_carriers.find({"is_active": True}, {"_id": 0}).to_list(100)
        lines = ["\n## Appendix A · Emergency Carrier Contact List (live snapshot)\n",
                 "| Carrier | MC | Dispatcher | Phone | Email | States |",
                 "| --- | --- | --- | --- | --- | --- |"]
        for c in rows:
            lines.append(f"| {c.get('legal_name', '')} | {c.get('mc_number', '')} | {c.get('contact_name', '')} "
                         f"| {c.get('contact_phone', '')} | {c.get('contact_email', '')} "
                         f"| {', '.join(c.get('service_states') or [])} |")
        drivers = await db.dispatch_drivers.find({"is_active": True}, {"_id": 0}).to_list(200)
        lines += ["\n## Appendix B · Driver Roster (live snapshot)\n",
                  "| Driver | CDL | Phone | Carrier | Home base |", "| --- | --- | --- | --- | --- |"]
        for d in drivers:
            lines.append(f"| {d.get('name', '')} | {d.get('cdl_number', '')} | {d.get('phone', '')} "
                         f"| {d.get('carrier_name', '')} | {d.get('home_base', '')} |")
        return "\n".join(lines)

    @api_router.get("/ops-runbook")
    async def runbook(_=Depends(get_current_user)) -> Dict[str, Any]:
        return {"markdown": RUNBOOK_MD, "generated_at": _now_str()}

    @api_router.get("/ops-runbook/pdf")
    async def runbook_pdf(_=Depends(get_current_user)) -> Response:
        md = RUNBOOK_MD + await _contacts_md()
        pdf = build_branded_markdown_pdf(md, title="Manual Operations Runbook",
                                         subtitle=f"Layer 5 Safety Net · Print & File · {_now_str()}")
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="Orisei_Manual_Ops_Runbook.pdf"'})

    @api_router.get("/ops-runbook/load-sheets.pdf")
    async def load_sheets(_=Depends(get_current_user)) -> Response:
        loads = await db.autopilot_loads.find({"stage": {"$nin": ["completed"]}}, {"_id": 0}).to_list(100)
        W, H = landscape(letter)
        buf = io.BytesIO()
        c = Canvas(buf, pagesize=landscape(letter))
        c.setFillColor(colors.HexColor("#0D1117")); c.rect(0, H - 60, W, 60, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 16); c.setFillColor(colors.white)
        c.drawString(40, H - 38, "ORISEI FREIGHT — PRINTABLE LOAD SHEET (MANUAL MODE)")
        c.setFont("Helvetica", 8.5); c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawString(40, H - 52, f"Snapshot {_now_str()} · {len(loads)} active loads · check-call every 4h · POD within 2h of delivery")
        cols = [("Load", 40), ("Lane", 105), ("Equip", 300), ("Stage", 360), ("Carrier / MC", 440),
                ("Driver / CDL", 590), ("Phone", 720), ("Rate", 800), ("BOL ✓  POD ✓", 855)]
        y = H - 84
        c.setFont("Helvetica-Bold", 8); c.setFillColor(colors.HexColor("#0D1117"))
        for label, x in cols:
            c.drawString(x, y, label)
        c.line(40, y - 4, W - 40, y - 4)
        y -= 18
        c.setFont("Helvetica", 7.5)
        for ld in loads:
            if y < 50:
                c.showPage(); y = H - 60; c.setFont("Helvetica", 7.5)
            drv = ld.get("driver") or {}
            ca = ld.get("carrier") or {}
            row = [(ld["load_id"], 40), (f"{ld['origin']} → {ld['dest']} ({ld['miles']}mi)", 105),
                   (ld["equipment"], 300), (ld["stage"], 360),
                   (f"{ca.get('name', '')[:22]} {ca.get('mc_number', '')}", 440),
                   (f"{drv.get('name', 'UNASSIGNED')} {drv.get('cdl_number', '')}", 590),
                   (drv.get("phone", ""), 720), (f"${ld['carrier_rate']:,.0f}", 800),
                   ("[  ]      [  ]", 855)]
            c.setFillColor(colors.HexColor("#0D1117"))
            for val, x in row:
                c.drawString(x, y, str(val)[:34])
            c.setStrokeColor(colors.HexColor("#E2E8F0")); c.line(40, y - 5, W - 40, y - 5)
            y -= 16
        c.save()
        return Response(content=buf.getvalue(), media_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="Orisei_Load_Sheets.pdf"'})
