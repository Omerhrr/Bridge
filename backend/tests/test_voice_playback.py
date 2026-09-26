"""Voice call playback: Play Text / Play Audio nodes must actually reach the
call, not just log an event. Before this fix the voice webhook only ever
read the `translation` variable, so Play Audio (and any Text-to-Speech +
Play Voice combination) never produced a <Play> response, and Play Text's
own configured text was silently ignored in favor of whatever a Translate
node had set earlier (or nothing at all, if there was no Translate node).
"""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_voice_playback.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

VOICE_URL = "/api/v1/webhooks/africastalking/voice"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _activate(client, workflow_id: int) -> None:
    resp = client.patch(f"/api/v1/workflows/{workflow_id}", json={"status": "active"})
    assert resp.status_code == 200, resp.text


def _create(client, name: str, definition: dict) -> int:
    resp = client.post("/api/v1/workflows", json={"name": name, "definition": definition})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_play_text_node_is_spoken_on_the_call(client):
    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "play_text", "config": {"text": "Welcome to Bridge support."}},
        ],
        "edges": [{"id": "e1", "source": "1", "target": "2"}],
    }
    workflow_id = _create(client, "Voice Play Text", definition)
    _activate(client, workflow_id)

    resp = client.post(VOICE_URL, data={
        "sessionId": "voice-sess-1", "isActive": "1",
        "callerNumber": "+254700000010", "destinationNumber": "22384",
    })
    assert resp.status_code == 200
    assert "<Say>Welcome to Bridge support.</Say>" in resp.text
    assert "<Play" not in resp.text


def test_play_audio_node_produces_play_element(client):
    # Deactivate the previous test's workflow first: only one active workflow
    # can answer a given trigger type (see test_workflow_activation_conflict
    # for what happens, and is now surfaced, when two are left active).
    client.patch("/api/v1/workflows/1", json={"status": "inactive"})

    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "play_audio", "config": {"url": "https://example.com/welcome.mp3"}},
        ],
        "edges": [{"id": "e1", "source": "1", "target": "2"}],
    }
    workflow_id = _create(client, "Voice Play Audio", definition)
    _activate(client, workflow_id)

    resp = client.post(VOICE_URL, data={
        "sessionId": "voice-sess-2", "isActive": "1",
        "callerNumber": "+254700000011", "destinationNumber": "22384",
    })
    assert resp.status_code == 200
    assert '<Play url="https://example.com/welcome.mp3"/>' in resp.text
    assert "<Say>" not in resp.text


def test_play_text_after_play_audio_overrides_it(client):
    """A later Play Text must win over an earlier Play Audio in the same
    call, not have the old audio_url silently take priority."""
    client.patch("/api/v1/workflows/2", json={"status": "inactive"})

    definition = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "play_audio", "config": {"url": "https://example.com/intro.mp3"}},
            {"id": "3", "type": "play_text", "config": {"text": "One moment please."}},
        ],
        "edges": [
            {"id": "e1", "source": "1", "target": "2"},
            {"id": "e2", "source": "2", "target": "3"},
        ],
    }
    workflow_id = _create(client, "Voice Audio Then Text", definition)
    _activate(client, workflow_id)

    resp = client.post(VOICE_URL, data={
        "sessionId": "voice-sess-3", "isActive": "1",
        "callerNumber": "+254700000012", "destinationNumber": "22384",
    })
    assert resp.status_code == 200
    assert "<Say>One moment please.</Say>" in resp.text
    assert "<Play" not in resp.text


def test_most_recently_activated_workflow_wins_when_two_share_a_trigger(client):
    """Regression: routing used to depend on arbitrary DB row order when two
    active workflows shared a trigger type. It must now deterministically
    favor whichever workflow was activated (updated) most recently."""
    definition_a = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "play_text", "config": {"text": "Flow A"}},
        ],
        "edges": [{"id": "e1", "source": "1", "target": "2"}],
    }
    definition_b = {
        "nodes": [
            {"id": "1", "type": "incoming_call"},
            {"id": "2", "type": "play_text", "config": {"text": "Flow B"}},
        ],
        "edges": [{"id": "e1", "source": "1", "target": "2"}],
    }
    id_a = _create(client, "Conflict Flow A", definition_a)
    id_b = _create(client, "Conflict Flow B", definition_b)
    _activate(client, id_a)
    _activate(client, id_b)  # activated (updated) after A: B should win

    resp = client.post(VOICE_URL, data={
        "sessionId": "voice-sess-conflict", "isActive": "1",
        "callerNumber": "+254700000099", "destinationNumber": "22384",
    })
    assert resp.status_code == 200
    assert "Flow B" in resp.text

    report = client.post(f"/api/v1/workflows/{id_b}/validate").json()
    messages = " ".join(i["message"] for i in report["issues"])
    assert "Conflict Flow A" in messages
    assert "same trigger" in messages

    client.patch(f"/api/v1/workflows/{id_a}", json={"status": "inactive"})
    client.patch(f"/api/v1/workflows/{id_b}", json={"status": "inactive"})
