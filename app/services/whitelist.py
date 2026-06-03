from redis.asyncio import Redis
from app.repositories.whitelist_repo import WhitelistRepository
from app.core.db import async_session_factory
import structlog

logger = structlog.get_logger(__name__)

class WhitelistService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def _get_active_key(self) -> str:
        version = await self.redis.get("whitelist:active_version")
        if not version:
            version = "1"
        return f"whitelist:domains:v{version}"

    async def refresh_cache(self):
        async with async_session_factory() as session:
            repo = WhitelistRepository(session)
            domains = await repo.get_all_domains()

        new_version = await self.redis.incr("whitelist:version")
        new_key = f"whitelist:domains:v{new_version}"
        if domains:
            await self.redis.delete(new_key)
            await self.redis.sadd(new_key, *domains)
        await self.redis.set("whitelist:active_version", new_version)
        logger.info("Whitelist cache refreshed", count=len(domains))

    async def is_domain_allowed(self, domain: str) -> bool:
        key = await self._get_active_key()
        is_member = await self.redis.sismember(key, domain)
        if is_member:
            return True
        # fallback to DB and re-add to current cache
        async with async_session_factory() as session:
            repo = WhitelistRepository(session)
            db_domains = await repo.get_all_domains()
            if domain in db_domains:
                await self.redis.sadd(key, domain)
                return True
        return False
