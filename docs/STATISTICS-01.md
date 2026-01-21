# STATISTICS-01: Core Statistics & Metrics (Read-Only, Non-Invasive)

## Цель

Реализована централизованная система READ-ONLY статистики для админки,
которая не влияет на бизнес-логику, не меняет состояние системы и
используется исключительно для наблюдения и анализа.

## Архитектурные Принципы

1. **Python 3.12 ONLY** - Использует современный синтаксис Python 3.12
2. **Никаких side-effects** - Все методы сервиса только читают данные
3. **SQL агрегаты** - Вся статистика вычисляется через SQL COUNT, GROUP BY, AVG
4. **Единственный источник данных** - Существующая PostgreSQL БД
5. **Fail-safe** - Ошибки в статистике не ломают систему, возвращаются частичные данные + warnings

## Модуль

### Структура

```
backend/app/services/statistics/
├── __init__.py           # Экспорт сервиса и схем
├── statistics_service.py # Основная логика подсчёта (SQL aggregates)
└── schemas.py           # Pydantic модели для ответов
```

### API Endpoints (READ-ONLY)

Все эндпоинты находятся в `/api/admin/statistics/`:

| Endpoint | Описание | Требуемое право |
|----------|----------|----------------|
| `GET /overview` | Общая статистика всей системы | `admin.statistics.view` |
| `GET /anime` | Статистика по аниме | `admin.statistics.view` |
| `GET /episodes` | Статистика по эпизодам | `admin.statistics.view` |
| `GET /parser` | Статистика парсер-джобов | `admin.statistics.view` |
| `GET /errors` | Статистика ошибок | `admin.statistics.view` |
| `GET /activity` | Статистика активности админов | `admin.statistics.view` |

## Метрики

### 1. Anime Statistics

**Источник данных**: `anime` таблица

| Метрика | SQL Query | Описание |
|---------|-----------|----------|
| `total_anime` | `COUNT(id) WHERE is_deleted=false` | Общее количество аниме (без soft-deleted) |
| `published_anime` | `COUNT(id) WHERE state='published'` | Опубликованные аниме |
| `draft_anime` | `COUNT(id) WHERE state='draft'` | Черновики |
| `broken_anime` | `COUNT(id) WHERE state='broken'` | Сломанные аниме |
| `pending_anime` | `COUNT(id) WHERE state='pending'` | В ожидании |
| `archived_anime` | `COUNT(id) WHERE state='archived'` | Архивированные |
| `ongoing_anime` | `COUNT(id) WHERE status='ongoing'` | Онгоинги |
| `completed_anime` | `COUNT(id) WHERE status='completed'` | Завершённые |
| `anime_with_errors` | `COUNT(id) WHERE state='broken' OR (is_locked=true AND locked_reason IS NOT NULL)` | С ошибками |
| `anime_without_episodes` | `LEFT JOIN releases, COUNT WHERE release.id IS NULL` | Без эпизодов |

### 2. Episode Statistics

**Источник данных**: `episodes` таблица

| Метрика | SQL Query | Описание |
|---------|-----------|----------|
| `total_episodes` | `COUNT(id) WHERE is_deleted=false` | Общее количество эпизодов |
| `published_episodes` | `COUNT(id) WHERE is_deleted=false` | Опубликованные эпизоды |
| `draft_episodes` | `COUNT(id) WHERE source='manual'` | Черновики (ручной ввод) |
| `episodes_with_errors` | `COUNT(id) WHERE is_locked=true AND locked_reason IS NOT NULL` | С ошибками |
| `episodes_missing_video` | `COUNT(id) WHERE iframe_url IS NULL OR iframe_url=''` | Без видео |

### 3. Parser Statistics

**Источник данных**: `parser_jobs`, `parser_sources` таблицы

| Метрика | SQL Query | Описание |
|---------|-----------|----------|
| `total_parser_jobs` | `COUNT(*) FROM parser_jobs` | Всего джобов парсера |
| `successful_jobs` | `COUNT(*) WHERE status IN ('success', 'completed')` | Успешные джобы |
| `failed_jobs` | `COUNT(*) WHERE status IN ('failed', 'error')` | Провальные джобы |
| `running_jobs` | `COUNT(*) WHERE status IN ('running', 'in_progress')` | Запущенные джобы |
| `disabled_sources` | `COUNT(*) FROM parser_sources WHERE enabled=false` | Выключенные источники |
| `active_sources` | `COUNT(*) FROM parser_sources WHERE enabled=true` | Активные источники |
| `average_job_duration` | `AVG(EXTRACT(epoch FROM finished_at - started_at))` | Средняя длительность джоба (сек) |
| `last_job_time` | `MAX(started_at)` | Время последнего джоба |

