from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import StoreOut
from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.get("", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    return db.query(models.Store).filter(models.Store.workspace_id == ws.id).limit(200).all()


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    store = db.query(models.Store).filter(models.Store.workspace_id == ws.id, models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/{store_id}/history")
def store_history(store_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    store = db.query(models.Store.id).filter(models.Store.workspace_id == ws.id, models.Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    snaps = (
        db.query(models.StoreSnapshot)
        .join(models.Store, models.StoreSnapshot.store_id == models.Store.id)
        .filter(models.Store.workspace_id == ws.id, models.Store.id == store_id)
        .order_by(models.StoreSnapshot.fetched_at.asc())
        .all()
    )
    return snaps
