import redis.asyncio as aioredis

from app.core.config import settings

redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global redis_pool
    if redis_pool is None:
        redis_pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_pool


async def close_redis() -> None:
    global redis_pool
    if redis_pool is not None:
        await redis_pool.aclose()
        redis_pool = None
