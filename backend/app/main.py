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

# Register semua domain models supaya SQLAlchemy mapper bisa resolve relationship
# cross-domain (mis. User.employee → Employee). Tanpa ini muncul
# InvalidRequestError saat query pertama yang trigger mapper config.
from app.identity import models as _identity_models  # noqa: F401
from app.organization import models as _organization_models  # noqa: F401
from app.assessment import models as _assessment_models  # noqa: F401
from app.project import models as _project_models  # noqa: F401
from app.outsource import models as _outsource_models  # noqa: F401
from app.payroll import models as _payroll_models  # noqa: F401
from app.sales import models as _sales_models  # noqa: F401
from app.hiring import models as _hiring_models  # noqa: F401
from app.onboarding import models as _onboarding_models  # noqa: F401
from app.separation import models as _separation_models  # noqa: F401
from app.finance import models as _finance_models  # noqa: F401
from app.notification import models as _notification_models  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan — startup/shutdown hooks."""
    # Startup
    print(f"🚀 {settings.app_name} v{__version__} starting in {settings.app_env}")

    # TSK-059 — Alert Rules Engine scheduler (daily 06:00 WIB)
    scheduler_started = False
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        from app.database import async_session_factory
        from app.notification.alert_rules import run_all_alert_rules

        async def _scheduled_alerts():
            async with async_session_factory() as session:
                try:
                    await run_all_alert_rules(session)
                except Exception as e:  # noqa: BLE001
                    print(f"⚠ Alert Rules Engine error: {e}")

        scheduler = AsyncIOScheduler()
        # Cron: setiap hari 06:00 Asia/Jakarta time
        scheduler.add_job(
            _scheduled_alerts,
            CronTrigger(hour=6, minute=0, timezone="Asia/Jakarta"),
            id="alert_rules_daily",
            replace_existing=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        scheduler_started = True
        print("⏰ Alert Rules scheduler ON — daily 06:00 WIB")
    except ImportError:
        print("⚠ APScheduler tidak terinstall — alert rules manual only")
        print("   Install: pip install apscheduler")
    except Exception as e:  # noqa: BLE001
        print(f"⚠ Scheduler setup failed: {e}")

    yield

    # Shutdown
    if scheduler_started and hasattr(app.state, "scheduler"):
        try:
            app.state.scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass

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
from app.organization.router import router as organization_router
from app.hiring.offer_router import router as hiring_offer_router
from app.hiring.router import router as hiring_router
from app.onboarding.router import router as onboarding_router
from app.separation.router import router as separation_router
from app.payroll.leave_router import router as leave_router
from app.assessment.router import router as assessment_router
from app.project.router import router as project_router
from app.project.document_router import router as project_document_router
from app.project.cr_router import router as project_cr_router
from app.outsource.router import router as outsource_router, public_router as outsource_public_router
from app.payroll.reimbursement_router import router as reimb_proc_router
from app.payroll.attendance_router import router as attendance_router
from app.payroll.payroll_router import router as payroll_router
from app.payroll.thr_router import router as thr_router
from app.sales.router import router as sales_router
from app.dashboard.router import router as dashboard_router
from app.finance.router import router as finance_router
from app.notification.admin_router import router as notification_admin_router
from app.notification.router import router as notification_router

app.include_router(identity_router, prefix="/api/v1")
app.include_router(identity_admin_router, prefix="/api/v1")
app.include_router(organization_router, prefix="/api/v1")  # M1.2 TSK-013
app.include_router(hiring_router, prefix="/api/v1")  # M1.2 TSK-015
app.include_router(hiring_offer_router, prefix="/api/v1")  # M1.3 TSK-034 — offer letter
app.include_router(onboarding_router, prefix="/api/v1")  # M1.2 TSK-016
app.include_router(separation_router, prefix="/api/v1")  # M1.2 TSK-017
app.include_router(leave_router, prefix="/api/v1")  # M1.2 TSK-019
app.include_router(assessment_router, prefix="/api/v1")  # M2.1 TSK-021
app.include_router(project_router, prefix="/api/v1")  # M2.1 TSK-022
app.include_router(project_document_router, prefix="/api/v1")  # M2.1 TSK-068
app.include_router(project_cr_router, prefix="/api/v1")  # M2.1 TSK-070
app.include_router(outsource_router, prefix="/api/v1")  # M2.3 TSK-100
app.include_router(outsource_public_router, prefix="/api/v1")  # M2.3 TSK-108 public KPI
app.include_router(reimb_proc_router, prefix="/api/v1")  # M2.2 TSK-023
app.include_router(payroll_router, prefix="/api/v1")  # M1.4 TSK-046
app.include_router(attendance_router, prefix="/api/v1")  # M1.4 TSK-047 — attendance input
app.include_router(thr_router, prefix="/api/v1")  # M1.4 TSK-053 — THR processing
app.include_router(sales_router, prefix="/api/v1")  # M3.1 TSK-024
app.include_router(dashboard_router, prefix="/api/v1")  # M3.2 TSK-025
app.include_router(finance_router, prefix="/api/v1")  # TSK-022C — invoice moved from project
app.include_router(notification_router, prefix="/api/v1")  # M1.4 TSK-057 — in-app notification
app.include_router(notification_admin_router, prefix="/api/v1")  # M1.4 TSK-059 + TSK-061

# Sprint 2+ (EP-02): app.include_router(employees_router, prefix="/api/v1")
# (etc. per roadmap milestone)
