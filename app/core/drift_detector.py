"""Drift detection — implemented in Week 2."""

from sqlalchemy.orm import Session

from app.config import settings


class DriftDetector:
    def __init__(self, db: Session):
        self.db = db

    def run(self, product_id: str | None = None) -> dict:
        return {
            "status": "not_implemented",
            "message": "Drift detection will be available in Week 2",
            "threshold": settings.drift_visual_threshold,
        }
