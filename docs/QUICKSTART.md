# QUICKSTART

## Требования
- Python 3.8+
- PyQt6
- bcrypt

## Установка зависимостей
```bash
pip install -r requirements.txt
```

## Где хранятся данные (Windows)
По умолчанию база и накладные хранятся в “Мои документы”:
- БД: `Documents\ArtelStorage\storage.db`
- Накладные: `Documents\ArtelStorage\pdf\*.pdf`

## Запуск основного приложения
```bash
python main_app.py
```

Приложение откроет модальное окно входа.
Пользователь по умолчанию:
- Логин: `admin`
- Пароль: `админ`

## Запуск админки
Использует ту же БД в “Мои документы”, если `--db` не указан:
```bash
python admin_app.py
```

Либо явно указать путь к базе:
```bash
python admin_app.py --db "C:\\Users\\<user>\\Documents\\ArtelStorage\\storage.db"
```

Админка требует вход пользователя с правами администратора.

## Быстрая настройка синхронизации (админка)
Откройте вкладку sync и заполните:
- `Server URL` — адрес Sync API (`https://...`).
- `Site UUID` — UUID площадки на сервере.
- `Device Token` — секрет устройства (заголовок `X-Device-Token`).
- `Client Version` — версия клиента (например, `ArtelStorage/1.1`).

Далее:
1. Нажмите `Сохранить`.
2. Включите чекбокс синхронизации.
3. Нажмите `Синхронизировать сейчас`.

## Операции и накладные
- Доступные операции: `приход`, `расход`, `списание`, `перемещение`.
- Накладные генерируются для всех операций, кроме `прихода`.

## Проверка ядра и сервисов
```bash
python final_test.py
python -m unittest discover -s tests -p "test_*.py"
```

## Миграция данных из v0.1
```bash
python migrate_db.py <старый_путь_к_db> "C:\\Users\\<user>\\Documents\\ArtelStorage\\storage.db"
```