### 4. Error Statistics

**Источник данных**: `audit_logs` таблица (действия с ошибками)

| Метрика | SQL Query | Описание |
|---------|-----------|----------|
| `total_errors` | `COUNT(*) WHERE action ILIKE '%error%' OR action ILIKE '%failed%' OR action ILIKE '%denied%'` | Все ошибки |
| `errors_last_24h` | `COUNT(*) WHERE created_at >= NOW() - INTERVAL '24 hours' AND action ILIKE ...` | Ошибки за 24ч |
| `errors_last_7d` | `COUNT(*) WHERE created_at >= NOW() - INTERVAL '7 days' AND action ILIKE ...` | Ошибки за 7 дней |
| `critical_errors` | `COUNT(*) WHERE action ILIKE '%critical%' OR action ILIKE '%emergency%'` | Критические ошибки |
| `most_frequent_error_types` | `GROUP BY action ORDER BY COUNT(*) DESC LIMIT 10` | Топ-10 типов ошибок |

### 5. Activity Statistics

**Источник данных**: `audit_logs` таблица

| Метрика | SQL Query | Описание |
|---------|-----------|----------|
| `total_audit_logs` | `COUNT(*)` | Всего записей аудита |
| `actions_last_24h` | `COUNT(*) WHERE created_at >= NOW() - INTERVAL '24 hours'` | Действий за 24ч |
| `most_active_admins` | `GROUP BY actor_id ORDER BY COUNT(*) DESC LIMIT 10` | Топ-10 активных админов |
| `most_common_actions` | `GROUP BY action ORDER BY COUNT(*) DESC LIMIT 10` | Топ-10 действий |

## RBAC

### Новое право

**Название**: `admin.statistics.view`

**Категория**: Admin Permissions

**Описание**: Позволяет просматривать статистику системы

### Роли с доступом

| Роль | Доступ |
|------|--------|
| `super_admin` | ✅ Да |
| `admin` | ✅ Да |
| `moderator` | ❌ Нет |
| `editor` | ❌ Нет |
| `support` | ❌ Нет |
| `user` | ❌ Нет |
| `parser_bot` | ❌ Нет (системные роли не имеют admin.* прав) |
| `worker_bot` | ❌ Нет (системные роли не имеют admin.* прав) |

### Аудит

Все обращения к статистике логируются:

```json
{
  "actor_id": "<user_id>",
  "actor_type": "user",
  "action": "statistics.view.<type>",
  "entity_type": "statistics",
  "entity_id": "system"
}
```

Типы действий:
- `statistics.view.overview`
- `statistics.view.anime`
- `statistics.view.episodes`
- `statistics.view.parser`
- `statistics.view.errors`
- `statistics.view.activity`

## Производительность

### Оптимизации

1. **Только SQL агрегаты** - Данные никогда не загружаются в память Python
2. **Индексы** - Используются существующие индексы на `is_deleted`, `state`, `status`, `created_at`
3. **No N+1 queries** - Все метрики в одном запросе на категорию
4. **Parallel-safe** - Каждая категория статистики независима

### Сложность запросов

| Endpoint | Queries | Complexity |
|----------|---------|------------|
| `/overview` | 5 | O(n) для каждой таблицы |
| `/anime` | 4 | O(n) для anime + releases |
| `/episodes` | 4 | O(n) для episodes |
| `/parser` | 6 | O(n) для parser_jobs + parser_sources |
| `/errors` | 5 | O(n) для audit_logs с WHERE |
| `/activity` | 4 | O(n) для audit_logs с GROUP BY |

**Рекомендации**:
- На продакшене с миллионами записей запросы могут занимать 1-5 секунд
- Рекомендуется добавить фоновое кэширование (вне scope STATISTICS-01)
- Для больших таблиц можно использовать материализованные представления (вне scope)

## Гарантии Безопасности

### READ-ONLY

✅ **Никаких INSERT/UPDATE/DELETE** - Сервис использует только SELECT запросы

✅ **Никаких транзакций** - Нет commit/rollback, только чтение

✅ **Immutable** - Состояние БД не меняется ни при каких условиях

### Изоляция

✅ **Бизнес-логика не знает о статистике** - Модуль изолирован в `services/statistics/`

✅ **Fail-safe** - Ошибки в статистике возвращают partial data + warnings, не ломают систему

✅ **No side effects** - Статистика не триггерит никаких событий

### Аудит

✅ **Все обращения логируются** - Каждый вызов API записывается в audit_logs

✅ **Permission checks** - Требуется `admin.statistics.view` для всех эндпоинтов

