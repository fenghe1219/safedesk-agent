from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.case import CaseOut, TimelineEventOut

ActionStatus = Literal[
    "PROPOSED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "SUCCEEDED",
    "FAILED",
    "REJECTED",
    "EXPIRED",
    "CANCELLED",
]
ApprovalStatus = Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ToolType = Literal["READ", "WRITE"]
ToolMockMode = Literal["success", "fail", "timeout"]


class ToolExecutionOut(BaseModel):
    id: str
    action_id: str
    tool_name: str
    status: str
    idempotency_key: str
    args_hash: str
    output: dict[str, object] = {}
    result_summary: str = ""
    verification: dict[str, object] = {}
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class ApprovalOut(BaseModel):
    id: str
    action_id: str
    status: ApprovalStatus
    status_label: str
    args_hash: str
    approver_id: str | None = None
    approver_name: str | None = None
    decision_reason: str | None = None
    requested_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    version: int


class ActionOut(BaseModel):
    id: str
    case_id: str
    tool_name: str
    tool_label: str
    tool_type: ToolType
    risk_level: RiskLevel
    risk_label: str
    status: ActionStatus
    status_label: str
    args: dict[str, object]
    args_hash: str
    rationale: str
    impact: str
    verification_plan: str
    rollback_plan: str
    evidence_ids: list[str] = []
    requested_by_id: str
    requested_by_name: str
    expires_at: datetime
    version: int
    created_at: datetime
    updated_at: datetime


class CaseActionOut(ActionOut):
    case_status: str
    case_status_label: str
    approval: ApprovalOut
    execution: ToolExecutionOut | None = None
    permissions: dict[str, bool] = {}
    blockers: list[str] = []


class ApprovalListItemOut(BaseModel):
    id: str
    action_id: str
    case_id: str
    case_title: str
    requester_id: str
    requester_name: str
    tool_name: str
    tool_label: str
    risk_level: RiskLevel
    risk_label: str
    impact: str
    status: ApprovalStatus
    status_label: str
    requested_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None
    can_decide: bool = False


class ApprovalDetailOut(BaseModel):
    approval: ApprovalOut
    action: ActionOut
    case: CaseOut
    execution: ToolExecutionOut | None = None
    timeline: list[TimelineEventOut] = []
    permissions: dict[str, bool] = {}
    blockers: list[str] = []


class ApprovalListResponse(BaseModel):
    items: list[ApprovalListItemOut]


class ApproveRequest(BaseModel):
    expected_args_hash: str = Field(min_length=1, max_length=80)
    approval_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class RejectRequest(BaseModel):
    approval_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class ActionDecisionResponse(BaseModel):
    approval: ApprovalOut
    action: ActionOut
    case: CaseOut
    execution: ToolExecutionOut | None = None
    message: str


class ToolPolicyOut(BaseModel):
    name: str
    label: str
    tool_type: ToolType
    risk_level: RiskLevel
    description: str
    requires_approval: bool
    timeout_seconds: int
    enabled: bool
    mock_mode: ToolMockMode


class ToolPolicyListResponse(BaseModel):
    items: list[ToolPolicyOut]
    kill_switch_enabled: bool
    kill_switch_reason: str | None = None


class ToolPolicyUpdate(BaseModel):
    enabled: bool | None = None
    mock_mode: ToolMockMode | None = None


class KillSwitchUpdate(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=300)


class KillSwitchOut(BaseModel):
    enabled: bool
    reason: str | None = None
    updated_at: datetime | None = None


class CheckpointOut(BaseModel):
    id: str
    case_id: str
    thread_id: str
    sequence: int
    node: str
    status: str
    workflow_version: int
    state: dict[str, object]
    created_at: datetime


class CheckpointListResponse(BaseModel):
    items: list[CheckpointOut]
