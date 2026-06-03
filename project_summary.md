
--- START OF FILE: .\.gitignore ---
__pycache__/
*.py[cod]
.env
.venv/
*.log
alembic/versions/*.pyc
test.db

--- END OF FILE: .\.gitignore ---

--- START OF FILE: .\collect.py ---
import os

# 1. Расширения, которые мы собираем
ALLOWED_EXTENSIONS = {'.py', '.js', '.html', '.css', '.txt', '.md', '.yaml', '.yml'}

# 2. Важные файлы без расширений
ALLOWED_FILES = {'Dockerfile', 'requirements.txt', '.dockerignore', '.gitignore'}

# 3. Безопасность: список запрещенных файлов
FORBIDDEN_FILES = {'.env', 'secrets.txt', 'config_private.yaml'}

# 4. Папки, которые мы полностью пропускаем
IGNORE_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', 'env', 
    '.idea', '.vscode', 'build', 'dist'
}

def collect_project_code(output_file='project_summary.md'):
    ignored_files_found = []
    
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for root, dirs, files in os.walk('.'):
            # Фильтруем папки
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                # Если файл — это сам отчет, пропускаем его
                if file == output_file:
                    continue
                    
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1]
                
                # Проверка на безопасность (черный список)
                if file in FORBIDDEN_FILES:
                    ignored_files_found.append(file_path)
                    continue
                
                # Условие сбора
                if ext in ALLOWED_EXTENSIONS or file in ALLOWED_FILES:
                    f_out.write(f"\n--- START OF FILE: {file_path} ---\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f_in:
                            f_out.write(f_in.read())
                    except Exception as e:
                        f_out.write(f"[Ошибка чтения файла: {e}]\n")
                    f_out.write(f"\n--- END OF FILE: {file_path} ---\n")

        # Запись в конце документа о пропущенных файлах
        f_out.write("\n\n--- SECURITY & IGNORE SUMMARY ---\n")
        if ignored_files_found:
            f_out.write("Следующие файлы были ПРОПУЩЕНЫ в целях безопасности или согласно списку исключений:\n")
            for ignored in ignored_files_found:
                f_out.write(f"- {ignored}\n")
        else:
            f_out.write("Исключенных (FORBIDDEN_FILES) файлов в проекте не обнаружено.\n")
        f_out.write("--- END OF SUMMARY ---\n")

    print(f"Готово! Сборка завершена в {output_file}.")
    if ignored_files_found:
        print(f"Внимание: {len(ignored_files_found)} файла(ов) были исключены из соображений безопасности.")

if __name__ == "__main__":
    collect_project_code()
--- END OF FILE: .\collect.py ---

--- START OF FILE: .\docker-compose.yml ---
services:
  redis:
    image: redis:7-alpine
    networks:
      - proxy-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  telegram-gateway:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - proxy-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    volumes:
      - app_logs:/var/log/telegram-gateway

networks:
  proxy-net:
    external: true

volumes:
  app_logs:

--- END OF FILE: .\docker-compose.yml ---

--- START OF FILE: .\Dockerfile ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /var/log/telegram-gateway

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

--- END OF FILE: .\Dockerfile ---

--- START OF FILE: .\README.md ---
# Telegram Gateway

Прокси-сервер между n8n (или любым клиентом) и Telegram Bot API с автоматическим управлением вебхуками, защитой от SSRF, кэшированием и rate limiting.

## Содержание

- [Требования](#требования)
- [Установка через Docker (рекомендуется)](#установка-через-docker-рекомендуется)
- [Локальная установка без Docker](#локальная-установка-без-docker)
- [Настройка после установки](#настройка-после-установки)
- [Проверка работы](#проверка-работы)
- [Production-чеклист](#production-чеклист)
- [Использование с n8n](#использование-с-n8n)
- [Тесты](#тесты)
- [Устранение неполадок](#устранение-неполадок)

---

## Требования

| Компонент | Версия |
|-----------|--------|
| Docker + Docker Compose | Docker 20+, Compose v2 |
| Python (локально) | 3.12 |
| MySQL | 5.7+ / 8.0 (внешний VPS) |
| Redis | 7 |

Для production дополнительно:

- Публичный домен с **HTTPS** (Telegram требует SSL для webhook)
- Reverse proxy (nginx, Traefik, Caddy) перед gateway на порту 8000

---

## Установка через Docker (рекомендуется)

### Шаг 1. Клонирование и конфигурация

```bash
git clone <url-репозитория> rehook
cd rehook
cp .env.example .env
```

### Шаг 2. Редактирование `.env`

**Все настройки проекта — только в одном файле `.env`.**  
Docker Compose и приложение читают его автоматически. Дублировать значения в других файлах не нужно.

```bash
cp .env.example .env
```

Для **production** (`.env.example`):

```env
APP_ENV=production
SQL_HOST=35613c069b21.vps.myjino.ru
SQL_PORT=49294
SQL_DB=bridge_api_service
GATEWAY_PUBLIC_URL=https://185-184-122-178.nip.io
AUTO_CREATE_TABLES=false
```

Для **локальной разработки**:

```env
APP_ENV=development
GATEWAY_PUBLIC_URL=http://localhost:8000
AUTO_CREATE_TABLES=true
```

Полный список переменных:

| Переменная | Описание | Пример |
|------------|----------|--------|
| `APP_ENV` | Режим: `development` / `production` | `production` |
| `SQL_HOST` | Хост MySQL | `35613c069b21.vps.myjino.ru` |
| `SQL_PORT` | Порт MySQL | `49294` |
| `SQL_DB` | Имя базы | `bridge_api_service` |
| `SQL_USER` | Пользователь БД | `bridge_user` |
| `SQL_PASSWORD` | Пароль БД | — |
| `REDIS_URL` | URL Redis | `redis://redis:6379/0` |
| `GATEWAY_PUBLIC_URL` | Публичный URL gateway | `https://tg.example.com` |
| `TELEGRAM_API_URL` | URL Telegram API | `https://api.telegram.org` |
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `LOG_FILE` | Путь к файлу логов | `/var/log/telegram-gateway/app.log` |
| `LOG_RETENTION_DAYS` | Хранение логов (дней) | `90` |
| `RATE_LIMIT` | Лимит запросов | `100/minute` |
| `ALLOW_HTTP_TARGETS` | Разрешить http:// webhook URL (только dev) | `false` |
| `AUTO_CREATE_TABLES` | Создавать таблицы при старте (только dev) | `false` |

> **Важно:** `.env` не коммитится в git. В production `GATEWAY_PUBLIC_URL` должен быть реальным HTTPS-доменом — placeholder `your-domain.com` блокируется при старте.

### Шаг 3. Запуск контейнеров

```bash
docker compose up -d --build
```

Дождитесь, пока все сервисы станут healthy:

```bash
docker compose ps
```

### Шаг 4. Миграции базы данных

```bash
docker compose exec telegram-gateway alembic upgrade head
```

### Шаг 5. Добавление доменов в whitelist

Gateway пропускает webhook только на домены из whitelist (защита от SSRF).

Добавьте домены через SQL (на внешнем MySQL):

```sql
INSERT INTO whitelist_domains (domain) VALUES ('n8n.example.com');
```

---

## Локальная установка без Docker

### 1. Запустите Redis и обеспечьте доступ к MySQL

Убедитесь, что оба сервиса доступны локально.

### 2. Виртуальное окружение

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Настройте `.env`

```env
SQL_HOST=35613c069b21.vps.myjino.ru
SQL_PORT=49294
SQL_DB=bridge_api_service
SQL_USER=bridge_user
SQL_PASSWORD=bridge_pass

REDIS_URL=redis://localhost:6379/0
GATEWAY_PUBLIC_URL=https://your-domain.com
LOG_FILE=./logs/app.log
```

### 4. Миграции и запуск

```bash
mkdir -p logs
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Настройка после установки

### Reverse proxy (nginx, пример)

Telegram требует HTTPS. Gateway слушает HTTP на порту 8000 внутри сети:

```nginx
server {
    listen 443 ssl;
    server_name tg.example.com;

    ssl_certificate     /etc/ssl/certs/tg.example.com.crt;
    ssl_certificate_key /etc/ssl/private/tg.example.com.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

В `.env` укажите: `GATEWAY_PUBLIC_URL=https://tg.example.com`

### Whitelist доменов

Каждый целевой домен webhook (n8n, ваш backend) должен быть в таблице `whitelist_domains`:

```sql
INSERT INTO whitelist_domains (domain) VALUES ('n8n.example.com');
INSERT INTO whitelist_domains (domain) VALUES ('hooks.your-service.com');
```

После добавления доменов перезапустите gateway для обновления Redis-кэша.

---

## Проверка работы

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Swagger UI

Откройте в браузере: `http://localhost:8000/docs`

### Установка webhook через gateway

Вместо прямого обращения к Telegram API клиент (n8n) обращается к gateway:

```bash
curl -X POST "http://localhost:8000/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://n8n.example.com/webhook/telegram-bot",
    "secret_token": "my-secret-token"
  }'
```

Gateway:
1. Проверит домен в whitelist
2. Зарегистрирует webhook в Telegram с URL `{GATEWAY_PUBLIC_URL}/hook/{uuid}`
3. Сохранит маппинг `{hook_id → target_url}` в MySQL + Redis

### Проверка webhook info

```bash
curl "http://localhost:8000/bot<TOKEN>/getWebhookInfo"
```

В ответе `result.url` будет показан **оригинальный** URL (n8n), а не gateway URL.

---

## Production-чеклист

- [ ] `APP_ENV=production`
- [ ] `GATEWAY_PUBLIC_URL` — реальный HTTPS-домен
- [ ] `AUTO_CREATE_TABLES=false` (только Alembic)
- [ ] `ALLOW_HTTP_TARGETS=false`
- [ ] Домены n8n/backend добавлены в `whitelist_domains`
- [ ] Применены миграции: `alembic upgrade head`
- [ ] Используется `secret_token` при setWebhook
- [ ] Настроен мониторинг логов (`LOG_FILE`)
- [ ] Firewall: порт 8000 не открыт наружу напрямую (только через proxy)

---

## Использование с n8n

1. В n8n создайте Telegram Trigger или HTTP Request node
2. Вместо `https://api.telegram.org` укажите URL gateway:
   ```
   https://tg.example.com/bot{{ $credentials.token }}/setWebhook
   ```
3. URL webhook в теле запроса — ваш n8n webhook URL (домен должен быть в whitelist)
4. Все остальные методы Bot API проксируются прозрачно:
   ```
   POST https://tg.example.com/bot<TOKEN>/sendMessage
   GET  https://tg.example.com/bot<TOKEN>/getMe
   ```

---

## Тесты

```bash
# В Docker
docker compose exec telegram-gateway pytest -v

# Локально (Python 3.12)
pytest -v
```

---

## Устранение неполадок

| Симптом | Причина | Решение |
|---------|---------|---------|
| `Domain not allowed` при setWebhook | Домен не в whitelist | `INSERT INTO whitelist_domains ...` |
| Telegram не шлёт updates | Неверный `GATEWAY_PUBLIC_URL` | Проверьте HTTPS и доступность `/hook/{id}` |
| `403 Forbidden` на incoming webhook | Неверный `secret_token` | Совпадение token в setWebhook и заголовке |
| `502 Telegram API error` | Нет связи с api.telegram.org | Проверьте сеть/firewall |
| Приложение не стартует | Нет `.env` или пустые поля | Скопируйте `.env.example`, заполните все обязательные поля |
| `alembic upgrade` падает | БД недоступна | `docker compose ps`, дождитесь healthy у `db` |

### Логи

```bash
# Docker
docker compose logs -f telegram-gateway

# Файл логов внутри контейнера
docker compose exec telegram-gateway tail -f /var/log/telegram-gateway/app.log
```

---

## Архитектура

```
Клиент (n8n) ──► Gateway :8000 ──► Telegram Bot API
                      │
                      ├── MySQL (hooks, whitelist)
                      ├── Redis (кэш hooks + whitelist)
                      │
Telegram ──► Gateway /hook/{id} ──► n8n webhook URL
```

## Особенности

- Единый прокси-эндпоинт для всех методов Telegram Bot API
- Автоматическое управление webhook: `setWebhook`, `getWebhookInfo`, `deleteWebhook`
- Проверка `secret_token` для входящих webhook
- Защита от SSRF через whitelist доменов (БД + Redis-кэш)
- Атомарная установка webhook: сначала Telegram, затем БД
- Retry при сбоях связи с Telegram API
- Rate limiting по IP через Redis
- Структурированное логирование (structlog) с ротацией

--- END OF FILE: .\README.md ---

--- START OF FILE: .\requirements.txt ---
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
sqlalchemy[asyncio]==2.0.35
aiomysql==0.2.0
alembic==1.13.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
redis==5.1.1
structlog==24.4.0
slowapi==0.1.9
tenacity==9.0.0
python-multipart==0.0.9
pytest==8.3.2
pytest-asyncio==0.24.0
aiosqlite==0.20.0
cryptography

--- END OF FILE: .\requirements.txt ---

--- START OF FILE: .\app\main.py ---
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.router import router as bot_router
from app.core.config import settings
from app.core.db import engine, get_db
from app.core.dependencies import close_redis, get_redis
from app.core.logging_config import configure_logging
from app.core.rate_limiter import limiter
from app.db.base import Base
import app.models  # noqa: F401 — регистрация таблиц в Base.metadata
from app.middleware.logging import StructlogMiddleware
from app.services.whitelist import WhitelistService

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    redis = await get_redis()
    service = WhitelistService(redis)
    try:
        await service.refresh_cache()
    except ProgrammingError:
        # First start before migrations: whitelist tables may not exist yet.
        logger.warning("Whitelist cache refresh skipped: run alembic upgrade head")
    logger.info("Application started", app_env=settings.APP_ENV)
    yield
    await close_redis()
    logger.info("Application shutdown")


app = FastAPI(
    title="Telegram Gateway",
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(StructlogMiddleware)
app.include_router(bot_router)



@app.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    checks: dict[str, str] = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Health check: DB unavailable", error=str(exc))
        checks["db"] = "error"
        checks["status"] = "degraded"

    try:
        if not await redis.ping():
            raise ConnectionError("Redis ping failed")
    except Exception as exc:
        logger.error("Health check: Redis unavailable", error=str(exc))
        checks["redis"] = "error"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=status_code)

--- END OF FILE: .\app\main.py ---

--- START OF FILE: .\app\__init__.py ---

--- END OF FILE: .\app\__init__.py ---

--- START OF FILE: .\app\api\router.py ---
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
    if expected_token and "X-Telegram-Bot-Api-Secret-Token" not in forwarded_headers:
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

--- END OF FILE: .\app\api\router.py ---

--- START OF FILE: .\app\api\__init__.py ---

--- END OF FILE: .\app\api\__init__.py ---

--- START OF FILE: .\app\core\config.py ---
from functools import lru_cache
from typing import Literal
from urllib.parse import quote_plus, urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_HOSTS = frozenset({"your-domain.com", "example.com"})


class Settings(BaseSettings):
    """
    Единый источник настроек приложения.
    Все значения задаются в файле .env (см. .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "production"] = "development"

    # --- MySQL (внешний VPS) ---
    SQL_HOST: str
    SQL_PORT: int = Field(default=49294, ge=1, le=65535)
    SQL_DB: str
    SQL_USER: str
    SQL_PASSWORD: str

    REDIS_URL: str

    TELEGRAM_API_URL: str = "https://api.telegram.org"
    GATEWAY_PUBLIC_URL: str

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/telegram-gateway/app.log"
    LOG_RETENTION_DAYS: int = Field(default=90, ge=1)

    RATE_LIMIT: str = "100/minute"
    REQUEST_TIMEOUT: float = Field(default=15.0, gt=0)

    ALLOW_HTTP_TARGETS: bool = False


    AUTO_CREATE_TABLES: bool = False

    @field_validator("GATEWAY_PUBLIC_URL")
    @classmethod
    def normalize_gateway_url(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        parsed = urlparse(self.GATEWAY_PUBLIC_URL)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("GATEWAY_PUBLIC_URL must be a valid http(s) URL")

        host = (parsed.hostname or "").lower()
        if "your-domain.com" in host:
            raise ValueError(
                "GATEWAY_PUBLIC_URL contains placeholder 'your-domain.com'. "
                "Set your real public URL in .env"
            )

        if self.APP_ENV == "production":
            if parsed.scheme != "https":
                raise ValueError("GATEWAY_PUBLIC_URL must use https in production")
            if host in _PLACEHOLDER_HOSTS:
                raise ValueError(
                    f"GATEWAY_PUBLIC_URL host '{host}' is not allowed in production"
                )

        if self.ALLOW_HTTP_TARGETS and self.APP_ENV == "production":
            raise ValueError("ALLOW_HTTP_TARGETS cannot be enabled in production")

        return self

    @property
    def DATABASE_URL_ASYNC(self) -> str:
        user = quote_plus(self.SQL_USER)
        password = quote_plus(self.SQL_PASSWORD)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.SQL_HOST}:{self.SQL_PORT}/{self.SQL_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

--- END OF FILE: .\app\core\config.py ---

--- START OF FILE: .\app\core\db.py ---
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

--- END OF FILE: .\app\core\db.py ---

--- START OF FILE: .\app\core\dependencies.py ---
import redis.asyncio as aioredis

from app.core.config import settings

redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global redis_pool
    if redis_pool is None:
        redis_pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return redis_pool


async def close_redis() -> None:
    global redis_pool
    if redis_pool is not None:
        await redis_pool.aclose()
        redis_pool = None

--- END OF FILE: .\app\core\dependencies.py ---

--- START OF FILE: .\app\core\logging_config.py ---
import logging
import os
import structlog
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

def configure_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        settings.LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=settings.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.LOG_LEVEL.upper())
    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(settings.LOG_LEVEL.upper())
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

--- END OF FILE: .\app\core\logging_config.py ---

--- START OF FILE: .\app\core\rate_limiter.py ---
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

--- END OF FILE: .\app\core\rate_limiter.py ---

--- START OF FILE: .\app\core\retry.py ---
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

retry_policy = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    reraise=True,
)

--- END OF FILE: .\app\core\retry.py ---

--- START OF FILE: .\app\core\security.py ---
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

--- END OF FILE: .\app\core\security.py ---

--- START OF FILE: .\app\core\__init__.py ---

--- END OF FILE: .\app\core\__init__.py ---

--- START OF FILE: .\app\db\base.py ---
from sqlalchemy.orm import declarative_base

Base = declarative_base()

--- END OF FILE: .\app\db\base.py ---

--- START OF FILE: .\app\db\__init__.py ---

--- END OF FILE: .\app\db\__init__.py ---

--- START OF FILE: .\app\middleware\logging.py ---
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import sanitize_log_path

logger = structlog.get_logger(__name__)


class StructlogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid.uuid4()),
            path=sanitize_log_path(request.url.path),
            method=request.method,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error("Unhandled exception", exc_info=True)
            raise
        elapsed = time.perf_counter() - start
        logger.info(
            "Request completed",
            status_code=response.status_code,
            elapsed=round(elapsed, 4),
        )
        return response

--- END OF FILE: .\app\middleware\logging.py ---

--- START OF FILE: .\app\middleware\__init__.py ---

--- END OF FILE: .\app\middleware\__init__.py ---

--- START OF FILE: .\app\models\telegram_hook.py ---
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

--- END OF FILE: .\app\models\telegram_hook.py ---

--- START OF FILE: .\app\models\whitelist_domain.py ---
from sqlalchemy import Column, Integer, String
from app.db.base import Base

class WhitelistDomain(Base):
    __tablename__ = "whitelist_domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(253), unique=True, nullable=False, index=True)

--- END OF FILE: .\app\models\whitelist_domain.py ---

--- START OF FILE: .\app\models\__init__.py ---
from app.models.telegram_hook import TelegramHook
from app.models.whitelist_domain import WhitelistDomain

--- END OF FILE: .\app\models\__init__.py ---

--- START OF FILE: .\app\repositories\hook_repo.py ---
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

--- END OF FILE: .\app\repositories\hook_repo.py ---

--- START OF FILE: .\app\repositories\whitelist_repo.py ---
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

--- END OF FILE: .\app\repositories\whitelist_repo.py ---

--- START OF FILE: .\app\repositories\__init__.py ---

--- END OF FILE: .\app\repositories\__init__.py ---

--- START OF FILE: .\app\schemas\webhook.py ---
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

--- END OF FILE: .\app\schemas\webhook.py ---

--- START OF FILE: .\app\schemas\__init__.py ---
from app.schemas.webhook import SetWebhookRequest, TelegramApiResponse

__all__ = [
    "SetWebhookRequest",
    "TelegramApiResponse",
]

--- END OF FILE: .\app\schemas\__init__.py ---

--- START OF FILE: .\app\services\proxy.py ---
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

--- END OF FILE: .\app\services\proxy.py ---

--- START OF FILE: .\app\services\telegram_headers.py ---
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

--- END OF FILE: .\app\services\telegram_headers.py ---

--- START OF FILE: .\app\services\webhook.py ---
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.repositories.hook_repo import HookRepository

logger = structlog.get_logger(__name__)


class WebhookService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.repo = HookRepository(db)
        self.redis = redis

    async def _cache_hook(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None,
    ) -> None:
        await self.redis.hset(
            f"hook:{hook_id}",
            mapping={
                "bot_token": bot_token,
                "target_url": target_url,
                "secret_token": secret_token or "",
            },
        )

    async def _uncache_hook(self, hook_id: str) -> None:
        await self.redis.delete(f"hook:{hook_id}")

    async def create_hook(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None = None,
    ):
        hook = await self.repo.create(
            hook_id=hook_id,
            bot_token=bot_token,
            target_url=target_url,
            secret_token=secret_token,
        )
        await self._cache_hook(hook_id, bot_token, target_url, secret_token)
        return hook

    async def replace_hook_for_token(
        self,
        hook_id: str,
        bot_token: str,
        target_url: str,
        secret_token: str | None = None,
    ):
        old_hook_ids = await self.repo.delete_by_token(bot_token)
        if old_hook_ids:
            await self.redis.delete(*[f"hook:{hid}" for hid in old_hook_ids])
        return await self.create_hook(hook_id, bot_token, target_url, secret_token)

    async def delete_hook_by_id(self, hook_id: str) -> None:
        deleted = await self.repo.delete_by_hook_id(hook_id)
        if deleted:
            await self._uncache_hook(hook_id)

    async def get_hook_by_id(self, hook_id: str) -> dict | None:
        cached = await self.redis.hgetall(f"hook:{hook_id}")
        if cached:
            return cached
        hook = await self.repo.get_by_hook_id(hook_id)
        if hook:
            data = {
                "hook_id": hook.hook_id,
                "bot_token": hook.bot_token,
                "target_url": hook.target_url,
                "secret_token": hook.secret_token or "",
            }
            await self.redis.hset(f"hook:{hook_id}", mapping=data)
            return data
        return None

    async def delete_hooks_by_token(self, bot_token: str) -> None:
        hook_ids = await self.repo.delete_by_token(bot_token)
        if hook_ids:
            await self.redis.delete(*[f"hook:{hook_id}" for hook_id in hook_ids])
        logger.info("Hooks deleted for token", token=bot_token[:8], count=len(hook_ids))

--- END OF FILE: .\app\services\webhook.py ---

--- START OF FILE: .\app\services\whitelist.py ---
from redis.asyncio import Redis
from app.repositories.whitelist_repo import WhitelistRepository
from app.core.db import async_session_factory
import structlog

logger = structlog.get_logger(__name__)

class WhitelistService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def _get_active_key(self) -> str:
        version = await self.redis.get("whitelist:active_version")
        if not version:
            version = "1"
        return f"whitelist:domains:v{version}"

    async def refresh_cache(self):
        async with async_session_factory() as session:
            repo = WhitelistRepository(session)
            domains = await repo.get_all_domains()

        new_version = await self.redis.incr("whitelist:version")
        new_key = f"whitelist:domains:v{new_version}"
        if domains:
            await self.redis.delete(new_key)
            await self.redis.sadd(new_key, *domains)
        await self.redis.set("whitelist:active_version", new_version)
        logger.info("Whitelist cache refreshed", count=len(domains))

    async def is_domain_allowed(self, domain: str) -> bool:
        key = await self._get_active_key()
        is_member = await self.redis.sismember(key, domain)
        if is_member:
            return True
        # fallback to DB and re-add to current cache
        async with async_session_factory() as session:
            repo = WhitelistRepository(session)
            db_domains = await repo.get_all_domains()
            if domain in db_domains:
                await self.redis.sadd(key, domain)
                return True
        return False

--- END OF FILE: .\app\services\whitelist.py ---

--- START OF FILE: .\app\services\__init__.py ---

--- END OF FILE: .\app\services\__init__.py ---


--- SECURITY & IGNORE SUMMARY ---
Следующие файлы были ПРОПУЩЕНЫ в целях безопасности или согласно списку исключений:
- .\.env
--- END OF SUMMARY ---
