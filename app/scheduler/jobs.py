from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.core.drift_detector import DriftDetector
from app.core.healer import Healer
from app.db.session import SessionLocal


def run_drift_and_heal() -> None:
    db = SessionLocal()
    try:
        detector = DriftDetector(db)
        result = detector.run()
        if settings.auto_heal_on_drift and result.nodes_meaningful > 0:
            healer = Healer(db)
            healer.heal_all_pending()
    finally:
        db.close()


def schedule_drift_checks(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        run_drift_and_heal,
        trigger=IntervalTrigger(hours=settings.drift_check_interval_hours),
        id="drift_check_and_heal",
        replace_existing=True,
    )
