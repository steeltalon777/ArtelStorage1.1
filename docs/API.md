# API

## Общие правила
- SQL допускается только в `core/*`.
- UI использует только сервисы из `core/services/*`.

## Auth
Файл: `core/auth.py`

Основные методы `AuthManager`:
- `authenticate(username, password) -> AuthResult`
- `initialize_admin_user()`
- `create_user(username, full_name, password, is_admin=False)`
- `update_user_password(user_id, new_password)`
- `update_user_admin_status(user_id, is_admin)`
- `logout()`
- `is_admin()`

## UsersService
Файл: `core/services/users_service.py`

- `get_all_users()`
- `get_user_by_id(user_id)`
- `create_user(username, full_name, password, is_admin=False)`
- `update_user(user_id, full_name=None, is_admin=None)`
- `change_password(user_id, new_password)`
- `toggle_admin_status(user_id)`
- `can_delete_user(user_id)`
- `delete_user(user_id)`

## ItemsService
Файл: `core/services/items_service.py`

- `get_all_items()`
- `get_item_by_id(item_id)`
- `create_item(name, unit, category_id=None)`
- `update_item(item_id, name=None, unit=None, category_id=None)`
- `can_delete_item(item_id)`
- `delete_item(item_id)`
- `search_items(query)`
- `upsert_server_items(items, conn=None)`

## CategoriesService
Файл: `core/services/categories_service.py`

- `get_all_categories()`
- `get_category_by_id(category_id)`
- `create_category(name)`
- `update_category(category_id, name)`
- `can_delete_category(category_id)`
- `delete_category(category_id)`
- `get_category_stats()`
- `upsert_server_categories(categories, conn=None)`

## OperationsService
Файл: `core/services/operations_service.py`

Основные методы:
- `create_operation(operation_type, created_by, lines, recipient_name=None, vehicle=None, target_site_name=None, comment=None)`
- `list_recent_operations(limit=15)`
- `list_operations(limit=300, search=None)`
- `get_operation_by_id(operation_id)`
- `get_operation_lines(operation_id)`

Правила:
- `incoming`: приход на локальный склад.
- `issue`: обязателен `recipient_name` и `vehicle`.
- `writeoff`: списание с локального склада.
- `move`: обязательны `target_site_name` и `vehicle`, источник всегда локальный склад.
- Для `issue/writeoff/move` проверяется остаток.
- Для операций кроме `incoming` генерируется накладная (PDF).

## StockService
Файл: `core/services/stock_service.py`

- `get_local_site_id()`
- `get_stock_rows(site_id=None, search=None, category_id=None)`

## PdfService
Файл: `core/services/pdf_service.py`

- `generate_invoice(operation_type, operation_id, created_at, lines, recipient_name=None, vehicle=None)`

## ExportService
Файл: `core/services/export_service.py`

- `export_snapshot()`
- `export_to_file(filepath)`

## ImportService
Файл: `core/services/import_service.py`

- `import_from_file(filepath)`
- `import_snapshot(snapshot)`

Импорт заменяет текущие данные в БД в рамках транзакции.

## SyncClient
Файл: `core/services/sync_client.py`

- `ping(payload)`
- `push_events(payload)`
- `pull_events(payload)`
- `get_catalog_items(payload)`
- `get_catalog_categories(payload)`

Особенности:
- Обязательные заголовки: `X-Device-Token` (и `X-Site-Id`/`X-Device-Id` для `/catalog/*`).
- Опциональный заголовок: `X-Client-Version`.
- Для ответа добавляется `_meta`: `endpoint`, `status_code`, `latency_ms`, `request_id`.
- Ошибки HTTP/сети пробрасываются как `SyncHttpError`.

## SyncOrchestrator
Файл: `core/services/sync_orchestrator.py`

Основной метод:
- `sync_once()`

Порядок цикла:
1. `/ping` (heartbeat, `server_seq_upto`, `backoff_seconds`)
2. `/push` (батчами outbox)
3. `/pull` (страницами до догонки курсора)
4. `/catalog/categories` (инкрементально)
5. `/catalog/items` (инкрементально)

Гарантии:
- Retry + exponential backoff + jitter для сетевых/`5xx`/`429`.
- Ограничение частоты: `/ping` не чаще 1 раза в 5 сек, `/push` не чаще 1 раза в 1 сек.
- Курсор `since_seq` хранится отдельно на `site_uuid`.
- Курсоры `updated_after` отдельно для `items` и `categories`.
- HTTP-телеметрия сохраняется в `sync_logs`.

## SyncOutboxService
Файл: `core/services/sync_outbox_service.py`

- `enqueue_operation_event(...)`
- `get_pending(limit=200)`
- `mark_sending(ids)`
- `apply_push_result(response)`
- `mark_batch_failed(ids, reason)`
- `list_queue(limit=500)`
- `pending_count()`

Правила:
- Для каждого исходящего события генерируется `event_uuid` (UUIDv4).
- `qty` в payload сериализуется как decimal-строка с 3 знаками.
- `accepted`/`duplicates` удаляются из outbox.
- `uuid_collision` помечается как конфликт (`status='rejected'`, `is_conflict=1`).
