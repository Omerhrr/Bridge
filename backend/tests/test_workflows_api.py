"""Workflow API tests: CRUD, versioning, validation endpoints (spec §31)."""


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "bridge-api"


def test_seeded_workflows_exist(client):
    response = client.get("/api/workflows")
    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert {"Voice Translator", "SMS Translator", "Voice to SMS"} <= names


def test_create_and_get_workflow(client, sample_definition):
    created = client.post(
        "/api/workflows",
        json={"name": "Test Flow", "description": "demo", "definition": sample_definition.model_dump()},
    )
    assert created.status_code == 201
    workflow_id = created.json()["id"]

    fetched = client.get(f"/api/workflows/{workflow_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test Flow"
    assert fetched.json()["current_version"] == 1
    assert len(fetched.json()["definition"]["nodes"]) == 5


def test_update_bumps_version(client, sample_definition):
    created = client.post(
        "/api/workflows", json={"name": "Versioned", "definition": sample_definition.model_dump()}
    )
    workflow_id = created.json()["id"]

    definition = sample_definition.model_dump()
    definition["nodes"][2]["config"]["target_language"] = "sw"
    updated = client.put(f"/api/workflows/{workflow_id}", json={"definition": definition})
    assert updated.status_code == 200
    assert updated.json()["current_version"] == 2

    # Unchanged definitions do not bump the version.
    same = client.put(f"/api/workflows/{workflow_id}", json={"definition": definition})
    assert same.json()["current_version"] == 2


def test_duplicate_name_rejected(client, sample_definition):
    client.post("/api/workflows", json={"name": "Unique", "definition": sample_definition.model_dump()})
    response = client.post("/api/workflows", json={"name": "Unique"})
    assert response.status_code == 409


def test_validate_endpoint_reports_issues(client):
    broken = {
        "nodes": [
            {"id": "1", "type": "translate", "config": {}},  # no trigger, missing required config
            {"id": "2", "type": "end"},
        ],
        "edges": [{"source": "1", "target": "2"}],
    }
    response = client.post("/api/workflows/validate", json=broken)
    assert response.status_code == 200
    report = response.json()
    assert report["valid"] is False
    assert any(issue["severity"] == "error" for issue in report["checks"])


def test_deploy_validates_and_enables(client, sample_definition):
    created = client.post(
        "/api/workflows", json={"name": "Deployable", "enabled": False}
    )
    workflow_id = created.json()["id"]
    deployed = client.post(
        f"/api/workflows/{workflow_id}/deploy", json=sample_definition.model_dump()
    )
    assert deployed.status_code == 200
    assert deployed.json()["enabled"] is True


def test_deploy_rejects_invalid_definition(client):
    created = client.post("/api/workflows", json={"name": "Broken"})
    workflow_id = created.json()["id"]
    deployed = client.post(
        f"/api/workflows/{workflow_id}/deploy",
        json={"nodes": [{"id": "1", "type": "send_sms", "config": {}}], "edges": []},
    )
    assert deployed.status_code == 422


def test_node_types_endpoint(client):
    response = client.get("/api/node-types")
    assert response.status_code == 200
    types = {n["type"] for n in response.json()}
    assert {"incoming_call", "incoming_sms", "speech_to_text", "translate", "text_to_speech",
            "play_text", "play_audio", "collect_speech", "send_sms", "condition", "end"} <= types
