from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", status_code=status.HTTP_200_OK)
def live():
    return {"status": "ok"}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "checks": {"database": "ok"}}
