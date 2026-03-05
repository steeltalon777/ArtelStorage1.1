# DEVELOPER GUIDE

## 1. Назначение
Этот документ для разработчика, который поддерживает и развивает `ArtelStorage v1.1`.

Цели проекта:
- Учет ТМЦ через неизменяемые операции.
- Разделение пользовательского и административного интерфейса.
- Минимальный и прозрачный сервисный слой поверх SQLite.

## 2. Архитектура
### 2.1 Слои
- `core/db.py` — подключение к SQLite, schema init, транзакции.
- `core/schema.py` — dataclass-модели.
- `core/auth.py` — аутентификация/авторизация.
- `core/services/*.py` — бизнес-логика и SQL.
- `ui/*.py` — UI основного приложения (без SQL).
- `apps/admin_app/ui/*.py` — UI админки (без SQL).

Правило: SQL только в `core/*`.

### 2.2 Точки входа
- `main_app.py` -> `app/main.py` (основное приложение).
- `admin_app.py` -> `apps/admin_app/main.py` (админка).

### 2.3 Хранение данных
Путь по умолчанию (Windows): `Documents\\ArtelStorage`.
- БД: `storage.db`
- Накладные: `pdf\\...`

Резолвер путей: `core/paths.py`.

### 2.4 Версия схемы БД
- Текущая целевая версия: `3`.
- v2 добавила базовые sync-таблицы (`sync_settings`, `sync_state`, `sync_outbox`).
- v3 добавила расширения sync:
  - `device_token`, `client_version` в `sync_settings`;
  - `is_conflict` в `sync_outbox`;
  - `sync_site_state` (per-site курсоры);
  - `sync_inbox_events` (входящие события pull);
  - `sync_logs` (telemetry по sync-запросам).

## 3. Ключевые сервисы
- `UsersService` — CRUD пользователей, смена пароля, права admin.
- `ItemsService` — CRUD ТМЦ.
- `CategoriesService` — CRUD категорий + проверки удаления.
- `OperationsService` — проведение операций, валидации, генерация накладных.
- `StockService` — расчет остатков для таблиц UI.
- `ExportService` / `ImportService` — snapshot экспорт/импорт.
- `PdfService` — генерация PDF накладной по шаблону.
- `SyncSettingsService` — настройки sync (URL, `site_uuid`, `device_uuid`, `device_token`, `client_version`).
- `SyncOutboxService` — outbox и обработка ACK/reject для `/push`.
- `SyncClient` — HTTP клиент Sync API + метаданные запроса.
- `SyncOrchestrator` — полный sync-цикл (`ping -> push -> pull -> catalog`).

## 4. Инварианты, которые нельзя ломать
- Операция `move`: источник всегда локальный склад.
- Для `issue` обязательны получатель и транспорт.
- Для `move` обязательны объект назначения и транспорт.
- Для `issue/writeoff/move` проверяется достаточность остатка.
- Накладные генерируются для всех операций, кроме `incoming`.
- UI не должен выполнять SQL напрямую.
- Для sync каждое исходящее событие обязано иметь уникальный `event_uuid` (UUIDv4).
- Курсоры sync должны обновляться только после успешного применения страницы.
- `uuid_collision` не должен бесконечно ретраиться.

## 4.1 Sync API инварианты
- Для `/ping`, `/push`, `/pull` обязателен заголовок `X-Device-Token`.
- Для `/catalog/*` обязательны `X-Site-Id`, `X-Device-Id`, `X-Device-Token`.
- `event_datetime` отправляется в ISO-8601 UTC (`...Z`).
- `/push` отправляется батчами, не чаще 1 раза в секунду на устройство.
- `/ping` вызывается не чаще 1 раза в 5 секунд.
- Retry для сетевых ошибок/`5xx`/`429` с exponential backoff + jitter.

## 5. Как вносить изменения безопасно
### 5.1 Если меняете UI
- Работайте через сервисы (`core/services`), не через `sqlite3`.
- Проверяйте роли (`is_admin`) перед admin-действиями.

### 5.2 Если меняете сервисы
- Сохраняйте сигнатуры публичных методов, если это возможно.
- Для breaking changes обновляйте `docs/API.md` и UI-вызовы.

### 5.3 Если меняете PDF
- Правки только в `core/services/pdf_service.py`.
- Не добавляйте технические ID в печатную форму.
- Проверяйте перенос длинных наименований и пагинацию.

## 6. Локальная разработка
```bash
pip install -r requirements.txt
python main_app.py
python admin_app.py
```

Проверка:
```bash
python final_test.py
python -m unittest discover -s tests -p "test_*.py"
```

## 6.1 Sync тесты
Файл: `tests/test_sync_requirements.py`

Покрытые сценарии:
- генерация нового `event_uuid` и формат `qty` в outbox;
- обработка `accepted`/`duplicates`/`uuid_collision`;
- обязательные sync-заголовки в HTTP-клиенте;
- обновление `since_seq` после pull-страниц.

## 7. Сборка и инсталлятор
Сборка exe:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\\build_exe.ps1 -Clean
```

Инсталлятор:
- открыть `installer\\ArtelStorage.iss` в Inno Setup
- выполнить Compile

## 8. Частые проблемы
- `PyQt6` не установлен -> не стартует UI/PDF генерация.
- Путь к БД неверный -> пустая БД создается в другом месте.
- Права пользователя -> недоступны разделы `Настройки`/админка.

## 9. Минимальный checklist перед release
- `python final_test.py` проходит.
- `python -m unittest discover -s tests -p "test_*.py"` проходит.
- Запускаются оба приложения (`main_app.py`, `admin_app.py`).
- Операции создаются, PDF открывается.
- Импорт/экспорт работают из UI.
- Sync в админке настроен (`Server URL`, `Site UUID`, `Device Token`, `Client Version`).
- Документация в `docs/` актуальна.
