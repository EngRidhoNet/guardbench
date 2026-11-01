from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from guardbench import __version__
from guardbench.adapters import HTTPAdapter, MockAdapter, PythonCallableAdapter, TargetAdapter
from guardbench.comparison import compare_runs
from guardbench.datasets import dataset_sha256
from guardbench.models import Dataset, RunConfig, RunReport
from guardbench.runner import run_evaluation

from .database import SessionLocal, get_db, initialize_database
from .schemas import DatasetPublish, ProjectCreate, RunCreate, TargetCreate
from .settings import settings
from .tables import DatasetRow, DatasetVersionRow, EvaluationRunRow, ProjectRow, TargetRow


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="GuardBench API",
    version=__version__,
    description="Evaluate allow, block, and escalate guardrail decisions.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def authenticate(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.api_key and (
        not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")


Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[None, Depends(authenticate)]


def _get_or_404(db: Session, model: Any, identifier: str) -> Any:
    value = db.get(model, identifier)
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return value


def _adapter(target: TargetRow) -> TargetAdapter:
    config = json.loads(target.config_json)
    if target.adapter_type == "mock":
        adapter: TargetAdapter = MockAdapter(
            config.get("block_patterns"), config.get("escalate_patterns")
        )
    elif target.adapter_type == "python":
        adapter = PythonCallableAdapter(config["callable"])
    elif target.adapter_type == "http":
        adapter = HTTPAdapter(
            config["url"],
            permitted_hosts=set(config.get("permitted_hosts", [])),
            allow_private=config.get("allow_private", False),
            headers=config.get("headers", {}),
        )
    else:
        raise ValueError(f"Unsupported adapter type: {target.adapter_type}")
    adapter.name = target.name
    adapter.version = target.version
    return adapter


