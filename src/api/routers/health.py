from __future__ import annotations

from fastapi import APIRouter, HTTPException
from redis import Redis
from sqlalchemy import text

from src.core.config import settings
from src.db.session import SessionLocal

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/readiness")
async def readiness() -> dict[str, str]:
    db_ok = False
    redis_ok = False

    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
        db_ok = True

    redis_client = Redis.from_url(settings.REDIS_URL)
    try:
        redis_ok = bool(redis_client.ping())
    finally:
        redis_client.close()

    if not (db_ok and redis_ok):
        raise HTTPException(status_code=503, detail="Dependencies not ready")

    return {"status": "ready"}