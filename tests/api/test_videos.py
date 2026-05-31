from core.models.job import Job
from core.models.rendition import Rendition
from core.models.enums import UploadStatus
from core.models.upload_session import UploadSession
from core.models.video import Video


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
        json={"parts": [{"part_number": 1, "etag": "etag-1"}]},
    )

    assert complete_response.status_code == 200
    upload_session = db_session.query(UploadSession).one()
    assert upload_session.status == UploadStatus.completed
    assert upload_session.completed_at is not None
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
            "part_count": 1,
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
        json={"parts": [{"part_number": 1, "etag": "etag-1"}]},
    )

    response = client.post(
        f"/api/v1/videos/{video_id}/upload/complete",
        json={"parts": [{"part_number": 1, "etag": "etag-1"}]},
    )

    assert response.status_code == 409


def test_get_video_returns_404_for_missing_video(client):
    response = client.get("/api/v1/videos/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Video not found"}
