from fastapi import APIRouter, HTTPException

from DAL.db import database_is_ready

router = APIRouter(prefix="/health", tags=["Operations"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    if not database_is_ready():
        raise HTTPException(status_code=503, detail="Database is not ready")
    return {"status": "ok", "database": "ready"}
