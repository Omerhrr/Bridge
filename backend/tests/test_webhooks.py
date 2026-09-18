"""Webhook tests: AT voice + SMS flows, idempotency, conversation records (spec §25, §27, §45)."""


def test_sms_webhook_translates_and_replies(client):
    """Full telecom path: SMS webhook -> workflow -> outgoing SMS (spec §7)."""
    response = client.post(
        "/webhooks/africastalking/sms",
        data={"from": "+234801234567", "to": "+234900", "text": "Where are you?", "id": "msg_001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"

    # The conversation recorded the exchange (spec §27).
    conversation = client.get(f"/api/conversations/{body['conversation_id']}").json()
    assert conversation["channel"] == "sms"
    assert conversation["from_number"] == "+234801234567"
    contents = [m["content"] for m in conversation["messages"]]
    assert "Where are you?" in contents
    assert "ina kake" in contents  # translated reply


def test_sms_webhook_is_idempotent(client):
    """Provider retries must not duplicate workflow executions (spec §45)."""
    payload = {"from": "+234802", "to": "+234900", "text": "Hello", "id": "msg_dup"}
    first = client.post("/webhooks/africastalking/sms", data=payload)
    second = client.post("/webhooks/africastalking/sms", data=payload)

    assert first.json()["status"] == "completed"
    assert second.json() == {"status": "duplicate_ignored"}

    runs = client.get("/api/runs").json()
    runs_for_sender = [r for r in runs if r.get("variables", {}).get("caller") == "+234802"]
    assert len(runs_for_sender) == 1


def test_voice_webhook_returns_actions_then_completes(client):
    """Call 1 returns Say+GetSpeech; call 2 (with recording) completes with translated Say."""
    session_id = "ATVoice_123"
    first = client.post(
        "/webhooks/africastalking/voice",
        data={"sessionId": session_id, "callerNumber": "+234803", "isActive": "1"},
    )
    assert first.status_code == 200
    actions = first.json()["actions"]
    kinds = [a["action"] for a in actions]
    assert "Say" in kinds and "GetSpeech" in kinds
    assert first.json()["status"] == "waiting_input"

    second = client.post(
        "/webhooks/africastalking/voice",
        data={
            "sessionId": session_id,
            "callerNumber": "+234803",
            "isActive": "1",
            "recordingUrl": "https://recordings.at/session123.mp3",
            "id": "evt_resume_1",
        },
    )
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "completed"
    say_actions = [a for a in body["actions"] if a["action"] == "Play"]
    assert say_actions, "translated audio should be played back to the caller"

    # Workflow run shows the full node trace (spec §29).
    run = client.get(f"/api/runs/{body['run_id']}").json()
    trace = [(e["node_id"], e["status"]) for e in run["events"]]
    assert trace[0][0] == "1" and trace[0][1] == "completed"
    assert run["status"] == "completed"
    assert run["duration_ms"] is not None


def test_voice_webhook_without_workflow_is_graceful(client, db):
    """No enabled incoming_call workflow -> polite fallback, no crash."""
    from app.modules.workflows import service as workflow_service

    for w in workflow_service.list_workflows(db):
        workflow_service.update_workflow(db, w, workflow_service.WorkflowUpdate(enabled=False))
    response = client.post(
        "/webhooks/africastalking/voice",
        data={"sessionId": "ATVoice_404", "callerNumber": "+234", "isActive": "1"},
    )
    assert response.status_code == 200
    assert response.json()["actions"][0]["action"] == "Say"


def test_webhook_accepts_json_payloads(client):
    response = client.post(
        "/webhooks/africastalking/sms",
        json={"from": "+234805", "to": "+234900", "text": "Thank you", "id": "msg_json"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
