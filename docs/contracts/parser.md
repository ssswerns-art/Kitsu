# Контракт парсера (PARSER-01)

**СТАТУС**: Утверждён — точка невозврата  
**ДАТА**: 2026-01-20  
**ВЕРСИЯ**: 1.0

---

## 1. РОЛЬ ПАРСЕРА

### 1.1. Идентификация

Parser — это **отдельный system actor**, НЕ равный администратору.

**Ключевые отличия от человека:**

| Аспект | Администратор (человек) | Parser (система) |
|--------|-------------------------|------------------|
| **Идентификация** | `created_by` / `updated_by` = UUID пользователя | `created_by` / `updated_by` = NULL |
| **Actor type** | `"user"` | `"system"` |
| **Роль в RBAC** | `admin`, `moderator`, `editor` | `parser_bot` |
| **Permissions** | `admin:*`, `anime.*`, `episode.*` | ТОЛЬКО `parser.*` |
| **Источник данных** | `source = "manual"` | `source = "parser"` |
| **Audit logs** | `actor_id` = user.id | `actor_id` = NULL, `actor_type = "system"` |
| **Приоритет данных** | **ВСЕГДА выше парсера** | Подчиняется manual |

### 1.2. Permissions парсера

Parser имеет **ТОЛЬКО** следующие разрешения:

**МОЖЕТ (✅)**:
- `parser.read` — чтение настроек парсера
- `parser.sync` — синхронизация данных из внешних источников
- `parser.update_staging` — обновление staging-таблиц (`anime_external`, `anime_schedule`, `anime_episodes_external`)
- `parser.suggest` — создание записей в состоянии `pending` для модерации

**НЕ МОЖЕТ (❌ НИКОГДА)**:
- ❌ `anime.publish` — публикация аниме (только админ)
- ❌ `anime.lock` — блокировка полей (только админ)
- ❌ `anime.delete` — удаление аниме (только админ)
- ❌ `episode.delete` — удаление серий (только админ)
- ❌ `admin.*` — любые административные операции
- ❌ `audit.view` — просмотр логов
- ❌ `security.*` — операции безопасности

### 1.3. Отличие от администратора

```python
# ❌ НЕПРАВИЛЬНО
if user.role == "admin" or user.role == "parser_bot":
    allow()

# ✅ ПРАВИЛЬНО  
if has_permission(user, "anime.publish"):
    allow()  # parser НЕ имеет этого права
```

Parser **НЕ эквивалентен** администратору и **НЕ МОЖЕТ**:
- Обходить блокировки (`is_locked = True`)
- Переводить аниме в `published` или `archived`
- Удалять данные (ни soft, ни hard delete)
- Изменять данные с `source = "manual"`

---

## 2. КОНТРАКТ ПАРСЕРА

### 2.1. Поля, которые парсер МОЖЕТ обновлять

**Anime (ТОЛЬКО если `source = "parser"` ИЛИ `source IS NULL`):**

| Поле | Условия | Примечание |
|------|---------|-----------|
| `title_ru` | Не locked | Русское название |
| `title_en` | Не locked | Английское название |
| `title_original` | Не locked | Оригинальное название |
| `description` | Не locked | Описание аниме |
| `poster_url` | Не locked | URL постера |
| `year` | Не locked | Год выхода |
| `season` | Не locked | Сезон (winter/spring/summer/fall) |
| `status` | Не locked | Статус (ongoing/finished/announced) |
| `genres` | Не locked | Список жанров (JSON) |
| `state` | **ТОЛЬКО** → `pending`, `broken` | НЕ может установить `published` |
| `source` | ВСЕГДА устанавливает `"parser"` | Обязательно при обновлении |
| `updated_by` | ВСЕГДА NULL (system) | Не указывать пользователя |

**Episode (ТОЛЬКО если `source = "parser"` ИЛИ `source IS NULL`):**

| Поле | Условия | Примечание |
|------|---------|-----------|
| `title` | Не locked | Название серии |
| `iframe_url` | Не locked | iframe для плеера |
| `available_translations` | Не locked | Список озвучек (JSON) |
| `available_qualities` | Не locked | Список качеств (JSON) |
| `source` | ВСЕГДА устанавливает `"parser"` | Обязательно при обновлении |
| `updated_by` | ВСЕГДА NULL (system) | Не указывать пользователя |

**Release:**
- ❌ Parser **НЕ МОЖЕТ** создавать или изменять Release
- Release создаётся ТОЛЬКО вручную администратором

### 2.2. Поля, которые парсер НЕ МОЖЕТ НИКОГДА трогать

