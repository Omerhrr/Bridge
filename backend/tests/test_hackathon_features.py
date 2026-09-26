"""Hackathon feature tests: USSD webhook loop and Airtime rewards.

Covers the two Africa's Talking tracks added for the hackathon:
  - USSD API: CON/END protocol, multi-level menus, invalid input handling.
  - Airtime API: send_airtime node executed inside an SMS workflow.
"""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_hackathon.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

USSD_URL = "/api/v1/webhooks/africastalking/ussd"
SMS_URL = "/api/v1/webhooks/africastalking/sms"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _activate(client: dict, workflow_id: int) -> None:
    resp = client.patch(f"/api/v1/workflows/{workflow_id}", json={"status": "active"})
    assert resp.status_code == 200, resp.text


def test_ussd_no_active_workflow_closes_session(client):
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-none", "serviceCode": "*384*99#",
        "phoneNumber": "+254700000001", "text": "",
    })
    assert resp.status_code == 200
    assert resp.text.startswith("END")


def test_ussd_menu_flow_con_then_end(client):
    definition = {
        "nodes": [
            {"id": "1", "type": "ussd_request"},
            {"id": "2", "type": "ussd_menu", "config": {
                "title": "Bridge Services",
                "options": "1. Check balance\n2. Translation help"}},
            {"id": "3", "type": "switch", "config": {"variable": "ussd_selection", "cases": "1,2"}},
            {"id": "4", "type": "ussd_end", "config": {"message": "Your balance is KES 240.50"}},
            {"id": "5", "type": "ussd_menu", "config": {
                "title": "Translation Help",
                "options": "1. English to Hausa\n2. Hausa to English"}},
            {"id": "6", "type": "ussd_end", "config": {"message": "A translator will call you back"}},
            {"id": "7", "type": "ussd_end", "config": {"message": "Invalid choice"}},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3"},
            {"source": "3", "target": "4", "source_handle": "1"},
            {"source": "3", "target": "5", "source_handle": "2"},
            {"source": "5", "target": "6"},
            {"source": "3", "target": "7", "source_handle": "default"},
        ],
    }
    created = client.post("/api/v1/workflows", json={"name": "USSD Test Service", "definition": definition})
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    _activate(client, workflow_id)

    # First screen: open menu -> CON
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-1", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "",
    })
    assert resp.status_code == 200
    assert resp.text.startswith("CON"), resp.text
    assert "Bridge Services" in resp.text
    assert "1. Check balance" in resp.text

    # Invalid choice while the session is open -> END
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-1", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "9",
    })
    assert resp.text.startswith("END"), resp.text
    assert "Invalid choice" in resp.text

    # New session: menu choice "1" -> balance screen -> END
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-3", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "",
    })
    assert resp.text.startswith("CON"), resp.text
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-3", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "1",
    })
    assert resp.text.startswith("END"), resp.text
    assert "KES 240.50" in resp.text


def test_ussd_star_accumulated_input(client):
    """Africa's Talking accumulates multi-level choices with '*'."""
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-2", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "",
    })
    assert resp.text.startswith("CON"), resp.text

    # Choice "2" opens the translation submenu (still open -> CON)
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-2", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "2",
    })
    assert resp.text.startswith("CON"), resp.text
    assert "Translation Help" in resp.text

    # Submenu choice "1" closes the session
    resp = client.post(USSD_URL, data={
        "sessionId": "sess-2", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "2*1",
    })
    assert resp.status_code == 200
    assert resp.text.startswith("END"), resp.text
    assert "translator will call you back" in resp.text


