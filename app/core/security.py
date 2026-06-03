import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

import structlog
from fastapi import HTTPException

from app.core.config import settings
from app.services.whitelist import WhitelistService

logger = structlog.get_logger(__name__)

PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _is_private_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in network for network in PRIVATE_NETWORKS)


def _resolve_host_ips(hostname: str) -> list[str]:
    try:
        results = socket.getaddrinfo(
            hostname, None, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Cannot resolve hostname") from exc
    return list({item[4][0] for item in results})


async def validate_target_url(url: str, whitelist_service: WhitelistService) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme == "http" and not settings.ALLOW_HTTP_TARGETS:
        raise HTTPException(status_code=403, detail="HTTP targets are not allowed")

    hostname = parsed.hostname.lower()

    if _is_private_ip(hostname):
        raise HTTPException(status_code=403, detail="Private IP not allowed")

    allowed = await whitelist_service.is_domain_allowed(hostname)
    if not allowed:
        logger.warning("Domain not whitelisted", domain=hostname)
        raise HTTPException(status_code=403, detail="Domain not allowed")

    resolved_ips = await asyncio.to_thread(_resolve_host_ips, hostname)
    for ip in resolved_ips:
        if _is_private_ip(ip):
            logger.warning("Resolved IP is private", domain=hostname, ip=ip)
            raise HTTPException(status_code=403, detail="Target resolves to private IP")


def extract_hook_id_from_url(url: str) -> str | None:
    pattern = r"/hook/([a-f0-9\-]{36})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def sanitize_log_path(path: str) -> str:
    """Маскирует bot token в URL-пути для логов."""
    return re.sub(r"(?i)^/bot[^/]+", "/bot***", path)
