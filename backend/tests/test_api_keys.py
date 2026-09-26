"""API key lifecycle and the public assistant endpoint: creation, listing,
revocation, X-Api-Key auth, and rate limiting. The LLM is faked."""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_api_keys.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.knowledge import apikeys as apikeys_module  # noqa: E402
from app.modules.knowledge import assistant as assistant_module  # noqa: E402

NEXT_ANSWER: dict = {}


async def fake_chat_json(system, user, **_):
    if "prepare a knowledge-base search" in system:
        return {"language": "en", "is_question": True, "question_en": user, "keywords": ["hours"]}
    return dict(NEXT_ANSWER)


@pytest.fixture(scope="module")
def client():
    saved = {k: getattr(settings, k) for k in ("ai_api_key", "ai_provider")}
    original_chat = assistant_module.chat_json
    settings.ai_api_key, settings.ai_provider = "test-key", "deepseek"
    assistant_module.chat_json = fake_chat_json
    apikeys_module.RATE_LIMIT_OVERRIDE = None
    with TestClient(app) as c:
        c.post("/api/v1/knowledge/sources", json={
            "kind": "text", "name": "FAQ",
            "config": {"text": "Opening hours: Monday to Saturday, 8am to 7pm. Closed Sundays."},
        })
        yield c
    for key, value in saved.items():
        setattr(settings, key, value)
    assistant_module.chat_json = original_chat


def test_create_key_returns_plaintext_once(client):
    resp = client.post("/api/v1/api-keys", json={"name": "Website widget"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["key"].startswith("brdg_")
    assert data["prefix"] == data["key"][:11]
    assert data["revoked_at"] is None


def test_list_keys_never_returns_plaintext(client):
    client.post("/api/v1/api-keys", json={"name": "Second key"})
    resp = client.get("/api/v1/api-keys")
    assert resp.status_code == 200
    for key in resp.json():
        assert "key" not in key


def test_public_ask_rejects_missing_or_bad_key(client):
    resp = client.post("/api/v1/public/assistant/ask", json={"question": "When are you open?"})
    assert resp.status_code == 401
    resp = client.post(
        "/api/v1/public/assistant/ask",
        json={"question": "When are you open?"},
        headers={"X-Api-Key": "brdg_not-a-real-key"},
    )
    assert resp.status_code == 401


def test_public_ask_answers_with_a_valid_key(client):
    raw_key = client.post("/api/v1/api-keys", json={"name": "For asking"}).json()["key"]
    NEXT_ANSWER.update({
        "answerable": True, "answer": "We're open 8am to 7pm, Monday to Saturday.",
        "evidence": ["Monday to Saturday, 8am to 7pm"], "sources": ["S1"],
    })
    resp = client.post(
        "/api/v1/public/assistant/ask",
        json={"question": "When are you open?"},
        headers={"X-Api-Key": raw_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answered"] is True
    assert "8am" in data["answer"]


def test_revoked_key_is_rejected(client):
    created = client.post("/api/v1/api-keys", json={"name": "To revoke"}).json()
    client.delete(f"/api/v1/api-keys/{created['id']}")
    resp = client.post(
        "/api/v1/public/assistant/ask",
        json={"question": "When are you open?"},
        headers={"X-Api-Key": created["key"]},
    )
    assert resp.status_code == 401


def test_rate_limit_blocks_after_the_budget_is_used(client, monkeypatch):
    monkeypatch.setattr(apikeys_module, "RATE_LIMIT", 2)
    raw_key = client.post("/api/v1/api-keys", json={"name": "Rate limited"}).json()["key"]
    NEXT_ANSWER.update({"answerable": True, "answer": "We're open 8am to 7pm.",
                        "evidence": ["8am to 7pm"], "sources": ["S1"]})
    for _ in range(2):
        resp = client.post(
            "/api/v1/public/assistant/ask",
            json={"question": "When are you open?"},
            headers={"X-Api-Key": raw_key},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/api/v1/public/assistant/ask",
        json={"question": "When are you open?"},
        headers={"X-Api-Key": raw_key},
    )
    assert resp.status_code == 429


def test_public_ask_preflight_gets_permissive_cors_headers(client):
    resp = client.options(
        "/api/v1/public/assistant/ask",
        headers={"Origin": "https://example-customer-site.com",
                  "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 204
    assert resp.headers["access-control-allow-origin"] == "https://example-customer-site.com"
