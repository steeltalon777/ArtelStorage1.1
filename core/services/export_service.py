"""Сервис для экспорта данных"""

import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from ..db import get_db
from ..schema import Snapshot, SnapshotData, User, Site, Category, Item, Operation, OperationLine


class ExportService:
    """Сервис экспорта данных в формат JSON Snapshot"""
    
    def __init__(self, db_path: str = None):
        self.db = get_db(db_path)
    
    def export_snapshot(self) -> Snapshot:
        """Экспортирует все данные в формате снимка"""
        snapshot_data = self._collect_all_data()
        
        return Snapshot(
            format="artelstorage-snapshot",
            version=1,
            exported_at=datetime.now(),
            data=snapshot_data
        )
    
    def export_to_file(self, filepath: str) -> None:
        """Экспортирует снимок в файл"""
        snapshot = self.export_snapshot()
        self._save_snapshot_to_file(snapshot, filepath)
    
    def _collect_all_data(self) -> SnapshotData:
        """Собирает все данные из базы"""
        with self.db.get_connection() as conn:
            # Пользователи
            users_cursor = conn.execute(
                "SELECT id, username, full_name, password_hash, is_admin, created_at FROM users"
            )
            users = []
            for row in users_cursor:
                users.append(User(
                    id=row['id'],
                    username=row['username'],
                    full_name=row['full_name'],
                    password_hash=row['password_hash'],
                    is_admin=bool(row['is_admin']),
                    created_at=row['created_at']
                ))
            
            # Площадки
            sites_cursor = conn.execute(
                "SELECT id, name, is_local, created_at FROM sites"
            )
            sites = []
            for row in sites_cursor:
                sites.append(Site(
                    id=row['id'],
                    name=row['name'],
                    is_local=bool(row['is_local']),
                    created_at=row['created_at']
                ))
            
            # Категории
            categories_cursor = conn.execute(
                "SELECT id, name, created_at FROM categories"
            )
            categories = []
            for row in categories_cursor:
                categories.append(Category(
                    id=row['id'],
                    name=row['name'],
                    created_at=row['created_at']
                ))
            
            # ТМЦ
            items_cursor = conn.execute(
                """
                SELECT id, name, unit, category_id, created_locally, created_at
                FROM items
                """
            )
            items = []
            for row in items_cursor:
                items.append(Item(
                    id=row['id'],
                    name=row['name'],
                    unit=row['unit'],
                    category_id=row['category_id'],
                    created_locally=bool(row['created_locally']),
                    created_at=row['created_at']
                ))
            
            # Операции с строками
            operations_cursor = conn.execute(
                """
                SELECT 
                    o.id, o.type, o.created_at, o.created_by, 
                    o.source_site_id, o.target_site_id, o.recipient_name,
                    o.vehicle, o.comment, o.pdf_path,
                    u.username as created_by_username,
                    s1.name as source_site_name,
                    s2.name as target_site_name
                FROM operations o
                LEFT JOIN users u ON o.created_by = u.id
                LEFT JOIN sites s1 ON o.source_site_id = s1.id
                LEFT JOIN sites s2 ON o.target_site_id = s2.id
                ORDER BY o.created_at
                """
            )
            
            operations = []
            for row in operations_cursor:
                operation = Operation(
                    id=row['id'],
                    type=row['type'],
                    created_at=row['created_at'],
                    created_by=row['created_by'],
                    created_by_username=row['created_by_username'],
                    source_site_id=row['source_site_id'],
                    source_site_name=row['source_site_name'],
                    target_site_id=row['target_site_id'],
                    target_site_name=row['target_site_name'],
                    recipient_name=row['recipient_name'],
                    vehicle=row['vehicle'],
                    comment=row['comment'],
                    pdf_path=row['pdf_path']
                )
                
                # Получаем строки операции
                lines_cursor = conn.execute(
                    """
                    SELECT 
                        ol.id, ol.operation_id, ol.item_id, ol.qty,
                        i.name as item_name
                    FROM operation_lines ol
                    LEFT JOIN items i ON ol.item_id = i.id
                    WHERE ol.operation_id = ?
                    """,
                    (row['id'],)
                )
                
                for line_row in lines_cursor:
                    operation.lines.append(OperationLine(
                        id=line_row['id'],
                        operation_id=line_row['operation_id'],
                        item_id=line_row['item_id'],
                        item_name=line_row['item_name'],
                        qty=line_row['qty']
                    ))
                
                operations.append(operation)
            
            return SnapshotData(
                users=users,
                sites=sites,
                categories=categories,
                items=items,
                operations=operations
            )
    
    def _save_snapshot_to_file(self, snapshot: Snapshot, filepath: str) -> None:
        """Сохраняет снимок в файл"""
        # Преобразуем снимок в словарь
        snapshot_dict = {
            "format": snapshot.format,
            "version": snapshot.version,
            "exported_at": snapshot.exported_at.isoformat(),
            "data": {
                "users": self._serialize_users(snapshot.data.users),
                "sites": self._serialize_sites(snapshot.data.sites),
                "categories": self._serialize_categories(snapshot.data.categories),
                "items": self._serialize_items(snapshot.data.items),
                "operations": self._serialize_operations(snapshot.data.operations)
            }
        }
        
        # Сохраняем в файл
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot_dict, f, ensure_ascii=False, indent=2, default=str)
    
    def _serialize_users(self, users: list[User]) -> list[dict]:
        """Сериализует пользователей"""
        return [
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "password_hash": user.password_hash,
                "is_admin": user.is_admin,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
    
    def _serialize_sites(self, sites: list[Site]) -> list[dict]:
        """Сериализует площадки"""
        return [
            {
                "id": site.id,
                "name": site.name,
                "is_local": site.is_local,
                "created_at": site.created_at.isoformat() if site.created_at else None
            }
            for site in sites
        ]
    
    def _serialize_categories(self, categories: list[Category]) -> list[dict]:
        """Сериализует категории"""
        return [
            {
                "id": category.id,
                "name": category.name,
                "created_at": category.created_at.isoformat() if category.created_at else None
            }
            for category in categories
        ]
    
    def _serialize_items(self, items: list[Item]) -> list[dict]:
        """Сериализует ТМЦ"""
        return [
            {
                "id": str(item.id),
                "name": item.name,
                "unit": item.unit,
                "category_id": item.category_id,
                "created_locally": item.created_locally,
                "created_at": item.created_at.isoformat() if item.created_at else None
            }
            for item in items
        ]
    
    def _serialize_operations(self, operations: list[Operation]) -> list[dict]:
        """Сериализует операции"""
        result = []
        for operation in operations:
            op_dict = {
                "id": str(operation.id),
                "type": operation.type,
                "created_at": operation.created_at.isoformat(),
                "created_by": operation.created_by,
                "source_site_id": operation.source_site_id,
                "target_site_id": operation.target_site_id,
                "recipient_name": operation.recipient_name,
                "vehicle": operation.vehicle,
                "comment": operation.comment,
                "pdf_path": operation.pdf_path,
                "lines": [
                    {
                        "id": line.id,
                        "operation_id": str(line.operation_id) if line.operation_id else None,
                        "item_id": str(line.item_id),
                        "qty": line.qty
                    }
                    for line in operation.lines
                ]
            }
            result.append(op_dict)
        return result