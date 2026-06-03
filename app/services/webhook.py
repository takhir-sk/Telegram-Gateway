from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.repositories.hook_repo import HookRepository

logger = structlog.get_logger(__name__)


class WebhookService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.repo = HookRepository(db)
        self.redis = redis

    async def _cache_hook(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None,
    ) -> None:
        await self.redis.hset(
            f"hook:{hook_id}",
            mapping={
                "bot_token": bot_token,
                "target_url": target_url,
                "secret_token": secret_token or "",
            },
        )

    async def _uncache_hook(self, hook_id: str) -> None:
        await self.redis.delete(f"hook:{hook_id}")

    async def create_hook(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None = None,
    ):
        hook = await self.repo.create(
            hook_id=hook_id,
            bot_token=bot_token,
            target_url=target_url,
            secret_token=secret_token,
        )
        await self._cache_hook(hook_id, bot_token, target_url, secret_token)
        return hook

    async def replace_hook_for_token(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None = None,
    ):
        old_hook_ids = await self.repo.delete_by_token(bot_token)
        if old_hook_ids:
            await self.redis.delete(*[f"hook:{hid}" for hid in old_hook_ids])
        return await self.create_hook(hook_id, bot_token, target_url, secret_token)

    async def delete_hook_by_id(self, hook_id: str) -> None:
        deleted = await self.repo.delete_by_hook_id(hook_id)
        if deleted:
            await self._uncache_hook(hook_id)

    async def get_hook_by_id(self, hook_id: str) -> dict | None:
        cached = await self.redis.hgetall(f"hook:{hook_id}")
        if cached:
            return cached
        hook = await self.repo.get_by_hook_id(hook_id)
        if hook:
            data = {
                "hook_id": hook.hook_id,
                "bot_token": hook.bot_token,
                "target_url": hook.target_url,
                "secret_token": hook.secret_token or "",
            }
            await self.redis.hset(f"hook:{hook_id}", mapping=data)
            return data
        return None

    async def delete_hooks_by_token(self, bot_token: str) -> None:
        hook_ids = await self.repo.delete_by_token(bot_token)
        if hook_ids:
            await self.redis.delete(*[f"hook:{hook_id}" for hook_id in hook_ids])
        logger.info("Hooks deleted for token", token=bot_token[:8], count=len(hook_ids))
