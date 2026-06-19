import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.drift_detector import DriftDetector
from app.core.healer import Healer
from app.db.session import get_db
from app.models.node import Node
from app.models.product import Product

router = APIRouter(prefix="/products", tags=["products"])


def _serialize_product(product: Product, node_count: int, last_node_update) -> dict:
    last_crawled = product.last_crawled_at or last_node_update
    return {
        "id": str(product.id),
        "name": product.name,
        "base_url": product.base_url,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "last_crawled_at": last_crawled.isoformat() if last_crawled else None,
        "last_checked_at": product.last_checked_at.isoformat() if product.last_checked_at else None,
        "node_count": node_count,
    }


@router.get("")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    node_stats = {
        row.product_id: (row.node_count, row.last_updated)
        for row in db.query(
            Node.product_id,
            func.count(Node.id).label("node_count"),
            func.max(Node.updated_at).label("last_updated"),
        )
        .group_by(Node.product_id)
        .all()
    }

    return {
        "count": len(products),
        "products": [
            _serialize_product(
                p,
                node_stats.get(p.id, (0, None))[0],
                node_stats.get(p.id, (0, None))[1],
            )
            for p in products
        ],
    }


@router.post("/{product_id}/recheck")
def recheck_product(
    product_id: str,
    threshold: float | None = Query(None, description="Visual diff threshold (0-1)"),
    auto_heal: bool | None = Query(None, description="Auto-heal meaningful drift after detection"),
    db: Session = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID") from exc

    product = db.query(Product).filter(Product.id == pid).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    detector = DriftDetector(db)
    try:
        result = detector.run(product_id=product_id, threshold=threshold)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Re-check failed: {exc}") from exc

    product.last_checked_at = datetime.now(timezone.utc)
    db.commit()

    response = DriftDetector.serialize_result(result)
    response["product_id"] = product_id
    response["product_name"] = product.name
    response["nodes_unchanged"] = max(0, result.nodes_checked - result.nodes_drifted)

    should_heal = auto_heal if auto_heal is not None else settings.auto_heal_on_drift
    if should_heal and result.nodes_meaningful > 0:
        healer = Healer(db)
        drift_log_ids = [event.drift_log_id for event in result.events if event.is_meaningful]
        healing = healer.heal_logs(drift_log_ids)
        response["healing"] = Healer.serialize_batch(healing)

    return response
