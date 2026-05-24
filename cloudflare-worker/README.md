# Cloudflare Worker для sochiautoparts.ru

## Описание

Этот Worker обслуживает статический сайт sochiautoparts.ru, проксируя контент с GitHub Pages и добавляя серверные API-эндпоинты для партнёрских ссылок, поиска и статистики.

## Функционал

| Эндпоинт | Описание |
|-----------|----------|
| `/` и все статические пути | Проксирует HTML/CSS/JS/изображения с GitHub Pages |
| `/api/{campaignId}` | Редирект на партнёрскую ссылку Admitad (302) |
| `/api/search?q=...&lang=ru` | Редирект на `/search/?q=...` (клиентский поиск) |
| `/api/stats` | JSON со статистикой сайта |

## Настройка и деплой

### 1. Создание Worker в Cloudflare

1. Перейдите в **Cloudflare Dashboard → Workers & Pages**
2. Нажмите **Create Application → Create Worker**
3. Назовите worker `sochiautoparts-worker`
4. Скопируйте содержимое `worker.js` в редактор
5. Нажмите **Save and Deploy**

### 2. Настройка переменных окружения

В настройках Worker (Settings → Variables) добавьте:

| Переменная | Значение | Описание |
|------------|----------|----------|
| `GITHUB_PAGES_URL` | `https://creastudioai-beep.github.io/sapapp` | URL GitHub Pages |
| `ADMITAD_BASE_URL` | `https://ujhjj.com/g/on8kt46xpp3c08bd9d2c648980e865/` | Базовый URL Admitad |
| `ADMITAD_SUBID` | `TEN` | SubID для Admitad |

### 3. Настройка маршрута (Route)

1. Перейдите в **Workers → Routes**
2. Добавьте маршрут:
   - **Route**: `sochiautoparts.ru/*`
   - **Worker**: `sochiautoparts-worker`

### 4. Настройка DNS

1. В **DNS настройках** домена `sochiautoparts.ru`:
   - Добавьте A-запись: `sochiautoparts.ru` → `192.0.2.1` (proxy через Cloudflare, оранжевое облако)
   - Включите **Proxy status** (оранжевое облако)

### 5. Настройка SSL

1. Перейдите в **SSL/TLS → Overview**
2. Выберите **Full (strict)** режим

## Архитектура

```
Пользователь → Cloudflare CDN → Worker → GitHub Pages (статика)
                              ↘ /api/* → Обработка в Worker
```

### Поток запросов

1. **Статический контент** (HTML, CSS, JS, изображения):
   - Worker проксирует запрос к GitHub Pages
   - Добавляет заголовки безопасности и кэширования
   - Поддерживает pretty URLs (`/post/123` → `/post/123.html`)

2. **API-эндпоинты**:
   - `/api/{id}` — генерирует партнёрскую ссылку Admitad и редиректит (302)
   - `/api/search` — редиректит на главную с параметром `?q=...`
   - `/api/stats` — возвращает JSON со статистикой

## Кэширование

| Тип контента | Cache-Control |
|-------------|---------------|
| HTML | `public, max-age=600, stale-while-revalidate=3600` |
| CSS/JS | `public, max-age=86400` |
| Изображения/шрифты | `public, max-age=604800, immutable` |
| JSON/XML | `public, max-age=3600` |

## Заголовки безопасности

Worker автоматически добавляет:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

## Мониторинг

Для мониторинга используйте:
- **Cloudflare Analytics** — трафик, запросы, ошибки
- **Cloudflare Web Analytics** — поведение пользователей
- **Worker Analytics** — логи выполнения Worker

## Обновление контента

Контент обновляется автоматически через GitHub Actions:
1. Каждые 2 часа запускается билд
2. Python-генератор создаёт статические HTML-файлы
3. Файлы деплоятся на GitHub Pages
4. Worker автоматически обслуживает новый контент

Для принудительного обновления кэша Cloudflare:
1. В GitHub Actions используйте `workflow_dispatch` с `purge_cache: true`
2. Или вручную: **Cloudflare Dashboard → Caching → Purge Everything**
