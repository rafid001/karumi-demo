from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.crawler import CrawlCredentials, Crawler
from app.core.graph_builder import GraphBuilder
from app.db.session import get_db

router = APIRouter(prefix="/crawl", tags=["crawl"])


class CrawlRequest(BaseModel):
    url: HttpUrl
    product_name: str = "Demo Product"
    login_url: HttpUrl | None = None
    username: str | None = None
    password: str | None = None
    max_pages: int | None = None
    max_depth: int | None = None


class CrawlResponse(BaseModel):
    product_id: str
    nodes_discovered: int
    edges_discovered: int
    pages_visited: list[str]


@router.post("", response_model=CrawlResponse)
def trigger_crawl(request: CrawlRequest, db: Session = Depends(get_db)) -> CrawlResponse:
    credentials = None
    if request.username or request.password:
        credentials = CrawlCredentials(
            username=request.username,
            password=request.password,
        )

    crawler = Crawler(db)
    try:
        result = crawler.crawl(
            url=str(request.url),
            product_name=request.product_name,
            credentials=credentials,
            login_url=str(request.login_url) if request.login_url else None,
            max_pages=request.max_pages,
            max_depth=request.max_depth,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crawl failed: {exc}") from exc

    return CrawlResponse(
        product_id=str(result.product_id),
        nodes_discovered=result.nodes_discovered,
        edges_discovered=result.edges_discovered,
        pages_visited=result.pages_visited,
    )
