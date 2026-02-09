"""
FastAPI application for FPlan v2.

Provides REST API endpoints for:
- Asset management (CRUD)
- Loan management (CRUD)
- Revenue streams (CRUD)
- Financial projections
- Portfolio analysis
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from fplan_v2.db.connection import get_engine, init_db
from fplan_v2.api.routes import assets, loans, revenue_streams, projections, historical_measurements, cash_flows, demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    is_serverless = bool(os.getenv("VERCEL"))
    if not is_serverless:
        # Startup: Initialize database connection (tables pre-created on Vercel)
        print("Initializing database connection...")
        init_db()
    yield
    if not is_serverless:
        # Shutdown: Close database connections
        print("Shutting down...")
        engine = get_engine()
        engine.dispose()


# Create FastAPI application
app = FastAPI(
    title="FPlan v2 API",
    description="Financial Planning Application - Portfolio Management and Projections API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS configuration for React frontend
_default_origins = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:3041,http://localhost:5173,http://localhost:8501"
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "type": type(exc).__name__,
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """API health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "service": "fplan-api",
    }


# Include routers
app.include_router(assets.router, prefix="/api/assets", tags=["Assets"])
app.include_router(loans.router, prefix="/api/loans", tags=["Loans"])
app.include_router(revenue_streams.router, prefix="/api/revenue-streams", tags=["Revenue Streams"])
app.include_router(projections.router, prefix="/api/projections", tags=["Projections"])
app.include_router(historical_measurements.router, prefix="/api/historical-measurements", tags=["Historical Measurements"])
app.include_router(cash_flows.router, prefix="/api/cash-flows", tags=["Cash Flows"])
app.include_router(demo.router, prefix="/api/demo", tags=["Demo"])


# Root endpoint
@app.get("/")
async def root() -> Dict[str, Any]:
    """API root endpoint with service information."""
    return {
        "service": "FPlan v2 API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "fplan_v2.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
