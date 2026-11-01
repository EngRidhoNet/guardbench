import os

os.environ["GUARDBENCH_DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient  # noqa: E402

from guardbench.api.app import app  # noqa: E402


def test_health_and_project_lifecycle():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        created = client.post(
            "/api/v1/projects",
            json={"name": "Fixture", "slug": "fixture", "description": "Test"},
        )
        assert created.status_code == 201
        projects = client.get("/api/v1/projects").json()
        assert projects[0]["slug"] == "fixture"


def test_complete_evaluation_lifecycle():
    with TestClient(app) as client:
        project = client.post(
            "/api/v1/projects",
            json={"name": "Full flow", "slug": "full-flow", "description": "Test"},
        ).json()
        dataset = {
            "name": "Fixture dataset",
            "version": "1",
            "cases": [
                {
                    "id": "safe-1",
                    "input": "Explain budgeting",
                    "expected_decision": "allow",
                    "category": "education",
                    "description": "Safe education",
                }
            ],
        }
        published = client.post(
            f"/api/v1/projects/{project['id']}/datasets",
            json={"dataset": dataset},
        )
        assert published.status_code == 201
        target = client.post(
            f"/api/v1/projects/{project['id']}/targets",
            json={
                "name": "Mock",
                "adapter_type": "mock",
                "version": "1",
                "config": {},
            },
        )
        assert target.status_code == 201
        started = client.post(
            f"/api/v1/projects/{project['id']}/runs",
            json={
                "dataset_version_id": published.json()["dataset_version_id"],
                "target_id": target.json()["id"],
                "config": {},
            },
        )
        assert started.status_code == 202
        report = client.get(f"/api/v1/runs/{started.json()['run_id']}").json()
        assert report["status"] == "completed"
        assert report["metrics"]["accuracy"] == 1
