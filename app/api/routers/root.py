from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/")
def root():
    return {
        "service": "rendition",
        "description": "Distributed video transcoding system",
        "status": "running",
    }
