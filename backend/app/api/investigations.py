from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.investigation_schemas import InvestigationCreate, InvestigationOut, InvestigationUpdate
from app.db import models
from app.db.session import get_db
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()


def _entity_details(db: Session, workspace_id: int, entity_type: str, entity_id: int) -> dict:
    if entity_type == "store":
        row = db.query(models.Store).filter(models.Store.workspace_id == workspace_id, models.Store.id == entity_id).first()
        if row:
            return {"title": row.domain, "subtitle": row.platform_guess.value, "url": f"/stores/{row.id}/overview"}
    elif entity_type == "product":
        row = db.query(models.Product).filter(models.Product.workspace_id == workspace_id, models.Product.id == entity_id).first()
        if row:
            store = db.query(models.Store).filter(models.Store.id == row.store_id, models.Store.workspace_id == workspace_id).first()
            return {"title": row.title, "subtitle": store.domain if store else None, "url": row.canonical_url}
    elif entity_type == "ad":
        row = db.query(models.Ad).filter(models.Ad.workspace_id == workspace_id, models.Ad.id == entity_id).first()
        if row:
            return {"title": row.headline or row.advertiser_name or f"Ad {row.id}", "subtitle": row.advertiser_name, "url": f"/ads/{row.id}"}
    raise HTTPException(status_code=404, detail=f"{entity_type.title()} not found")


def _item_or_404(db: Session, workspace_id: int, item_id: int) -> models.InvestigationItem:
    row = db.query(models.InvestigationItem).filter(
        models.InvestigationItem.workspace_id == workspace_id,
        models.InvestigationItem.id == item_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Investigation item not found")
    return row


def _replace_evidence(db: Session, workspace_id: int, item: models.InvestigationItem, evidence_ids: list[int]) -> None:
    unique_ids = list(dict.fromkeys(evidence_ids))
    evidence = db.query(models.EvidenceRecord).filter(
        models.EvidenceRecord.workspace_id == workspace_id,
        models.EvidenceRecord.id.in_(unique_ids),
    ).all() if unique_ids else []
    if len(evidence) != len(unique_ids):
        raise HTTPException(status_code=422, detail="One or more evidence IDs are outside this workspace or do not exist")
    db.query(models.InvestigationEvidenceLink).filter(
        models.InvestigationEvidenceLink.investigation_id == item.id
    ).delete(synchronize_session=False)
    for evidence_id in unique_ids:
        db.add(models.InvestigationEvidenceLink(investigation_id=item.id, evidence_id=evidence_id))


def _response(db: Session, workspace_id: int, item: models.InvestigationItem) -> dict:
    entity = _entity_details(db, workspace_id, item.entity_type, item.entity_id)
    evidence_rows = (
        db.query(models.EvidenceRecord)
        .join(models.InvestigationEvidenceLink, models.InvestigationEvidenceLink.evidence_id == models.EvidenceRecord.id)
        .filter(
            models.InvestigationEvidenceLink.investigation_id == item.id,
            models.EvidenceRecord.workspace_id == workspace_id,
        )
        .order_by(models.InvestigationEvidenceLink.id.asc())
        .all()
    )
    return {
        "id": item.id,
        "entity_type": item.entity_type,
        "entity_id": item.entity_id,
        "entity_title": entity["title"],
        "entity_subtitle": entity["subtitle"],
        "entity_url": entity["url"],
        "workflow_stage": item.workflow_stage,
        "decision": item.decision,
        "priority": item.priority,
        "thesis": item.thesis,
        "risks": item.risks,
        "next_action": item.next_action,
        "evidence": [
            {
                "id": row.id,
                "evidence_type": row.evidence_type,
                "source_type": row.source_type,
                "details": row.details,
                "observed_at": row.observed_at,
            }
            for row in evidence_rows
        ],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("", response_model=list[InvestigationOut])
def list_investigations(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    workflow_stage: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    query = db.query(models.InvestigationItem).filter(models.InvestigationItem.workspace_id == workspace.id)
    if not include_archived:
        query = query.filter(models.InvestigationItem.workflow_stage != "archived")
    if entity_type:
        query = query.filter(models.InvestigationItem.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(models.InvestigationItem.entity_id == entity_id)
    if workflow_stage:
        query = query.filter(models.InvestigationItem.workflow_stage == workflow_stage)
    rows = query.order_by(models.InvestigationItem.updated_at.desc(), models.InvestigationItem.id.desc()).all()
    return [_response(db, workspace.id, row) for row in rows]


@router.post("", response_model=InvestigationOut)
def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _entity_details(db, workspace.id, payload.entity_type, payload.entity_id)
    existing = db.query(models.InvestigationItem).filter(
        models.InvestigationItem.workspace_id == workspace.id,
        models.InvestigationItem.entity_type == payload.entity_type,
        models.InvestigationItem.entity_id == payload.entity_id,
    ).first()
    if existing:
        return _response(db, workspace.id, existing)
    row = models.InvestigationItem(
        workspace_id=workspace.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        workflow_stage=payload.workflow_stage,
        decision=payload.decision,
        priority=payload.priority,
        thesis=payload.thesis,
        risks=payload.risks,
        next_action=payload.next_action,
    )
    db.add(row)
    db.flush()
    _replace_evidence(db, workspace.id, row, payload.evidence_ids)
    db.commit()
    db.refresh(row)
    return _response(db, workspace.id, row)


@router.put("/{item_id}", response_model=InvestigationOut)
def update_investigation(
    item_id: int,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    row = _item_or_404(db, workspace.id, item_id)
    row.workflow_stage = payload.workflow_stage
    row.decision = payload.decision
    row.priority = payload.priority
    row.thesis = payload.thesis
    row.risks = payload.risks
    row.next_action = payload.next_action
    row.updated_at = datetime.utcnow()
    if payload.evidence_ids is not None:
        _replace_evidence(db, workspace.id, row, payload.evidence_ids)
    db.commit()
    db.refresh(row)
    return _response(db, workspace.id, row)


@router.delete("/{item_id}")
def archive_investigation(
    item_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    row = _item_or_404(db, workspace.id, item_id)
    row.workflow_stage = "archived"
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "archived", "investigation_id": item_id}
