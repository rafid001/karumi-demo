import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.crawler import Crawler
from app.core.graph_builder import GraphBuilder
from app.models.drift_log import DriftLog
from app.models.node import Node
from app.services.llm import get_llm_service


@dataclass
class HealingResult:
    drift_log_id: str
    node_id: str
    status: str
    nodes_refreshed: int = 0
    edges_updated: int = 0
    change_summary: str | None = None
    detail: str | None = None


@dataclass
class HealingBatchResult:
    healed: int
    skipped: int
    failed: int
    results: list[HealingResult] = field(default_factory=list)


def parse_semantic_diff(semantic_diff: str | None) -> dict:
    if not semantic_diff:
        return {}
    try:
        return json.loads(semantic_diff)
    except json.JSONDecodeError:
        return {}


def drift_log_needs_healing(log: DriftLog) -> bool:
    if log.healed:
        return False
    semantic = parse_semantic_diff(log.semantic_diff)
    return bool(semantic.get("needs_healing", semantic.get("is_meaningful", False)))


class Healer:
    def __init__(self, db: Session):
        self.db = db
        self.graph = GraphBuilder(db)
        self.crawler = Crawler(db)
        self.llm = get_llm_service()

    def heal(self, drift_log_id: str) -> HealingResult:
        try:
            log_uuid = uuid.UUID(drift_log_id)
        except ValueError:
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id="",
                status="failed",
                detail="Invalid drift_log_id UUID",
            )

        log = self.db.query(DriftLog).filter(DriftLog.id == log_uuid).first()
        if not log:
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id="",
                status="failed",
                detail="Drift log not found",
            )

        if log.healed:
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id=str(log.node_id),
                status="skipped",
                detail="Already healed",
            )

        if not drift_log_needs_healing(log):
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id=str(log.node_id),
                status="skipped",
                detail="needs_healing is false",
            )

        node = self.db.query(Node).filter(Node.id == log.node_id).first()
        if not node:
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id=str(log.node_id),
                status="failed",
                detail="Node not found",
            )

        neighbor_ids = self.graph.get_neighbor_node_ids(node.id)
        subgraph_node_ids = [node.id, *neighbor_ids]

        old_subgraph = self.graph.get_subgraph(subgraph_node_ids)

        try:
            refresh = self.crawler.refresh_nodes(node.product_id, subgraph_node_ids)
        except Exception as exc:
            return HealingResult(
                drift_log_id=drift_log_id,
                node_id=str(log.node_id),
                status="failed",
                detail=f"Re-exploration failed: {exc}",
            )

        new_subgraph = self.graph.get_subgraph(subgraph_node_ids)

        change_summary = None
        try:
            reconcile = self.llm.reconcile_subgraph(old_subgraph, new_subgraph)
            change_summary = reconcile.get("change_summary")
        except Exception as exc:
            change_summary = f"Graph updated via re-crawl (LLM reconcile unavailable: {exc})"

        semantic = parse_semantic_diff(log.semantic_diff)
        semantic["healing_summary"] = change_summary
        semantic["healed_subgraph"] = {
            "nodes_refreshed": refresh.nodes_refreshed,
            "edges_updated": refresh.edges_updated,
            "node_ids": refresh.node_ids,
        }

        log.semantic_diff = json.dumps(semantic)
        log.healed = True
        log.healed_at = datetime.now(timezone.utc)
        self.db.commit()

        return HealingResult(
            drift_log_id=drift_log_id,
            node_id=str(log.node_id),
            status="healed",
            nodes_refreshed=refresh.nodes_refreshed,
            edges_updated=refresh.edges_updated,
            change_summary=change_summary,
        )

    def heal_all_pending(self) -> HealingBatchResult:
        logs = (
            self.db.query(DriftLog)
            .filter(DriftLog.healed.is_(False))
            .order_by(DriftLog.detected_at.asc())
            .all()
        )
        return self._heal_logs(logs)

    def heal_logs(self, drift_log_ids: list[str]) -> HealingBatchResult:
        if not drift_log_ids:
            return HealingBatchResult(healed=0, skipped=0, failed=0)

        ids = []
        for drift_log_id in drift_log_ids:
            try:
                ids.append(uuid.UUID(drift_log_id))
            except ValueError:
                continue

        logs = (
            self.db.query(DriftLog)
            .filter(DriftLog.id.in_(ids), DriftLog.healed.is_(False))
            .order_by(DriftLog.detected_at.asc())
            .all()
        )
        return self._heal_logs(logs)

    def _heal_logs(self, logs: list[DriftLog]) -> HealingBatchResult:
        batch = HealingBatchResult(healed=0, skipped=0, failed=0)
        for log in logs:
            if not drift_log_needs_healing(log):
                continue

            result = self.heal(str(log.id))
            batch.results.append(result)
            if result.status == "healed":
                batch.healed += 1
            elif result.status == "skipped":
                batch.skipped += 1
            else:
                batch.failed += 1

        return batch

    @staticmethod
    def serialize_batch(result: HealingBatchResult) -> dict:
        return {
            "healed": result.healed,
            "skipped": result.skipped,
            "failed": result.failed,
            "results": [
                {
                    "drift_log_id": r.drift_log_id,
                    "node_id": r.node_id,
                    "status": r.status,
                    "nodes_refreshed": r.nodes_refreshed,
                    "edges_updated": r.edges_updated,
                    "change_summary": r.change_summary,
                    "detail": r.detail,
                }
                for r in result.results
            ],
        }

    @staticmethod
    def serialize_result(result: HealingResult) -> dict:
        return {
            "drift_log_id": result.drift_log_id,
            "node_id": result.node_id,
            "status": result.status,
            "nodes_refreshed": result.nodes_refreshed,
            "edges_updated": result.edges_updated,
            "change_summary": result.change_summary,
            "detail": result.detail,
        }
