from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.router import router as bot_router
from app.core.config import settings
from app.core.db import engine, get_db
from app.core.dependencies import close_redis, get_redis
from app.core.logging_config import configure_logging
from app.core.rate_limiter import limiter
from app.db.base import Base
import app.models  # noqa: F401 — регистрация таблиц в Base.metadata
from app.middleware.logging import StructlogMiddleware
from app.services.whitelist import WhitelistService

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    redis = await get_redis()
    service = WhitelistService(redis)
    try:
        await service.refresh_cache()
    except ProgrammingError:
        logger.warning(
            "Whitelist cache refresh skipped: database tables are not initialized"
        )
    logger.info("Application started", app_env=settings.APP_ENV)
    yield
    await close_redis()
    logger.info("Application shutdown")


app = FastAPI(
    title="Telegram Gateway",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(StructlogMiddleware)
app.include_router(bot_router)



@app.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    checks: dict[str, str] = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check: DB unavailable", error=str(exc))
        checks["db"] = "error"
        checks["status"] = "degraded"

    try:
        if not await redis.ping():
            raise ConnectionError("Redis ping failed")
    except Exception as exc:
        logger.error("Health check: Redis unavailable", error=str(exc))
        checks["redis"] = "error"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=status_code)
