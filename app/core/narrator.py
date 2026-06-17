"""Demo narrator — implemented in Week 4."""

from sqlalchemy.orm import Session

from app.core.graph_builder import GraphBuilder
from app.services.llm import get_llm_service


class DemoNarrator:
    def __init__(self, db: Session):
        self.db = db
        self.graph = GraphBuilder(db)
        self.llm = get_llm_service()

    def generate_demo(self, product_id: str, persona: str) -> dict:
        return {
            "status": "not_implemented",
            "message": "Demo narration will be available in Week 4",
            "product_id": product_id,
            "persona": persona,
        }
