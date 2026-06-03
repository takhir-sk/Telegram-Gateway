# Telegram Gateway

Secure Telegram Bot API Gateway with webhook proxying, domain whitelist validation, SSRF protection, Redis caching, and MySQL persistence.

## Features

* Proxy all Telegram Bot API methods
* Replace original Telegram webhooks with gateway webhooks
* Restore original webhook URLs in `getWebhookInfo`
* Domain whitelist enforcement
* SSRF protection
* Secret token validation
* Redis caching
* MySQL persistence
* Structured JSON logging
* Rate limiting
* Docker support
* Health checks

## Architecture

```text
Telegram
    │
    ▼
Telegram Gateway
    │
    ▼
Your Application
```

When a bot registers a webhook:

1. Original webhook URL is stored in MySQL.
2. Telegram receives a gateway URL.
3. Incoming Telegram updates are validated.
4. Updates are forwarded to the original destination.

## Technology Stack

* FastAPI
* SQLAlchemy Async
* MySQL
* Redis
* HTTPX
* Structlog
* SlowAPI
* Docker

## Project Structure

```text
app/
├── api/
├── core/
├── db/
├── middleware/
├── models/
├── repositories/
├── schemas/
└── services/

docker-compose.yml
Dockerfile
requirements.txt
```

## Environment Variables

Create a `.env` file:

```env
APP_ENV=production

SQL_HOST=127.0.0.1
SQL_PORT=3306
SQL_DB=telegram_gateway
SQL_USER=user
SQL_PASSWORD=password

REDIS_URL=redis://redis:6379/0

GATEWAY_PUBLIC_URL=https://gateway.example.com

LOG_LEVEL=INFO
LOG_FILE=/var/log/telegram-gateway/app.log

RATE_LIMIT=100/minute
REQUEST_TIMEOUT=15
ALLOW_HTTP_TARGETS=false
```

## Docker Deployment

Create external Docker network:

```bash
docker network create proxy-net
```

Start services:

```bash
docker compose up -d --build
```

Check health:

```bash
curl http://localhost:8000/health
```

## API Endpoints

### Telegram API Proxy

```text
/bot<TOKEN>/<METHOD>
```

Examples:

```text
/bot123456:ABCDEF/getMe
/bot123456:ABCDEF/sendMessage
/bot123456:ABCDEF/setWebhook
```

### Health Check

```text
GET /health
```

### Internal Webhook Endpoint

```text
POST /hook/{hook_id}
```

Used internally by Telegram after webhook registration.

## Security

### SSRF Protection

The gateway rejects:

* Private IP addresses
* Loopback addresses
* Link-local addresses
* Non-whitelisted domains
* Domains resolving to private networks

### Secret Token Validation

If Telegram webhook secret tokens are configured, all incoming requests are validated before forwarding.

### Domain Whitelist

Only approved domains can receive webhook traffic.

## Logging

Structured JSON logs are generated using Structlog.

Example:

```json
{
  "event": "Incoming webhook forwarded",
  "hook_id": "xxxx",
  "target": "https://example.com/webhook"
}
```

## Health Monitoring

Health endpoint validates:

* MySQL connectivity
* Redis connectivity

Example response:

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok"
}
```

## License

MIT License

```
```
