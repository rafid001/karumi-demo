from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.narrator import DemoNarrator
from app.db.session import get_db

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoRequest(BaseModel):
    product_id: str
    persona: str = "Technical decision maker evaluating the product"


@router.post("")
def generate_demo(request: DemoRequest, db: Session = Depends(get_db)):
    narrator = DemoNarrator(db)
    return narrator.generate_demo(product_id=request.product_id, persona=request.persona)
