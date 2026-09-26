"""Shared pytest configuration.

Test modules point DATABASE_URL at SQLite files whose "./name" paths resolve
against the process working directory. Two hazards this conftest removes:

1. Stale database files from a previous run break re-runs (workflows.name has
   a UNIQUE constraint), so every test DB artifact is removed before the
   session starts and after it finishes.
2. ``app.main`` is imported only once per pytest process, so only the first
   test module's environment variables take effect; all integration modules
   share one database. With the files wiped up front that shared database is
   empty at session start, which keeps the modules order-independent.
"""
import os
from pathlib import Path

import pytest

TEST_DB_FILES = ("test_api.db", "test_hackathon.db", "test.db", "smoke.db")


def _db_paths():
    # The test modules use relative SQLite URLs ("sqlite+aiosqlite:///./x.db"),
    # which resolve against the current working directory.
    cwd = Path.cwd()
    return [cwd / name for name in TEST_DB_FILES]


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    os.environ.setdefault("SEED_DEMO_DATA", "false")
    # Run SMS workflows inline so tests can assert on the run synchronously.
    os.environ.setdefault("SMS_BACKGROUND_PROCESSING", "false")
    # API tests exercise routes directly; test_auth.py switches auth back on.
    os.environ.setdefault("AUTH_ENABLED", "false")
    for path in _db_paths():
        if path.exists():
            path.unlink()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    # Leave the working tree clean: the artifacts are disposable.
    for path in _db_paths():
        if path.exists():
            path.unlink()
