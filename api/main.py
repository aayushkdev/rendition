from fastapi import FastAPI
from api.errors import register_exception_handlers
from api.middleware.request_id import request_id_middleware
from api.routers import health, root, videos

app = FastAPI(
    title="Rendition",
    description="Distributed video transcoding system",
)

app.middleware("http")(request_id_middleware)
register_exception_handlers(app)

API_PREFIX = "/api/v1"

app.include_router(root.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(videos.router, prefix=API_PREFIX)
