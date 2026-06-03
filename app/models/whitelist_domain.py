from sqlalchemy import Column, Integer, String
from app.db.base import Base

class WhitelistDomain(Base):
    __tablename__ = "whitelist_domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(253), unique=True, nullable=False, index=True)
