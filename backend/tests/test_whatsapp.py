"""WhatsApp (Meta Cloud API) channel: webhook verification, an incoming
message routed through a workflow, and the Send WhatsApp node. The Meta
Graph API call is faked; no network leaves the process."""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_whatsapp.db")
os.environ.setdefault("SMS_BACKGROUND_PROCESSING", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.modules.communications import service as comms_service_module  # noqa: E402
from app.modules.communications.whatsapp import WhatsAppProvider, WhatsAppSendResult  # noqa: E402

WA_URL = "/api/v1/webhooks/whatsapp"
OUTBOX: list[dict] = []


class FakeWhatsApp(WhatsAppProvider):
    async def send_text(self, to, text):
        OUTBOX.append({"to": to, "text": text})
        return WhatsAppSendResult(message_id=f"wamid.fake-{len(OUTBOX)}", status="sent", provider="whatsapp")


def _webhook_body(*, from_="254700111222", phone_number_id="1234567890", text="Hello", message_id="wamid.1"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "wa-account-1",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "254700000000", "phone_number_id": phone_number_id},
                    "contacts": [{"profile": {"name": "Test"}, "wa_id": from_}],
                    "messages": [{"from": from_, "id": message_id, "timestamp": "1700000000",
                                 "type": "text", "text": {"body": text}}],
                },
            }],
        }],
    }


def _activate(client, workflow_id):
    resp = client.patch(f"/api/v1/workflows/{workflow_id}", json={"status": "active"})
    assert resp.status_code == 200, resp.text


@pytest.fixture(scope="module")
def client():
    original_provider = comms_service_module.get_whatsapp_provider
    # Credentials now live in the database (Settings page), not env vars;
    # the phone_number_id/access_token args are ignored here since the fake
    # provider doesn't need real ones to "succeed".
    comms_service_module.get_whatsapp_provider = lambda *a, **k: FakeWhatsApp()
    with TestClient(app) as c:
        resp = c.put("/api/v1/settings/whatsapp", json={
            "phone_number_id": "1234567890", "verify_token": "test-verify-token",
            "access_token": "test-access-token",
        })
        assert resp.status_code == 200, resp.text
        yield c
    comms_service_module.get_whatsapp_provider = original_provider


def test_whatsapp_settings_never_return_the_access_token(client):
    resp = client.get("/api/v1/settings/whatsapp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phone_number_id"] == "1234567890"
    assert data["has_access_token"] is True
    assert data["configured"] is True
    assert "access_token" not in data


def test_resaving_without_a_token_keeps_the_existing_one(client):
    resp = client.put("/api/v1/settings/whatsapp", json={
        "phone_number_id": "1234567890", "verify_token": "test-verify-token", "access_token": None,
    })
    assert resp.status_code == 200
    assert resp.json()["has_access_token"] is True


def test_verify_handshake_echoes_the_challenge(client):
    resp = client.get(WA_URL, params={
        "hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "12345",
    })
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verify_handshake_rejects_a_wrong_token(client):
    resp = client.get(WA_URL, params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345",
    })
    assert resp.status_code == 403


def test_incoming_message_runs_the_matching_workflow(client):
    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_whatsapp"},
            {"id": "2", "type": "send_whatsapp", "config": {"text": "Hello {{sender}}, thanks for reaching out!"}},
        ],
        "edges": [{"source": "1", "target": "2"}],
    }
    created = client.post("/api/v1/workflows", json={"name": "WhatsApp Greeter", "definition": definition})
    assert created.status_code == 201, created.text
    _activate(client, created.json()["id"])

    resp = client.post(WA_URL, json=_webhook_body(text="hi there"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    assert OUTBOX and OUTBOX[-1]["to"] == "254700111222"
    assert "254700111222" in OUTBOX[-1]["text"]

    log = client.get("/api/v1/messages/log").json()
    # log_inbound runs the number through clean_phone, which adds the "+".
    inbound = [m for m in log if m["from_number"] == "+254700111222" and m["direction"] == "inbound"]
    assert inbound, log


def test_duplicate_delivery_is_ignored(client):
    before = len(OUTBOX)
    resp = client.post(WA_URL, json=_webhook_body(text="hi again", message_id="wamid.dup-1"))
    assert resp.status_code == 200
    resp2 = client.post(WA_URL, json=_webhook_body(text="hi again", message_id="wamid.dup-1"))
    assert resp2.status_code == 200
    # The second delivery of the same provider message id must not run the
    # workflow (and therefore not send) a second time.
    assert len(OUTBOX) == before + 1


def test_non_text_messages_are_acknowledged_and_ignored(client):
    body = _webhook_body(message_id="wamid.status-1")
    body["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    resp = client.post(WA_URL, json=body)
    assert resp.status_code == 200