**Anime:**
- ❌ `id` — первичный ключ
- ❌ `created_by` — создатель записи
- ❌ `updated_by` — должен быть NULL при parser updates
- ❌ `is_locked` — только админ
- ❌ `locked_fields` — только админ
- ❌ `locked_by` — только админ
- ❌ `locked_reason` — только админ
- ❌ `locked_at` — только админ
- ❌ `is_deleted` — только админ (soft delete)
- ❌ `deleted_at` — только админ
- ❌ `deleted_by` — только админ
- ❌ `delete_reason` — только админ
- ❌ `created_at` — системное поле
- ❌ `updated_at` — обновляется БД автоматически

**Episode:**
- ❌ `id` — первичный ключ
- ❌ `release_id` — связь с релизом
- ❌ `number` — номер серии (устанавливается при создании)
- ❌ `created_by` — создатель записи
- ❌ `updated_by` — должен быть NULL при parser updates
- ❌ `is_locked`, `locked_*` — только админ
- ❌ `is_deleted`, `deleted_*` — только админ
- ❌ `created_at`, `updated_at` — системные поля

### 2.3. Что происходит при конфликте с manual

**ИНВАРИАНТ: Manual > Parser**

```python
# Проверка перед обновлением парсером
if anime.source == "manual":
    raise ParserCannotOverrideManualError(
        f"Anime {anime.id} has source='manual', parser cannot modify it"
    )

if anime.is_locked:
    # Проверяем конкретные поля
    if locked_fields is None or any(field in anime.locked_fields for field in fields_to_update):
        raise EntityLockedError(
            f"Anime {anime.id} is locked, parser cannot modify locked fields"
        )
```

**Сценарии конфликтов:**

| Сценарий | Решение |
|----------|---------|
| Anime создано вручную (`source = "manual"`) | ❌ Parser НЕ обновляет, пропускает |
| Поля заблокированы (`is_locked = True`, `locked_fields = ["title", "poster_url"]`) | ❌ Parser НЕ обновляет заблокированные поля |
| Anime в состоянии `published` | ❌ Parser НЕ может изменить состояние обратно на `pending` |
| Админ вручную отредактировал описание | Source меняется на `"manual"` → Parser больше НЕ трогает |
| Parser нашёл новые данные для `source = "parser"` anime | ✅ Обновляет, если не locked |

**Правило перехода source:**
```
manual → manual  (навсегда)
parser → manual  (при любом ручном изменении)
manual → parser  (НИКОГДА автоматически, только через админку)
```

---

## 3. АДМИНКА ПАРСЕРА (ТРЕБОВАНИЯ)

### 3.1. Глобальный toggle (on/off)

**Таблица**: `parser_settings.mode`

**Значения:**
- `"manual"` — автопарсинг **ВЫКЛЮЧЕН**, парсер запускается ТОЛЬКО вручную
- `"auto"` — автопарсинг **ВКЛЮЧЁН**, фоновые задачи выполняются по расписанию

**UI-требования:**
- Переключатель **ВИДИМ** только для ролей `super_admin`, `admin`
- Показывать текущий статус: `"Автопарсинг активен"` / `"Автопарсинг отключён"`
- При переключении требовать подтверждение: *"Вы уверены, что хотите включить автоматическое обновление?"*
- Логировать изменение в `audit_logs` с указанием `actor_id` и причины

**Backend-проверка:**
```python
# Перед запуском любой автоматической задачи
settings = await parser_settings_repo.get()
if settings.mode != "auto":
    logger.info("Parser is in manual mode, skipping automatic task")
    return
```

### 3.2. Режимы работы

**Таблица**: `parser_settings.dry_run`

**Значения:**
- `dry_run = False` — **Нормальный режим**: парсер пишет данные в БД
- `dry_run = True` — **Dry-run режим**: парсер ТОЛЬКО логирует, что собирается сделать, но НЕ пишет в БД

**Дополнительные режимы (будущие расширения):**
- `metadata_only` — обновлять ТОЛЬКО метаданные (title, description, poster), НЕ трогать эпизоды
- `episodes_only` — обновлять ТОЛЬКО эпизоды, НЕ трогать метаданные аниме

**UI-требования:**
- Checkbox "Dry-run mode (тестовый режим, без записи в БД)"
- При включении dry-run показывать **оранжевый баннер**: *"Парсер в тестовом режиме, данные НЕ будут сохранены"*
- Логи dry-run должны быть **чётко помечены**: `[DRY-RUN]` prefix

### 3.3. Фильтры

**Таблица**: `parser_settings`

**Фильтры:**

