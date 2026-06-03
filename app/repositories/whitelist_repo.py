from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.whitelist_domain import WhitelistDomain

class WhitelistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_domains(self) -> list[str]:
        result = await self.session.execute(select(WhitelistDomain.domain))
        return list(result.scalars().all())

    async def add_domain(self, domain: str) -> WhitelistDomain:
        wl = WhitelistDomain(domain=domain)
        self.session.add(wl)
        await self.session.commit()
        await self.session.refresh(wl)
        return wl

    async def remove_domain(self, domain: str) -> None:
        result = await self.session.execute(
            select(WhitelistDomain).where(WhitelistDomain.domain == domain)
        )
        wl = result.scalar_one_or_none()
        if wl:
            await self.session.delete(wl)
            await self.session.commit()
