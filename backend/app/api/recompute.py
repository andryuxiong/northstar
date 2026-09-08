from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace
from app.workers.tasks import recompute_scores_task
from app.workers.runner import enqueue

router = APIRouter()


@router.post("/scores")
def recompute_scores(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    workspace = get_default_workspace(db, user.id)
    products = db.query(models.Product.id).filter(models.Product.workspace_id == workspace.id).all()
    for (pid,) in products:
        enqueue(recompute_scores_task, "product", pid, label=f"Recompute product {pid}")
    return {"queued": len(products)}
