import asyncio
import json
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.crawler import CrawlCredentials, Crawler
from app.db.session import SessionLocal, get_db

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


def _run_crawl_in_thread(
    queue: Queue,
    *,
    url: str,
    product_name: str,
    max_pages: int | None,
    max_depth: int | None,
) -> None:
    db = SessionLocal()
    try:
        crawler = Crawler(db)
        crawler.crawl(
            url=url,
            product_name=product_name,
            max_pages=max_pages,
            max_depth=max_depth,
            on_progress=queue.put,
        )
    except Exception as exc:
        queue.put({"event": "error", "detail": str(exc)})
    finally:
        db.close()
        queue.put(None)


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


@router.get("/stream")
async def crawl_stream(
    url: str = Query(..., description="Site URL to crawl"),
    product_name: str = Query("Demo Product"),
    max_pages: int | None = Query(None, ge=1, le=200),
    max_depth: int | None = Query(None, ge=0, le=10),
):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    queue: Queue = Queue()
    thread = Thread(
        target=_run_crawl_in_thread,
        kwargs={
            "queue": queue,
            "url": url,
            "product_name": product_name,
            "max_pages": max_pages,
            "max_depth": max_depth,
        },
        daemon=True,
    )
    thread.start()

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            try:
                item = await loop.run_in_executor(None, lambda: queue.get(timeout=60))
            except Empty:
                yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"
                continue

            if item is None:
                break

            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
