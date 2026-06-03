from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_hook import TelegramHook


class HookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None = None,
    ) -> TelegramHook:
        hook = TelegramHook(
            hook_id=hook_id,
            bot_token=bot_token,
            target_url=target_url,
            secret_token=secret_token,
        )
        self.session.add(hook)
        await self.session.commit()
        await self.session.refresh(hook)
        return hook

    async def get_by_hook_id(self, hook_id: str) -> TelegramHook | None:
        result = await self.session.execute(
            select(TelegramHook).where(TelegramHook.hook_id == hook_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_hook_id(self, hook_id: str) -> bool:
        result = await self.session.execute(
            delete(TelegramHook).where(TelegramHook.hook_id == hook_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def delete_by_token(self, bot_token: str) -> list[str]:
        result = await self.session.execute(
            select(TelegramHook.hook_id).where(TelegramHook.bot_token == bot_token)
        )
        hook_ids = list(result.scalars().all())
        await self.session.execute(
            delete(TelegramHook).where(TelegramHook.bot_token == bot_token)
        )
        await self.session.commit()
        return hook_ids
