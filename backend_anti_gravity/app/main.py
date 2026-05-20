"""
main.py — ElectroInventory v3 FastAPI Application Entry Point.

Responsibilities:
  - FastAPI app instantiation with OpenAPI metadata.
  - Async lifespan: database initialisation, seed data, cleanup.
  - Enterprise CORS policy for React frontend consumers.
  - Global exception handlers and structured logging.
  - API v1 router registration.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from .api import auth, copilot, inventory, logistics

from .api import procurement

from .core.config import settings
from .core.database import AsyncSessionLocal, init_db
from .api import returns


# ── Seed Helpers ─────────────────────────────────────────────────────────────
async def _seed_roles() -> None:
    """Ensure the three canonical roles exist in the database."""
    from .models.auth import Role
    from sqlalchemy import select

    roles_to_seed = [
        ("SYS_ADMIN", "Full platform access — all read/write operations"),
        ("PROCUREMENT_MGR", "Manage suppliers, orders, and inventory adjustments"),
        ("RETURN_APPROVER", "Approve or decline customer return requests"),
    ]
    async with AsyncSessionLocal() as db:
        for name, desc in roles_to_seed:
            result = await db.execute(select(Role).where(Role.role_code == name))
            if not result.scalar_one_or_none():
                db.add(Role(role_code=name, role_name=name, role_description=desc))
        await db.commit()
    logger.info("Roles seeded successfully.")


async def _seed_cities() -> None:
    """Ensure the five serviceable cities exist in the database."""
    from .models.logistics import ServiceableCity
    from sqlalchemy import select

    cities = [
        ("Delhi", "Delhi"), ("Mumbai", "Maharashtra"),
        ("Bangalore", "Karnataka"), ("Jaipur", "Rajasthan"), ("Kolkata", "West Bengal"),
    ]
    async with AsyncSessionLocal() as db:
        for city_name, state in cities:
            result = await db.execute(select(ServiceableCity).where(ServiceableCity.city_name == city_name))
            if not result.scalar_one_or_none():
                db.add(ServiceableCity(city_name=city_name, state=state))
        await db.commit()
    logger.info("Serviceable cities seeded successfully.")


async def _seed_kpis() -> None:
    """Seed KPI definitions for frontend tooltip cards."""
    from .models.analytics import KpiDefinition
    from sqlalchemy import select

    kpis = [
        ("TOTAL_REVENUE", "Total Revenue", "Sum of all sale amounts in INR", "SUM(sales.total_amount)", "INR", None, None, True, "Finance"),
        ("STOCKOUT_RATE", "Stockout Rate", "Percentage of SKUs currently out of stock", "OUT_OF_STOCK_SKUS / TOTAL_SKUS × 100", "%", 5.0, 15.0, False, "Inventory"),
        ("AVG_LEAD_TIME", "Avg Lead Time", "Average supplier lead time across all active suppliers", "AVG(suppliers.avg_lead_time_days)", "days", 10.0, 20.0, False, "Procurement"),
        ("RETURN_RATE", "Return Rate", "Percentage of sold units returned by customers", "RETURNS / SALES × 100", "%", 8.0, 15.0, False, "Returns"),
        ("ON_TIME_DELIVERY", "On-Time Delivery Rate", "Fraction of shipments delivered on or before expected date", "ON_TIME / TOTAL_SHIPMENTS × 100", "%", 85.0, 70.0, True, "Logistics"),
        ("AVG_FRAUD_SCORE", "Avg Fraud Score", "Average ML fraud score across all pending returns", "AVG(returns.fraud_score)", "score", 0.35, 0.65, False, "Returns"),
        ("INVENTORY_TURNOVER", "Inventory Turnover", "How many times inventory is sold/replaced in a period", "COGS / AVG_INVENTORY_VALUE", "ratio", 4.0, 2.0, True, "Inventory"),
        ("PENDING_ORDERS", "Pending Purchase Orders", "Count of purchase orders in DRAFT or APPROVED state", "COUNT(PO WHERE status IN DRAFT,APPROVED)", "units", 10, 20, False, "Procurement"),
    ]
    async with AsyncSessionLocal() as db:
        for kpi_code, display_name, desc, formula, unit, warn, crit, higher, cat in kpis:
            result = await db.execute(select(KpiDefinition).where(KpiDefinition.kpi_code == kpi_code))
            if not result.scalar_one_or_none():
                db.add(KpiDefinition(
                    kpi_code=kpi_code, kpi_name=display_name, description=desc,
                    formula=formula, unit=unit, warning_threshold=warn,
                    critical_threshold=crit, higher_is_better=higher, kpi_category=cat,
                ))
        await db.commit()
    logger.info("KPI definitions seeded successfully.")


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Runs startup tasks (DB init, seed) and cleanup on shutdown.
    """
    logger.info(f"Starting ElectroInventory v3 API — env={settings.environment}")
    await init_db()
    await _seed_roles()
    await _seed_cities()
    await _seed_kpis()
    logger.info("Startup complete. API is ready to serve requests.")
    yield
    logger.info("Shutdown initiated. Closing database connections.")