def _execute_run(run_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(EvaluationRunRow, run_id)
        if not row or row.status == "cancelled":
            return
        row.status = "running"
        db.commit()
        try:
            dataset_row = db.get(DatasetVersionRow, row.dataset_version_id)
            target = db.get(TargetRow, row.target_id)
            if not dataset_row or not target:
                raise ValueError("Run references missing dataset or target")
            dataset = Dataset.model_validate_json(dataset_row.payload_json)
            config = RunConfig.model_validate_json(row.config_json)
            report = asyncio.run(run_evaluation(dataset, _adapter(target), config))
            db.refresh(row)
            if row.status == "cancelled":
                return
            report.id = UUID(run_id)
            row.status = "completed"
            row.report_json = report.model_dump_json()
            row.completed_at = datetime.now(UTC)
        except Exception as exc:
            row.status = "failed"
            row.error_message = str(exc)
            row.completed_at = datetime.now(UTC)
        db.commit()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/api/v1/projects", status_code=201, dependencies=[Depends(authenticate)])
def create_project(payload: ProjectCreate, db: Db) -> dict[str, Any]:
    if db.scalar(select(ProjectRow).where(ProjectRow.slug == payload.slug)):
        raise HTTPException(409, "Project slug already exists")
    row = ProjectRow(**payload.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id, **payload.model_dump(), "created_at": row.created_at}


@app.get("/api/v1/projects", dependencies=[Depends(authenticate)])
def list_projects(db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
    return [
        {"id": row.id, "name": row.name, "slug": row.slug, "description": row.description}
        for row in rows
    ]


@app.post(
    "/api/v1/projects/{project_id}/datasets", status_code=201, dependencies=[Depends(authenticate)]
)
def publish_dataset(project_id: str, payload: DatasetPublish, db: Db) -> dict[str, Any]:
    _get_or_404(db, ProjectRow, project_id)
    logical = db.scalar(
        select(DatasetRow).where(
            DatasetRow.project_id == project_id, DatasetRow.name == payload.dataset.name
        )
    )
    if logical is None:
        logical = DatasetRow(
            project_id=project_id,
            name=payload.dataset.name,
            description=payload.dataset.description,
        )
        db.add(logical)
        db.flush()
    if db.scalar(
        select(DatasetVersionRow).where(
            DatasetVersionRow.dataset_id == logical.id,
            DatasetVersionRow.version == payload.dataset.version,
        )
    ):
        raise HTTPException(409, "Dataset version is immutable and already exists")
    version = DatasetVersionRow(
        dataset_id=logical.id,
        version=payload.dataset.version,
        content_sha256=dataset_sha256(payload.dataset),
        payload_json=payload.dataset.model_dump_json(),
    )
    db.add(version)
    db.commit()
    return {
        "dataset_id": logical.id,
        "dataset_version_id": version.id,
        "cases": len(payload.dataset.cases),
    }


@app.get("/api/v1/projects/{project_id}/datasets", dependencies=[Depends(authenticate)])
def list_datasets(project_id: str, db: Db) -> list[dict[str, Any]]:
    rows = db.execute(
        select(DatasetRow, DatasetVersionRow)
        .join(DatasetVersionRow, DatasetVersionRow.dataset_id == DatasetRow.id)
        .where(DatasetRow.project_id == project_id)
        .order_by(DatasetVersionRow.created_at.desc())
    ).all()
    return [
        {
            "id": dataset.id,
            "name": dataset.name,
            "version_id": version.id,
            "version": version.version,
            "sha256": version.content_sha256,
        }
        for dataset, version in rows
    ]


@app.post(
    "/api/v1/projects/{project_id}/targets", status_code=201, dependencies=[Depends(authenticate)]
)
def create_target(project_id: str, payload: TargetCreate, db: Db) -> dict[str, Any]:
    _get_or_404(db, ProjectRow, project_id)
    if payload.adapter_type not in {"mock", "python", "http"}:
        raise HTTPException(422, "adapter_type must be mock, python, or http")
    row = TargetRow(
        project_id=project_id,
        name=payload.name,
        adapter_type=payload.adapter_type,
        version=payload.version,
        config_json=json.dumps(payload.config),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, **payload.model_dump()}


@app.get("/api/v1/projects/{project_id}/targets", dependencies=[Depends(authenticate)])
def list_targets(project_id: str, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(select(TargetRow).where(TargetRow.project_id == project_id)).all()
    return [
        {"id": row.id, "name": row.name, "adapter_type": row.adapter_type, "version": row.version}
        for row in rows
    ]


@app.post(
    "/api/v1/projects/{project_id}/runs", status_code=202, dependencies=[Depends(authenticate)]
)
def create_run(
    project_id: str, payload: RunCreate, background: BackgroundTasks, db: Db
) -> dict[str, str]:
    _get_or_404(db, ProjectRow, project_id)
    dataset = _get_or_404(db, DatasetVersionRow, payload.dataset_version_id)
    target = _get_or_404(db, TargetRow, payload.target_id)
    if target.project_id != project_id:
        raise HTTPException(422, "Target does not belong to project")
    logical = _get_or_404(db, DatasetRow, dataset.dataset_id)
    if logical.project_id != project_id:
        raise HTTPException(422, "Dataset does not belong to project")
    row = EvaluationRunRow(
        project_id=project_id,
        dataset_version_id=payload.dataset_version_id,
        target_id=payload.target_id,
        config_json=payload.config.model_dump_json(),
    )
    db.add(row)
    db.commit()
    background.add_task(_execute_run, row.id)
    return {"run_id": row.id, "status": row.status}


@app.get("/api/v1/projects/{project_id}/runs", dependencies=[Depends(authenticate)])
def list_runs(
    project_id: str,
    db: Db,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(EvaluationRunRow)
        .where(EvaluationRunRow.project_id == project_id)
        .order_by(EvaluationRunRow.created_at.desc())
        .limit(limit)
    ).all()
    output = []
    for row in rows:
        report = json.loads(row.report_json) if row.report_json else None
        output.append(
            {
                "id": row.id,
                "status": row.status,
                "created_at": row.created_at,
                "completed_at": row.completed_at,
                "metrics": report.get("metrics") if report else None,
                "error": row.error_message,
            }
        )
    return output


@app.get("/api/v1/runs/{run_id}", dependencies=[Depends(authenticate)])
def get_run(run_id: str, db: Db) -> dict[str, Any]:
    row = _get_or_404(db, EvaluationRunRow, run_id)
    if row.report_json:
        return json.loads(row.report_json)
    return {"id": row.id, "status": row.status, "error": row.error_message}


@app.post("/api/v1/runs/{run_id}/cancel", dependencies=[Depends(authenticate)])
def cancel_run(run_id: str, db: Db) -> dict[str, str]:
    row = _get_or_404(db, EvaluationRunRow, run_id)
    if row.status not in {"queued", "running"}:
        raise HTTPException(409, "Only queued or running runs can be cancelled")
    row.status = "cancelled"
    db.commit()
    return {"run_id": row.id, "status": row.status}


@app.post("/api/v1/runs/compare", dependencies=[Depends(authenticate)])
def compare(payload: dict[str, str], db: Db) -> dict[str, Any]:
    baseline = _get_or_404(db, EvaluationRunRow, payload.get("baseline_run_id", ""))
    candidate = _get_or_404(db, EvaluationRunRow, payload.get("candidate_run_id", ""))
    if not baseline.report_json or not candidate.report_json:
        raise HTTPException(409, "Both runs must be completed")
    return compare_runs(
        RunReport.model_validate_json(baseline.report_json),
        RunReport.model_validate_json(candidate.report_json),
    )


@app.get("/api/v1/overview", dependencies=[Depends(authenticate)])
def overview(db: Db) -> dict[str, int]:
    return {
        "projects": db.scalar(select(func.count()).select_from(ProjectRow)) or 0,
        "datasets": db.scalar(select(func.count()).select_from(DatasetVersionRow)) or 0,
        "targets": db.scalar(select(func.count()).select_from(TargetRow)) or 0,
        "runs": db.scalar(select(func.count()).select_from(EvaluationRunRow)) or 0,
    }
