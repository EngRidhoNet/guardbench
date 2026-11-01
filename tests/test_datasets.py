import json

import pytest

from guardbench.datasets import DatasetValidationError, load_dataset


def test_loads_list_shorthand(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "one",
                    "input": "Hello",
                    "expected_decision": "allow",
                    "category": "safe",
                    "description": "Greeting",
                }
            ]
        )
    )
    dataset = load_dataset(path)
    assert dataset.name == "cases"
    assert dataset.cases[0].expected_decision == "allow"


def test_rejects_duplicate_ids(tmp_path):
    case = {
        "id": "duplicate",
        "input": "Hello",
        "expected_decision": "allow",
        "category": "safe",
        "description": "Greeting",
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"name": "bad", "cases": [case, case]}))
    with pytest.raises(DatasetValidationError, match="duplicate case ids"):
        load_dataset(path)
