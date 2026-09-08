from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.api.schemas import ProductOut, ProductDetail, ProductHistoryPoint
from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.get("", response_model=list[ProductOut])
def list_products(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    min_score: Optional[float] = None,
    sort: Optional[str] = "newest",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    ws = get_default_workspace(db, user.id)
    q = db.query(models.Product).filter(models.Product.workspace_id == ws.id)

    if query:
        term = f"%{query.strip()}%"
        q = q.filter(or_(models.Product.title.ilike(term), models.Product.description.ilike(term)))

    if tag:
        q = q.join(models.TagAssignment, models.TagAssignment.entity_id == models.Product.id).join(models.Tag, models.Tag.id == models.TagAssignment.tag_id)
        q = q.filter(models.TagAssignment.entity_type == models.TagEntityType.product, models.Tag.name == tag)

    # Legacy scores remain available only when a caller explicitly requests
    # them.  They are not the default intelligence view and are always scoped
    # to product entities to avoid matching an ad/store with the same id.
    requested_score_type = None
    if sort == "winner":
        requested_score_type = models.ScoreType.winner
    elif sort == "momentum" or min_score is not None:
        requested_score_type = models.ScoreType.momentum

    score_alias = None
    if requested_score_type is not None:
        score_alias = (
            db.query(models.Score)
            .filter(
                models.Score.entity_type == models.SignalEntityType.product,
                models.Score.score_type == requested_score_type,
            )
            .subquery()
        )
        q = q.join(score_alias, score_alias.c.entity_id == models.Product.id)
        if min_score is not None:
            q = q.filter(score_alias.c.score_value >= min_score)

    if requested_score_type is not None and score_alias is not None:
        q = q.order_by(desc(score_alias.c.score_value))
    elif sort == "newest":
        q = q.order_by(desc(models.Product.created_at))
    else:
        q = q.order_by(desc(models.Product.last_seen_at))

    return q.limit(100).all()


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    product = (
        db.query(models.Product)
        .filter(models.Product.workspace_id == ws.id, models.Product.id == product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/history", response_model=list[ProductHistoryPoint])
def product_history(product_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    snaps = (
        db.query(models.ProductSnapshot)
        .join(models.Product, models.ProductSnapshot.product_id == models.Product.id)
        .filter(models.Product.workspace_id == ws.id, models.Product.id == product_id)
        .order_by(models.ProductSnapshot.fetched_at.asc())
        .all()
    )
    return [
        ProductHistoryPoint(
            fetched_at=s.fetched_at,
            price_min=s.price_min,
            price_max=s.price_max,
            available=s.available,
            variant_count=s.variant_count,
        )
        for s in snaps
    ]
