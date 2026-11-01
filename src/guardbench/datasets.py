from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import Dataset


class DatasetValidationError(ValueError):
    """Raised when an imported dataset cannot be normalized."""


def _load_csv(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row.get("tags"):
            row["tags"] = [tag.strip() for tag in row["tags"].split(",") if tag.strip()]
        else:
            row["tags"] = []
    return {"name": path.stem, "version": "1", "cases": rows}


def load_dataset(path: str | Path) -> Dataset:
    source = Path(path)
    if not source.exists():
        raise DatasetValidationError(f"dataset does not exist: {source}")
    try:
        if source.suffix.lower() == ".json":
            payload = json.loads(source.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                payload = {"name": source.stem, "version": "1", "cases": payload}
        elif source.suffix.lower() == ".csv":
            payload = _load_csv(source)
        else:
            raise DatasetValidationError("supported dataset formats are .json and .csv")
        return Dataset.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise DatasetValidationError(str(exc)) from exc


def dataset_sha256(dataset: Dataset) -> str:
    canonical = dataset.model_dump_json(exclude_none=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def export_dataset(dataset: Dataset, path: str | Path) -> Path:
    destination = Path(path)
    destination.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")
    return destination
