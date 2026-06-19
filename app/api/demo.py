import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.narrator import DemoNarrator
from app.db.session import get_db
from app.models.product import Product

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoRequest(BaseModel):
    product_id: str
    persona: str = "Technical decision maker evaluating the product"
    execute: bool = True


@router.post("")
def generate_demo(request: DemoRequest, db: Session = Depends(get_db)):
    try:
        uuid.UUID(request.product_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid product_id UUID") from exc

    narrator = DemoNarrator(db)
    try:
        result = narrator.generate_demo(
            product_id=request.product_id,
            persona=request.persona,
            execute=request.execute,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Demo generation failed: {exc}") from exc

    return DemoNarrator.serialize_result(result)
