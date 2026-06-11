#!/usr/bin/env python3
"""Generate realistic Shopify-like order export CSVs for testing the pipeline.

Models real e-commerce behavior:
- 12 months of orders with weekly + seasonal (Q4/BFCM) demand patterns
- A power-law customer base (most buy once, a loyal tail buys repeatedly)
- A catalog with distinct price points, variants, and bestsellers
- Refunds, pending payments, discounts, and multiple sales channels
- Deliberate dirt (duplicate rows, missing values, inconsistent casing) so the
  cleaning layer has something to do

Usage:
    python3 scripts/generate_synthetic_data.py --rows 5000 --out data/shopify_orders.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

CATALOG = [
    # (product_title, variants, base_price, popularity_weight)
    ("Aurora Ceramic Mug", ["White / 350ml", "Black / 350ml", "Sage / 350ml"], 18.0, 10),
    ("Linen Throw Blanket", ["Natural", "Charcoal", "Rust"], 79.0, 6),
    ("Soy Wax Candle — Cedar", ["Single", "Set of 3"], 24.0, 9),
    ("Organic Cotton Tote", ["Cream", "Navy"], 15.0, 8),
    ("Walnut Serving Board", ["Small", "Large"], 54.0, 4),
    ("Stoneware Dinner Plate Set", ["Set of 4", "Set of 6"], 96.0, 3),
    ("Brass Pour-Over Stand", ["Standard"], 68.0, 2),
    ("Recycled Glass Vase", ["Amber", "Smoke"], 42.0, 5),
    ("Merino Wool Beanie", ["Oat", "Forest", "Black"], 32.0, 7),
    ("Botanical Print A3", ["Eucalyptus", "Fern", "Olive"], 28.0, 5),
]

CHANNELS = [("online_store", 0.72), ("instagram", 0.12), ("pos", 0.09), ("draft_order", 0.07)]
COUNTRIES = [("DE", 0.34), ("US", 0.22), ("GB", 0.14), ("FR", 0.10), ("NL", 0.08), ("AT", 0.07), ("CH", 0.05)]
FIRST_NAMES = ["emma", "liam", "mia", "noah", "lena", "paul", "sofia", "jonas", "clara", "felix",
               "anna", "max", "laura", "ben", "marie", "tom", "julia", "luis", "nina", "erik"]
LAST_NAMES = ["mueller", "schmidt", "fischer", "weber", "wagner", "becker", "hoffmann", "koch",
              "richter", "klein", "wolf", "neumann", "schwarz", "braun", "krueger", "hartmann"]


def weighted_choice(rng: random.Random, pairs):
    items, weights = zip(*pairs)
    return rng.choices(items, weights=weights, k=1)[0]


def seasonal_weight(day: datetime) -> float:
    """Demand multiplier: weekend lift, Q4 ramp, BFCM spike, January slump."""
    w = 1.0
    if day.weekday() >= 5:
        w *= 1.25
    month_factor = {1: 0.7, 2: 0.8, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.9,
                    7: 0.85, 8: 0.9, 9: 1.0, 10: 1.15, 11: 1.6, 12: 1.45}
    w *= month_factor[day.month]
    # Black Friday / Cyber Monday window (late November)
    if day.month == 11 and 24 <= day.day <= 30:
        w *= 2.2
    # Gentle year-over-year growth across the window
    w *= 1.0 + 0.35 * ((day - datetime(day.year, 1, 1)).days / 365.0)
    return w


def build_customers(rng: random.Random, n: int):
    """Power-law customer base: ~65% one-timers, a loyal tail with high order counts."""
    customers = []
    for i in range(n):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        # Pareto-ish propensity: most ~1, few up to 15+
        propensity = min(1 + int(rng.paretovariate(1.6)) - 1, 18)
        customers.append({
            "id": f"CUST-{i + 1:05d}",
            "email": f"{first}.{last}{rng.randint(1, 999)}@example.com",
            "propensity": propensity,
            "country": weighted_choice(rng, COUNTRIES),
        })
    return customers


def generate(rows: int, seed: int, end: datetime) -> list[dict]:
    rng = random.Random(seed)
    start = end - timedelta(days=365)
    customers = build_customers(rng, max(rows // 3, 50))

    # Pre-compute daily demand distribution over the window
    days = [start + timedelta(days=d) for d in range(366)]
    day_weights = [seasonal_weight(d) for d in days]

    records = []
    order_no = 1001
    while len(records) < rows:
        day = rng.choices(days, weights=day_weights, k=1)[0]
        hour = int(min(max(rng.gauss(15, 4), 0), 23))  # purchases peak mid-afternoon
        created_at = day.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))

        customer = rng.choices(customers, weights=[c["propensity"] for c in customers], k=1)[0]
        channel = weighted_choice(rng, CHANNELS)

        # 1-3 line items per order, skewed to 1
        n_items = rng.choices([1, 2, 3], weights=[68, 24, 8], k=1)[0]
        order_id = f"#{order_no}"
        order_no += 1

        # Order-level status: mostly paid, some refunded/pending
        status = rng.choices(["paid", "refunded", "pending"], weights=[91, 6, 3], k=1)[0]
        discount_order = rng.random() < (0.35 if day.month == 11 else 0.12)

        weights = [p[3] for p in CATALOG]
        for product, variants, base_price, _ in rng.choices(CATALOG, weights=weights, k=n_items):
            qty = rng.choices([1, 2, 3], weights=[80, 15, 5], k=1)[0]
            price = round(base_price * rng.uniform(0.97, 1.03), 2)
            discount = round(price * qty * rng.uniform(0.10, 0.25), 2) if discount_order else 0.0
            total = round(price * qty - discount, 2)
            records.append({
                "Order ID": order_id,
                "Created At": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Customer ID": customer["id"],
                "Customer Email": customer["email"],
                "Product Title": product,
                "Variant Title": rng.choice(variants),
                "Quantity": qty,
                "Unit Price": price,
                "Total Discount": discount,
                "Total": total,
                "Financial Status": status,
                "Country": customer["country"],
                "Sales Channel": channel,
            })
            if len(records) >= rows:
                break

    # Inject realistic dirt for the cleaning layer (~2% of rows)
    n_dirty = max(rows // 50, 5)
    for _ in range(n_dirty):
        records.append(dict(rng.choice(records)))  # exact duplicate rows
    for rec in rng.sample(records, n_dirty):
        rec["Country"] = ""  # missing values
    for rec in rng.sample(records, n_dirty):
        rec["Financial Status"] = rec["Financial Status"].upper()  # inconsistent casing
    for rec in rng.sample(records, max(n_dirty // 2, 2)):
        rec["Total"] = ""  # missing totals → must be recomputed or dropped

    records.sort(key=lambda r: r["Created At"])
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000, help="approx. number of line items")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/shopify_orders.csv"))
    args = parser.parse_args()

    end = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    records = generate(args.rows, args.seed, end)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    orders = len({r["Order ID"] for r in records})
    print(f"Wrote {len(records)} line items / {orders} orders to {args.out}")


if __name__ == "__main__":
    main()
