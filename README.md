
# Telegram Gateway

Прокси-сервер и умный шлюз между вашими backend-приложениями (n8n, Node.js/Python сервисы) и Telegram Bot API. 

Проект решает проблему безопасного, централизованного и скрытого управления вебхуками Telegram. Он обеспечивает встроенную защиту от SSRF-атак, маскирование реальных адресов вашей инфраструктуры, кэширование маршрутов в Redis и ограничение частоты запросов (Rate Limiting).

---

## 💡 Зачем нужен этот проект?

### ❌ До использования Gateway
Обычно ваши скрипты, бэкенды или узлы n8n регистрируют свой реальный адрес напрямую в Telegram:

```text
Ваш Backend (n8n) ───► POST /setWebhook {"url": "[https://n8n.my-backend.com/webhook](https://n8n.my-backend.com/webhook)"} ───► Telegram

```

**Проблема:** Telegram шлет апдейты напрямую на ваш реальный хост. Адрес вашей внутренней инфраструктуры (`n8n.my-backend.com`) светится во внешних запросах и открыт всему интернету.

### После использования Gateway

Вы перенаправляете запросы регистрации на единую точку входа — Telegram Gateway:

```text
Ваш Backend (n8n) ───► POST [https://gateway.domain.com/bot](https://gateway.domain.com/bot)<TOKEN>/setWebhook {"url": "[https://n8n.my-backend.com/webhook](https://n8n.my-backend.com/webhook)"}

```

**Что делает Gateway под капотом:**

1. Проверяет, разрешен ли целевой домен (`n8n.my-backend.com`) в белом списке (защита от несанкционированного использования).
2. Сохраняет маппинг токена и реального адреса в базу данных MySQL и мгновенно кэширует его в Redis.
3. Генерирует защищенный случайный UUID вебхука.
4. Регистрирует в самом Telegram **свой собственный скрытый URL**: `https://gateway.domain.com/hook/c8f4f8e4-xxxx-xxxx-xxxx-xxxxxxxxxxxx`.

### 🔄 Поток данных при обработке сообщений (Маршрутизация):

```text
Telegram ──► Gateway (:8000 /hook/{uuid}) ──► Redis/MySQL (Декодирование) ──► Ваш реальный Backend URL

```

* **Полная анонимность backend-адресов:** Telegram и внешние наблюдатели видят только публичный адрес шлюза.
* **Прозрачная подмена (getWebhookInfo):** При вызове метода `/getWebhookInfo` Gateway перехватывает ответ от серверов Telegram и подставляет туда ваш *оригинальный* backend-адрес. Разработчик в n8n или коде видит свои привычные URL, даже не замечая прослойки.

---

## 🛠️ Структура базы данных

При старте приложение автоматически создает две таблицы в MySQL (если их еще нет):

### 1. Таблица `whitelist_domains`

Список доверенных доменов, куда шлюзу разрешено пересылать входящий трафик от Telegram.

* `id` (INT, Primary Key, Auto Increment)
* `domain` (VARCHAR(255), Unique, Index) — Пример: `n8n.my-backend.com`

### 2. Таблица `telegram_hooks`

Реестр зарегистрированных ботов и маппинг их скрытых путей.

* `id` (VARCHAR(36), Unique, Primary Key) — Внутренний UUID вебхука, по которому его идентифицирует Telegram.
* `bot_token` (VARCHAR(255), Index) — Токен вашего Telegram-бота.
* `target_url` (TEXT) — Реальный адрес назначения (куда шлюз перенаправит JSON).
* `secret_token` (VARCHAR(255)) — Секретный токен верификации Telegram.

---

## 🚀 Быстрый старт за 5 минут

### Шаг 1. Подготовка Базы Данных

Создайте пустую базу данных на вашем сервере MySQL / MariaDB:

```sql
CREATE DATABASE telegram_gateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

```

### Шаг 2. Настройка Docker-сети

Проект ориентирован на работу через внешний reverse-proxy (например, Nginx / Traefik) внутри общей сети Docker. Создайте сеть, если она у вас еще не создана:

```bash
docker network create proxy-net

```

### Шаг 3. Настройка конфигурации (`.env`)

Создайте файл `.env` в корневой директории проекта и заполните его вашими данными:

```env
APP_ENV=production

# Подключение к вашей базе данных MySQL
SQL_HOST=your-mysql-host.ru
SQL_PORT=3306
SQL_DB=telegram_gateway
SQL_USER=gateway_user
SQL_PASSWORD=your_strong_password

# Ссылка на контейнер Redis (настраивается автоматически через docker-compose)
REDIS_URL=redis://redis:6379/0

# Публичный HTTPS адрес, по которому этот шлюз будет доступен из интернета
GATEWAY_PUBLIC_URL=[https://gateway.yourdomain.com](https://gateway.yourdomain.com)

LOG_LEVEL=INFO
LOG_FILE=/var/log/telegram-gateway/app.log

RATE_LIMIT=100/minute
AUTO_CREATE_TABLES=true
ALLOW_HTTP_TARGETS=false

```

