from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import crawl, demo, drift, graph
from app.db.base import Base
from app.db.session import engine
from app.services.llm import check_llm_health


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Self-Healing Demo Agent",
    description="Autonomous SaaS demo agent with self-healing knowledge graph",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl.router)
app.include_router(graph.router)
app.include_router(drift.router)
app.include_router(demo.router)


@app.get("/health")
def health():
    llm_health = check_llm_health()
    return {
        "status": "ok" if llm_health["status"] == "ok" else "degraded",
        "llm": llm_health,
    }
