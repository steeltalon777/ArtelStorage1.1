#!/usr/bin/env python3
"""
Миграция существующей базы данных в новую схему с аутентификацией
"""

import sys
import os
import sqlite3
from pathlib import Path
import bcrypt

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from core.db import Database


def hash_password(password: str) -> str:
    """Хеширует пароль с использованием bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def migrate_database(old_db_path: str, new_db_path: str = None):
    """Мигрирует данные из старой базы в новую"""
    if new_db_path is None:
        new_db_path = old_db_path  # Перезаписываем существующую базу
    
    print(f"Миграция базы данных из {old_db_path} в {new_db_path}")
    
    # Подключаемся к старой базе
    old_conn = sqlite3.connect(old_db_path)
    old_conn.row_factory = sqlite3.Row
    
    # Создаем новую базу
    new_db = Database(new_db_path)
    new_db.init_schema()
    
    with new_db.get_connection() as new_conn:
        # Мигрируем пользователей
        print("Миграция пользователей...")
        old_cursor = old_conn.execute("SELECT * FROM users")
        for row in old_cursor:
            # Для существующих пользователей устанавливаем пароль 'пароль123' по умолчанию
            password_hash = hash_password('пароль123')
            new_conn.execute(
                """
                INSERT OR REPLACE INTO users (id, username, full_name, password_hash, is_admin)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row['id'], row['username'], row['full_name'], password_hash, 0)
            )
        
        # Обновляем администратора
        new_conn.execute(
            "UPDATE users SET password_hash = ?, is_admin = 1 WHERE username = 'admin'",
            (hash_password('админ'),)
        )
        
        # Мигрируем площадки
        print("Миграция площадок...")
        old_cursor = old_conn.execute("SELECT * FROM sites")
        for row in old_cursor:
            new_conn.execute(
                "INSERT OR REPLACE INTO sites (id, name, is_local) VALUES (?, ?, ?)",
                (row['id'], row['name'], row['is_local'])
            )
        
        # Мигрируем категории
        print("Миграция категорий...")
        old_cursor = old_conn.execute("SELECT * FROM categories")
        for row in old_cursor:
            new_conn.execute(
                "INSERT OR REPLACE INTO categories (id, name) VALUES (?, ?)",
                (row['id'], row['name'])
            )
        
        # Мигрируем ТМЦ
        print("Миграция ТМЦ...")
        old_cursor = old_conn.execute("SELECT * FROM items")
        for row in old_cursor:
            new_conn.execute(
                """
                INSERT OR REPLACE INTO items 
                (id, name, unit, category_id, created_locally) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (row['id'], row['name'], row['unit'], row['category_id'], row['created_locally'])
            )
        
        # Мигрируем операции
        print("Миграция операций...")
        old_cursor = old_conn.execute("SELECT * FROM operations")
        for row in old_cursor:
            new_conn.execute(
                """
                INSERT OR REPLACE INTO operations 
                (id, type, created_at, created_by, source_site_id, target_site_id, 
                 recipient_name, vehicle, comment, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (row['id'], row['type'], row['created_at'], row['created_by'],
                 row['source_site_id'], row['target_site_id'],
                 row['recipient_name'], row['vehicle'], row['comment'], row['pdf_path'])
            )
        
        # Мигрируем строки операций
        print("Миграция строк операций...")
        old_cursor = old_conn.execute("SELECT * FROM operation_lines")
        for row in old_cursor:
            new_conn.execute(
                "INSERT OR REPLACE INTO operation_lines (id, operation_id, item_id, qty) VALUES (?, ?, ?, ?)",
                (row['id'], row['operation_id'], row['item_id'], row['qty'])
            )
        
        new_conn.commit()
        print("Миграция завершена успешно!")
        print("\nДанные для входа:")
        print("  Администратор: username='admin', password='админ'")
        print("  Обычные пользователи: password='пароль123' (рекомендуется сменить)")
    
    old_conn.close()


def main():
    if len(sys.argv) < 2:
        print("Использование: python migrate_db.py <путь_к_базе_данных> [новый_путь]")
        print("Пример: python migrate_db.py db/storage.db")
        return 1
    
    old_db_path = sys.argv[1]
    new_db_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(old_db_path).exists():
        print(f"Ошибка: файл {old_db_path} не существует")
        return 1
    
    try:
        migrate_database(old_db_path, new_db_path)
        return 0
    except Exception as e:
        print(f"Ошибка миграции: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())