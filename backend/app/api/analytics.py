from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.auth import User
from app.models.analytics import KpiDefinition
from app.schemas.analytics import KpiMetadataResponse, DashboardKpiSummary

router = APIRouter(prefix="/analytics", tags=["Dashboard & Analytics"])

@router.get("/kpi-metadata", response_model=List[KpiMetadataResponse])
async def get_kpi_metadata(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches dynamic formulas and tooltips for dashboard KPI cards."""
    result = await db.execute(select(KpiDefinition))
    kpis = result.scalars().all()
    
    if not kpis:
        # Provide fallback metadata if database is unseeded
        return [
            KpiMetadataResponse(
                kpi_key="KPI_TOTAL_REVENUE",
                display_name="Total Revenue",
                formula_text="SUM(final_amount) WHERE status != Cancelled",
                description_summary="Gross revenue from all delivered orders.",
                critical_threshold=None
            )
        ]
    return kpis

@router.get("/dashboard/summary", response_model=List[DashboardKpiSummary])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculates and returns live metrics for the main control center."""
    # In a full deployment, these would aggregate actual DB tables.
    # We return mock structured shapes matching our enterprise schema.
    return [
        DashboardKpiSummary(
            kpi_key="KPI_TOTAL_REVENUE",
            display_name="Total Revenue",
            computed_value=12450000.0,
            variance_percentage=12.5,
            is_critical_alert=False
        ),
        DashboardKpiSummary(
            kpi_key="KPI_RETURN_RATE",
            display_name="Return Rate",
            computed_value=8.2,
            variance_percentage=-1.5,
            is_critical_alert=True  # E.g., crosses the 8.0% warning threshold
        )
    ]