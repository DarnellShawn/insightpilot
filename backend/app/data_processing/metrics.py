"""KPI computation on cleaned order data.

This module is also the privacy boundary: `compute_metrics` returns only
aggregates (totals, rates, top-N lists). No row-level data, emails, or customer
identifiers leave this layer — which is exactly what gets sent to the LLM.
"""

from __future__ import annotations

import pandas as pd

from app.models.schemas import Metrics, MonthlyRevenue, TopProduct

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def compute_metrics(df: pd.DataFrame) -> Metrics:
    paid = df[df["financial_status"] != "refunded"] if "financial_status" in df.columns else df
    refunded = df[df["financial_status"] == "refunded"] if "financial_status" in df.columns else df.iloc[0:0]

    total_revenue = float(df["total"].sum())
    refunded_revenue = float(refunded["total"].sum())
    net_revenue = float(paid["total"].sum())

    orders = paid.groupby("order_id").agg(
        revenue=("total", "sum"),
        created_at=("created_at", "min"),
    )
    total_orders = len(orders)
    aov = float(orders["revenue"].mean()) if total_orders else 0.0
    total_units = int(paid["quantity"].sum()) if "quantity" in paid.columns else len(paid)

    # Customer metrics (computed on IDs in memory; only aggregates are returned)
    if "customer_id" in paid.columns and paid["customer_id"].notna().any():
        per_customer = paid.groupby("customer_id")["order_id"].nunique()
        unique_customers = int(per_customer.size)
        repeat_rate = float((per_customer > 1).mean() * 100) if unique_customers else 0.0
        avg_orders = float(per_customer.mean()) if unique_customers else 0.0
        revenue_per_customer = net_revenue / unique_customers if unique_customers else 0.0
    else:
        unique_customers, repeat_rate, avg_orders, revenue_per_customer = 0, 0.0, 0.0, 0.0

    discount_total = float(paid["total_discount"].sum()) if "total_discount" in paid.columns else 0.0
    gross = net_revenue + discount_total
    discount_share = (discount_total / gross * 100) if gross else 0.0

    monthly = (
        orders.assign(month=orders["created_at"].dt.strftime("%Y-%m"))
        .groupby("month")
        .agg(revenue=("revenue", "sum"), n=("revenue", "size"))
        .reset_index()
        .sort_values("month")
    )
    monthly_revenue = [
        MonthlyRevenue(month=r.month, revenue=round(float(r.revenue), 2), orders=int(r.n))
        for r in monthly.itertuples()
    ]
    best_month = max(monthly_revenue, key=lambda m: m.revenue) if monthly_revenue else None

    mom_growth = None
    if len(monthly_revenue) >= 2 and monthly_revenue[-2].revenue > 0:
        # Compare the last two *complete*-ish months as reported
        mom_growth = round(
            (monthly_revenue[-1].revenue - monthly_revenue[-2].revenue)
            / monthly_revenue[-2].revenue * 100, 1,
        )

    top_products: list[TopProduct] = []
    if "product_title" in paid.columns:
        prod = paid.groupby("product_title").agg(
            revenue=("total", "sum"),
            units=("quantity", "sum") if "quantity" in paid.columns else ("total", "size"),
            orders=("order_id", "nunique"),
        ).sort_values("revenue", ascending=False).head(10)
        top_products = [
            TopProduct(product=str(name), revenue=round(float(r.revenue), 2),
                       units=int(r.units), orders=int(r.orders))
            for name, r in zip(prod.index, prod.itertuples())
        ]

    def _share(col: str) -> dict[str, float]:
        if col not in paid.columns:
            return {}
        s = paid.groupby(col)["total"].sum().sort_values(ascending=False).head(10)
        return {str(k): round(float(v), 2) for k, v in s.items()}

    weekday_rev = (
        paid.assign(weekday=paid["created_at"].dt.day_name())
        .groupby("weekday")["total"].sum()
    )
    revenue_by_weekday = {d: round(float(weekday_rev.get(d, 0.0)), 2) for d in WEEKDAYS}

    hours = paid["created_at"].dt.hour
    peak_hour = int(hours.mode().iloc[0]) if not hours.empty else None

    refund_rate = (refunded_revenue / total_revenue * 100) if total_revenue else 0.0

    return Metrics(
        period_start=df["created_at"].min().strftime("%Y-%m-%d"),
        period_end=df["created_at"].max().strftime("%Y-%m-%d"),
        total_revenue=round(total_revenue, 2),
        net_revenue=round(net_revenue, 2),
        refunded_revenue=round(refunded_revenue, 2),
        refund_rate_pct=round(refund_rate, 2),
        total_orders=total_orders,
        total_units=total_units,
        average_order_value=round(aov, 2),
        unique_customers=unique_customers,
        repeat_customer_rate_pct=round(repeat_rate, 2),
        avg_orders_per_customer=round(avg_orders, 2),
        revenue_per_customer=round(revenue_per_customer, 2),
        discount_share_pct=round(discount_share, 2),
        revenue_mom_growth_pct=mom_growth,
        best_month=best_month,
        monthly_revenue=monthly_revenue,
        top_products=top_products,
        revenue_by_channel=_share("sales_channel"),
        revenue_by_country=_share("country"),
        revenue_by_weekday=revenue_by_weekday,
        peak_hour=peak_hour,
    )


def to_llm_payload(metrics: Metrics) -> dict:
    """The exact data allowed to reach the LLM: aggregates only.

    Kept as an explicit function so the privacy boundary is visible and testable.
    """
    return metrics.model_dump()
