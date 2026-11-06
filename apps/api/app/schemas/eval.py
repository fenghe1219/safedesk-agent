from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DatasetType = Literal["knowledge", "triage", "security"]
ManualVerdict = Literal["PASS", "FAIL"]


class EvalDatasetOut(BaseModel):
    id: str
    name: str
    dataset_type: DatasetType
    version: str
    description: str
    item_count: int
    is_fixed: bool
    created_at: datetime


class EvalDatasetListResponse(BaseModel):
    items: list[EvalDatasetOut]


class EvalItemOut(BaseModel):
    id: str
    ordinal: int
    input: dict[str, Any]
    expected: dict[str, Any]
    labels: dict[str, Any]
    source: str


class EvalDatasetDetail(EvalDatasetOut):
    items: list[EvalItemOut] = []


class EvalRunCreate(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=40)
    label: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=80)
    model_settings: dict[str, Any] = {}
    retrieval_config: dict[str, Any] = {}
    run_config: dict[str, Any] = {}


class EvalRunOut(BaseModel):
    id: str
    dataset_id: str
    dataset_name: str
    dataset_type: DatasetType
    label: str
    prompt_version: str
    model_settings: dict[str, Any]
    retrieval_config: dict[str, Any]
    run_config: dict[str, Any]
    status: str
    metrics: dict[str, Any]
    sample_count: int
    created_by_id: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class EvalRunListResponse(BaseModel):
    items: list[EvalRunOut]


class EvalResultOut(BaseModel):
    id: str
    run_id: str
    item_id: str
    ordinal: int
    input: dict[str, Any]
    expected: dict[str, Any]
    labels: dict[str, Any]
    actual: dict[str, Any]
    score: float
    passed: bool
    failure_reason: str
    citations: list[dict[str, Any]] = []
    latency_ms: int
    token_count: int
    cost_usd: float
    manual_verdict: ManualVerdict | None = None
    manual_note: str
    reviewed_by_id: str | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class EvalResultListResponse(BaseModel):
    items: list[EvalResultOut]
    total: int
    offset: int
    limit: int


class EvalReviewUpdate(BaseModel):
    verdict: ManualVerdict
    note: str = Field(default="", max_length=1000)


class EvalMetricDiff(BaseModel):
    key: str
    label: str
    unit: str
    baseline: float | None = None
    candidate: float | None = None
    delta: float | None = None
    lower_is_better: bool = False
    regressed: bool = False


class EvalCompareResponse(BaseModel):
    baseline: EvalRunOut
    candidate: EvalRunOut
    metrics: list[EvalMetricDiff]
    regression_blocked: bool
    threshold: float
    blocking_metrics: list[str] = []


class EvalRunDetail(BaseModel):
    run: EvalRunOut
    results: EvalResultListResponse
