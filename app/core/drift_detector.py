import json
import uuid
from dataclasses import dataclass, field

from playwright.sync_api import Page, sync_playwright
from sqlalchemy.orm import Session

from app.config import settings
from app.core.crawler import CrawlCredentials
from app.models.drift_log import DriftLog
from app.models.node import Node
from app.models.product import Product
from app.services.diff import visual_diff_score
from app.services.llm import get_llm_service
from app.services.screenshot import ScreenshotService


@dataclass
class DriftEvent:
    node_id: str
    url: str
    title: str | None
    visual_diff_score: float
    diff_method: str
    semantic_diff: dict
    is_meaningful: bool
    drift_log_id: str
    fresh_screenshot_path: str


@dataclass
class DriftResult:
    product_id: str | None
    nodes_checked: int
    nodes_skipped: int
    nodes_drifted: int
    nodes_meaningful: int
    threshold: float
    events: list[DriftEvent] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)


class DriftDetector:
    COSMETIC_TYPES = {"cosmetic", "cosmetic change", "cosmetic_change"}

    def __init__(self, db: Session):
        self.db = db
        self.screenshots = ScreenshotService()
        self.llm = get_llm_service()

    def run(
        self,
        product_id: str | None = None,
        threshold: float | None = None,
    ) -> DriftResult:
        threshold = threshold if threshold is not None else settings.drift_visual_threshold
        query = self.db.query(Node)
        if product_id:
            query = query.filter(Node.product_id == uuid.UUID(product_id))

        nodes = query.all()
        events: list[DriftEvent] = []
        skipped: list[dict] = []
        nodes_checked = 0

        products = {p.id: p for p in self.db.query(Product).all()}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()
            logged_in_products: set[uuid.UUID] = set()

            for node in nodes:
                product = products.get(node.product_id)
                if not node.screenshot_path or not self.screenshots.exists(node.screenshot_path):
                    skipped.append(
                        {
                            "node_id": str(node.id),
                            "url": node.url,
                            "reason": "missing_baseline_screenshot",
                        }
                    )
                    continue

                if product and product.id not in logged_in_products:
                    self._maybe_login(page, product)
                    logged_in_products.add(product.id)

                nodes_checked += 1
                try:
                    page.goto(node.url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1000)
                    fresh_path = self.screenshots.save_drift_bytes(
                        node.product_id,
                        node.id,
                        page.screenshot(full_page=False),
                    )
                except Exception as exc:
                    skipped.append(
                        {
                            "node_id": str(node.id),
                            "url": node.url,
                            "reason": f"navigation_failed: {exc}",
                        }
                    )
                    continue

                score, method = visual_diff_score(node.screenshot_path, fresh_path)
                if score <= threshold:
                    continue

                semantic = self._semantic_diff(node.screenshot_path, fresh_path, score)
                is_meaningful = self._is_meaningful(semantic)
                semantic["is_meaningful"] = is_meaningful
                semantic["needs_healing"] = is_meaningful

                drift_log = DriftLog(
                    node_id=node.id,
                    visual_diff_score=score,
                    semantic_diff=json.dumps(semantic),
                    healed=False,
                )
                self.db.add(drift_log)
                self.db.flush()

                events.append(
                    DriftEvent(
                        node_id=str(node.id),
                        url=node.url,
                        title=node.title,
                        visual_diff_score=score,
                        diff_method=method,
                        semantic_diff=semantic,
                        is_meaningful=is_meaningful,
                        drift_log_id=str(drift_log.id),
                        fresh_screenshot_path=fresh_path,
                    )
                )

            browser.close()

        self.db.commit()

        return DriftResult(
            product_id=product_id,
            nodes_checked=nodes_checked,
            nodes_skipped=len(skipped),
            nodes_drifted=len(events),
            nodes_meaningful=sum(1 for e in events if e.is_meaningful),
            threshold=threshold,
            events=events,
            skipped=skipped,
        )

    def _semantic_diff(self, old_path: str, new_path: str, score: float) -> dict:
        try:
            result = self.llm.compare_screenshots(old_path, new_path, score)
            result["llm_source"] = "llm"
            return result
        except Exception as exc:
            return {
                "changes": "Semantic analysis unavailable",
                "change_type": "unknown",
                "affected_flows": [],
                "severity": "unknown",
                "llm_source": "fallback",
                "llm_error": str(exc)[:500],
            }

    def _is_meaningful(self, semantic: dict) -> bool:
        change_type = str(semantic.get("change_type", "")).strip().lower()
        severity = str(semantic.get("severity", "")).strip().lower()

        if change_type in self.COSMETIC_TYPES:
            return False
        if "cosmetic" in change_type and severity == "low":
            return False
        if severity == "low" and not semantic.get("affected_flows"):
            return False
        return True

    def _maybe_login(self, page: Page, product: Product) -> None:
        if not product.login_url or not product.credentials:
            return

        creds = CrawlCredentials(
            username=product.credentials.get("username"),
            password=product.credentials.get("password"),
            username_selector=product.credentials.get(
                "username_selector",
                'input[type="email"], input[name="email"], input[name="username"]',
            ),
            password_selector=product.credentials.get("password_selector", 'input[type="password"]'),
            submit_selector=product.credentials.get(
                "submit_selector", 'button[type="submit"], input[type="submit"]'
            ),
        )
        page.goto(product.login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        if creds.username:
            page.locator(creds.username_selector).first.fill(creds.username)
        if creds.password:
            page.locator(creds.password_selector).first.fill(creds.password)
        page.locator(creds.submit_selector).first.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)

    @staticmethod
    def serialize_result(result: DriftResult) -> dict:
        return {
            "status": "completed",
            "product_id": result.product_id,
            "nodes_checked": result.nodes_checked,
            "nodes_skipped": result.nodes_skipped,
            "nodes_drifted": result.nodes_drifted,
            "nodes_meaningful": result.nodes_meaningful,
            "threshold": result.threshold,
            "events": [
                {
                    "node_id": event.node_id,
                    "url": event.url,
                    "title": event.title,
                    "visual_diff_score": event.visual_diff_score,
                    "diff_method": event.diff_method,
                    "semantic_diff": event.semantic_diff,
                    "is_meaningful": event.is_meaningful,
                    "needs_healing": event.is_meaningful,
                    "drift_log_id": event.drift_log_id,
                    "fresh_screenshot_path": event.fresh_screenshot_path,
                }
                for event in result.events
            ],
            "skipped": result.skipped,
        }
