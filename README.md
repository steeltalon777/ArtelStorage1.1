# ArtelStorage v1.1

Локальная система учета ТМЦ на `PyQt6 + SQLite` с аутентификацией, операциями склада и генерацией PDF накладных.

## Основные возможности
- Аутентификация пользователей (bcrypt), роли `admin`/`user`.
- Операции: `incoming`, `issue`, `writeoff`, `move`.
- PDF-накладные для всех операций, кроме `incoming`.
- Экспорт/импорт данных (Snapshot v1).
- Offline-first синхронизация с Sync API (`/ping`, `/push`, `/pull`, `/catalog/*`).
- Отдельные приложения: основное и административное.

## Запуск
```bash
python main_app.py
python admin_app.py
```

По умолчанию данные хранятся в `Documents\\ArtelStorage`:
- БД: `storage.db`
- PDF: `pdf\\*.pdf`

## Структура
- `core/` — БД, схема, auth, сервисы.
- `ui/` — UI основного приложения.
- `apps/admin_app/ui/` — UI админки.
- `docs/` — документация.
- `installer/` — Inno Setup скрипт.
- `scripts/` — сборочные скрипты.

## Проверка
```bash
python final_test.py
python -m unittest discover -s tests -p "test_*.py"
```

## Документация
- `docs/QUICKSTART.md`
- `docs/API.md`
- `docs/UI_INTEGRATION.md`
- `docs/INSTALLER.md`
- `docs/DEVELOPER_GUIDE.md`