✅ **Actor type validation** - Только `actor_type="user"` может вызывать статистику

## Ограничения

### Что НЕ включено

❌ **Кэширование** - Нет Redis, нет in-memory кэша (можно добавить позже)

❌ **Background jobs** - Нет воркеров для предподсчёта (можно добавить позже)

❌ **Графики** - Нет графиков/визуализации (только JSON данные)

❌ **Фильтрация** - Нет фильтров по датам/пользователям (можно добавить позже)

❌ **Экспорт** - Нет экспорта в CSV/Excel (можно добавить позже)

### Зависимости

- **PostgreSQL** - Используются PostgreSQL-специфичные функции (EXTRACT, INTERVAL)
- **Существующие таблицы** - Требуются таблицы: anime, episodes, releases, audit_logs, parser_jobs, parser_sources

## Примеры Использования

### GET /api/admin/statistics/overview

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/admin/statistics/overview
```

Ответ:
```json
{
  "anime": {
    "total_anime": 150,
    "published_anime": 120,
    "draft_anime": 20,
    "broken_anime": 5,
    "pending_anime": 3,
    "archived_anime": 2,
    "ongoing_anime": 80,
    "completed_anime": 70,
    "anime_with_errors": 5,
    "anime_without_episodes": 10
  },
  "episodes": {
    "total_episodes": 5000,
    "published_episodes": 4800,
    "draft_episodes": 150,
    "episodes_with_errors": 25,
    "episodes_missing_video": 50
  },
  "parser": {
    "total_parser_jobs": 1000,
    "successful_jobs": 950,
    "failed_jobs": 30,
    "running_jobs": 2,
    "disabled_sources": 1,
    "active_sources": 5,
    "average_job_duration": 45.5,
    "last_job_time": "2026-01-21T05:00:00Z"
  },
  "errors": {
    "total_errors": 100,
    "errors_last_24h": 5,
    "errors_last_7d": 20,
    "critical_errors": 2,
    "most_frequent_error_types": [
      {"action": "permission_denied", "count": 50},
      {"action": "anime.edit.failed", "count": 30}
    ]
  },
  "activity": {
    "total_audit_logs": 10000,
    "actions_last_24h": 150,
    "most_active_admins": [
      {"actor_id": "uuid-1", "action_count": 500},
      {"actor_id": "uuid-2", "action_count": 300}
    ],
    "most_common_actions": [
      {"action": "anime.edit", "count": 2000},
      {"action": "episode.create", "count": 1500}
    ]
  },
  "warnings": []
}
```

### GET /api/admin/statistics/parser

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/admin/statistics/parser
```

Ответ:
```json
{
  "total_parser_jobs": 1000,
  "successful_jobs": 950,
  "failed_jobs": 30,
  "running_jobs": 2,
  "disabled_sources": 1,
  "active_sources": 5,
  "average_job_duration": 45.5,
  "last_job_time": "2026-01-21T05:00:00Z"
}
```

## Тестирование

### Запуск тестов

```bash
cd backend
python -m pytest tests/test_statistics.py -v
```

### Покрытие

Тесты проверяют:

1. ✅ **RBAC Contract** - Права корректно определены
2. ✅ **READ-ONLY** - Статистика не меняет данные
3. ✅ **Empty DB** - Пустая БД возвращает нули
4. ✅ **Filled DB** - Заполненная БД возвращает корректные значения
5. ✅ **Partial Failure** - Ошибки возвращают partial data + warnings

## Мониторинг

### Метрики для Prometheus (будущее)

После добавления Prometheus можно экспортировать:

- `kitsu_anime_total` - Общее количество аниме
- `kitsu_episodes_total` - Общее количество эпизодов
- `kitsu_parser_jobs_total{status="success|failed|running"}` - Парсер джобы по статусу
- `kitsu_errors_24h` - Ошибки за 24 часа

### Логи

Все обращения к статистике логируются в `audit_logs`:

```sql
SELECT * FROM audit_logs 
WHERE action LIKE 'statistics.view.%' 
ORDER BY created_at DESC;
```

## Дальнейшее Развитие

Возможные улучшения (вне scope STATISTICS-01):

1. **Кэширование** - Redis для хранения результатов на 5-15 минут
2. **Фоновые джобы** - Предподсчёт статистики каждые 10 минут
3. **Фильтрация** - Статистика за период, по источнику, по пользователю
4. **Экспорт** - CSV/Excel выгрузка
5. **Графики** - Временные ряды для трендов
6. **Alerts** - Уведомления при критических значениях

---

**Статус**: ✅ Реализовано  
**Версия**: 1.0.0  
**Дата**: 2026-01-21
