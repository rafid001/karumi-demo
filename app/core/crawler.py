import uuid
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, sync_playwright
from sqlalchemy.orm import Session

from app.config import settings
from app.core.graph_builder import GraphBuilder
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

                try:
                    page.goto(normalized, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1000)
                except Exception:
                    continue

                elements = self._extract_elements(page)
                html_snapshot = page.content()[:50000]
                title = page.title()

                node = self.graph.upsert_node(
                    product_id=product.id,
                    url=normalized,
                    title=title,
                    screenshot_path=None,
                    html_snapshot=html_snapshot,
                    elements=elements,
                    metadata={"depth": depth, "page_type": "discovered"},
                )

                screenshot_bytes = page.screenshot(full_page=False)
                screenshot_path = self.screenshots.save_bytes(product.id, node.id, screenshot_bytes)
                node.screenshot_path = screenshot_path

                llm_source = "llm"
                llm_error = None
                try:
                    analysis = self.llm.analyze_page(normalized, elements, screenshot_path)
                except Exception as exc:
                    analysis = fallback_page_analysis(normalized, elements)
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
                    edge = self.graph.add_edge(
                        from_node_id=from_node_id,
                        to_node_id=node.id,
                        trigger="navigation",
                    )
                    if edge:
                        edges_count += 1

                for link_url in self._discover_links(page, base_url):
                    if link_url not in visited:
                        queue.append((link_url, depth + 1, node.id))

            browser.close()

        self.db.commit()

        return CrawlResult(
            product_id=product.id,
            nodes_discovered=len(visited),
            edges_discovered=edges_count,
            pages_visited=pages_visited,
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