| Фильтр | Поле | Тип | Описание |
|--------|------|-----|----------|
| **По году** | `year_from`, `year_to` | INT | Парсить только аниме с годом в диапазоне |
| **По сезону** | `season_filter` | JSON | Список сезонов: `["winter", "spring", "summer", "fall"]` |
| **По статусу** | `status_filter` | JSON | Список статусов: `["ongoing", "finished", "announced"]` |
| **По источнику** | `enabled_sources` | JSON | Список источников: `["shikimori", "kodik"]` |
| **По качеству** | `allowed_qualities` | JSON | Список качеств: `["720p", "1080p"]` |
| **По озвучке** | `allowed_translation_types` | JSON | Список типов: `["voice", "sub"]` |
| **Приоритет озвучек** | `translation_priority` | JSON | Порядок приоритета: `["AniLibria", "AniDub", "..."]` |

**Blacklist:**

| Таблица | Поле | Описание |
|---------|------|----------|
| `parser_blacklist` | `title` | Заблокированное название (не парсить) |
| `parser_blacklist` | `external_id` | Заблокированный внешний ID |

**UI-требования:**
- Фильтры должны быть **видны** на одной странице (не скрыты в табах)
- При изменении фильтров показывать предварительное количество аниме, которое будет затронуто
- Blacklist должен иметь отдельную страницу с возможностью добавления/удаления записей

### 3.4. Dry-run режим

**Поведение:**
```python
if settings.dry_run:
    logger.info(f"[DRY-RUN] Would update anime {anime.id}: title={new_title}")
    logger.info(f"[DRY-RUN] Would set state=pending")
    return  # НЕ выполнять UPDATE
else:
    anime.title = new_title
    anime.state = "pending"
    await session.commit()
    logger.info(f"Updated anime {anime.id}")
```

**UI-требования:**
- Кнопка "Запустить в dry-run режиме"
- Результаты dry-run показывать в отдельной вкладке "Dry-run logs"
- Dry-run логи должны автоматически очищаться через 24 часа

### 3.5. Лимиты

**Таблица**: `parser_settings`, `parser_sources`

**Лимиты:**

| Лимит | Поле | Тип | Описание |
|-------|------|-----|----------|
| **Лимит за запуск** | `max_items_per_run` | INT | Максимум N аниме за один запуск (default: 100) |
| **Rate limit** | `rate_limit_per_min` | INT | Макс. запросов к источнику в минуту (per source) |
| **Concurrency** | `max_concurrency` | INT | Макс. параллельных запросов (per source) |
| **Timeout** | `request_timeout_sec` | INT | Таймаут запроса к источнику (default: 30s) |

**UI-требования:**
- Показывать текущее использование лимитов: `"Обработано: 45/100 аниме"`
- При достижении лимита показывать уведомление: *"Достигнут лимит обработки, остальные аниме будут обработаны в следующем запуске"*

### 3.6. Логи ошибок

**Таблицы**: `parser_job_logs`, `parser_jobs`

**Уровни логов:**
- `ERROR` — критическая ошибка (источник недоступен, парсинг провален)
- `WARNING` — предупреждение (аниме пропущено из-за блокировки, несоответствие данных)
- `INFO` — информация (успешное обновление, dry-run результат)

**UI-требования:**
- Страница "Parser Logs" с фильтрами:
  - По уровню (ERROR / WARNING / INFO)
  - По источнику (Shikimori / Kodik)
  - По дате (последние 24 часа / неделя / месяц)
- Показывать количество ошибок за последние 24 часа: `"Ошибок: 12"`
- Для каждой ошибки показывать:
  - Время
  - Источник
  - Тип задачи
  - Сообщение об ошибке
  - Affected anime ID (если применимо)
- Возможность **экспортировать** логи в CSV

---

## 4. АВТОПАРСИНГ

### 4.1. Как включается

**Требования:**
1. `parser_settings.mode = "auto"` (через админку)
2. `parser_sources.enabled = True` для нужных источников
3. Фоновый worker **ЗАПУЩЕН** (отдельный процесс)

**Процесс включения:**
```
1. Админ заходит в админку → Settings → Parser
2. Переключает "Parser mode" → "Auto"
3. Подтверждает диалог: "Enable automatic parsing?"
4. Backend сохраняет mode = "auto" в БД
5. Логируется в audit_logs: action = "parser.settings.mode_changed", after = {"mode": "auto"}
6. Фоновый worker обнаруживает изменение при следующем опросе (каждые 60 секунд)
7. Worker начинает выполнять задачи по расписанию
```

### 4.2. Кто может включать

**RBAC:**
- **Может включать**: `super_admin`, `admin`
- **Не может**: `moderator`, `editor`, `parser_bot`, `support`, `user`

