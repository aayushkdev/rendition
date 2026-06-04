import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typing import cast

from api.main import app
from core.db.base import Base
from core.db.session import get_db
from core.models import job, outbox, rendition, upload_session, video  # noqa: F401
from core.queue import get_job_queue_publisher
from core.storage import (
    get_object_storage,
)
from tests.fakes import FakeJobQueuePublisher, FakeObjectStorage


class TestClientWithFakes(TestClient):
    storage: FakeObjectStorage
    publisher: FakeJobQueuePublisher


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    storage = FakeObjectStorage()
    publisher = FakeJobQueuePublisher()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_job_queue_publisher] = lambda: publisher
    try:
        with TestClient(app) as test_client:
            typed_client = cast(TestClientWithFakes, test_client)
            typed_client.storage = storage
            typed_client.publisher = publisher
            yield typed_client
    finally:
        app.dependency_overrides.clear()
