from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.economics_schemas import ProductEconomicsIn, ProductEconomicsOut, ProductEconomicsStored
from app.db import models
from app.db.session import get_db
from app.services.product_economics import VERSION, calculate_product_economics
from app.services.workspace import get_default_workspace
from app.utils.security import get_current_user


router = APIRouter()

INPUT_FIELDS = (
    "name", "currency", "selling_price", "product_cost_low", "product_cost_high",
    "shipping_cost_low", "shipping_cost_high", "fulfillment_cost_low", "fulfillment_cost_high",
    "other_variable_cost_low", "other_variable_cost_high", "payment_fee_rate",
    "payment_fee_fixed", "refund_allowance_rate", "target_profit_margin", "notes",
)


def _product_or_404(db: Session, workspace_id: int, product_id: int) -> models.Product:
    product = db.query(models.Product).filter(
        models.Product.workspace_id == workspace_id,
        models.Product.id == product_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _scenario_or_404(db: Session, workspace_id: int, product_id: int, scenario_id: int) -> models.ProductEconomicsScenario:
    scenario = db.query(models.ProductEconomicsScenario).filter(
        models.ProductEconomicsScenario.workspace_id == workspace_id,
        models.ProductEconomicsScenario.product_id == product_id,
        models.ProductEconomicsScenario.id == scenario_id,
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Economics scenario not found")
    return scenario


def _response(row: models.ProductEconomicsScenario) -> dict:
    stored = ProductEconomicsStored.model_validate(row).model_dump(mode="python")
    return {**stored, "calculation": calculate_product_economics(stored)}


def _new_row(*, workspace_id: int, product_id: int, payload: ProductEconomicsIn, scenario_key: str, revision: int, supersedes_id: int | None = None) -> models.ProductEconomicsScenario:
    values = payload.model_dump(mode="python")
    return models.ProductEconomicsScenario(
        workspace_id=workspace_id,
        product_id=product_id,
        scenario_key=scenario_key,
        revision=revision,
        supersedes_id=supersedes_id,
        is_active=True,
        version=VERSION,
        input_source="user_entered",
        **values,
    )


@router.get("/products/{product_id}/economics", response_model=list[ProductEconomicsOut])
def list_product_economics(
    product_id: int,
    include_history: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _product_or_404(db, workspace.id, product_id)
    query = db.query(models.ProductEconomicsScenario).filter(
        models.ProductEconomicsScenario.workspace_id == workspace.id,
        models.ProductEconomicsScenario.product_id == product_id,
    )
    if not include_history:
        query = query.filter(models.ProductEconomicsScenario.is_active.is_(True))
    rows = query.order_by(models.ProductEconomicsScenario.updated_at.desc(), models.ProductEconomicsScenario.id.desc()).all()
    return [_response(row) for row in rows]


@router.post("/products/{product_id}/economics", response_model=ProductEconomicsOut)
def create_product_economics(
    product_id: int,
    payload: ProductEconomicsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _product_or_404(db, workspace.id, product_id)
    row = _new_row(
        workspace_id=workspace.id,
        product_id=product_id,
        payload=payload,
        scenario_key=uuid4().hex,
        revision=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _response(row)


@router.put("/products/{product_id}/economics/{scenario_id}", response_model=ProductEconomicsOut)
def revise_product_economics(
    product_id: int,
    scenario_id: int,
    payload: ProductEconomicsIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _product_or_404(db, workspace.id, product_id)
    previous = _scenario_or_404(db, workspace.id, product_id, scenario_id)
    if not previous.is_active:
        raise HTTPException(status_code=409, detail="Revise the active scenario revision")
    previous.is_active = False
    previous.updated_at = datetime.utcnow()
    row = _new_row(
        workspace_id=workspace.id,
        product_id=product_id,
        payload=payload,
        scenario_key=previous.scenario_key,
        revision=previous.revision + 1,
        supersedes_id=previous.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _response(row)


@router.delete("/products/{product_id}/economics/{scenario_id}")
def archive_product_economics(
    product_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    workspace = get_default_workspace(db, user.id)
    _product_or_404(db, workspace.id, product_id)
    row = _scenario_or_404(db, workspace.id, product_id, scenario_id)
    row.is_active = False
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "archived", "scenario_id": scenario_id}