**Проверка:**
```python
@router.post("/admin/parser/settings")
async def update_parser_settings(
    settings: ParserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service)
):
    # Требуем права админа
    await permission_service.require_permission(current_user, "admin:parser.settings")
    
    # ...
```

### 4.3. Как останавливается

**Способы остановки:**

1. **Через админку** (graceful):
   - Админ переключает `mode = "manual"`
   - Текущие задачи **ДОХОДЯТ ДО КОНЦА**
   - Новые задачи **НЕ ЗАПУСКАЮТСЯ**

2. **Emergency stop** (немедленная):
   - Backend endpoint: `POST /admin/parser/emergency-stop`
   - Требует permission: `admin:parser.emergency`
   - **НЕМЕДЛЕННО** останавливает ВСЕ задачи (cancel asyncio tasks)
   - Логирует в audit_logs с уровнем WARNING

3. **Автоматическая остановка при ошибках**:
   - Если источник недоступен > 10 минут → отключить `parser_sources.enabled = False`
   - Если > 50 ошибок за 1 час → переключить `mode = "manual"` и отправить алерт админу

### 4.4. Где виден статус

**Dashboard** (`/admin/parser/dashboard`):

**Показывать:**
- **Режим работы**: `"Auto"` / `"Manual"` с цветовым индикатором (зелёный/серый)
- **Dry-run**: ON/OFF
- **Источники**:
  - Shikimori: Enabled, Last sync: 5 min ago, Status: OK
  - Kodik: Enabled, Last sync: 2 min ago, Status: OK
- **Активные задачи**:
  - catalog_sync: Running, Progress: 45/100, Started: 10 min ago
  - episode_sync: Queued, Priority: normal
- **Последние завершённые задачи**:
  - catalog_sync: Succeeded, Processed: 100 anime, Finished: 1 hour ago
  - episode_sync: Failed, Error: Source timeout, Finished: 30 min ago
- **Ошибки за 24 часа**: 12 (красный индикатор при > 10)

**Real-time updates:**
- Страница обновляется через WebSocket или polling каждые 10 секунд
- При изменении статуса задачи показывать уведомление

### 4.5. Как избежать «само запустилось»

**ЗАПРЕТЫ (fail-fast):**

1. ❌ **НЕ ИСПОЛЬЗОВАТЬ системный cron**
   - Всё управление через БД (`parser_settings.mode`)
   - Cron может запускать worker, но НЕ задачи напрямую

2. ❌ **НЕТ скрытых конфигов**
   - Все настройки ТОЛЬКО в БД (`parser_settings`, `parser_sources`)
   - НЕТ environment variables для включения автопарсинга

3. ❌ **НЕТ "default = auto"**
   - При первой инициализации `mode = "manual"` по умолчанию
   - Требуется **явное** включение через админку

4. ❌ **НЕТ автоматических миграций settings**
   - Migration создаёт `parser_settings` с `mode = "manual"`
   - НЕ изменять mode в последующих миграциях

**ПРОВЕРКИ (audit trail):**

```python
# Каждое изменение mode логируется
await audit_service.log_update(
    entity_type="parser_settings",
    entity_id="global",
    before_data={"mode": "manual"},
    after_data={"mode": "auto"},
    actor=current_user,
    reason=f"Enabled automatic parsing by {current_user.email}"
)
```

**Архитектура worker:**
```python
# background/parser_worker.py
async def parser_worker_loop():
    while True:
        settings = await get_parser_settings()
        
        if settings.mode != "auto":
            logger.info("Parser in manual mode, sleeping...")
            await asyncio.sleep(60)
            continue
        
        # Запускать задачи ТОЛЬКО если mode = "auto"
        await run_scheduled_tasks()
        await asyncio.sleep(60)
```

---

## 5. ЛОГИ И ОШИБКИ

### 5.1. Где смотреть ошибки парсера

**Источники логов:**

1. **Parser Job Logs** (`parser_job_logs`):
   - Структурированные логи каждой задачи
   - Уровни: INFO, WARNING, ERROR
   - Связаны с `parser_jobs.id`

2. **Audit Logs** (`audit_logs`):
   - Изменения настроек парсера
   - Включение/выключение источников
   - Emergency stops
   - `actor_type = "system"` для автоматических действий

3. **Application Logs** (stdout/файлы):
   - Критические ошибки парсера
   - Недоступность источников
   - Exceptions и stack traces

**UI доступ:**
- `/admin/parser/logs` — Parser Job Logs (интерфейс)
- `/admin/audit-logs` — Audit Logs (фильтр по `entity_type = "parser_*"`)
- Application logs — только через сервер (для super_admin)

