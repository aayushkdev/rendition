from core.models.job import Job
from core.models.rendition import Rendition
from core.models.video import Video


def test_create_video_returns_video_id_and_creates_work(client, db_session):
    response = client.post("/api/v1/videos", json={"source": "s3://input/video.mp4"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["video_id"]

    assert db_session.query(Video).count() == 1
    assert db_session.query(Rendition).count() == 3
    assert db_session.query(Job).count() == 3


def test_get_video_returns_production_response_shape(client):
    create_response = client.post(
        "/api/v1/videos",
        json={"source": "s3://input/video.mp4"},
    )
    video_id = create_response.json()["video_id"]

    response = client.get(f"/api/v1/videos/{video_id}")

    assert response.status_code == 200
    assert response.json() == {
        "video_id": video_id,
        "status": "pending",
        "renditions": [
            {"resolution": "1080p", "status": "pending"},
            {"resolution": "720p", "status": "pending"},
            {"resolution": "480p", "status": "pending"},
        ],
    }


def test_get_video_returns_404_for_missing_video(client):
    response = client.get("/api/v1/videos/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Video not found"}
