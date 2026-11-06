from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DistributionItem(BaseModel):
    key: str
    label: str
    count: int
    rate: float


class EvalTrendPoint(BaseModel):
    run_id: str
    dataset_type: str
    label: str
    sample_size: int
    pass_rate: float
    key_metric: str
    key_metric_label: str
    key_metric_value: float
    created_at: datetime


class DashboardResponse(BaseModel):
    range: str
    range_label: str
    generated_at: datetime
    cases_total: int
    knowledge_resolution_rate: float
    ticket_rate: float
    approval_requests: int
    approval_rejected: int
    approval_failed: int
    category_distribution: list[DistributionItem]
    priority_distribution: list[DistributionItem]
    manual_correction_rate: float
    avg_handling_minutes: float
    approval_pass_rate: float
    avg_approval_wait_minutes: float
    approval_expiry_rate: float
    duplicate_execution_blocked: int
    avg_answer_latency_ms: float
    avg_retrieval_latency_ms: float
    avg_tool_latency_ms: float
    avg_answer_cost_usd: float
    eval_trend: list[EvalTrendPoint]
    sample_sizes: dict[str, int]
    methodology: dict[str, Any]