### 5.2. Как админ видит «проблемные аниме»

**Таблица**: `parser_jobs` + `parser_job_logs`

**Проблемные аниме:**
- Anime, которое парсер НЕ смог обработать
- Anime с конфликтами (несколько совпадений по названию)
- Anime, заблокированное от обновления

**UI:** `/admin/parser/problem-anime`

**Колонки:**
| Поле | Описание |
|------|----------|
| Anime ID | Ссылка на аниме |
| Title | Название аниме |
| Problem | "Locked by admin" / "Multiple matches" / "Source unavailable" |
| Last Attempt | Когда парсер последний раз пытался обновить |
| Error Message | Подробности ошибки |
| Actions | "Unlock" / "Bind manually" / "Ignore" |

**Фильтры:**
- По типу проблемы
- По источнику (Shikimori / Kodik)
- По дате последней попытки

**Автоматические уведомления:**
- Если > 10 проблемных аниме за 24 часа → email админу
- Если конкретное аниме fail 3 раза подряд → добавить в "Requires attention" список

### 5.3. Связь с audit_log

**Все действия парсера ОБЯЗАТЕЛЬНО логируются в `audit_logs`:**

| Действие | `action` | `entity_type` | `entity_id` | `actor_type` |
|----------|----------|---------------|-------------|--------------|
| Обновление аниме парсером | `"anime.update"` | `"anime"` | anime.id | `"system"` |
| Создание anime в pending | `"anime.create"` | `"anime"` | anime.id | `"system"` |
| Изменение настроек | `"parser.settings.update"` | `"parser_settings"` | `"global"` | `"user"` |
| Включение source | `"parser.source.enable"` | `"parser_sources"` | source.id | `"user"` |
| Emergency stop | `"parser.emergency_stop"` | `"parser_jobs"` | job.id | `"user"` |

**Формат audit log для parser updates:**
```json
{
  "id": "uuid",
  "actor_id": null,
  "actor_type": "system",
  "action": "anime.update",
  "entity_type": "anime",
  "entity_id": "anime-uuid",
  "before": {
    "description": "Old description",
    "poster_url": "old_url.jpg"
  },
  "after": {
    "description": "New description from parser",
    "poster_url": "new_url.jpg",
    "source": "parser"
  },
  "reason": "Automatic sync from Shikimori",
  "ip_address": "127.0.0.1",
  "user_agent": "ParserWorker/1.0",
  "created_at": "2026-01-20T19:00:00Z"
}
```

**Требования:**
- ❗ **КАЖДОЕ** обновление парсером должно иметь audit log
- ❗ `before` и `after` должны содержать ТОЛЬКО изменённые поля
- ❗ `reason` должно указывать источник: `"Automatic sync from {source_name}"`
- ❗ Dry-run НЕ создаёт audit logs (только parser_job_logs)

---

## 6. ИНВАРИАНТЫ (САМЫЙ ВАЖНЫЙ ПУНКТ)

### 6.1. Что парсер НИКОГДА не имеет права делать

**❌ АБСОЛЮТНЫЕ ЗАПРЕТЫ (FAIL FAST):**

1. ❌ **Изменять данные с `source = "manual"`**
   ```python
   if entity.source == "manual":
       raise ParserCannotOverrideManualError()
   ```

2. ❌ **Обновлять заблокированные поля**
   ```python
   if entity.is_locked and (
       entity.locked_fields is None or 
       any(field in entity.locked_fields for field in fields_to_update)
   ):
       raise EntityLockedError()
   ```

3. ❌ **Устанавливать состояние `published` или `archived`**
   ```python
   if new_state in ["published", "archived"]:
       raise ParserCannotPublishError()
   ```

4. ❌ **Удалять записи (soft или hard delete)**
   ```python
   if action == "delete":
       raise ParserCannotDeleteError()
   ```

5. ❌ **Создавать или изменять Release**
   ```python
   if entity_type == "Release":
       raise ParserCannotManageReleasesError()
   ```

6. ❌ **Обходить RBAC проверки**
   ```python
   # Парсер ОБЯЗАН иметь permission "parser.sync"
   if not has_permission(system_actor, "parser.sync"):
       raise PermissionDeniedError()
   ```

7. ❌ **Выполняться без audit logging**
   ```python
   # После КАЖДОГО UPDATE обязателен audit log
   await audit_service.log_update(...)
   ```

8. ❌ **Работать в режиме "auto" без явного включения**
   ```python
   settings = await get_parser_settings()
   if settings.mode != "auto":
       raise AutoParsingNotEnabledError()
   ```

