# UI INTEGRATION

## Основное приложение
Файлы:
- `app/main.py`
- `ui/auth_dialog.py`
- `ui/main_window.py`
- `ui/operation_dialog.py`

Поток запуска:
1. `init_database(...)`
2. `AuthManager.initialize_admin_user()`
3. Модальный `LoginDialog`
4. `MainWindow(db_path, auth_manager, user)`

Ролевое поведение:
- В статус-баре отображается текущий пользователь и роль.
- Для обычных пользователей скрыта вкладка `Настройки`.
- Доступ к разделу `Данные` защищен проверкой `is_admin`.
- Меню `Сессия -> Выход` завершает сессию и возвращает к окну входа.

## UI: операции
- Диалог создания операции: `ui/operation_dialog.py`.
- Показывает последние операции (до 15) и список позиций ТМЦ.
- Поля меняются в зависимости от типа операции (получатель, транспорт, объект).

## UI: остатки
- Вкладка `Остатки` в `ui/main_window.py`.
- Поиск по ТМЦ/категории/инв. номеру.
- Сортировка в таблице включена.
- Фильтрация по категориям.

## UI: операции/накладные
- Вкладка `Операции` в `ui/main_window.py`.
- Поиск и сортировка по таблице операций.
- Кнопка `Открыть накладную` открывает PDF, если он создан.

## Админ-приложение
Файлы:
- `admin_app.py`
- `apps/admin_app/main.py`
- `apps/admin_app/ui/admin_window.py`
- `apps/admin_app/ui/items_tab.py`
- `apps/admin_app/ui/categories_tab.py`
- `apps/admin_app/ui/users_tab.py`
- `apps/admin_app/ui/import_export_tab.py`

Поток запуска:
1. `python admin_app.py --db <path>`
2. Инициализация БД
3. Логин через `LoginDialog`
4. Проверка `user.is_admin`
5. Открытие `AdminWindow`

## Импорт/экспорт в UI
- Используются `ExportService` и `ImportService`.
- В UI есть подтверждение перед импортом (замена данных).
- Во время операции показывается модальный `QProgressDialog`.
