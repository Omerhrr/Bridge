"""Test fixtures: one shared in-memory SQLite database for app + tests.

The app's lifespan (init_db) and the API routes all go through
``app.core.database.engine`` / ``SessionLocal`` — patching those module
globals to a single StaticPool engine gives every layer the same database.
"""

import os

# Isolate from any local .env / global env before importing the app.
os.environ["BRIDGE_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["BRIDGE_COMMS_PROVIDER"] = "mock"
os.environ.pop("BRIDGE_API_TOKEN", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.core.database as database  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.workflows import service as workflow_service  # noqa: E402
from app.modules.workflows.schemas import WorkflowDefinition  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    original_engine, original_session_local = database.engine, database.SessionLocal
    database.engine = engine
    database.SessionLocal = TestingSession
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:  # lifespan runs init_db + seeding on this engine
        yield test_client

    database.engine, database.SessionLocal = original_engine, original_session_local


@pytest.fixture()
def db(client):
    """Direct session sharing the same database as the test client."""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def voice_workflow(db):
    return workflow_service.get_workflow_by_name(db, "Voice Translator")


@pytest.fixture()
def sms_workflow(db):
    return workflow_service.get_workflow_by_name(db, "SMS Translator")


@pytest.fixture()
def sample_definition() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(workflow_service.SMS_TRANSLATOR)