9. ❌ **Игнорировать rate limits**
   ```python
   if requests_this_minute > source.rate_limit_per_min:
       await asyncio.sleep(60)
   ```

10. ❌ **Скрывать ошибки (silent failures)**
    ```python
    # ВСЕ ошибки ОБЯЗАНЫ логироваться
    try:
        await update_anime(anime)
    except Exception as e:
        logger.error(f"Failed to update anime {anime.id}: {e}")
        await log_parser_error(anime.id, str(e))
        raise  # НЕ подавлять
    ```

### 6.2. Обязательные проверки перед КАЖДЫМ апдейтом

**Чеклист (в порядке выполнения):**

```python
async def parser_update_anime(anime_id: UUID, updates: dict) -> None:
    """
    Обновление аниме парсером с ПОЛНЫМ набором проверок.
    """
    # 1. Получить существующую запись
    anime = await anime_repo.get(anime_id)
    if anime is None:
        raise AnimeNotFoundError(anime_id)
    
    # 2. ПРОВЕРКА: source != "manual"
    if anime.source == "manual":
        logger.warning(f"Anime {anime_id} has source='manual', skipping parser update")
        raise ParserCannotOverrideManualError(
            f"Cannot update anime {anime_id}: source is 'manual'"
        )
    
    # 3. ПРОВЕРКА: не заблокировано
    if anime.is_locked:
        locked_fields = anime.locked_fields or []
        conflicting_fields = set(updates.keys()) & set(locked_fields)
        if locked_fields == [] or conflicting_fields:
            logger.warning(f"Anime {anime_id} is locked, fields: {conflicting_fields}")
            raise EntityLockedError(
                f"Cannot update anime {anime_id}: fields {conflicting_fields} are locked"
            )
    
    # 4. ПРОВЕРКА: не удалено
    if anime.is_deleted:
        raise EntityDeletedError(f"Anime {anime_id} is deleted")
    
    # 5. ПРОВЕРКА: state transition
    if "state" in updates:
        new_state = updates["state"]
        if new_state in ["published", "archived"]:
            raise ParserCannotPublishError(
                f"Parser cannot set state to '{new_state}'"
            )
        if new_state not in ["draft", "pending", "broken"]:
            raise InvalidStateTransitionError(f"Invalid state: {new_state}")
    
    # 6. ПРОВЕРКА: режим dry-run
    settings = await get_parser_settings()
    if settings.dry_run:
        logger.info(f"[DRY-RUN] Would update anime {anime_id} with {updates}")
        return  # НЕ выполнять UPDATE
    
    # 7. Сохранить before state для audit log
    before_state = LockService.serialize_entity(anime)
    
    # 8. Применить изменения
    for field, value in updates.items():
        setattr(anime, field, value)
    
    # 9. Установить обязательные поля
    anime.source = "parser"
    anime.updated_by = None  # System update
    
    # 10. Сохранить в БД
    await session.commit()
    
    # 11. ОБЯЗАТЕЛЬНО: audit log
    await audit_service.log_update(
        entity_type="anime",
        entity_id=str(anime_id),
        before_data=before_state,
        after_data=LockService.serialize_entity(anime),
        actor=None,
        actor_type="system",
        reason=f"Automatic sync from {updates.get('_source_name', 'parser')}"
    )
    
    logger.info(f"Successfully updated anime {anime_id} by parser")
```

### 6.3. Условия, приводящие к FAIL FAST

**Критические ошибки → немедленная остановка задачи:**

1. **Database connection lost**
   ```python
   except asyncpg.exceptions.ConnectionDoesNotExistError:
       logger.critical("Database connection lost, stopping parser")
       await emergency_stop_parser()
       raise
   ```

2. **Permission denied** (неправильная конфигурация RBAC)
   ```python
   except PermissionDeniedError:
       logger.critical("Parser lacks required permissions, check RBAC configuration")
       await emergency_stop_parser()
       raise
   ```

3. **Превышение rate limit на 200%** (защита от бана источника)
   ```python
   if requests_per_minute > source.rate_limit_per_min * 2:
       logger.critical(f"Rate limit exceeded by 200% for {source.name}, stopping")
       await disable_source(source.id)
       raise RateLimitExceededError()
   ```

4. **Попытка обновить `source = "manual"` аниме**
   ```python
   except ParserCannotOverrideManualError:
       # НЕ останавливать парсер, просто пропустить это аниме
       logger.warning(f"Skipping manual anime {anime_id}")
       await log_skipped_anime(anime_id, "manual_source")
       continue  # Переход к следующему аниме
   ```

