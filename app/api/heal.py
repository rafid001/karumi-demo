import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.healer import Healer, drift_log_needs_healing, parse_semantic_diff
from app.db.session import get_db
from app.models.drift_log import DriftLog

router = APIRouter(prefix="/heal", tags=["heal"])


@router.post("")
def heal_all_pending(db: Session = Depends(get_db)):
    healer = Healer(db)
    result = healer.heal_all_pending()
    return Healer.serialize_batch(result)


@router.post("/{drift_log_id}")
def heal_drift_log(drift_log_id: str, db: Session = Depends(get_db)):
    try:
        uuid.UUID(drift_log_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid drift_log_id UUID") from exc

    healer = Healer(db)
    result = healer.heal(drift_log_id)
    if result.status == "failed" and result.detail == "Drift log not found":
        raise HTTPException(status_code=404, detail=result.detail)
    return Healer.serialize_result(result)


@router.get("/pending")
def list_pending_healing(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(DriftLog)
        .filter(DriftLog.healed.is_(False))
        .order_by(DriftLog.detected_at.desc())
        .limit(limit)
        .all()
    )
    pending = [log for log in logs if drift_log_needs_healing(log)]
    return {
        "count": len(pending),
        "logs": [
            {
                "id": str(log.id),
                "node_id": str(log.node_id),
                "node_url": log.node.url if log.node else None,
                "detected_at": log.detected_at.isoformat() if log.detected_at else None,
                "visual_diff_score": log.visual_diff_score,
                "needs_healing": True,
                "semantic_diff": parse_semantic_diff(log.semantic_diff),
            }
            for log in pending
        ],
    }
