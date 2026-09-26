"""Messaging tests: the Bridge relay, translated sends, contacts and the
DeepSeek-backed translator. Telecom and AI providers are faked so the tests
run offline and deterministically."""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_hackathon.db")

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.modules.ai import service as ai_service_module  # noqa: E402
from app.modules.ai.translation import TranslationResult, TranslationService  # noqa: E402
from app.modules.communications import service as comms_service_module  # noqa: E402
from app.modules.communications.sms import SMSProvider, SmsSendResult  # noqa: E402
from app.modules.messaging.service import InvalidPhoneNumber, normalize_phone  # noqa: E402

SMS_URL = "/api/v1/webhooks/africastalking/sms"
AMINA = "+2348031234567"   # writes Hausa
JUMA = "+254712345678"     # writes Swahili
SHORTCODE = "57000"

OUTBOX: list[dict] = []


class FakeSMS(SMSProvider):
    provider = "fake"

    async def send_sms(self, to, text, sender_id=None):
        OUTBOX.append({"to": to, "text": text, "from": sender_id})
        return SmsSendResult(message_id=f"fake-{len(OUTBOX)}", status="success", provider="fake")


class FakeTranslator(TranslationService):
    """Detects by keyword and marks translations with the target code."""

    @staticmethod
    def _lang(text: str) -> str:
        lowered = text.lower()
        if "sannu" in lowered or "ina" in lowered:
            return "ha"
        if "habari" in lowered or "asante" in lowered:
            return "sw"
        return "en"

    async def translate(self, text, source="auto", target="en"):
        detected = source if source not in ("", "auto") else self._lang(text)
        if detected == target:
            return TranslationResult(text=text, source=detected, target=target, provider="fake")
        return TranslationResult(text=f"<{target}> {text}", source=detected, target=target, provider="fake")

    async def detect(self, text):
        return self._lang(text)


@pytest.fixture(scope="module")
def client():
    patches = [
        (comms_service_module, "get_sms_provider", lambda: FakeSMS()),
        (ai_service_module, "get_translation_service", lambda: FakeTranslator()),
    ]
    originals = [(mod, name, getattr(mod, name)) for mod, name, _ in patches]
    for mod, name, value in patches:
        setattr(mod, name, value)
    with TestClient(app) as c:
        # Make a relay workflow the only active SMS workflow.
        for wf in c.get("/api/v1/workflows").json():
            if wf["status"] == "active":
                c.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "inactive"})
        wf = c.post("/api/v1/workflows", json={
            "name": "Relay under test",
            "definition": {
                "nodes": [
                    {"id": "1", "type": "incoming_sms", "config": {}},
                    {"id": "2", "type": "bridge_relay", "config": {}},
                ],
                "edges": [{"source": "1", "target": "2"}],
            },
        }).json()
        c.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "active"})
        yield c
        c.patch(f"/api/v1/workflows/{wf['id']}", json={"status": "inactive"})
    for mod, name, value in originals:
        setattr(mod, name, value)


def _sms(client, sender, text, msg_id):
    OUTBOX.clear()
    resp = client.post(SMS_URL, data={"from": sender, "to": SHORTCODE, "text": text, "id": msg_id})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_normalize_phone():
    assert normalize_phone("+254 712-345-678") == "+254712345678"
    assert normalize_phone("00254712345678") == "+254712345678"
    assert normalize_phone("0803 123 4567", reference="+2348000000000") == "+2348031234567"
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("12345")


def test_unknown_sender_gets_help(client):
    body = _sms(client, AMINA, "Sannu", "r-1")
    assert body["status"] == "completed"
    assert len(OUTBOX) == 1
    reply = OUTBOX[0]
    assert reply["to"] == AMINA and reply["from"] == SHORTCODE
    # Help is localized into the detected language (Hausa).
    assert reply["text"].startswith("<ha>") and "TO +2547" in reply["text"]


def test_set_language_command(client):
    _sms(client, JUMA, "LANG Swahili", "r-2")
    assert "Swahili" in OUTBOX[0]["text"]
    contacts = {c["phone_number"]: c for c in client.get("/api/v1/contacts").json()}
    assert contacts[JUMA]["language"] == "sw"
    assert contacts[JUMA]["language_locked"] is True


def test_relay_translates_both_ways(client):
    _sms(client, AMINA, f"TO {JUMA} Ina kwana?", "r-3")
    to_juma = next(m for m in OUTBOX if m["to"] == JUMA)
    assert to_juma["from"] == SHORTCODE
    assert "<sw> Ina kwana?" in to_juma["text"] and AMINA in to_juma["text"]
    confirm = next(m for m in OUTBOX if m["to"] == AMINA)
    assert "Swahili" in confirm["text"]

    # Juma just replies: it goes back to Amina, in Hausa.
    _sms(client, JUMA, "Habari njema", "r-4")
    assert len(OUTBOX) == 1
    assert OUTBOX[0]["to"] == AMINA and "<ha> Habari njema" in OUTBOX[0]["text"]


