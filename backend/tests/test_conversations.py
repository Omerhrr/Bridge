"""Dashboard stats and conversation API tests (spec §19, §27, §28)."""


def test_stats_after_activity(client):
    """Dashboard answers: sessions happened? failures visible? (spec §19)"""
    client.post(
        "/webhooks/africastalking/sms",
        data={"from": "+234801", "text": "Where are you?", "id": "stat_msg_1"},
    )
    response = client.get("/api/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["sms"] >= 1
    assert body["total_runs"] >= 1
    assert body["success_rate"] is not None
    assert len(body["recent_conversations"]) >= 1
    activity = {a["name"]: a for a in body["workflow_activity"]}
    assert "SMS Translator" in activity
    assert activity["SMS Translator"]["runs"] >= 1


def test_conversation_timeline_shows_communication(client):
    """Timeline contains the original message and its translation (spec §28)."""
    created = client.post(
        "/webhooks/africastalking/sms",
        data={"from": "+234809", "text": "How are you?", "id": "tl_msg_1"},
    )
    conversation_id = created.json()["conversation_id"]
    detail = client.get(f"/api/conversations/{conversation_id}").json()

    assert detail["status"] == "completed"
    assert detail["target_language"] == "ha"
    timeline = [(m["role"], m["content"]) for m in detail["messages"]]
    assert ("user", "How are you?") in timeline
    assert ("system", "ya kake") in timeline


def test_add_message_to_conversation(client):
    created = client.post(
        "/webhooks/africastalking/sms",
        data={"from": "+234810", "text": "Hello", "id": "add_msg_1"},
    )
    conversation_id = created.json()["conversation_id"]
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"role": "system", "channel": "sms", "content": "Operator note"},
    )
    assert response.status_code == 201
    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert any(m["content"] == "Operator note" for m in detail["messages"])


def test_conversation_filters_by_channel(client):
    client.post(
        "/webhooks/africastalking/sms",
        data={"from": "+234811", "text": "Hello", "id": "filter_msg_1"},
    )
    sms_list = client.get("/api/conversations", params={"channel": "sms"}).json()
    assert all(c["channel"] == "sms" for c in sms_list)
    voice_list = client.get("/api/conversations", params={"channel": "voice"}).json()
    assert isinstance(voice_list, list)
