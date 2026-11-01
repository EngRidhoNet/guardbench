from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class Decision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class OutcomeStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    INDETERMINATE = "indeterminate"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False


class TestCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=160)
    input: str = Field(min_length=1)
    expected_decision: Decision
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    policy_reference: str | None = None
    language: str | None = None
    severity: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Dataset(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(default="1", min_length=1, max_length=40)
    description: str = ""
    policy_version: str | None = None
    cases: list[TestCase]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Dataset:
        ids = [case.id for case in self.cases]
        duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate case ids: {', '.join(duplicates)}")
        if not self.cases:
            raise ValueError("dataset must contain at least one case")
        return self


class AdapterResult(BaseModel):
    decision: Decision | None = None
    outcome_status: OutcomeStatus = OutcomeStatus.SUCCESS
    reason: str | None = None
    policy_reference: str | None = None
    model: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None

    @model_validator(mode="after")
    def decision_matches_status(self) -> AdapterResult:
        if self.outcome_status == OutcomeStatus.SUCCESS and self.decision is None:
            raise ValueError("successful adapter results require a normalized decision")
        if self.outcome_status != OutcomeStatus.SUCCESS and self.decision is not None:
            raise ValueError("failed or indeterminate adapter results cannot include a decision")
        return self


class CaseResult(BaseModel):
    case_id: str
    input: str
    expected_decision: Decision
    actual_decision: Decision | None = None
    outcome_status: OutcomeStatus
    correct: bool | None = None
    reason: str | None = None
    policy_reference: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: ErrorDetail | None = None


class RunConfig(BaseModel):
    concurrency: int = Field(default=4, ge=1, le=100)
    timeout_seconds: float = Field(default=30, gt=0, le=600)
    retries: int = Field(default=0, ge=0, le=5)
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class RunReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    dataset_name: str
    dataset_version: str
    policy_version: str | None = None
    target_name: str
    target_version: str
    evaluator_version: str = "0.1.0-alpha"
    status: RunStatus = RunStatus.COMPLETED
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    config: RunConfig = Field(default_factory=RunConfig)
    results: list[CaseResult]
    metrics: dict[str, Any]
