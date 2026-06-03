from pydantic import BaseModel, Field, HttpUrl


class SetWebhookRequest(BaseModel):
    url: HttpUrl
    secret_token: str | None = Field(default=None, max_length=256)
    drop_pending_updates: bool | None = None
    max_connections: int | None = Field(default=None, ge=1, le=100)
    allowed_updates: list[str] | None = None


class TelegramApiResponse(BaseModel):
    ok: bool
    result: bool | dict | None = None
    description: str | None = None
