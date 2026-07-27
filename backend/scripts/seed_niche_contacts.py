"""One-time seeder: contact intel for the MN niche-market board (public research, 2026-07)."""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
NOW = datetime.now(timezone.utc).isoformat()
VERIFY = "Seeded from public research (LinkedIn/company sources, Jul 2026). Email is a pattern-based guess — verify before sending."

# name -> intel. Anchors have real publicly-listed people; bench rows get sourcing intel only.
ANCHORS = {
    "The Toro Company": {
        "contact_name": "Steve Abiadal", "contact_title": "Sr. Director, Global Logistics",
        "contact_email": "steve.abiadal@toro.com", "contact_phone": "(952) 888-8801 (HQ)",
        "company_domain": "toro.com", "email_pattern": "first.last@toro.com",
        "alt_contacts": "Kevin Carpenter — Chief Supply Chain Officer",
    },
    "Summit Brewing Co": {
        "contact_name": "Donavan Moon", "contact_title": "Shipping / Transportation Manager",
        "contact_email": "donavan.moon@summitbrewing.com", "contact_phone": "(651) 265-7800 (HQ)",
        "company_domain": "summitbrewing.com", "email_pattern": "first.last@summitbrewing.com",
        "alt_contacts": "Stuart Johnson — VP Business Operations (brewing, packaging, logistics)",
    },
    "Bobcat Company": {
        "contact_name": "Daniel Jamison", "contact_title": "Director, Supply Chain & Logistics",
        "contact_email": "daniel.jamison@doosan.com", "contact_phone": "(701) 241-8700 (Fargo ops)",
        "company_domain": "bobcat.com / doosan.com", "email_pattern": "first.last@doosan.com",
        "alt_contacts": "",
    },
    "Land O'Lakes": {
        "contact_name": "Nicholas Najjar", "contact_title": "Sr. Director, Warehousing (prev. Dir. Distribution Planning & Transportation)",
        "contact_email": "nicholas.najjar@landolakes.com", "contact_phone": "(651) 375-2222 (HQ)",
        "company_domain": "landolakes.com", "email_pattern": "first.last@landolakes.com",
        "alt_contacts": "Ken Hoover — Chief Supply Chain Officer",
    },
    "Medtronic": {
        "contact_name": "Kelton Graham", "contact_title": "Director, Americas Transportation",
        "contact_email": "kelton.graham@medtronic.com", "contact_phone": "(763) 514-4000 (Ops HQ)",
        "company_domain": "medtronic.com", "email_pattern": "first.last@medtronic.com",
        "alt_contacts": "Jason Lunde — Sr. Director Global Transportation · Kim Minne — Director of Logistics",
    },
    "Cargill": {
        "contact_name": "Randy Brown", "contact_title": "VP, Cargill Transportation & Logistics — North America",
        "contact_email": "randy_brown@cargill.com", "contact_phone": "(952) 742-7575 (HQ)",
        "company_domain": "cargill.com", "email_pattern": "first_last@cargill.com (underscore)",
        "alt_contacts": "",
    },
    "Target Corporation": {
        "contact_name": "Meaghan Juettner", "contact_title": "VP, Global Transportation",
        "contact_email": "meaghan.juettner@target.com", "contact_phone": "(612) 304-6073 (HQ)",
        "company_domain": "target.com", "email_pattern": "first.last@target.com",
        "alt_contacts": "Jeff England — EVP, Chief Global Supply Chain & Logistics Officer",
    },
    "Best Buy": {
        "contact_name": "Nate Omann", "contact_title": "Director, Supply Chain & Transportation",
        "contact_email": "nate.omann@bestbuy.com", "contact_phone": "(612) 291-1000 (HQ)",
        "company_domain": "bestbuy.com", "email_pattern": "first.last@bestbuy.com",
        "alt_contacts": "Chuck Dow — Director of Logistics",
    },
    "General Mills": {
        "contact_name": "Phillip West", "contact_title": "Sr. Director, North America Logistics",
        "contact_email": "phillip.west@genmills.com", "contact_phone": "(763) 764-7600 (HQ)",
        "company_domain": "generalmills.com (email: genmills.com)", "email_pattern": "first.last@genmills.com",
        "alt_contacts": "",
    },
}

BENCH_DOMAINS = {
    "Abbott (St. Jude Medical campus)": "abbott.com",
    "Boston Scientific": "bostonscientific.com",
    "Teleflex (Vascular Solutions)": "teleflex.com",
    "Surmodics": "surmodics.com",
    "Tactile Medical": "tactilemedical.com",
    "Hormel Foods": "hormel.com",
    "Schwan's Company": "schwans.com",
    "Post Consumer Brands": "postconsumerbrands.com",
    "Digi-Key Electronics": "digikey.com",
    "Honeywell": "honeywell.com",
    "3M": "mmm.com",
    "TD SYNNEX": "tdsynnex.com",
    "McKesson (regional DC)": "mckesson.com",
    "Cardinal Health (regional hub)": "cardinalhealth.com",
    "Upsher-Smith Laboratories": "upsher-smith.com",
    "Padagis": "padagis.com",
    "CNH Industrial (Benson plant)": "cnh.com",
    "Ziegler CAT": "zieglercat.com",
    "Daikin Applied": "daikinapplied.com",
    "Amazon (MSP fulfillment)": "amazon.com (Relay: relay.amazon.com)",
    "Fleet Farm": "fleetfarm.com",
    "Surly Brewing": "surlybrewing.com",
    "Indeed Brewing": "indeedbrewing.com",
    "Bent Paddle Brewing": "bentpaddle.com",
    "Fulton Beer": "fultonbeer.com",
    "CHS Inc": "chsinc.com",
    "AGCO (Jackson plant)": "agcocorp.com",
    "RDO Equipment (Deere dealer network)": "rdoequipment.com",
    "Hawkins Inc": "hawkinsinc.com",
    "Ecolab": "ecolab.com",
    "Brenntag Great Lakes": "brenntag.com",
    "Univar Solutions": "univarsolutions.com",
    "Sappi North America (Cloquet mill)": "sappi.com",
    "Packaging Corp of America (Int'l Falls)": "packagingcorp.com",
    "Smurfit Westrock (regional)": "smurfitwestrock.com",
    "Liberty Packaging": "libertypackaging.com",
}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rows = await db.niche_targets.find({}, {"_id": 0, "id": 1, "name": 1, "vertical": 1,
                                            "contact_name": 1, "last_touchpoint": 1}).to_list(500)
    anchors = bench = 0
    for r in rows:
        name = r["name"]
        li = f"{name.split('(')[0].strip()} transportation OR logistics director"
        if name in ANCHORS:
            a = ANCHORS[name]
            upd = {**a, "email_confidence": "pattern_guess",
                   "linkedin_search": li, "updated_at": NOW}
            if not r.get("last_touchpoint"):
                upd["last_touchpoint"] = VERIFY
                upd["last_touch_at"] = NOW
            await db.niche_targets.update_one({"id": r["id"]}, {"$set": upd})
            anchors += 1
        else:
            dom = BENCH_DOMAINS.get(name)
            if not dom:
                continue
            await db.niche_targets.update_one({"id": r["id"]}, {"$set": {
                "company_domain": dom, "email_pattern": f"first.last@{dom.split(' ')[0]} (verify w/ Hunter.io)",
                "linkedin_search": li, "email_confidence": "unsourced", "updated_at": NOW}})
            bench += 1
    print(f"seeded {anchors} anchors with named contacts, {bench} bench targets with sourcing intel")

asyncio.run(main())
