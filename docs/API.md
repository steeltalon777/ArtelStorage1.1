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

## CategoriesService
Файл: `core/services/categories_service.py`

- `get_all_categories()`
- `get_category_by_id(category_id)`
- `create_category(name)`
- `update_category(category_id, name)`
- `can_delete_category(category_id)`
- `delete_category(category_id)`
- `get_category_stats()`

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
