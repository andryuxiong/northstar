from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.workers.tasks import fetch_url_task, crawl_store_sitemap_task, recompute_scores_task
from app.workers.runner import enqueue
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.post("/product/{product_id}")
def track_product(product_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    product = db.query(models.Product).filter(
        models.Product.workspace_id == workspace.id,
        models.Product.id == product_id,
    ).first()
    if not product:
        return {"ok": False}
    source = db.query(models.SourceUrl).filter(
        models.SourceUrl.workspace_id == workspace.id,
        models.SourceUrl.url == product.canonical_url,
    ).first()
    if source:
        enqueue(fetch_url_task, source.id, label=f"Refresh product {product.title}")
    enqueue(recompute_scores_task, "product", product_id, label=f"Recompute product {product_id}")
    return {"ok": True}


@router.post("/store/{store_id}")
def track_store(store_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    store = db.query(models.Store).filter(
        models.Store.workspace_id == workspace.id,
        models.Store.id == store_id,
    ).first()
    if not store:
        return {"ok": False}
    enqueue(crawl_store_sitemap_task, store.id, label=f"Refresh store {store.domain}")
    return {"ok": True}
