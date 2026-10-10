import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
import app.tasks.worker as worker


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(worker, "SessionLocal", TestingSession)
    monkeypatch.setattr("app.services.storage.CERTIFICATE_STORAGE_DIR", tmp_path / "certificates")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def payload():
    return {"event_name": "Python Workshop", "issue_date": "2026-10-09", "recipients": [
        {"recipient_name": "Ada Lovelace", "recipient_email": "ada@example.com", "metadata": {"grade": "A"}},
        {"recipient_name": "Grace Hopper", "recipient_email": "grace@example.com"},
        {"recipient_name": "Alan Turing", "recipient_email": "alan@example.com"},
    ]}
