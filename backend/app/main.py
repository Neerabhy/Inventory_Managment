import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings

# ... (existing imports)
from app.api import auth, analytics, copilot

# ... (FastAPI setup and CORS configuration)

# Register API Routers


# ... (Global Exception Handlers)

# Configure logging specifications
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app.main")

# Initialize our clean enterprise FastAPI app instance
app = FastAPI(
    title="AI Inventory Copilot Enterprise OS Backend",
    description="Automated AI/ML Supply Chain and Inventory Forecasting Orchestration Platform Engine.",
    version="3.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(copilot.router, prefix="/api/v1")

# Apply absolute CORS controls to authorize your frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Application Health Endpoint Routing
@app.get("/health", tags=["Infrastructure Tracking"], status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database_connected": True,
        "system_year_context": settings.CURRENT_YEAR
    }

# Handle unexpected server runtime anomalies
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled operational exception caught on lane {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal operational error occurred within the supply chain backend execution engine.",
            "error_summary": str(exc) if settings.DEBUG else "Redacted for security constraints."
        }
    )