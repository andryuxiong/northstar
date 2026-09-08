from sqlalchemy.orm import Session

from app.db import models


def get_default_workspace(db: Session, user_id: int) -> models.Workspace:
    ws = db.query(models.Workspace).filter(models.Workspace.owner_user_id == user_id).first()
    if not ws:
        ws = models.Workspace(name="Default", owner_user_id=user_id)
        db.add(ws)
        db.commit()
        db.refresh(ws)
    return ws
