import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.drift_detector import DriftDetector
from app.db.session import get_db
from app.models.drift_log import DriftLog
from app.models.node import Node

router = APIRouter(prefix="/drift", tags=["drift"])


@router.get("")
def run_drift_detection(
    product_id: str | None = Query(None, description="Limit drift check to one product"),
    threshold: float | None = Query(None, description="Visual diff threshold (0-1)"),
    db: Session = Depends(get_db),
):
    if product_id:
        try:
            uuid.UUID(product_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid product_id UUID") from exc

    detector = DriftDetector(db)
    try:
        result = detector.run(product_id=product_id, threshold=threshold)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Drift detection failed: {exc}") from exc

    return DriftDetector.serialize_result(result)


@router.get("/logs")
def list_drift_logs(
    product_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(DriftLog).join(Node, DriftLog.node_id == Node.id).order_by(DriftLog.detected_at.desc())
    if product_id:
        try:
            pid = uuid.UUID(product_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid product_id UUID") from exc
        query = query.filter(Node.product_id == pid)

    logs = query.limit(limit).all()
    return {
        "count": len(logs),
        "logs": [
            {
                "id": str(log.id),
                "node_id": str(log.node_id),
                "node_url": log.node.url if log.node else None,
                "node_title": log.node.title if log.node else None,
                "detected_at": log.detected_at.isoformat() if log.detected_at else None,
                "visual_diff_score": log.visual_diff_score,
                "semantic_diff": log.semantic_diff,
                "healed": log.healed,
                "healed_at": log.healed_at.isoformat() if log.healed_at else None,
            }
            for log in logs
        ],
    }
