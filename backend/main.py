from datetime import datetime, timezone
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.catalog import router as catalog_router
from app.routes.customers import router as customers_router
from app.routes.imports import router as imports_router
from app.routes.inventory import router as inventory_router
from app.routes.orders import router as orders_router
from app.routes.organisations import router as organisations_router
from app.routes.rossmann import router as rossmann_router
from app.routes.simulation import router as simulation_router

app = FastAPI(
    title="FLASHCORE",
    description=(
        "Retail analytics and high-concurrency "
        "inventory simulation platform powered by "
        "authentic Rossmann historical store data."
    ),
    version="1.0.0",
)

# Restrict browser access to explicitly approved frontend origins.
# Locally defaults to Vite; production origins are supplied by the environment.
frontend_origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
allowed_origins = [
    origin.strip().rstrip("/")
    for origin in frontend_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Idempotency-Key",
        "X-Organisation-Id",
    ],
)

app.include_router(auth_router)
app.include_router(organisations_router)
app.include_router(admin_router)
app.include_router(rossmann_router)
app.include_router(simulation_router)
app.include_router(imports_router)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(orders_router)


@app.get("/")
def root():
    return {
        "project": "FLASHCORE",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
        )

    return {
        "status": "connected",
    }


@app.get("/api/health")
def api_system_health():
    db_status = "connected"
    services = [
        {
            "name": "FastAPI Application",
            "status": "healthy",
            "detail": "Operational (v1.0.0)",
        },
    ]
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            services.append({
                "name": "PostgreSQL Database",
                "status": "healthy",
                "detail": "Connected",
            })
    except Exception:
        db_status = "unavailable"
        services.append({
            "name": "PostgreSQL Database",
            "status": "unhealthy",
            "detail": "Database unavailable",
        })

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "1.0.0",
        "database": "PostgreSQL" if db_status == "connected" else "Unavailable",
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/health/database")
def api_database_health():
    return database_health()
