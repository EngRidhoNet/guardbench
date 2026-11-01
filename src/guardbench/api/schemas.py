from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from guardbench.models import Dataset, RunConfig


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = ""


class DatasetPublish(BaseModel):
    dataset: Dataset


class TargetCreate(BaseModel):
    name: str
    adapter_type: str = "mock"
    version: str = "1"
    config: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    dataset_version_id: str
    target_id: str
    config: RunConfig = Field(default_factory=RunConfig)
