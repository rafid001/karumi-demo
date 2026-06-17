import uuid

from sqlalchemy.orm import Session

from app.models.edge import Edge
from app.models.node import Node
from app.models.product import Product


class GraphBuilder:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_product(
        self,
        name: str,
        base_url: str,
        login_url: str | None = None,
        credentials: dict | None = None,
    ) -> Product:
        product = (
            self.db.query(Product)
            .filter(Product.base_url == base_url.rstrip("/"))
            .first()
        )
        if product:
            return product

        product = Product(
            name=name,
            base_url=base_url.rstrip("/"),
            login_url=login_url,
            credentials=credentials,
        )
        self.db.add(product)
        self.db.flush()
        return product

    def upsert_node(
        self,
        product_id: uuid.UUID,
        url: str,
        title: str | None,
        screenshot_path: str | None,
        html_snapshot: str | None,
        elements: list[dict],
        metadata: dict,
    ) -> Node:
        normalized_url = url.rstrip("/")
        node = (
            self.db.query(Node)
            .filter(Node.product_id == product_id, Node.url == normalized_url)
            .first()
        )
        if node:
            node.title = title or node.title
            node.screenshot_path = screenshot_path or node.screenshot_path
            node.html_snapshot = html_snapshot
            node.elements = elements
            node.metadata_ = {**(node.metadata_ or {}), **metadata}
            return node

        node = Node(
            product_id=product_id,
            url=normalized_url,
            title=title,
            screenshot_path=screenshot_path,
            html_snapshot=html_snapshot,
            elements=elements,
            metadata_=metadata,
        )
        self.db.add(node)
        self.db.flush()
        return node

    def add_edge(
        self,
        from_node_id: uuid.UUID,
        to_node_id: uuid.UUID,
        trigger: str | None = None,
        metadata: dict | None = None,
    ) -> Edge | None:
        if from_node_id == to_node_id:
            return None

        existing = (
            self.db.query(Edge)
            .filter(
                Edge.from_node_id == from_node_id,
                Edge.to_node_id == to_node_id,
            )
            .first()
        )
        if existing:
            return existing

        edge = Edge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            trigger=trigger,
            metadata_=metadata or {},
        )
        self.db.add(edge)
        self.db.flush()
        return edge

    def get_graph(self, product_id: uuid.UUID) -> dict:
        nodes = self.db.query(Node).filter(Node.product_id == product_id).all()
        node_ids = {n.id for n in nodes}
        edges = (
            self.db.query(Edge)
            .filter(Edge.from_node_id.in_(node_ids), Edge.to_node_id.in_(node_ids))
            .all()
        )

        return {
            "product_id": str(product_id),
            "nodes": [self._serialize_node(n) for n in nodes],
            "edges": [self._serialize_edge(e) for e in edges],
        }

    def get_all_graphs(self) -> list[dict]:
        products = self.db.query(Product).all()
        return [self.get_graph(p.id) for p in products]

    @staticmethod
    def _serialize_node(node: Node) -> dict:
        return {
            "id": str(node.id),
            "url": node.url,
            "title": node.title,
            "screenshot_path": node.screenshot_path,
            "elements": node.elements or [],
            "metadata": node.metadata_ or {},
            "created_at": node.created_at.isoformat() if node.created_at else None,
            "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        }

    @staticmethod
    def _serialize_edge(edge: Edge) -> dict:
        return {
            "id": str(edge.id),
            "from_node_id": str(edge.from_node_id),
            "to_node_id": str(edge.to_node_id),
            "trigger": edge.trigger,
            "metadata": edge.metadata_ or {},
        }
