"""CSV loading with flexible column mapping for Shopify-like exports.

Real merchant exports vary: Shopify's order export, app exports, and hand-edited
sheets all name columns differently. We normalize headers and map them onto a
canonical schema so the rest of the pipeline works with one set of names.
"""

from __future__ import annotations

import io

import pandas as pd

# Canonical column -> accepted normalized header aliases (lowercase, stripped of
# spaces/underscores/hyphens). First match wins.
COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id": ["orderid", "ordernumber", "name", "order", "id"],
    "created_at": ["createdat", "date", "orderdate", "processedat", "createddate"],
    "customer_id": ["customerid", "customer"],
    "customer_email": ["customeremail", "email", "buyeremail"],
    "product_title": ["producttitle", "lineitemname", "product", "itemname", "title"],
    "variant_title": ["varianttitle", "variant", "lineitemvariant"],
    "quantity": ["quantity", "lineitemquantity", "qty", "units"],
    "unit_price": ["unitprice", "lineitemprice", "price", "itemprice"],
    "total_discount": ["totaldiscount", "discountamount", "discount", "lineitemdiscount"],
    "total": ["total", "linetotal", "subtotal", "totalprice", "amount", "revenue"],
    "financial_status": ["financialstatus", "paymentstatus", "status"],
    "country": ["country", "shippingcountry", "billingcountry", "countrycode"],
    "sales_channel": ["saleschannel", "channel", "source", "sourcename"],
}

REQUIRED_COLUMNS = {"order_id", "created_at", "total"}


class CSVValidationError(ValueError):
    """Raised when an upload cannot be parsed into the canonical schema."""


def _normalize(header: str) -> str:
    return "".join(ch for ch in header.lower() if ch.isalnum())


def load_csv(content: bytes, max_rows: int) -> tuple[pd.DataFrame, dict[str, str]]:
    """Parse raw CSV bytes into a DataFrame with canonical column names.

    Returns the DataFrame and the applied {original_header: canonical_name} mapping.
    Everything stays in memory — `content` is never written to disk.
    """
    try:
        df = pd.read_csv(io.BytesIO(content), dtype=str, encoding="utf-8-sig")
    except Exception as exc:
        raise CSVValidationError(f"Could not parse file as CSV: {exc}") from exc

    if df.empty:
        raise CSVValidationError("The uploaded CSV contains no data rows.")
    if len(df) > max_rows:
        raise CSVValidationError(
            f"File has {len(df)} rows; the limit is {max_rows}. Split the export and retry."
        )

    mapping: dict[str, str] = {}
    used_canonical: set[str] = set()
    for original in df.columns:
        normalized = _normalize(str(original))
        for canonical, aliases in COLUMN_ALIASES.items():
            if canonical in used_canonical:
                continue
            if normalized in aliases:
                mapping[str(original)] = canonical
                used_canonical.add(canonical)
                break

    missing = REQUIRED_COLUMNS - used_canonical
    if missing:
        raise CSVValidationError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
            + ". Expected a Shopify-like order export with at least an order id, "
            "an order date, and a total amount."
        )

    df = df.rename(columns=mapping)
    return df[[c for c in COLUMN_ALIASES if c in df.columns]], mapping
