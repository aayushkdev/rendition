import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from core.db.base import Base
from core.db.session import get_db
from core.models import job, rendition, upload_session, video  # noqa: F401
from core.storage import (
    CompletedUploadPart,
    MultipartUploadPart,
    MultipartUploadSession,
    get_object_storage,
)


class FakeObjectStorage:
    bucket = "test-bucket"
    fail_create = False

    def __init__(self):
        self.completed_uploads = []
        self.aborted_uploads = []
        self.existing_keys = set()

    def create_multipart_upload(
        self,
        key: str,
        content_type: str,
        part_count: int,
    ) -> MultipartUploadSession:
        if self.fail_create:
            from core.storage import ObjectStorageError

            raise ObjectStorageError("storage unavailable")

        return MultipartUploadSession(
            bucket=self.bucket,
            key=key,
            upload_id="test-upload-id",
            parts=[
                MultipartUploadPart(
                    part_number=part_number,
                    upload_url=f"http://storage.test/{key}?partNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ],
        )

    def refresh_multipart_upload_urls(
        self,
        key: str,
        upload_id: str,
        part_count: int,
    ) -> MultipartUploadSession:
        return MultipartUploadSession(
            bucket=self.bucket,
            key=key,
            upload_id=upload_id,
            parts=[
                MultipartUploadPart(
                    part_number=part_number,
                    upload_url=f"http://storage.test/{key}?refreshPartNumber={part_number}",
                )
                for part_number in range(1, part_count + 1)
            ],
        )

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[CompletedUploadPart],
    ) -> None:
        self.completed_uploads.append(
            {"key": key, "upload_id": upload_id, "parts": parts}
        )
        self.existing_keys.add(key)

    def object_exists(self, key: str) -> bool:
        return key in self.existing_keys

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        self.aborted_uploads.append({"key": key, "upload_id": upload_id})


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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage] = lambda: storage
    try:
        with TestClient(app) as test_client:
            test_client.storage = storage
            yield test_client
    finally:
        app.dependency_overrides.clear()
