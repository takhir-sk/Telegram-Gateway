import json
import uuid

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.dependencies import get_redis
from app.core.rate_limiter import limiter
from app.core.retry import retry_policy
from app.core.security import extract_hook_id_from_url, validate_target_url
from app.schemas.webhook import SetWebhookRequest
from app.services.proxy import proxy_request
from app.services.telegram_headers import extract_telegram_forward_headers
from app.services.webhook import WebhookService
from app.services.whitelist import WhitelistService

logger = structlog.get_logger(__name__)
router = APIRouter()
_timeout = settings.REQUEST_TIMEOUT


@router.api_route(
    "/bot{token}/{method:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
@limiter.limit(settings.RATE_LIMIT)
async def proxy_bot_api(
    request: Request,
    token: str,
    method: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = WebhookService(db, redis)
    body = await request.body()

    if method == "setWebhook":
        return await _handle_set_webhook(token, body, service, redis)
    if method == "getWebhookInfo":
        return await _handle_get_webhook_info(token, service)
    if method == "deleteWebhook":
        return await _handle_delete_webhook(token, body, service)

    return await proxy_request(
        token=token,
        method=method,
        http_method=request.method,
        body=body,
        query_params=dict(request.query_params),
        headers=dict(request.headers),
    )


@retry_policy
async def _call_telegram_set_webhook(token: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=_timeout) as client:
        tg_url = f"{settings.TELEGRAM_API_URL}/bot{token}/setWebhook"
        resp = await client.post(tg_url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def _handle_set_webhook(
    token: str,
    body: bytes,
    service: WebhookService,
    redis: Redis,
):
    try:
        webhook_req = SetWebhookRequest.model_validate_json(body)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    original_url = str(webhook_req.url)
    whitelist_service = WhitelistService(redis)
    await validate_target_url(original_url, whitelist_service)

    hook_id = str(uuid.uuid4())
    gateway_url = f"{settings.GATEWAY_PUBLIC_URL}/hook/{hook_id}"

    # 1–2. Сохранить mapping в MySQL (промпт: сначала БД)
    try:
        await service.replace_hook_for_token(
            hook_id=hook_id,
            bot_token=token,
            target_url=original_url,
            secret_token=webhook_req.secret_token,
        )
    except Exception as exc:
        logger.error("setWebhook DB save failed", bot_token=token[:8], error=str(exc))
        raise HTTPException(
            status_code=500, detail="Failed to persist webhook mapping"
        ) from exc

    # 3. Зарегистрировать gateway URL в Telegram
    payload = webhook_req.model_dump(mode="json", exclude_none=True)
    payload["url"] = gateway_url

    try:
        tg_response = await _call_telegram_set_webhook(token, payload)
    except httpx.HTTPError as exc:
        await service.delete_hook_by_id(hook_id)
        logger.error("setWebhook failed", bot_token=token[:8], error=str(exc))
        raise HTTPException(status_code=502, detail="Telegram API error") from exc

    if not tg_response.get("ok"):
        await service.delete_hook_by_id(hook_id)
        description = tg_response.get("description", "Telegram rejected webhook")
        logger.error("setWebhook rejected", bot_token=token[:8], detail=description)
        raise HTTPException(status_code=502, detail=description)

    logger.info(
        "setWebhook succeeded",
        hook_id=hook_id,
        bot_token=token[:8],
        target_url=original_url,
    )
    return tg_response


async def _handle_get_webhook_info(token: str, service: WebhookService):
    async with httpx.AsyncClient(timeout=_timeout) as client:
        tg_url = f"{settings.TELEGRAM_API_URL}/bot{token}/getWebhookInfo"
        resp = await client.get(tg_url)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        return data

    webhook_url = data.get("result", {}).get("url", "")
    if webhook_url:
        hook_id = extract_hook_id_from_url(webhook_url)
        if hook_id:
            hook = await service.get_hook_by_id(hook_id)
            if hook:
                data["result"]["url"] = hook["target_url"]
    return data


async def _handle_delete_webhook(
    token: str, body: bytes, service: WebhookService
):
    # 1. Удалить из БД (промпт: сначала БД)
    await service.delete_hooks_by_token(token)

    headers = {}
    if body:
        headers["Content-Type"] = "application/json"

    # 2. Вызвать deleteWebhook в Telegram
    async with httpx.AsyncClient(timeout=_timeout) as client:
        tg_url = f"{settings.TELEGRAM_API_URL}/bot{token}/deleteWebhook"
        resp = await client.post(tg_url, content=body or None, headers=headers or None)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("ok"):
        description = data.get("description", "Telegram rejected deleteWebhook")
        logger.error("deleteWebhook rejected", bot_token=token[:8], detail=description)
        raise HTTPException(status_code=502, detail=description)

    logger.info("deleteWebhook", bot_token=token[:8])
    return data


@router.get("/hook/{hook_id}")
async def verify_hook(hook_id: str):
    """Telegram webhook verification"""
    # Можно проверить, существует ли hook в БД, но не обязательно.
    return Response(status_code=200, content="OK")
    

@router.post("/hook/{hook_id}")
@limiter.limit(settings.RATE_LIMIT)
async def incoming_webhook(
    hook_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    service = WebhookService(db, redis)
    hook = await service.get_hook_by_id(hook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Hook not found")

    expected_token = hook.get("secret_token")
    if expected_token:
        incoming_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not incoming_token or incoming_token != expected_token:
            logger.warning("Invalid secret token for hook", hook_id=hook_id)
            raise HTTPException(status_code=403, detail="Forbidden")

    whitelist_service = WhitelistService(redis)
    await validate_target_url(hook["target_url"], whitelist_service)

    body = await request.body()
    forwarded_headers = extract_telegram_forward_headers(request)
    # Проверяем наличие любого варианта заголовка без учёта регистра
    has_token_header = any(
        k.lower() == "x-telegram-bot-api-secret-token" for k in forwarded_headers
    )
    if expected_token and not has_token_header:
        forwarded_headers["X-Telegram-Bot-Api-Secret-Token"] = expected_token

    async with httpx.AsyncClient(timeout=_timeout) as client:
        try:
            resp = await client.post(
                hook["target_url"],
                content=body,
                headers=forwarded_headers,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Webhook forward failed", hook_id=hook_id, error=str(exc))
            raise HTTPException(
                status_code=502, detail="Failed to forward webhook"
            ) from exc

    logger.info(
        "Incoming webhook forwarded",
        hook_id=hook_id,
        target=hook["target_url"],
    )
    return Response(status_code=200, content="OK")
