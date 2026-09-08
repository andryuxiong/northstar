from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.get("/product/{product_id}")
def product_graph(product_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    product = db.query(models.Product).filter(models.Product.workspace_id == ws.id, models.Product.id == product_id).first()
    if not product:
        return {"ads": [], "landings": [], "products": []}

    landing_edges = db.query(models.LandingProductEdge).filter(models.LandingProductEdge.product_id == product_id).all()
    landing_url_ids = [e.landing_url_id for e in landing_edges]
    landing_urls = db.query(models.SourceUrl).filter(models.SourceUrl.id.in_(landing_url_ids)).all() if landing_url_ids else []

    ad_edges = db.query(models.AdLandingEdge).filter(models.AdLandingEdge.url_id.in_(landing_url_ids)).all() if landing_url_ids else []
    ad_ids = [e.ad_id for e in ad_edges]
    ads = db.query(models.Ad).filter(models.Ad.id.in_(ad_ids)).all() if ad_ids else []

    return {
        "ads": ads,
        "landings": landing_urls,
        "product": product,
    }