def test_sms_airtime_reward_flow(client):
    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_sms"},
            {"id": "2", "type": "condition", "config": {
                "variable": "text", "operator": "contains", "value": "REWARD"}},
            {"id": "3", "type": "send_airtime", "config": {"amount": "10", "currency_code": "KES"}},
            {"id": "4", "type": "send_sms", "config": {"text": "Asante! KES 10 airtime received."}},
            {"id": "5", "type": "send_sms", "config": {"text": "Send the word REWARD for KES 10 airtime."}},
        ],
        "edges": [
            {"source": "1", "target": "2"},
            {"source": "2", "target": "3", "source_handle": "true"},
            {"source": "3", "target": "4"},
            {"source": "2", "target": "5", "source_handle": "false"},
        ],
    }
    created = client.post("/api/v1/workflows", json={"name": "Airtime Reward Test", "definition": definition})
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    _activate(client, workflow_id)

    # "REWARD" keyword -> airtime branch
    resp = client.post(SMS_URL, data={
        "from": "+254700333444", "to": "20980", "text": "REWARD",
        "id": "at-hack-1", "date": "2026-09-21",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed", body
    run_id = body["run_id"]

    detail = client.get(f"/api/v1/runs/{run_id}")
    assert detail.status_code == 200
    run = detail.json()
    assert run["variables"]["airtime_status"] == "simulated"
    assert run["variables"]["airtime_transaction_id"]
    event_names = {e["event"] for e in run["events"]}
    assert "airtime.sent" in event_names
    assert "sms.sent" in event_names

    # Non-keyword SMS -> info branch, no airtime event
    resp = client.post(SMS_URL, data={
        "from": "+254700333444", "to": "20980", "text": "hello there",
        "id": "at-hack-2", "date": "2026-09-21",
    })
    assert resp.status_code == 200
    detail = client.get(f"/api/v1/runs/{resp.json()['run_id']}")
    event_names = {e["event"] for e in detail.json()["events"]}
    assert "airtime.sent" not in event_names
    assert "sms.sent" in event_names


def test_ussd_completed_without_end_screen_closes_session(client):
    """A run finishing without an ussd_end node must reply END, never CON;
    otherwise Africa's Talking holds the session open until timeout with no
    waiting run left to answer the next callback."""
    definition = {
        "nodes": [
            {"id": "1", "type": "ussd_request"},
            {"id": "2", "type": "ussd_menu", "config": {"title": "Ping"}},
        ],
        "edges": [{"source": "1", "target": "2"}],
    }
    created = client.post("/api/v1/workflows", json={"name": "USSD No End Test", "definition": definition})
    assert created.status_code == 201, created.text
    _activate(client, created.json()["id"])

    resp = client.post(USSD_URL, data={
        "sessionId": "sess-noend", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "",
    })
    assert resp.text.startswith("CON"), resp.text

    resp = client.post(USSD_URL, data={
        "sessionId": "sess-noend", "serviceCode": "*384*1234#",
        "phoneNumber": "+254700111222", "text": "1",
    })
    assert resp.status_code == 200
    assert resp.text.startswith("END"), resp.text


def test_send_sms_renders_variables(client):
    """send_sms config supports {{variable}} templates (parity with the
    airtime node)."""
    # Trigger matching is first-active-workflow-wins (MVP behaviour): retire
    # earlier SMS workflows created by other tests so this one receives the
    # webhook.
    for workflow in client.get("/api/v1/workflows").json():
        if workflow["status"] == "active":
            has_sms_trigger = any(
                n["type"] == "incoming_sms"
                for n in (workflow["current_version"] or {}).get("definition", {}).get("nodes", [])
            )
            if has_sms_trigger and workflow["name"] != "SMS Template Test":
                client.patch(f"/api/v1/workflows/{workflow['id']}", json={"status": "inactive"})

    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_sms"},
            {"id": "2", "type": "send_sms", "config": {"text": "Hello {{sender}}"}},
        ],
        "edges": [{"source": "1", "target": "2"}],
    }
    created = client.post("/api/v1/workflows", json={"name": "SMS Template Test", "definition": definition})
    assert created.status_code == 201, created.text
    _activate(client, created.json()["id"])

    resp = client.post(SMS_URL, data={
        "from": "+254700777888", "to": "20980", "text": "hi",
        "id": "at-tpl-1", "date": "2026-09-21",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed", resp.text
    detail = client.get(f"/api/v1/runs/{resp.json()['run_id']}")
    sent = [e for e in detail.json()["events"] if e["event"] == "sms.sent"]
    assert sent and sent[0]["payload"]["text"] == "Hello +254700777888", sent


def test_send_airtime_requires_amount(client):
    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_sms"},
            {"id": "3", "type": "send_airtime", "config": {}},
        ],
        "edges": [{"source": "1", "target": "3"}],
    }
    resp = client.post("/api/v1/workflows/validate", json=definition)
    assert resp.status_code == 200
    report = resp.json()
    assert not report["valid"]
    assert any("amount" in issue["message"] for issue in report["issues"])


def test_node_catalog_includes_telecom_nodes(client):
    resp = client.get("/api/v1/workflows/node-types")
    assert resp.status_code == 200
    by_type = {n["type"]: n for n in resp.json()}
    for node_type in ("ussd_menu", "ussd_end", "send_airtime"):
        assert node_type in by_type, node_type
        assert by_type[node_type]["category"] == "telecom"
