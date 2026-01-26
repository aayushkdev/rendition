from fastapi import FastAPI
from api.routers import root

app = FastAPI(
    title="Rendition",
    description="Distributed video transcoding system",
)

app.include_router(root.router)
