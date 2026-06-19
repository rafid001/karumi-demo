import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright
from sqlalchemy.orm import Session

from app.config import settings
from app.core.graph_builder import GraphBuilder
from app.models.node import Node
from app.models.product import Product
from app.services.llm import get_llm_service
from app.services.llm_utils import fallback_page_analysis
from app.services.screenshot import ScreenshotService


@dataclass
class CrawlCredentials:
    username: str | None = None
    password: str | None = None
    username_selector: str = 'input[type="email"], input[name="email"], input[name="username"]'
    password_selector: str = 'input[type="password"]'
    submit_selector: str = 'button[type="submit"], input[type="submit"]'


@dataclass
class CrawlResult:
    product_id: uuid.UUID
    nodes_discovered: int
    edges_discovered: int
    pages_visited: list[str] = field(default_factory=list)


@dataclass
class PageExploreResult:
    node: Node
    discovered_links: list[str]


@dataclass
class RefreshResult:
    product_id: uuid.UUID
    nodes_refreshed: int
    edges_updated: int
    node_ids: list[str] = field(default_factory=list)


class Crawler:
    INTERACTIVE_SELECTORS = "a[href], button, input, select, textarea, [role='button'], [role='link']"

    def __init__(self, db: Session):
        self.db = db
        self.graph = GraphBuilder(db)
        self.screenshots = ScreenshotService()
        self.llm = get_llm_service()

    def crawl(
        self,
        url: str,
        product_name: str,
        credentials: CrawlCredentials | None = None,
        login_url: str | None = None,
        max_pages: int | None = None,
        max_depth: int | None = None,
        on_progress: Callable[[dict], None] | None = None,
    ) -> CrawlResult:
        max_pages = max_pages or settings.crawl_max_pages
        max_depth = max_depth or settings.crawl_max_depth
        base_url = self._normalize_origin(url)

        product = self.graph.get_or_create_product(
            name=product_name,
            base_url=base_url,
            login_url=login_url,
            credentials=credentials.__dict__ if credentials else None,
        )

        self._emit(
            on_progress,
            "started",
            product_id=str(product.id),
            url=url,
            max_pages=max_pages,
            max_depth=max_depth,
        )

        visited: set[str] = set()
        queue: list[tuple[str, int, uuid.UUID | None]] = [(url, 0, None)]
        pages_visited: list[str] = []
        edges_count = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            if credentials and login_url:
                self._login(page, login_url, credentials)

            while queue and len(visited) < max_pages:
                current_url, depth, from_node_id = queue.pop(0)
                normalized = self._normalize_url(current_url, base_url)
                if not normalized or normalized in visited or depth > max_depth:
                    continue
                if not self._same_origin(normalized, base_url):
                    continue

                visited.add(normalized)
                pages_visited.append(normalized)

                self._emit(
                    on_progress,
                    "page_crawling",
                    url=normalized,
                    nodes_so_far=len(visited),
                )

                result = self._process_page(
                    page=page,
                    product=product,
                    url=normalized,
                    base_url=base_url,
                    from_node_id=from_node_id,
                    depth=depth,
                    metadata_extra={"page_type": "discovered"},
                )
                if not result:
                    self._emit(
                        on_progress,
                        "page_failed",
                        url=normalized,
                        nodes_so_far=len(visited),
                    )
                    continue

                self._emit(
                    on_progress,
                    "page_crawled",
                    url=normalized,
                    title=result.node.title,
                    nodes_so_far=len(visited),
                )

                if from_node_id:
                    edge = self.graph.add_edge(
                        from_node_id=from_node_id,
                        to_node_id=result.node.id,
                        trigger="navigation",
                    )
                    if edge:
                        edges_count += 1

                for link_url in result.discovered_links:
                    if link_url not in visited:
                        queue.append((link_url, depth + 1, result.node.id))

            browser.close()

        product.last_crawled_at = datetime.now(timezone.utc)
        self.db.commit()

        result = CrawlResult(
            product_id=product.id,
            nodes_discovered=len(visited),
            edges_discovered=edges_count,
            pages_visited=pages_visited,
        )
        self._emit(
            on_progress,
            "done",
            product_id=str(result.product_id),
            nodes_discovered=result.nodes_discovered,
            edges_discovered=result.edges_discovered,
            pages_visited=result.pages_visited,
        )
        return result

    def refresh_nodes(self, product_id: uuid.UUID, node_ids: list[uuid.UUID]) -> RefreshResult:
        """Re-explore and update a fixed set of nodes (used by the healer)."""
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        nodes = self.db.query(Node).filter(Node.id.in_(node_ids)).all()
        if not nodes:
            return RefreshResult(product_id=product_id, nodes_refreshed=0, edges_updated=0)

        base_url = product.base_url
        target_urls = {self._normalize_url(n.url, base_url) or n.url.rstrip("/") for n in nodes}
        credentials = self._credentials_from_product(product)
        login_url = product.login_url

        url_to_node: dict[str, Node] = {}
        pending_edges: list[tuple[str, str]] = []
        edges_updated = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            if credentials and login_url:
                self._login(page, login_url, credentials)

            for node in nodes:
                normalized = self._normalize_url(node.url, base_url) or node.url.rstrip("/")
                result = self._process_page(
                    page=page,
                    product=product,
                    url=normalized,
                    base_url=base_url,
                    depth=node.metadata_.get("depth", 0) if node.metadata_ else 0,
                    metadata_extra={"page_type": "healed", "healed": True},
                )
                if not result:
                    continue

                url_to_node[result.node.url] = result.node
                for link_url in result.discovered_links:
                    if link_url in target_urls and link_url != result.node.url:
                        pending_edges.append((result.node.url, link_url))

            for from_url, to_url in pending_edges:
                from_node = url_to_node.get(from_url)
                to_node = url_to_node.get(to_url)
                if from_node and to_node:
                    edge = self.graph.add_edge(
                        from_node_id=from_node.id,
                        to_node_id=to_node.id,
                        trigger="navigation",
                        metadata={"source": "healing_refresh"},
                    )
                    if edge:
                        edges_updated += 1

            browser.close()

        self.db.commit()

        return RefreshResult(
            product_id=product_id,
            nodes_refreshed=len(url_to_node),
            edges_updated=edges_updated,
            node_ids=[str(n.id) for n in url_to_node.values()],
        )

    def _process_page(
        self,
        page: Page,
        product: Product,
        url: str,
        base_url: str,
        from_node_id: uuid.UUID | None = None,
        depth: int = 0,
        metadata_extra: dict | None = None,
    ) -> PageExploreResult | None:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1000)
        except Exception:
            return None

        elements = self._extract_elements(page)
        html_snapshot = page.content()[:50000]
        title = page.title()

        node = self.graph.upsert_node(
            product_id=product.id,
            url=url,
            title=title,
            screenshot_path=None,
            html_snapshot=html_snapshot,
            elements=elements,
            metadata={"depth": depth, **(metadata_extra or {})},
        )

        screenshot_bytes = page.screenshot(full_page=False)
        screenshot_path = self.screenshots.save_bytes(product.id, node.id, screenshot_bytes)
        node.screenshot_path = screenshot_path

        llm_source = "llm"
        llm_error = None
        try:
            analysis = self.llm.analyze_page(url, elements, screenshot_path)
        except Exception as exc:
            analysis = fallback_page_analysis(url, elements)
            llm_source = "fallback"
            llm_error = str(exc)[:500]

        node.title = analysis.get("page_name") or title
        node.metadata_ = {
            **(node.metadata_ or {}),
            "purpose": analysis.get("purpose"),
            "primary_action": analysis.get("primary_action"),
            "leads_to": analysis.get("leads_to"),
            "journey_moment": analysis.get("journey_moment"),
            "is_key_moment": analysis.get("is_key_moment", False),
            "llm_source": llm_source,
            "llm_error": llm_error,
        }

        if from_node_id:
            self.graph.add_edge(from_node_id=from_node_id, to_node_id=node.id, trigger="navigation")

        discovered_links = self._discover_links(page, base_url)
        return PageExploreResult(node=node, discovered_links=discovered_links)

    def _credentials_from_product(self, product: Product) -> CrawlCredentials | None:
        if not product.credentials:
            return None
        return CrawlCredentials(
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

    def _extract_elements(self, page: Page) -> list[dict]:
        elements: list[dict] = []
        seen: set[str] = set()

        for el in page.locator(self.INTERACTIVE_SELECTORS).all()[:100]:
            try:
                tag = el.evaluate("e => e.tagName.toLowerCase()")
                text = (el.inner_text() or el.get_attribute("aria-label") or "").strip()[:100]
                href = el.get_attribute("href") or ""
                el_type = el.get_attribute("type") or tag
                selector_hint = el.evaluate(
                    """e => {
                        if (e.id) return '#' + e.id;
                        if (e.name) return e.tagName.toLowerCase() + '[name="' + e.name + '"]';
                        return e.tagName.toLowerCase();
                    }"""
                )
                key = f"{tag}:{text}:{href}"
                if key in seen:
                    continue
                seen.add(key)
                elements.append(
                    {
                        "tag": tag,
                        "text": text,
                        "href": href,
                        "type": el_type,
                        "selector": selector_hint,
                    }
                )
            except Exception:
                continue

        return elements

    def _discover_links(self, page: Page, base_url: str) -> list[str]:
        links: list[str] = []
        for el in page.locator("a[href]").all():
            try:
                href = el.get_attribute("href")
                if not href or href.startswith("#") or href.startswith("javascript:"):
                    continue
                absolute = urljoin(page.url, href)
                normalized = self._normalize_url(absolute, base_url)
                if normalized and self._same_origin(normalized, base_url):
                    links.append(normalized)
            except Exception:
                continue
        return list(dict.fromkeys(links))

    @staticmethod
    def _normalize_origin(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _normalize_url(url: str, base_url: str) -> str | None:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    @staticmethod
    def _same_origin(url: str, base_url: str) -> bool:
        return urlparse(url).netloc == urlparse(base_url).netloc

    @staticmethod
    def _emit(on_progress: Callable[[dict], None] | None, event: str, **payload) -> None:
        if on_progress:
            on_progress({"event": event, **payload})