# ── Application Factory ───────────────────────────────────────────────────────
app = FastAPI(
    title="ElectroInventory v3 — Enterprise Supply Chain API",
    description=(
        "Production-grade FastAPI backend powering the ElectroInventory supply chain platform. "
        "Features: JWT RBAC authentication, async SQLAlchemy ORM, ML intelligence layer "
        "(Prophet, XGBoost, Isolation Forest, VADER/DistilBERT), and a guardrailed LLM copilot."
    ),
    version="3.0.0",
    contact={"name": "ElectroInventory Engineering", "email": "api@electroinventory.io"},
    license_info={"name": "Proprietary"},
    openapi_tags=[
        {"name": "Authentication", "description": "JWT login, registration, and RBAC management"},
        {"name": "Inventory",      "description": "Products, stock levels, movements ledger, ABC analysis"},
        {"name": "Procurement",    "description": "Suppliers, purchase orders, vendor ranking, decisions"},
        {"name": "Logistics",      "description": "Shipment tracking, cost estimation, delay analysis"},
        {"name": "Returns",        "description": "AI-assisted return approval workflow"},
        {"name": "AI Copilot",     "description": "Natural language LLM copilot with guardrailed reasoning"},
    ],
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://id-preview--98ca6d99-eeb9-4d89-8bde-5b4c9e71d47b.lovable.app",
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def _request_timing_middleware(request: Request, call_next):
    """Attaches processing time header to every response for performance monitoring."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time"] = f"{elapsed}ms"
    logger.debug(f"{request.method} {request.url.path} → {response.status_code} ({elapsed}ms)")
    return response


# ── Global Exception Handlers ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — returns structured JSON error."""
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again or contact support.",
            "type": type(exc).__name__,
        },
    )


# ── API v1 Router Registration ────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router,        prefix=API_PREFIX)
app.include_router(inventory.router,   prefix=API_PREFIX)
app.include_router(procurement.router, prefix=API_PREFIX)
app.include_router(logistics.router,   prefix=API_PREFIX)
app.include_router(returns.router,     prefix=API_PREFIX)
app.include_router(copilot.router,     prefix=API_PREFIX)


# ── Health & System Endpoints ─────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Lightweight health check for load balancers and orchestration monitors."""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "environment": settings.environment,
    }


@app.get("/api/v1/system/info", tags=["System"])
async def system_info():
    """Return non-sensitive system configuration metadata."""
    return {
        "app_name": "ElectroInventory v3",
        "api_version": "v1",
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "serviceable_cities": settings.serviceable_cities,
        "current_year": settings.current_year,
    }


# ── Dev Server Entry Point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
        access_log=True,
    )
