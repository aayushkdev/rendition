from core.models.job import Job
from core.models.outbox import OutboxMessage
from core.models.rendition import Rendition
from core.models.enums import UploadStatus
from core.models.upload_session import UploadSession
from core.models.video import Video


def test_get_upload_config_returns_backend_limits(client):
    response = client.get("/api/v1/videos/upload/config")

    assert response.status_code == 200
    assert response.json() == {
        "max_size_bytes": 5_368_709_120,
        "max_part_count": 10_000,
        "part_size_bytes": 8_388_608,
        "allowed_content_types": [
            "video/mp4",
            "video/quicktime",
            "video/x-matroska",
        ],
    }


def test_list_videos_returns_persisted_uploads(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.get("/api/v1/videos")

    assert response.status_code == 200
    assert response.json() == [
        {
            "video_id": video_id,
            "title": "video.mp4",
            "uploaded_at": None,
            "created_at": response.json()[0]["created_at"],
            "status": "uploading",
            "size_bytes": 12_345,
        }
    ]


def test_create_video_returns_multipart_upload_session(client, db_session):
    response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["video_id"]
    assert payload["bucket"] == "test-bucket"
    assert payload["key"].endswith("/video.mp4")
    assert payload["upload_id"] == "test-upload-id"
    assert [part["part_number"] for part in payload["parts"]] == [1, 2]

    assert db_session.query(Video).count() == 1
    assert db_session.query(UploadSession).count() == 1
    assert db_session.query(Rendition).count() == 0
    assert db_session.query(Job).count() == 0
    assert db_session.query(OutboxMessage).count() == 0


def test_create_video_rejects_invalid_upload_request(client):
    response = client.post(
        "/api/v1/videos",
        json={
            "filename": "../video.mp4",
            "content_type": "application/octet-stream",
            "size_bytes": 0,
            "part_count": 0,
        },
    )

    assert response.status_code == 422
    assert response.headers["X-Request-ID"]
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_create_video_returns_standard_storage_error(client):
    client.storage.fail_create = True

    response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "storage_unavailable",
        "message": "Storage unavailable",
        "request_id": response.headers["X-Request-ID"],
    }


def test_get_video_returns_production_response_shape(client, db_session):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]
    complete_response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [{"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        },
    )

    assert complete_response.status_code == 200
    upload_session = db_session.query(UploadSession).one()
    assert upload_session.status == UploadStatus.completed
    assert upload_session.completed_at is not None
    assert db_session.query(Job).count() == 3
    outbox_messages = db_session.query(OutboxMessage).order_by(OutboxMessage.created_at)
    assert outbox_messages.count() == 3
    assert {
        (message.job_id, message.video_id, message.rendition_id)
        for message in outbox_messages
    } == {
        (job.id, job.video_id, job.rendition_id) for job in db_session.query(Job).all()
    }
    assert {message.status for message in outbox_messages} == {"published"}
    assert len(client.publisher.published_messages) == 3
    assert {
        (
            published["message"].job_id,
            published["message"].video_id,
            published["message"].rendition_id,
        )
        for published in client.publisher.published_messages
    } == {
        (job.id, job.video_id, job.rendition_id) for job in db_session.query(Job).all()
    }
    assert complete_response.json() == {
        "video_id": video_id,
        "status": "pending",
        "renditions": [
            {"resolution": "1080p", "status": "pending"},
            {"resolution": "720p", "status": "pending"},
            {"resolution": "480p", "status": "pending"},
        ],
    }

    response = client.get(f"/api/v1/videos/{video_id}")

    assert response.status_code == 200
    assert response.json() == complete_response.json()


def test_refresh_upload_returns_new_part_urls(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/refresh",
        json={"part_count": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == video_id
    assert payload["upload_id"] == "test-upload-id"
    assert [part["part_number"] for part in payload["parts"]] == [1, 2]
    assert "refreshPartNumber=1" in payload["parts"][0]["upload_url"]


def test_refresh_upload_rejects_part_count_mismatch(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/refresh",
        json={"part_count": 1},
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_upload_parts",
        "message": "refresh part count must match upload session",
        "request_id": response.headers["X-Request-ID"],
    }


def test_abort_upload_marks_video_failed(client, db_session):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.delete(f"/api/v1/videos/{video_id}/upload")

    assert response.status_code == 204
    upload_session = db_session.query(UploadSession).one()
    assert upload_session.status == UploadStatus.aborted
    assert upload_session.aborted_at is not None

    state_response = client.get(f"/api/v1/videos/{video_id}")
    assert state_response.status_code == 200
    assert state_response.json()["status"] == "failed"


def test_complete_upload_rejects_inactive_upload(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]
    client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [{"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        },
    )

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [{"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "upload_not_active",
        "message": "video upload is not active",
        "request_id": response.headers["X-Request-ID"],
    }


def test_complete_upload_rejects_out_of_order_parts(client, db_session):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [
                {"part_number": 2, "etag": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
                {"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
            ]
        },
    )

    assert response.status_code == 400
    assert db_session.query(UploadSession).one().status == UploadStatus.active
    assert client.storage.completed_uploads == []
    assert response.json()["error"] == {
        "code": "invalid_upload_parts",
        "message": "upload parts must be ordered and complete from 1 to part_count",
        "request_id": response.headers["X-Request-ID"],
    }


def test_complete_upload_rejects_missing_parts(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [{"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        },
    )

    assert response.status_code == 400
    assert client.storage.completed_uploads == []
    assert response.json()["error"]["code"] == "invalid_upload_parts"


def test_complete_upload_rejects_duplicate_parts(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 2,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [
                {"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
                {"part_number": 1, "etag": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
            ]
        },
    )

    assert response.status_code == 400
    assert client.storage.completed_uploads == []
    assert response.json()["error"]["code"] == "invalid_upload_parts"


def test_complete_upload_rejects_blank_etag(client):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={"parts": [{"part_number": 1, "etag": "   "}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_complete_upload_rejects_storage_metadata_mismatch(client, db_session):
    create_response = client.post(
        "/api/v1/videos",
        json={
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": 12_345,
            "part_count": 1,
        },
    )
    video_id = create_response.json()["video_id"]
    client.storage.completed_content_length = 999

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={
            "parts": [{"part_number": 1, "etag": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
        },
    )

    assert response.status_code == 502
    upload_session = db_session.query(UploadSession).one()
    assert upload_session.status == UploadStatus.failed
    assert upload_session.error == "completed upload size mismatch"
    assert client.storage.deleted_objects == [upload_session.object_key]
    assert response.json()["error"] == {
        "code": "storage_unavailable",
        "message": "Storage unavailable",
        "request_id": response.headers["X-Request-ID"],
    }


def test_get_video_returns_404_for_missing_video(client):
    response = client.get(
        "/api/v1/videos/00000000-0000-0000-0000-000000000000",
        headers={"X-Request-ID": "test-request-id"},
    )

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "test-request-id"
    assert response.json() == {
        "error": {
            "code": "video_not_found",
            "message": "Video not found",
            "request_id": "test-request-id",
        }
    }
