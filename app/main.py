from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import crawl, demo, drift, graph, heal, products
from app.config import settings
from app.db.base import Base
from app.db.migrations import ensure_product_timestamps
from app.db.session import engine
from app.scheduler.jobs import schedule_drift_checks
from app.services.llm import check_llm_health

DASHBOARD_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
SCREENSHOT_DIR = Path(settings.screenshot_dir).resolve()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_product_timestamps()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    scheduler = BackgroundScheduler()
    if settings.drift_check_interval_hours > 0:
        schedule_drift_checks(scheduler)
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="Self-Healing Demo Agent",
    description="Autonomous SaaS demo agent with self-healing knowledge graph",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl.router)
app.include_router(graph.router)
app.include_router(drift.router)
app.include_router(heal.router)
app.include_router(demo.router)
app.include_router(products.router)

app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")
if DASHBOARD_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")


@app.get("/health")
def health():
    llm_health = check_llm_health()
    return {
        "status": "ok" if llm_health["status"] == "ok" else "degraded",
        "llm": llm_health,
        "scheduler": {
            "drift_check_interval_hours": settings.drift_check_interval_hours,
            "auto_heal_on_drift": settings.auto_heal_on_drift,
        },
        "dashboard": "/ui" if DASHBOARD_DIR.exists() else None,
    }
