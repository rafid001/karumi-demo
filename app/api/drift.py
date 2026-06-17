from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.drift_detector import DriftDetector
from app.db.session import get_db

router = APIRouter(prefix="/drift", tags=["drift"])


@router.get("")
def run_drift_detection(
    product_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    detector = DriftDetector(db)
    return detector.run(product_id=product_id)
