from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL_ASYNC,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    connect_args={"charset": "utf8mb4"},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with async_session_factory() as session:
        yield session
