"""Africa's Talking can reject a well-formed sender id/shortcode with
InvalidSenderId when the account itself hasn't provisioned it for SMS (a
shortcode registered only for USSD/Voice, for example). Retrying once
without a "from" value means the reply still reaches the person instead of
failing outright every time until the account is reconfigured.
"""
import pytest

from app.core.config import settings
from app.modules.communications.sms import AfricaTalkingSMSProvider


def _at_response(status_code: int, status: str = "Success"):
    return {"SMSMessageData": {"Recipients": [{"statusCode": status_code, "status": status,
                                               "messageId": "ATXid_123"}]}}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def _configure_at(monkeypatch):
    monkeypatch.setattr(settings, "at_username", "sandbox")
    monkeypatch.setattr(settings, "at_api_key", "test-key")
    monkeypatch.setattr(settings, "at_sandbox", True)


@pytest.mark.asyncio
async def test_retries_without_sender_id_when_rejected(monkeypatch):
    calls = []

    async def fake_post(self, url, data=None, headers=None):
        calls.append(dict(data))
        if "from" in data:
            return _FakeResponse(_at_response(406, "InvalidSenderId"))
        return _FakeResponse(_at_response(101, "Sent"))

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    result = await AfricaTalkingSMSProvider().send_sms("+254700000000", "hello", sender_id="57000")

    assert result.status == "sent"
    assert len(calls) == 2
    assert calls[0]["from"] == "57000"
    assert "from" not in calls[1]


@pytest.mark.asyncio
async def test_does_not_retry_when_no_sender_id_was_used(monkeypatch):
    calls = []

    async def fake_post(self, url, data=None, headers=None):
        calls.append(dict(data))
        return _FakeResponse(_at_response(406, "InvalidSenderId"))

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    with pytest.raises(RuntimeError):
        await AfricaTalkingSMSProvider().send_sms("+254700000000", "hello", sender_id=None)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_other_rejection_reasons_are_not_retried(monkeypatch):
    calls = []

    async def fake_post(self, url, data=None, headers=None):
        calls.append(dict(data))
        return _FakeResponse(_at_response(500, "InsufficientBalance"))

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    with pytest.raises(RuntimeError, match="InsufficientBalance"):
        await AfricaTalkingSMSProvider().send_sms("+254700000000", "hello", sender_id="57000")

    assert len(calls) == 1
