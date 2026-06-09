from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import logger

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe. Indicates if the API server process is running."""
    return {"status": "healthy", "version": "1.0.0"}


@router.get("/readiness", status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe. Checks connectivity to Postgres and Redis.
    Returns 503 if any service is down.
    """
    db_healthy = False
    redis_healthy = False
    details = {}

    # 1. Test Postgres Connection
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
        details["postgres"] = "connected"
    except Exception as e:
        logger.error(f"Readiness check failed - Postgres connection issue: {e}")
        details["postgres"] = f"unhealthy: {str(e)}"

    # 2. Test Redis Connection
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        await redis_client.ping()
        await redis_client.close()
        redis_healthy = True
        details["redis"] = "connected"
    except Exception as e:
        logger.error(f"Readiness check failed - Redis connection issue: {e}")
        details["redis"] = f"unhealthy: {str(e)}"

    if not db_healthy or not redis_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unready", "components": details}
        )

    return {"status": "ready", "components": details}
