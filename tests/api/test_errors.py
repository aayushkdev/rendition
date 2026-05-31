from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from api.errors import register_exception_handlers
from api.middleware.request_id import request_id_middleware


def test_unhandled_errors_use_standard_response():
    app = FastAPI()
    app.middleware("http")(request_id_middleware)
    register_exception_handlers(app)

    router = APIRouter()

    @router.get("/api/v1/test-error")
    def test_error():
        raise RuntimeError("boom")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            "/api/v1/test-error",
            headers={"X-Request-ID": "error-id"},
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "error-id"
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": "error-id",
        }
    }
