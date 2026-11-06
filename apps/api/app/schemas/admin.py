from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AdminRole = Literal["employee", "support", "approver", "admin", "evaluator", "auditor"]


class AdminUserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str
    department: str
    is_active: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]


class AdminUserUpdate(BaseModel):
    role: AdminRole | None = None
    department: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None


class RuntimeConfig(BaseModel):
    retrieval_limit: int = Field(default=5, ge=1, le=10)
    max_context_chunks: int = Field(default=5, ge=1, le=10)
    retrieval_min_score: float = Field(default=0.2, ge=0, le=1)
    max_steps: int = Field(default=6, ge=1, le=20)
    approval_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    evaluation_regression_threshold: float = Field(default=0.03, ge=0, le=1)
    answer_style: Literal["concise", "detailed"] = "concise"


class PromptVersionOut(BaseModel):
    id: str
    version: str
    name: str
    system_prompt: str
    is_active: bool
    created_by_id: str | None = None
    created_by_name: str | None = None
    created_at: datetime


class PromptVersionListResponse(BaseModel):
    items: list[PromptVersionOut]


class PromptVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(min_length=1, max_length=8000)
    activate: bool = False


class TaxonomyResponse(BaseModel):
    categories: list[dict[str, str]]
    priorities: list[dict[str, str]]
    roles: list[dict[str, Any]]


class AdminSettingsResponse(BaseModel):
    runtime_config: RuntimeConfig
    prompts: list[PromptVersionOut]
    taxonomy: TaxonomyResponse
    users: list[AdminUserOut]


class DemoResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=40)


class DemoResetResponse(BaseModel):
    reset_at: datetime
    deleted: dict[str, int]
    reseeded_documents: int
    audit_event_id: str
    message: str
