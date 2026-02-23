"""Сервис для импорта данных"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID

from ..db import get_db
from ..schema import Snapshot, SnapshotData, User, Site, Category, Item, Operation, OperationLine


class ImportService:
    """Сервис импорта данных из формата JSON Snapshot"""
    
    def __init__(self, db_path: str = None):
        self.db = get_db(db_path)
    
    def import_from_file(self, filepath: str) -> bool:
        """Импортирует данные из файла снимка"""
        try:
            snapshot = self._load_snapshot_from_file(filepath)
            return self.import_snapshot(snapshot)
        except Exception as e:
            raise ValueError(f"Ошибка импорта: {str(e)}")
    
    def import_snapshot(self, snapshot: Snapshot) -> bool:
        """Импортирует данные из снимка"""
        # Валидация снимка
        self._validate_snapshot(snapshot)
        
        # Импорт в транзакции
        return self.db.execute_in_transaction(self._import_snapshot_transaction, snapshot)
    
    def _import_snapshot_transaction(self, conn, snapshot: Snapshot) -> bool:
        """Импортирует снимок в транзакции"""
        # Очищаем все таблицы в правильном порядке (с учетом внешних ключей)
        self._clear_all_tables(conn)
        
        # Импортируем данные
        self._import_users(conn, snapshot.data.users)
        self._import_sites(conn, snapshot.data.sites)
        self._import_categories(conn, snapshot.data.categories)
        self._import_items(conn, snapshot.data.items)
        self._import_operations(conn, snapshot.data.operations)
        
        return True
    
    def _load_snapshot_from_file(self, filepath: str) -> Snapshot:
        """Загружает снимок из файла"""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Файл не найден: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем формат
        if data.get('format') != 'artelstorage-snapshot':
            raise ValueError("Неверный формат снимка")
        
        if data.get('version') != 1:
            raise ValueError(f"Неподдерживаемая версия снимка: {data.get('version')}")
        
        # Парсим данные
        snapshot_data = data.get('data', {})
        
        # Пользователи
        users = []
        for user_data in snapshot_data.get('users', []):
            users.append(User(
                id=user_data.get('id'),
                username=user_data.get('username'),
                full_name=user_data.get('full_name'),
                password_hash=user_data.get('password_hash'),
                is_admin=user_data.get('is_admin', False),
                created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else None
            ))
        
        # Площадки
        sites = []
        for site_data in snapshot_data.get('sites', []):
            sites.append(Site(
                id=site_data.get('id'),
                name=site_data.get('name'),
                is_local=site_data.get('is_local', False),
                created_at=datetime.fromisoformat(site_data['created_at']) if site_data.get('created_at') else None
            ))
        
        # Категории
        categories = []
        for category_data in snapshot_data.get('categories', []):
            categories.append(Category(
                id=category_data.get('id'),
                name=category_data.get('name'),
                created_at=datetime.fromisoformat(category_data['created_at']) if category_data.get('created_at') else None
            ))
        
        # ТМЦ
        items = []
        for item_data in snapshot_data.get('items', []):
            items.append(Item(
                id=UUID(item_data['id']) if item_data.get('id') else None,
                name=item_data.get('name'),
                unit=item_data.get('unit'),
                category_id=item_data.get('category_id'),
                created_locally=item_data.get('created_locally', True),
                created_at=datetime.fromisoformat(item_data['created_at']) if item_data.get('created_at') else None
            ))
        
        # Операции
        operations = []
        for operation_data in snapshot_data.get('operations', []):
            operation = Operation(
                id=UUID(operation_data['id']) if operation_data.get('id') else None,
                type=operation_data.get('type'),
                created_at=datetime.fromisoformat(operation_data['created_at']) if operation_data.get('created_at') else None,
                created_by=operation_data.get('created_by'),
                source_site_id=operation_data.get('source_site_id'),
                target_site_id=operation_data.get('target_site_id'),
                recipient_name=operation_data.get('recipient_name'),
                vehicle=operation_data.get('vehicle'),
                comment=operation_data.get('comment'),
                pdf_path=operation_data.get('pdf_path')
            )
            
            # Строки операции
            for line_data in operation_data.get('lines', []):
                operation.lines.append(OperationLine(
                    id=line_data.get('id'),
                    operation_id=UUID(line_data['operation_id']) if line_data.get('operation_id') else None,
                    item_id=UUID(line_data['item_id']) if line_data.get('item_id') else UUID(int=0),
                    qty=line_data.get('qty', 0.0)
                ))
            
            operations.append(operation)
        
        return Snapshot(
            format=data['format'],
            version=data['version'],
            exported_at=datetime.fromisoformat(data['exported_at']) if data.get('exported_at') else datetime.now(),
            data=SnapshotData(
                users=users,
                sites=sites,
                categories=categories,
                items=items,
                operations=operations
            )
        )
    
    def _validate_snapshot(self, snapshot: Snapshot):
        """Валидирует снимок"""
        if snapshot.format != 'artelstorage-snapshot':
            raise ValueError("Неверный формат снимка")
        
        if snapshot.version != 1:
            raise ValueError(f"Неподдерживаемая версия снимка: {snapshot.version}")
        
        # Валидация данных
        for item in snapshot.data.items:
            if not item.id:
                raise ValueError("ТМЦ без ID")
            # Убрана проверка qty, так как у Item нет этого атрибута
            # qty проверяется только для OperationLine

        for operation in snapshot.data.operations:
            if operation.type not in ['incoming', 'issue', 'writeoff', 'move']:
                raise ValueError(f"Неверный тип операции: {operation.type}")
            
            for line in operation.lines:
                if line.qty <= 0:
                    raise ValueError(f"Строка операции имеет неположительное количество: {line.qty}")
    
    def _clear_all_tables(self, conn):
        """Очищает все таблицы в правильном порядке"""
        # Отключаем внешние ключи для очистки
        conn.execute("PRAGMA foreign_keys = OFF")
        
        # Очищаем в порядке, обратном зависимостям
        conn.execute("DELETE FROM operation_lines")
        conn.execute("DELETE FROM operations")
        conn.execute("DELETE FROM items")
        conn.execute("DELETE FROM categories")
        conn.execute("DELETE FROM sites")
        conn.execute("DELETE FROM users")
        
        # Включаем внешние ключи обратно
        conn.execute("PRAGMA foreign_keys = ON")
    
    def _import_users(self, conn, users: list[User]):
        """Импортирует пользователей"""
        for user in users:
            conn.execute(
                """
                INSERT INTO users (id, username, full_name, password_hash, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user.id, user.username, user.full_name, user.password_hash, 
                 1 if user.is_admin else 0, user.created_at)
            )
    
    def _import_sites(self, conn, sites: list[Site]):
        """Импортирует площадки"""
        for site in sites:
            conn.execute(
                """
                INSERT INTO sites (id, name, is_local, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (site.id, site.name, 1 if site.is_local else 0, site.created_at)
            )
    
    def _import_categories(self, conn, categories: list[Category]):
        """Импортирует категории"""
        for category in categories:
            conn.execute(
                """
                INSERT INTO categories (id, name, created_at)
                VALUES (?, ?, ?)
                """,
                (category.id, category.name, category.created_at)
            )
    
    def _import_items(self, conn, items: list[Item]):
        """Импортирует ТМЦ"""
        for item in items:
            conn.execute(
                """
                INSERT INTO items (id, name, unit, category_id, created_locally, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item.id, item.name, item.unit, item.category_id, 
                 1 if item.created_locally else 0, item.created_at)
            )
    
    def _import_operations(self, conn, operations: list[Operation]):
        """Импортирует операции"""
        for operation in operations:
            conn.execute(
                """
                INSERT INTO operations 
                (id, type, created_at, created_by, source_site_id, target_site_id, 
                 recipient_name, vehicle, comment, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (operation.id, operation.type, operation.created_at, operation.created_by,
                 operation.source_site_id, operation.target_site_id,
                 operation.recipient_name, operation.vehicle, operation.comment, operation.pdf_path)
            )
            
            # Импортируем строки операции
            for line in operation.lines:
                conn.execute(
                    """
                    INSERT INTO operation_lines (operation_id, item_id, qty)
                    VALUES (?, ?, ?)
                    """,
                    (operation.id, line.item_id, line.qty)
                )