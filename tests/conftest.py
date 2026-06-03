import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from core.db.base import Base
from core.db.session import get_db
from core.models import job, outbox, rendition, upload_session, video  # noqa: F401
from core.queue import get_job_queue_publisher
from core.storage import (
    CompletedUploadPart,
    MultipartUploadPart,
    MultipartUploadSession,
    ObjectMetadata,
    get_object_storage,
)


class FakeObjectStorage:
    bucket = "test-bucket"
    fail_create = False

    def __init__(self):
        self.completed_uploads = []
        self.aborted_uploads = []
        self.deleted_objects = []
        self.metadata_by_key = {}
        self.completed_content_length = 12_345
        self.completed_content_type = "video/mp4"
        self.fail_complete = False
        self.fail_delete = False

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
        if self.fail_complete:
            from core.storage import ObjectStorageError

            raise ObjectStorageError("complete failed")

        self.completed_uploads.append(
            {"key": key, "upload_id": upload_id, "parts": parts}
        )
        self.metadata_by_key[key] = ObjectMetadata(
            content_length=self.completed_content_length,
            content_type=self.completed_content_type,
        )

    def object_exists(self, key: str) -> bool:
        return key in self.metadata_by_key

    def get_object_metadata(self, key: str) -> ObjectMetadata | None:
        return self.metadata_by_key.get(key)

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        if getattr(self, "fail_abort", False):
            from core.storage import ObjectStorageError

            raise ObjectStorageError("abort failed")

        self.aborted_uploads.append({"key": key, "upload_id": upload_id})

    def delete_object(self, key: str) -> None:
        if self.fail_delete:
            from core.storage import ObjectStorageError

            raise ObjectStorageError("delete failed")

        self.deleted_objects.append(key)
        self.metadata_by_key.pop(key, None)


class FakeJobQueuePublisher:
    def __init__(self):
        self.published_messages = []
        self.session_count = 0

    def session(self):
        self.session_count += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def publish_encoding_job(self, message, exchange: str, routing_key: str) -> None:
        self.published_messages.append(
            {
                "message": message,
                "exchange": exchange,
                "routing_key": routing_key,
            }
        )


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
            test_client.storage = storage
            test_client.publisher = publisher
            yield test_client
    finally:
        app.dependency_overrides.clear()
