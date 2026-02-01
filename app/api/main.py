from fastapi import FastAPI
from app.api.routers import root, videos

app = FastAPI(
    title="Rendition",
    description="Distributed video transcoding system",
)


API_PREFIX = "/api/v1"

app.include_router(root.router, prefix=API_PREFIX)
app.include_router(videos.router, prefix=API_PREFIX)
