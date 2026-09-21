"""API integration tests: health and workflow CRUD (spec section 44)."""
import os

os.environ.setdefault("SEED_DEMO_DATA", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_api.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


def test_node_types_contains_mvp_nodes(client):
    resp = client.get("/api/v1/workflows/node-types")
    assert resp.status_code == 200
    types = {n["type"] for n in resp.json()}
    assert {"incoming_call", "incoming_sms", "speech_to_text", "translate",
            "text_to_speech", "send_sms", "condition", "end"} <= types


def test_workflow_crud_and_validate(client):
    created = client.post("/api/v1/workflows", json={"name": "T Workflow"})
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_sms"},
            {"id": "2", "type": "translate", "config": {"target_language": "en"}},
            {"id": "3", "type": "send_sms"},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
        ],
    }
    saved = client.post(f"/api/v1/workflows/{workflow_id}/versions", json={"definition": definition})
    assert saved.status_code == 200
    assert saved.json()["current_version"]["version_number"] == 2

    validated = client.post(f"/api/v1/workflows/{workflow_id}/validate")
    assert validated.status_code == 200
    assert validated.json()["valid"]

    runs = client.post(f"/api/v1/workflows/{workflow_id}/test-run", json={"payload": {"from": "+234801", "text": "hello"}})
    assert runs.status_code == 200
    body = runs.json()
    assert body["status"] in {"completed", "failed"}
