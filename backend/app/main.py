"""FastAPI application entry point.

Sprint 0 skeleton: health endpoint + CORS + basic structure.
Modul domain (identity, payroll, dst) akan di-register di sini per epic.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan — startup/shutdown hooks."""
    # Startup
    print(f"🚀 {settings.app_name} v{__version__} starting in {settings.app_env}")
    yield
    # Shutdown — close Redis connection
    from app.core.redis_client import close_redis

    await close_redis()
    print(f"👋 {settings.app_name} shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="IDEA Internal Portal — Backend API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Root endpoint — hello world."""
    return {
        "name": settings.app_name,
        "version": __version__,
        "env": settings.app_env,
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check endpoint — used by docker healthcheck + load balancer."""
    return {"status": "ok"}


# ─── Register domain routers ───────────────────────────────────
from app.identity.admin_router import router as identity_admin_router
from app.identity.router import router as identity_router

app.include_router(identity_router, prefix="/api/v1")
app.include_router(identity_admin_router, prefix="/api/v1")

# Sprint 2+ (EP-02): app.include_router(employees_router, prefix="/api/v1")
# (etc. per roadmap milestone)
