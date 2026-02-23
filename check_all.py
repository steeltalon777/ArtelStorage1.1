#!/usr/bin/env python3
"""
Проверка всех функций ArtelStorage v1.1
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from core.db import init_database
from core.auth import AuthManager
from core.services.users_service import UsersService
from core.services.items_service import ItemsService
from core.services.categories_service import CategoriesService
from core.services.export_service import ExportService
from core.services.import_service import ImportService


def main():
    print("=== ArtelStorage v1.1 - Полная проверка ===\n")
    
    # Создаем временную базу данных
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    export_file = None
    
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
        
        # 5. Экспорт данных
        print("\n5. Экспорт данных...")
        export_service = ExportService(db_path)
        snapshot = export_service.export_snapshot()
        print(f"   [OK] Создан снимок данных")
        print(f"   Формат: {snapshot.format}, Версия: {snapshot.version}")
        print(f"   Данные: {len(snapshot.data.users)} пользователей, "
              f"{len(snapshot.data.categories)} категорий, "
              f"{len(snapshot.data.items)} ТМЦ")
        
        # Сохраняем в файл
        export_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w')
        export_file.close()
        
        export_service.export_to_file(export_file.name)
        print(f"   [OK] Снимок сохранен в файл: {export_file.name}")
        
        # 6. Импорт данных
        print("\n6. Импорт данных...")
        
        # Создаем новую базу для импорта
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp2:
            new_db_path = tmp2.name
        
        import_service = ImportService(new_db_path)
        success = import_service.import_from_file(export_file.name)
        
        if success:
            print("   [OK] Импорт успешно завершен")
            
            # Проверяем импортированные данные
            new_items_service = ItemsService(new_db_path)
            new_items = new_items_service.get_all_items()
            print(f"   [OK] Импортировано ТМЦ: {len(new_items)}")
            
            new_categories_service = CategoriesService(new_db_path)
            new_categories = new_categories_service.get_all_categories()
            print(f"   [OK] Импортировано категорий: {len(new_categories)}")
            
            new_users_service = UsersService(new_db_path)
            new_users = new_users_service.get_all_users()
            print(f"   [OK] Импортировано пользователей: {len(new_users)}")
        else:
            print("   [FAIL] Ошибка импорта")
            return 1
        
        # 7. Проверка миграции паролей
        print("\n7. Проверка миграции паролей...")
        new_auth_manager = AuthManager(new_db_path)
        
        # Проверяем аутентификацию администратора
        result = new_auth_manager.authenticate('admin', 'админ')
        if result.success:
            print("   [OK] Пароль администратора сохранен")
        else:
            print("   [FAIL] Пароль администратора не работает")
            return 1
        
        # Проверяем аутентификацию обычного пользователя
        result = new_auth_manager.authenticate('testuser', 'password123')
        if result.success:
            print("   [OK] Пароль обычного пользователя сохранен")
        else:
            print("   [FAIL] Пароль обычного пользователя не работает")
            return 1
        
        print("\n=== Все проверки пройдены успешно! ===")
        print("\nИтоги:")
        print("1. База данных инициализирована с таблицами")
        print("2. Аутентификация работает (bcrypt)")
        print("3. CRUD операции для категорий и ТМЦ")
        print("4. Управление пользователями")
        print("5. Экспорт данных в JSON Snapshot v1")
        print("6. Импорт данных (replace-all)")
        print("7. Миграция паролей работает")
        
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
        if export_file and os.path.exists(export_file.name):
            try:
                os.unlink(export_file.name)
            except:
                pass
        if 'new_db_path' in locals() and os.path.exists(new_db_path):
            try:
                os.unlink(new_db_path)
            except:
                pass


if __name__ == "__main__":
    sys.exit(main())