"""Shared fixtures. Integration tests need PostgreSQL (see TEST_DATABASE_URL)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import create_app


@pytest.fixture(scope="session")
def postgres_engine():
    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://registry:registry@127.0.0.1:5433/portal_registry",
    )
    try:
        eng = create_engine(database_url, pool_pre_ping=True, future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — surface connection errors as skip
        pytest.skip(f"Integration tests need PostgreSQL: {exc}")
    return eng


@pytest.fixture
def db_session(postgres_engine):
    SessionLocal = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    session = SessionLocal()
    session.execute(text("TRUNCATE audits, releases, features RESTART IDENTITY CASCADE"))
    session.commit()
    yield session
    session.execute(text("TRUNCATE audits, releases, features RESTART IDENTITY CASCADE"))
    session.commit()
    session.close()


@pytest.fixture
def client(db_session):
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
