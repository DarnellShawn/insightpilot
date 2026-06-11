"""Pydantic response models — the API contract shared with the frontend."""

from __future__ import annotations

from pydantic import BaseModel


class CleaningSummary(BaseModel):
    rows_received: int
    rows_after_cleaning: int
    duplicates_removed: int
    rows_dropped_invalid: int
    columns_mapped: dict[str, str]


class TopProduct(BaseModel):
    product: str
    revenue: float
    units: int
    orders: int


class MonthlyRevenue(BaseModel):
    month: str  # YYYY-MM
    revenue: float
    orders: int


class Metrics(BaseModel):
    period_start: str
    period_end: str
    total_revenue: float
    net_revenue: float
    refunded_revenue: float
    refund_rate_pct: float
    total_orders: int
    total_units: int
    average_order_value: float
    unique_customers: int
    repeat_customer_rate_pct: float
    avg_orders_per_customer: float
    revenue_per_customer: float
    discount_share_pct: float
    revenue_mom_growth_pct: float | None
    best_month: MonthlyRevenue | None
    monthly_revenue: list[MonthlyRevenue]
    top_products: list[TopProduct]
    revenue_by_channel: dict[str, float]
    revenue_by_country: dict[str, float]
    revenue_by_weekday: dict[str, float]
    peak_hour: int | None


class ReportResult(BaseModel):
    generated: bool
    model: str | None = None
    markdown: str | None = None
    error: str | None = None


class AnalyzeResponse(BaseModel):
    cleaning: CleaningSummary
    metrics: Metrics
    report: ReportResult


class HealthResponse(BaseModel):
    status: str
    version: str
    report_enabled: bool
