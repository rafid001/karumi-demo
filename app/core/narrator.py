import uuid
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from sqlalchemy.orm import Session

from app.config import settings
from app.core.crawler import CrawlCredentials, Crawler
from app.core.graph_builder import GraphBuilder
from app.models.node import Node
from app.models.product import Product
from app.services.llm import get_llm_service
from app.services.screenshot import ScreenshotService


@dataclass
class DemoStep:
    step: int
    node_id: str
    url: str
    title: str | None
    action: str
    narration: str
    action_result: str | None = None
    screenshot_path: str | None = None
    executed: bool = False


@dataclass
class DemoResult:
    run_id: str
    product_id: str
    product_name: str
    persona: str
    steps: list[DemoStep] = field(default_factory=list)


class DemoNarrator:
    def __init__(self, db: Session):
        self.db = db
        self.graph = GraphBuilder(db)
        self.llm = get_llm_service()
        self.screenshots = ScreenshotService()

    def generate_demo(self, product_id: str, persona: str, execute: bool = True) -> DemoResult:
        pid = uuid.UUID(product_id)
        product = self.db.query(Product).filter(Product.id == pid).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        graph = self.graph.get_graph(pid)
        if not graph["nodes"]:
            raise ValueError("Knowledge graph is empty — run a crawl first")

        raw_steps = self.llm.generate_demo_path(graph, persona)
        node_map = {n["id"]: n for n in graph["nodes"]}
        run_id = str(uuid.uuid4())

        planned_steps = self._normalize_steps(raw_steps, node_map, graph["nodes"])
        if not planned_steps:
            raise ValueError("LLM returned no valid demo steps")

        if execute:
            executed_steps = self._execute_demo(product, planned_steps, run_id)
        else:
            executed_steps = [
                DemoStep(
                    step=i + 1,
                    node_id=s["node_id"],
                    url=s["url"],
                    title=s.get("title"),
                    action=s["action"],
                    narration=s["narration"],
                    executed=False,
                )
                for i, s in enumerate(planned_steps)
            ]

        return DemoResult(
            run_id=run_id,
            product_id=product_id,
            product_name=product.name,
            persona=persona,
            steps=executed_steps,
        )

    def _normalize_steps(
        self, raw_steps: list[dict], node_map: dict[str, dict], all_nodes: list[dict]
    ) -> list[dict]:
        normalized: list[dict] = []
        seen: set[str] = set()

        for step in raw_steps:
            node_id = str(step.get("node_id", ""))
            node = node_map.get(node_id)
            if not node and all_nodes:
                node = all_nodes[min(len(normalized), len(all_nodes) - 1)]
                node_id = node["id"]
            if not node or node_id in seen:
                continue
            seen.add(node_id)
            normalized.append(
                {
                    "node_id": node_id,
                    "url": node["url"],
                    "title": node.get("title"),
                    "elements": node.get("elements") or [],
                    "action": step.get("action") or "Review this page",
                    "narration": step.get("narration") or "",
                }
            )
        return normalized

    def _execute_demo(self, product: Product, steps: list[dict], run_id: str) -> list[DemoStep]:
        results: list[DemoStep] = []
        credentials = Crawler(db=self.db)._credentials_from_product(product)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            if credentials and product.login_url:
                self._login(page, product.login_url, credentials)

            for i, step in enumerate(steps):
                demo_step = DemoStep(
                    step=i + 1,
                    node_id=step["node_id"],
                    url=step["url"],
                    title=step.get("title"),
                    action=step["action"],
                    narration=step["narration"],
                )
                try:
                    page.goto(step["url"], wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1000)
                    demo_step.action_result = self._execute_action(page, step["elements"], step["action"])
                    screenshot_path = self._save_demo_screenshot(
                        product.id, run_id, i + 1, page.screenshot(full_page=False)
                    )
                    demo_step.screenshot_path = screenshot_path
                    demo_step.executed = True
                except Exception as exc:
                    demo_step.action_result = f"Step failed: {exc}"
                    demo_step.executed = False

                results.append(demo_step)

            browser.close()

        return results

    def _execute_action(self, page: Page, elements: list[dict], action: str) -> str:
        action_lower = action.lower()

        for el in elements:
            text = (el.get("text") or "").strip()
            if not text or len(text) < 2:
                continue
            if text.lower() in action_lower or action_lower in text.lower():
                try:
                    tag = el.get("tag", "")
                    if tag == "a" and el.get("href"):
                        link = page.locator(f"a[href='{el['href']}']").first
                        if link.count():
                            link.click()
                            page.wait_for_load_state("domcontentloaded")
                            page.wait_for_timeout(800)
                            return f"Clicked link: {text}"
                    target = page.get_by_role("link", name=text).first
                    if target.count():
                        target.click()
                        page.wait_for_load_state("domcontentloaded")
                        page.wait_for_timeout(800)
                        return f"Clicked: {text}"
                    target = page.get_by_text(text, exact=False).first
                    if target.count():
                        target.click()
                        page.wait_for_timeout(800)
                        return f"Clicked: {text}"
                except Exception:
                    continue

        return "Reviewed page (no matching interactive element found)"

    def _save_demo_screenshot(
        self, product_id: uuid.UUID, run_id: str, step: int, data: bytes
    ) -> str:
        demo_dir = Path(settings.screenshot_dir) / str(product_id) / "demo" / run_id
        demo_dir.mkdir(parents=True, exist_ok=True)
        path = demo_dir / f"step_{step}.png"
        path.write_bytes(data)
        return str(path)

    def _login(self, page: Page, login_url: str, credentials: CrawlCredentials) -> None:
        page.goto(login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(500)
        if credentials.username:
            page.locator(credentials.username_selector).first.fill(credentials.username)
        if credentials.password:
            page.locator(credentials.password_selector).first.fill(credentials.password)
        page.locator(credentials.submit_selector).first.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)

    @staticmethod
    def serialize_result(result: DemoResult) -> dict:
        screenshot_base = Path(settings.screenshot_dir).resolve()

        def screenshot_url(path: str | None) -> str | None:
            if not path or not Path(path).exists():
                return None
            try:
                rel = Path(path).resolve().relative_to(screenshot_base)
                return f"/screenshots/{rel.as_posix()}"
            except ValueError:
                return None

        return {
            "run_id": result.run_id,
            "product_id": result.product_id,
            "product_name": result.product_name,
            "persona": result.persona,
            "steps": [
                {
                    "step": s.step,
                    "node_id": s.node_id,
                    "url": s.url,
                    "title": s.title,
                    "action": s.action,
                    "narration": s.narration,
                    "action_result": s.action_result,
                    "screenshot_path": s.screenshot_path,
                    "screenshot_url": screenshot_url(s.screenshot_path),
                    "executed": s.executed,
                }
                for s in result.steps
            ],
        }
