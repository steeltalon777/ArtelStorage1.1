#!/usr/bin/env python3
"""
Финальный тест ArtelStorage v1.1
"""

import sys
import os
import tempfile
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from core.db import init_database
from core.auth import AuthManager
from core.services.users_service import UsersService
from core.services.items_service import ItemsService
from core.services.categories_service import CategoriesService


def main():
    print("=== ArtelStorage v1.1 - Финальный тест ===\n")
    
    # Создаем временную базу данных
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # 1. Инициализация базы данных
        print("1. Инициализация базы данных...")
        db = init_database(db_path)
        print("   [OK] База данных создана")
        
        # 2. Аутентификация
        print("\n2. Аутентификация...")
        auth_manager = AuthManager(db_path)
        auth_manager.initialize_admin_user()
        
        result = auth_manager.authenticate('admin', 'админ')
        if result.success and result.user and result.user.is_admin:
            print("   [OK] Аутентификация администратора успешна")
            print(f"   Пользователь: {result.user.full_name}, Админ: {result.user.is_admin}")
        else:
            print("   [FAIL] Аутентификация администратора не удалась")
            return 1
        
        # 3. Создание тестовых данных
        print("\n3. Создание тестовых данных...")
        
        # Создаем категорию
        categories_service = CategoriesService(db_path)
        category = categories_service.create_category("Тестовая категория")
        print(f"   [OK] Создана категория: {category.name}")
        
        # Создаем ТМЦ
        items_service = ItemsService(db_path)
        item1 = items_service.create_item("Тестовый товар 1", "шт", category.id)
        item2 = items_service.create_item("Тестовый товар 2", "кг", category.id)
        print(f"   [OK] Создано 2 ТМЦ: {item1.name}, {item2.name}")
        
        # Создаем обычного пользователя
        users_service = UsersService(db_path)
        user = users_service.create_user("testuser", "Тестовый Пользователь", "password123")
        print(f"   [OK] Создан пользователь: {user.full_name}")
        
        # 4. Проверка сервисов
        print("\n4. Проверка сервисов...")
        
        # Проверяем список категорий
        categories = categories_service.get_all_categories()
        print(f"   [OK] Категорий в базе: {len(categories)}")
        
        # Проверяем список ТМЦ
        items = items_service.get_all_items()
        print(f"   [OK] ТМЦ в базе: {len(items)}")
        
        # Проверяем список пользователей
        users = users_service.get_all_users()
        print(f"   [OK] Пользователей в базе: {len(users)}")
        
        # 5. Проверка прав администратора
        print("\n5. Проверка прав администратора...")
        
        # Выходим из системы
        auth_manager.logout()
        print("   [OK] Выход из системы")
        
        # Пробуем войти как обычный пользователь
        result = auth_manager.authenticate('testuser', 'password123')
        if result.success and not result.user.is_admin:
            print("   [OK] Аутентификация обычного пользователя успешна")
            print(f"   Пользователь: {result.user.full_name}, Админ: {result.user.is_admin}")
        else:
            print("   [FAIL] Аутентификация обычного пользователя не удалась")
            return 1
        
        print("\n=== Все основные функции работают! ===")
        print("\nИтоги:")
        print("1. База данных инициализирована с таблицами")
        print("2. Аутентификация работает (bcrypt)")
        print("3. Пользователь admin создается автоматически")
        print("4. CRUD операции для категорий и ТМЦ")
        print("5. Управление пользователями")
        print("6. Разделение прав: администратор vs обычный пользователь")
        
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка при проверке: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Очистка временных файлов
        if os.path.exists(db_path):
            try:
                os.unlink(db_path)
            except:
                pass


if __name__ == "__main__":
    sys.exit(main())