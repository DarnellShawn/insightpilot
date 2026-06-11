"""In-memory cleaning of canonical order data."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class CleaningReport:
    rows_received: int
    rows_after_cleaning: int
    duplicates_removed: int
    rows_dropped_invalid: int


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """Coerce types, repair what's repairable, drop what isn't.

    Rules:
    - exact duplicate rows are dropped
    - dates parsed; rows with unparseable dates dropped
    - numerics coerced; missing `total` recomputed from qty * price - discount
      when possible, otherwise the row is dropped
    - text fields trimmed and lower-cased where they are categorical
    """
    rows_received = len(df)
    df = df.copy()

    before = len(df)
    df = df.drop_duplicates()
    duplicates_removed = before - len(df)

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", format="mixed")

    for col in ("quantity", "unit_price", "total_discount", "total"):
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".", regex=False).str.strip(),
                errors="coerce",
            )

    if "quantity" in df.columns:
        df["quantity"] = df["quantity"].fillna(1).clip(lower=1)
    if "total_discount" in df.columns:
        df["total_discount"] = df["total_discount"].fillna(0.0)

    # Recompute missing totals when line-item economics are available
    if {"quantity", "unit_price"}.issubset(df.columns):
        computable = df["total"].isna() & df["unit_price"].notna()
        discount = df["total_discount"] if "total_discount" in df.columns else 0.0
        df.loc[computable, "total"] = (
            df.loc[computable, "quantity"] * df.loc[computable, "unit_price"]
            - (discount[computable] if hasattr(discount, "__getitem__") else 0.0)
        ).round(2)

    for col in ("financial_status", "sales_channel", "country"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower().replace({"nan": np.nan, "": np.nan})

    if "country" in df.columns:
        df["country"] = df["country"].str.upper().fillna("UNKNOWN")
    if "financial_status" in df.columns:
        df["financial_status"] = df["financial_status"].fillna("paid")
    if "sales_channel" in df.columns:
        df["sales_channel"] = df["sales_channel"].fillna("unknown")

    before = len(df)
    df = df.dropna(subset=["created_at", "total", "order_id"])
    df = df[df["total"] >= 0]
    rows_dropped_invalid = before - len(df)

    df = df.sort_values("created_at").reset_index(drop=True)
    report = CleaningReport(
        rows_received=rows_received,
        rows_after_cleaning=len(df),
        duplicates_removed=duplicates_removed,
        rows_dropped_invalid=rows_dropped_invalid,
    )
    return df, report
