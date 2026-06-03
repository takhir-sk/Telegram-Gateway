import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text

from app.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TelegramHook(Base):
    __tablename__ = "telegram_hooks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # MySQL: indexed columns should be VARCHAR, not TEXT without prefix length.
    bot_token = Column(String(255), nullable=False, index=True)
    hook_id = Column(String(36), unique=True, nullable=False, index=True)
    target_url = Column(Text, nullable=False)
    secret_token = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
