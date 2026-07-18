"""One-time idempotent Stripe catalog setup for Hot Shot TMS SaaS tiers."""
import os

import stripe
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CATALOG = [
    {"emergent_product_id": "hotshot_starter", "name": "Hot Shot TMS — Starter (Founder Rate)",
     "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "hotshot_starter_monthly", "amount": 39000, "currency": "usd", "interval": "month"}]},
    {"emergent_product_id": "hotshot_growth", "name": "Hot Shot TMS — Growth (Founder Rate)",
     "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "hotshot_growth_monthly", "amount": 97500, "currency": "usd", "interval": "month"}]},
    {"emergent_product_id": "hotshot_dwy", "name": "Hot Shot TMS — Done-With-You (Founder Rate)",
     "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "hotshot_dwy_monthly", "amount": 260000, "currency": "usd", "interval": "month"}]},
]


def ensure_tax_settings():
    s = stripe.tax.Settings.retrieve()
    if s.head_office and getattr(s.head_office, "address", None):
        return
    stripe.tax.Settings.modify(
        head_office={"address": {"country": "US", "line1": "100 Washington Ave S",
                                 "city": "Minneapolis", "state": "MN", "postal_code": "55401"}},
        defaults={"tax_behavior": "exclusive"},
    )


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(name=entry["name"], tax_code=entry.get("tax_code"),
                                 metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]})


def main():
    ensure_tax_settings()
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for p in entry["prices"]:
            existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
            if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
                stripe.Price.modify(existing[0].id, active=False)
                existing = []
            if not existing:
                kwargs = dict(product=product.id, unit_amount=p["amount"], currency=p["currency"],
                              lookup_key=p["lookup_key"], transfer_lookup_key=True)
                if p.get("interval"):
                    kwargs["recurring"] = {"interval": p["interval"]}
                stripe.Price.create(**kwargs)
            print(f"OK {entry['name']} :: {p['lookup_key']} ${p['amount']/100:.2f}/{p.get('interval','once')}")


if __name__ == "__main__":
    main()
