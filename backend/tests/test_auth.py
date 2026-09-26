"""Authentication: protected API, first-run owner setup, sign-in."""
import os

os.environ["SEED_DEMO_DATA"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_hackathon.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import update  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    saved = (settings.auth_enabled, settings.setup_code, settings.allow_registration)
    settings.auth_enabled, settings.setup_code, settings.allow_registration = True, "open-sesame", False
    with TestClient(app) as c:
        # Start from "no active users" regardless of what other modules created.
        import asyncio

        from app.core.database import async_session_factory
        from app.modules.workflows.models import User

        async def deactivate_all():
            async with async_session_factory() as session:
                await session.execute(update(User).values(is_active=False))
                await session.commit()

        asyncio.run(deactivate_all())
        yield c
    settings.auth_enabled, settings.setup_code, settings.allow_registration = saved


def test_protected_routes_need_a_token(client):
    assert client.get("/api/v1/workflows").status_code == 401
    assert client.get("/api/v1/knowledge/sources").status_code == 401
    assert client.get("/api/v1/health").status_code == 200
    # Telecom webhooks stay public.
    assert client.post("/api/v1/webhooks/africastalking/ussd", data={
        "sessionId": "auth-1", "serviceCode": "*1#", "phoneNumber": "+254700000009", "text": ""}).status_code == 200


def test_owner_setup_requires_code(client):
    status = client.get("/api/v1/auth/setup").json()
    assert status["needs_setup"] and status["setup_code_required"]
    body = {"email": "owner@shop.example", "password": "a-strong-pass", "full_name": "Owner"}
    assert client.post("/api/v1/auth/register", json={**body, "setup_code": "wrong"}).status_code == 403
    resp = client.post("/api/v1/auth/register", json={**body, "setup_code": "open-sesame"})
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    assert client.get("/api/v1/workflows", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    # Registration closes once the owner exists.
    assert client.get("/api/v1/auth/setup").json()["needs_setup"] is False
    assert client.post("/api/v1/auth/register", json={
        "email": "intruder@x.example", "password": "whatever12"}).status_code == 403


def test_login_and_me(client):
    bad = client.post("/api/v1/auth/login", data={"username": "owner@shop.example", "password": "nope"})
    assert bad.status_code == 401
    good = client.post("/api/v1/auth/login", data={"username": "Owner@Shop.example", "password": "a-strong-pass"})
    assert good.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {good.json()['access_token']}"})
    assert me.json()["email"] == "owner@shop.example"
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