> ⚠️ **Важно:** В режиме `APP_ENV=production` шлюз из соображений безопасности принудительно требует, чтобы `GATEWAY_PUBLIC_URL` работал строго по протоколу `https`, а также блокирует отправку хуков на незащищенные `http://` адреса бэкендов.

### Шаг 4. Запуск контейнеров

Запустите сборку и старт шлюза одной командой:

```bash
docker compose up -d --build

```

*Благодаря параметру `AUTO_CREATE_TABLES=true`, шлюз при первом запуске сам выполнит проверку структуры и создаст таблицы в MySQL.*

### Шаг 5. Проверка статуса (Health Check)

Убедитесь, что шлюз успешно запустился и установил соединения с MySQL и Redis:

```bash
curl http://localhost:8000/health

```

Ожидаемый ответ:

```json
{"status":"ok","db":"ok","redis":"ok"}

```

---

## 🧑‍💻 Инструкция по использованию

### 1. Добавление домена в Белый список (ОБЯЗАТЕЛЬНО)

Шлюз защищает вашу инфраструктуру от SSRF-атак и **не пропустит ни один запрос**, если домен целевого назначения отсутствует в таблице `whitelist_domains`.

Перед регистрацией бота добавьте домен вашего бэкенда или n8n напрямую в базу данных:

```sql
INSERT INTO whitelist_domains (domain) VALUES ('n8n.yourdomain.com');

```

*Шлюз мгновенно подхватит изменения, валидирует домен и обновит кэш в Redis.*

### 2. Регистрация Вебхука (setWebhook)

Вместо отправки запроса на сервера Telegram, отправьте стандартный запрос регистрации вебхука на ваш развернутый шлюз.

**Пример cURL-запроса:**

```bash
curl -X POST "[https://gateway.yourdomain.com/bot123456:ABC-DEF_your_bot_token/setWebhook](https://gateway.yourdomain.com/bot123456:ABC-DEF_your_bot_token/setWebhook)" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "[https://n8n.yourdomain.com/webhook/telegram-input](https://n8n.yourdomain.com/webhook/telegram-input)",
    "secret_token": "my-super-secret-pass"
  }'

```

**Что произойдет в этот момент:**

1. Gateway перехватит запрос и проверит, что домен `n8n.yourdomain.com` находится в вайтлисте.
2. Сгенерирует внутренний UUID (например, `550e8400-e29b-41d4-a716-446655440000`).
3. Сам обратится к серверам Telegram и зарегистрирует для вашего бота адрес: `https://gateway.yourdomain.com/hook/550e8400-e29b-41d4-a716-446655440000`.
4. Вернет вашему приложению оригинальный успешный ответ от API Telegram.

### 3. Проверка информации о вебхуке (getWebhookInfo)

Если вы захотите проверить статус вашего вебхука, выполните стандартный запрос:

```bash
curl "[https://gateway.yourdomain.com/bot123456:ABC-DEF_your_bot_token/getWebhookInfo](https://gateway.yourdomain.com/bot123456:ABC-DEF_your_bot_token/getWebhookInfo)"

```

**Ответ шлюза:**

```json
{
  "ok": true,
  "result": {
    "url": "[https://n8n.yourdomain.com/webhook/telegram-input](https://n8n.yourdomain.com/webhook/telegram-input)",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}

```

*Несмотря на то, что в самом Telegram привязан скрытый UUID шлюза, для вас система прозрачно подменяет адрес на ваш оригинальный бэкенд.*

### 4. Прозрачное проксирование других методов

Все остальные стандартные методы Telegram Bot API проксируются через шлюз "как есть", без изменений. Вы можете отправлять сообщения, файлы или удалять вебхуки:

```bash
# Отправка текстовых сообщений через шлюз
POST [https://gateway.yourdomain.com/bot](https://gateway.yourdomain.com/bot)<TOKEN>/sendMessage

# Удаление вебхука (автоматически очистит запись в БД шлюза и сбросит настройки в Telegram)
POST [https://gateway.yourdomain.com/bot](https://gateway.yourdomain.com/bot)<TOKEN>/deleteWebhook

```

---

## 🛡️ Функции безопасности

* **Анти-SSRF фильтрация:** Перед пересылкой трафика шлюз не только проверяет домен по белому списку, но и резолвит его IP-адрес. Если домен пытается сослаться на приватные диапазоны подсетей (`127.0.0.1`, `192.168.x.x`, `10.x.x.x` и т.д.), запрос немедленно блокируется.
* **Валидация Telegram Secret Token:** Если при регистрации вебхука был указан параметр `secret_token`, шлюз будет автоматически сверять заголовок `X-Telegram-Bot-Api-Secret-Token` у всех входящих пакетов от серверов Telegram. При несовпадении запрос сбрасывается с кодом `403 Forbidden`.
* **Защита от DDOS (Rate Limiting):** Ограничение частоты запросов к эндпоинтам шлюза по IP-адресу через Redis (настраивается переменной `RATE_LIMIT` в `.env`).
* **Маскирование токенов в логах:** Шлюз ведет структурированные JSON-логи через `Structlog`. Любые токены ботов в путях URL автоматически маскируются под значение `bot***`, исключая случайную утечку конфиденциальных токенов в файлы логов.

