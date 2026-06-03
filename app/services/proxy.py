import httpx
import structlog
from fastapi import HTTPException, Response

from app.core.config import settings

logger = structlog.get_logger(__name__)

ALLOWED_REQUEST_HEADERS = {
    "content-type",
    "accept",
    "user-agent",
    "accept-encoding",
    "accept-language",
}


def _filter_headers(headers: dict) -> dict:
    return {
        k: v for k, v in headers.items() if k.lower() in ALLOWED_REQUEST_HEADERS
    }


async def proxy_request(
    token: str,
    method: str,
    http_method: str,
    body: bytes,
    query_params: dict,
    headers: dict,
):
    url = f"{settings.TELEGRAM_API_URL}/bot{token}/{method}"
    safe_headers = _filter_headers(headers)
    timeout = settings.REQUEST_TIMEOUT

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(
                method=http_method,
                url=url,
                content=body,
                headers=safe_headers,
                params=query_params,
            )
            resp.raise_for_status()
            logger.info(
                "Telegram request proxied",
                method=method,
                http_method=http_method,
                status=resp.status_code,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type"),
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Telegram proxy HTTP error",
                method=method,
                status=exc.response.status_code,
            )
            return Response(
                content=exc.response.content,
                status_code=exc.response.status_code,
                headers=dict(exc.response.headers),
                media_type=exc.response.headers.get("content-type"),
            )
        except httpx.RequestError as exc:
            logger.error("Telegram proxy request failed", method=method, error=str(exc))
            raise HTTPException(status_code=502, detail="Telegram API unreachable") from exc