5. **Источник недоступен > 10 минут**
   ```python
   if time.time() - source.last_successful_sync > 600:
       logger.error(f"Source {source.name} unavailable for 10+ minutes")
       await disable_source(source.id)
       await notify_admin(f"Source {source.name} disabled due to unavailability")
   ```

**НЕ критичные ошибки → логировать и продолжить:**

1. **Аниме не найдено в источнике** → пропустить
2. **Заблокированное аниме** → пропустить, залогировать
3. **Несоответствие данных** (conflicting year/title) → залогировать, добавить в "requires manual binding"
4. **Timeout на одном аниме** → retry до 3 раз, затем пропустить

---

## 7. АРХИТЕКТУРНЫЕ ГАРАНТИИ

### 7.1. Staging Architecture (Non-Invasive)

**Парсер работает через отдельные таблицы:**

```
[External Sources] 
    ↓ (fetch)
[Parser Service]
    ↓ (write)
[Staging Tables]           [Main Catalog]
- anime_external            - anime
- anime_schedule           - episodes  
- anime_episodes_external  - releases
    ↓ (publish, manual approval)
[Main Catalog]
```

**Гарантии:**
- ❗ Parser **НЕ МОЖЕТ** напрямую писать в `anime`, `episodes` без админского подтверждения
- ❗ Все данные парсера сначала попадают в staging tables
- ❗ Publish service проверяет все инварианты перед переносом в main catalog

### 7.2. Actor Separation

**Система актеров:**

| Actor Type | Идентификация | Permissions | Audit Trail |
|------------|---------------|-------------|-------------|
| User (admin) | `created_by = user.id` | `admin.*`, `anime.*` | `actor_id = user.id`, `actor_type = "user"` |
| User (editor) | `created_by = user.id` | `anime.edit`, `episode.edit` | `actor_id = user.id`, `actor_type = "user"` |
| System (parser) | `created_by = NULL` | `parser.*` | `actor_id = NULL`, `actor_type = "system"` |

**Запреты:**
- ❌ Parser НЕ может иметь `actor_type = "user"`
- ❌ Parser НЕ может устанавливать `created_by` / `updated_by` на реального пользователя
- ❌ Нельзя смешивать parser и admin permissions в одной роли

### 7.3. State Machine Enforcement

**Allowed transitions:**

| From | To | Who Can |
|------|----|---------|
| `draft` | `pending` | Parser, Admin |
| `draft` | `published` | ❌ Parser, ✅ Admin |
| `pending` | `published` | ❌ Parser, ✅ Admin |
| `pending` | `broken` | Parser, Admin |
| `published` | `archived` | ❌ Parser, ✅ Admin |
| `broken` | `pending` | Parser, Admin |

**Enforcement:**
```python
PARSER_ALLOWED_STATES = {"draft", "pending", "broken"}

if new_state not in PARSER_ALLOWED_STATES:
    raise ParserCannotSetStateError(
        f"Parser can only set states: {PARSER_ALLOWED_STATES}"
    )
```

### 7.4. Lock Service Integration

**Field-Level Locking:**

```python
# Админ может заблокировать конкретные поля
anime.locked_fields = ["title", "description"]

# Parser проверяет перед обновлением
LockService.check_parser_update(
    entity=anime,
    fields_to_update=["poster_url"],  # OK
    actor_type="system"
)

LockService.check_parser_update(
    entity=anime,
    fields_to_update=["title"],  # ❌ FAIL
    actor_type="system"
)
# → raises EntityLockedError
```

### 7.5. Audit Trail Completeness

**100% Coverage Rule:**
- ❗ **КАЖДОЕ** изменение данных ОБЯЗАНО иметь audit log
- ❗ Dry-run НЕ создаёт audit logs (только parser_job_logs)
- ❗ Before/After states ОБЯЗАТЕЛЬНЫ для UPDATE операций
- ❗ System actions имеют `actor_id = NULL`, `actor_type = "system"`

**Проверка в CI:**
```python
# В тестах: убедиться что каждый parser update создаёт audit log
assert len(audit_logs) == number_of_updates
```

---

## 8. MIGRATION PLAN (Design Only)

### 8.1. Phase 1: Settings & Admin UI

**Deliverables:**
- [ ] `parser_settings` таблица с `mode = "manual"` по умолчанию
- [ ] Admin UI для управления settings (toggle, filters, dry-run)
- [ ] Endpoint `GET /admin/parser/settings`
- [ ] Endpoint `POST /admin/parser/settings` с permission check
- [ ] Audit logging для изменения settings

**Acceptance Criteria:**
- Админ может переключать mode через UI
- Все изменения логируются в audit_logs
- Default mode = "manual" после миграции

