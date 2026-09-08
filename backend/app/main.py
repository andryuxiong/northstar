from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api import auth, ingest, products, stores, ads, graph, signals, scores, alerts, snapshots, track, recompute, library, integrations, traffic, intelligence, economics, investigations, comparisons, exports, ad_watchlists
from app.db.schema_compat import upgrade_database_schema
from app.db.session import engine
from app.services.ad_watchlists import start_ad_watch_scheduler, stop_ad_watch_scheduler

setup_logging()

@asynccontextmanager
async def lifespan(_: FastAPI):
    upgrade_database_schema(engine)
    start_ad_watch_scheduler()
    try:
        yield
    finally:
        stop_ad_watch_scheduler()


app = FastAPI(title="Northstar Personal Commerce Intelligence", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}),
    allow_origin_regex=r"chrome-extension://[a-z]{32}",
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(stores.router, prefix="/stores", tags=["stores"])
app.include_router(ads.router, prefix="/ads", tags=["ads"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(signals.router, prefix="/signals", tags=["signals"])
app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(snapshots.router, prefix="/snapshots", tags=["snapshots"])
app.include_router(track.router, prefix="/track", tags=["track"])
app.include_router(recompute.router, prefix="/recompute", tags=["recompute"])
app.include_router(library.router, prefix="/library", tags=["library"])
app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
app.include_router(traffic.router, prefix="/traffic", tags=["traffic"])
app.include_router(intelligence.router, prefix="/intelligence", tags=["intelligence"])
app.include_router(economics.router, tags=["economics"])
app.include_router(investigations.router, prefix="/investigations", tags=["investigations"])
app.include_router(comparisons.router, prefix="/comparisons", tags=["comparisons"])
app.include_router(exports.router, prefix="/exports", tags=["exports"])
app.include_router(ad_watchlists.router, prefix="/ad-watches", tags=["ad-watches"])


@app.get("/")
def root():
    return {"status": "ok"}
