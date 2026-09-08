from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


EntityType = Literal["store", "product", "ad"]
WorkflowStage = Literal["inbox", "researching", "ready_to_test", "testing", "decided", "archived"]
Decision = Literal["undecided", "investigate", "test", "reject"]
Priority = Literal["low", "medium", "high"]


class InvestigationCreate(BaseModel):
    entity_type: EntityType
    entity_id: int = Field(gt=0)
    workflow_stage: WorkflowStage = "inbox"
    decision: Decision = "undecided"
    priority: Priority = "medium"
    thesis: Optional[str] = Field(default=None, max_length=5000)
    risks: Optional[str] = Field(default=None, max_length=5000)
    next_action: Optional[str] = Field(default=None, max_length=2000)
    evidence_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("thesis", "risks", "next_action")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class InvestigationUpdate(BaseModel):
    workflow_stage: WorkflowStage
    decision: Decision
    priority: Priority
    thesis: Optional[str] = Field(default=None, max_length=5000)
    risks: Optional[str] = Field(default=None, max_length=5000)
    next_action: Optional[str] = Field(default=None, max_length=2000)
    evidence_ids: Optional[list[int]] = Field(default=None, max_length=100)

    @field_validator("thesis", "risks", "next_action")
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class InvestigationEvidenceOut(BaseModel):
    id: int
    evidence_type: str
    source_type: str
    details: Optional[str] = None
    observed_at: Optional[datetime] = None


class InvestigationOut(BaseModel):
    id: int
    entity_type: EntityType
    entity_id: int
    entity_title: str
    entity_subtitle: Optional[str] = None
    entity_url: str
    workflow_stage: WorkflowStage
    decision: Decision
    priority: Priority
    thesis: Optional[str] = None
    risks: Optional[str] = None
    next_action: Optional[str] = None
    evidence: list[InvestigationEvidenceOut]
    created_at: datetime
    updated_at: datetime
