import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.graph_builder import GraphBuilder
from app.db.session import get_db

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
def get_graph(
    product_id: str | None = Query(None, description="Filter by product UUID"),
    db: Session = Depends(get_db),
):
    builder = GraphBuilder(db)

    if product_id:
        try:
            pid = uuid.UUID(product_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid product_id UUID") from exc
        return builder.get_graph(pid)

    graphs = builder.get_all_graphs()
    return {"graphs": graphs, "count": len(graphs)}
