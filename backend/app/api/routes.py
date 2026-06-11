"""API routes. All processing is request-scoped and in-memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.config import Settings, get_settings
from app.data_processing.cleaning import clean
from app.data_processing.loader import CSVValidationError, load_csv
from app.data_processing.metrics import compute_metrics
from app.models.schemas import (
    AnalyzeResponse,
    CleaningSummary,
    HealthResponse,
    ReportResult,
)
from app.services.report_generator import generate_report

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.version,
        report_enabled=settings.report_enabled,
    )


@router.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(..., description="Shopify-like order export (CSV)"),
    include_report: bool = Query(True, description="Set false for metrics-only (no LLM call)"),
    settings: Settings = Depends(get_settings),
) -> AnalyzeResponse:
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit.",
        )

    try:
        df, mapping = load_csv(content, max_rows=settings.max_rows)
    except CSVValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        del content  # raw upload is no longer needed; only the DataFrame lives on

    df, cleaning = clean(df)
    if df.empty:
        raise HTTPException(
            status_code=422,
            detail="No valid rows remained after cleaning. Check dates and amount columns.",
        )

    metrics = compute_metrics(df)
    del df  # row-level data is done; only aggregates continue

    if include_report:
        report = generate_report(metrics, settings)
    else:
        report = ReportResult(generated=False, error=None)

    return AnalyzeResponse(
        cleaning=CleaningSummary(
            rows_received=cleaning.rows_received,
            rows_after_cleaning=cleaning.rows_after_cleaning,
            duplicates_removed=cleaning.duplicates_removed,
            rows_dropped_invalid=cleaning.rows_dropped_invalid,
            columns_mapped=mapping,
        ),
        metrics=metrics,
        report=report,
    )
