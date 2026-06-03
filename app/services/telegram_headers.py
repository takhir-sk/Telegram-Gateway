from starlette.requests import Request

_PASSTHROUGH_HEADERS = frozenset(
    {
        "content-type",
        "user-agent",
        "accept",
        "accept-encoding",
        "accept-language",
    }
)


def extract_telegram_forward_headers(request: Request) -> dict[str, str]:
    """Пробрасывает все Telegram-заголовки и стандартные HTTP-заголовки."""
    forwarded: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower.startswith("x-telegram-") or lower in _PASSTHROUGH_HEADERS:
            forwarded[name] = value
    if "content-type" not in {k.lower() for k in forwarded}:
        forwarded["Content-Type"] = request.headers.get(
            "content-type", "application/json"
        )
    return forwarded
