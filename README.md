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
SQL_HOST=your-mysql-host.com
SQL_PORT=3306
SQL_DB=bridge_api_service
GATEWAY_PUBLIC_URL=https://your-domain.com
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
