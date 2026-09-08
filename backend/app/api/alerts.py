from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.utils.security import get_current_user
from app.services.workspace import get_default_workspace

router = APIRouter()


@router.post("/rules")
def create_rule(payload: dict, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    rule = models.AlertRule(
        workspace_id=ws.id,
        entity_type=models.SignalEntityType(payload["entity_type"]),
        entity_id=payload["entity_id"],
        rule_type=models.AlertRuleType(payload["rule_type"]),
        threshold_json=payload.get("threshold_json"),
        is_enabled=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/events")
def list_events(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    rules = db.query(models.AlertRule.id).filter(models.AlertRule.workspace_id == ws.id).subquery()
    events = db.query(models.AlertEvent).filter(models.AlertEvent.alert_rule_id.in_(rules)).order_by(models.AlertEvent.fired_at.desc()).limit(200).all()
    return events


@router.post("/events/{event_id}/read")
def mark_event_read(event_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    ws = get_default_workspace(db, user.id)
    event = (
        db.query(models.AlertEvent)
        .join(models.AlertRule, models.AlertEvent.alert_rule_id == models.AlertRule.id)
        .filter(models.AlertEvent.id == event_id, models.AlertRule.workspace_id == ws.id)
        .first()
    )
    if event:
        event.is_read = True
        db.commit()
    return {"ok": True}
