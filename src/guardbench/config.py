from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from .models import RunConfig


class TargetConfig(BaseModel):
    type: Literal["mock", "python", "http"] = "mock"
    version: str = "1"
    callable: str | None = None
    url: str | None = None
    permitted_hosts: list[str] = Field(default_factory=list)
    allow_private: bool = False
    headers: dict[str, str] = Field(default_factory=dict)


class QualityGates(BaseModel):
    minimum_macro_f1: float | None = Field(default=None, ge=0, le=1)
    maximum_false_block_rate: float | None = Field(default=None, ge=0, le=1)
    maximum_missed_block_rate: float | None = Field(default=None, ge=0, le=1)
    maximum_indeterminate_rate: float | None = Field(default=None, ge=0, le=1)


class GuardBenchConfig(BaseModel):
    dataset: str
    target: TargetConfig = Field(default_factory=TargetConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    quality_gates: QualityGates = Field(default_factory=QualityGates)
    output: str = ".guardbench/latest.json"


def load_config(path: str | Path) -> GuardBenchConfig:
    payload: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return GuardBenchConfig.model_validate(payload)


def evaluate_gates(metrics: dict[str, Any], gates: QualityGates) -> list[str]:
    failures: list[str] = []
    checks = (
        ("macro_f1", gates.minimum_macro_f1, "minimum", lambda actual, limit: actual >= limit),
        (
            "false_block_rate",
            gates.maximum_false_block_rate,
            "maximum",
            lambda actual, limit: actual <= limit,
        ),
        (
            "missed_block_rate",
            gates.maximum_missed_block_rate,
            "maximum",
            lambda actual, limit: actual <= limit,
        ),
        (
            "indeterminate_rate",
            gates.maximum_indeterminate_rate,
            "maximum",
            lambda actual, limit: actual <= limit,
        ),
    )
    for metric, limit, kind, predicate in checks:
        if limit is None:
            continue
        actual = metrics.get(metric)
        if actual is None or not predicate(actual, limit):
            failures.append(f"{metric}={actual} failed {kind} gate {limit}")
    return failures