def test_local_number_uses_sender_country_code(client):
    _sms(client, AMINA, "TO 08031112222 Sannu", "r-5")
    assert any(m["to"] == "+2348031112222" for m in OUTBOX)


def test_stop_ends_chat(client):
    _sms(client, JUMA, "STOP", "r-6")
    assert len(OUTBOX) == 1 and OUTBOX[0]["to"] == JUMA
    contacts = {c["phone_number"]: c for c in client.get("/api/v1/contacts").json()}
    assert contacts[JUMA]["partner_number"] is None


def test_message_log_records_both_directions(client):
    log = client.get("/api/v1/messages/log", params={"phone": JUMA}).json()
    kinds = {(m["direction"], m["kind"]) for m in log}
    assert ("inbound", "inbound") in kinds and ("outbound", "relay") in kinds
    relay = next(m for m in log if m["kind"] == "relay" and m["to_number"] == JUMA)
    assert relay["from_number"] == AMINA and relay["target_language"] == "sw"


def test_broadcast_translates_per_recipient(client):
    OUTBOX.clear()
    resp = client.post("/api/v1/messages/send", json={
        "recipients": [AMINA, JUMA, "+233201234567", "nope"],
        "text": "Clinic opens at 9am tomorrow",
        "language": "contact",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sent"] == 3 and body["failed"] == 1
    by_to = {m["to"]: m for m in OUTBOX}
    assert by_to[AMINA]["text"] == "<ha> Clinic opens at 9am tomorrow"
    assert by_to[JUMA]["text"] == "<sw> Clinic opens at 9am tomorrow"
    # Unknown language: sent as written.
    assert by_to["+233201234567"]["text"] == "Clinic opens at 9am tomorrow"


def test_send_with_fixed_language_and_preview(client):
    OUTBOX.clear()
    resp = client.post("/api/v1/messages/send", json={
        "recipients": [JUMA], "text": "Hello", "language": "French"})
    assert resp.json()["results"][0]["target_language"] == "fr"
    assert OUTBOX[0]["text"] == "<fr> Hello"
    preview = client.post("/api/v1/messages/translate", json={"text": "Hello", "language": "yo"}).json()
    assert preview["text"] == "<yo> Hello" and preview["target_language"] == "yo"
    assert client.post("/api/v1/messages/send", json={
        "recipients": [JUMA], "text": "x", "language": "klingon"}).status_code == 422


def test_contacts_crud(client):
    created = client.post("/api/v1/contacts", json={
        "phone_number": "+255 754 000 111", "name": "Neema", "language": "Swahili"}).json()
    assert created["phone_number"] == "+255754000111" and created["language"] == "sw"
    patched = client.patch(f"/api/v1/contacts/{created['id']}", json={"language": ""}).json()
    assert patched["language"] is None and patched["language_locked"] is False
    assert client.delete(f"/api/v1/contacts/{created['id']}").status_code == 204
    assert client.get("/api/v1/languages").json()[0]["name"]


def test_llm_translator_parses_deepseek_reply(monkeypatch):
    from app.modules.ai import translation

    captured = {}

    async def fake_chat_json(system, user, **_):
        captured["user"] = user
        return {"detected_language": "yo", "translation": "Good morning"}

    monkeypatch.setattr(translation, "chat_json", fake_chat_json)
    result = asyncio.run(translation.LLMTranslationService().translate("E kaaro", target="English"))
    assert result.text == "Good morning" and result.source == "yo" and result.target == "en"
    assert "English (en)" in captured["user"]


def test_sms_webhook_background_mode(client):
    from app.core.config import settings

    settings.sms_background_processing = True
    try:
        OUTBOX.clear()
        resp = client.post(SMS_URL, data={"from": AMINA, "to": SHORTCODE, "text": "HELP", "id": "bg-1"})
        assert resp.json()["status"] == "accepted"
        # TestClient waits for background tasks: the reply has been sent.
        assert OUTBOX and OUTBOX[0]["to"] == AMINA
        inbound = next(m for m in client.get("/api/v1/messages/log").json() if m["direction"] == "inbound")
        assert inbound["run_id"]
        # A retried delivery is ignored.
        again = client.post(SMS_URL, data={"from": AMINA, "to": SHORTCODE, "text": "HELP", "id": "bg-1"})
        assert again.json()["status"] == "duplicate_ignored"
    finally:
        settings.sms_background_processing = False


def test_sender_with_decoded_plus_is_normalized(client):
    # A "+" form-decoded into a space must still match the saved contact.
    _sms(client, " 254712345678", "HELP", "r-plus")
    assert OUTBOX[0]["to"] == JUMA
