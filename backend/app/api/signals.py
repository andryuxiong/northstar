from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import SignalOut
from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.get("/{entity_type}/{entity_id}", response_model=list[SignalOut])
def get_signals(entity_type: str, entity_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    entity_enum = models.SignalEntityType(entity_type)
    workspace = get_default_workspace(db, user.id)
    if entity_enum == models.SignalEntityType.product:
        owned = db.query(models.Product.id).filter(models.Product.workspace_id == workspace.id, models.Product.id == entity_id).first()
    elif entity_enum == models.SignalEntityType.store:
        owned = db.query(models.Store.id).filter(models.Store.workspace_id == workspace.id, models.Store.id == entity_id).first()
    else:
        owned = db.query(models.Ad.id).filter(models.Ad.workspace_id == workspace.id, models.Ad.id == entity_id).first()
    if not owned:
        raise HTTPException(status_code=404, detail="Entity not found")
    signals = (
        db.query(models.Signal)
        .filter(models.Signal.entity_type == entity_enum, models.Signal.entity_id == entity_id)
        .order_by(models.Signal.computed_at.desc())
        .all()
    )
    return signals