### 8.2. Phase 2: Parser Compliance

**Deliverables:**
- [ ] Обновить parser services для соблюдения контракта
- [ ] Добавить все проверки из раздела 6.2
- [ ] Интегрировать LockService
- [ ] Интегрировать AuditService
- [ ] Добавить dry-run support

**Acceptance Criteria:**
- Parser НЕ может обновлять `source = "manual"` аниме
- Parser НЕ может обходить блокировки
- Все updates логируются в audit_logs
- Dry-run НЕ пишет в БД

### 8.3. Phase 3: Auto-Parsing

**Deliverables:**
- [ ] Background worker с проверкой `mode`
- [ ] Scheduler для catalog/episode sync
- [ ] Emergency stop endpoint
- [ ] Dashboard с real-time статусом

**Acceptance Criteria:**
- Worker НЕ запускает задачи при `mode = "manual"`
- Emergency stop работает немедленно
- Dashboard показывает статус в реальном времени

### 8.4. Phase 4: Monitoring & Alerts

**Deliverables:**
- [ ] Problem anime page
- [ ] Email alerts при критических ошибках
- [ ] Автоматическое отключение источника при недоступности
- [ ] Metrics (Prometheus/Grafana)

**Acceptance Criteria:**
- Админ получает email при > 50 ошибках/час
- Источник автоматически отключается при unavailability > 10 min
- Metrics экспортируются корректно

---

## 9. TESTING REQUIREMENTS (Design Only)

### 9.1. Unit Tests

**Must Cover:**
- [ ] `source = "manual"` блокирует parser updates
- [ ] Locked fields блокируют parser updates
- [ ] Parser НЕ может устанавливать `published` state
- [ ] Dry-run НЕ пишет в БД
- [ ] Audit log создаётся для каждого update
- [ ] Permission checks работают корректно

### 9.2. Integration Tests

**Must Cover:**
- [ ] End-to-end parser flow: fetch → staging → publish
- [ ] LockService integration
- [ ] AuditService integration
- [ ] Emergency stop
- [ ] Auto-parsing enable/disable

### 9.3. E2E Tests

**Must Cover:**
- [ ] Админ включает auto-parsing через UI
- [ ] Parser обновляет anime
- [ ] Админ видит изменения в audit logs
- [ ] Админ блокирует поля → parser НЕ обновляет
- [ ] Emergency stop через UI

---

## 10. COMPLIANCE CHECKLIST

**Перед мержем в main:**

- [ ] Все инварианты из раздела 6.1 реализованы
- [ ] Все проверки из раздела 6.2 присутствуют в коде
- [ ] Parser НЕ МОЖЕТ работать в auto mode без явного включения
- [ ] Default `parser_settings.mode = "manual"`
- [ ] Все parser updates логируются в audit_logs
- [ ] LockService интегрирован
- [ ] AuditService интегрирован
- [ ] Permission checks на всех endpoints
- [ ] Dry-run режим работает
- [ ] Emergency stop реализован
- [ ] Dashboard показывает статус
- [ ] Документация обновлена
- [ ] Unit tests проходят
- [ ] Integration tests проходят
- [ ] E2E tests проходят
- [ ] Code review пройдён
- [ ] Security audit пройдён

---

## 11. APPENDIX: DLE Parser Example (Reference)

**Что взять из DLE:**
- ✅ Admin-controlled toggle (включение/выключение через админку)
- ✅ Settings persistence (настройки в БД, не в конфигах)
- ✅ Dry-run mode
- ✅ Blacklist management
- ✅ Error logging

**Что НЕ брать:**
- ❌ Cron напрямую запускает парсинг (у нас через background worker)
- ❌ Прямое изменение каталога (у нас через staging tables)
- ❌ Отсутствие RBAC (у нас permission-based)
- ❌ Отсутствие audit trail (у нас всё логируется)

---

## CONCLUSION

**Этот контракт является точкой невозврата.**

Любое отклонение от контракта **ОБЯЗАНО**:
1. Быть задокументировано в этом файле (новый раздел)
2. Пройти review у lead/архитектора
3. Быть обоснованно критической необходимостью
4. НЕ нарушать core invariants из раздела 6.1

**При нарушении контракта:**
- Немедленный rollback изменений
- Post-mortem анализ
- Обновление контракта и тестов

**Контракт актуален на:** 2026-01-20  
**Следующий review:** При изменении требований или обнаружении архитектурных проблем

---

**ПОДПИСЬ:** Architectural Audit Complete ✅  
**READY FOR IMPLEMENTATION:** Yes ✅
