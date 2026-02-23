"""Сервис для работы с ТМЦ"""

import sqlite3
from typing import List, Optional
from uuid import UUID, uuid4

from ..db import get_db
from ..schema import Item


class ItemsService:
    """Сервис управления товарно-материальными ценностями"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
    
    def get_all_items(self) -> List[Item]:
        """Возвращает все ТМЦ"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    i.id, i.name, i.unit, i.category_id, i.created_locally, i.created_at,
                    c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                ORDER BY i.name
                """
            )
            
            items = []
            for row in cursor:
                items.append(Item(
                    id=row['id'],
                    name=row['name'],
                    unit=row['unit'],
                    category_id=row['category_id'],
                    category_name=row['category_name'],
                    created_locally=bool(row['created_locally']),
                    created_at=row['created_at']
                ))
            
            return items
    
    def get_item_by_id(self, item_id: UUID) -> Optional[Item]:
        """Возвращает ТМЦ по ID"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    i.id, i.name, i.unit, i.category_id, i.created_locally, i.created_at,
                    c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.id = ?
                """,
                (item_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return Item(
                    id=row['id'],
                    name=row['name'],
                    unit=row['unit'],
                    category_id=row['category_id'],
                    category_name=row['category_name'],
                    created_locally=bool(row['created_locally']),
                    created_at=row['created_at']
                )
            return None
    
    def create_item(self, name: str, unit: str, category_id: Optional[int] = None) -> Item:
        """Создает новую ТМЦ"""
        item_id = uuid4()
        
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO items (id, name, unit, category_id)
                VALUES (?, ?, ?, ?)
                """,
                (item_id, name, unit, category_id)
            )
            conn.commit()
            
            return self.get_item_by_id(item_id)
    
    def update_item(self, item_id: UUID, name: Optional[str] = None, 
                   unit: Optional[str] = None, category_id: Optional[int] = None) -> bool:
        """Обновляет данные ТМЦ"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if unit is not None:
            updates.append("unit = ?")
            params.append(unit)
        
        if category_id is not None:
            updates.append("category_id = ?")
            params.append(category_id)
        
        if not updates:
            return False
        
        params.append(item_id)
        
        with self.db.get_connection() as conn:
            query = f"UPDATE items SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def can_delete_item(self, item_id: UUID) -> bool:
        """Проверяет, можно ли удалить ТМЦ"""
        with self.db.get_connection() as conn:
            # Проверяем, участвует ли ТМЦ в операциях
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM operation_lines WHERE item_id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            return row['count'] == 0
    
    def delete_item(self, item_id: UUID) -> bool:
        """Удаляет ТМЦ"""
        if not self.can_delete_item(item_id):
            return False
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def search_items(self, query: str) -> List[Item]:
        """Ищет ТМЦ по названию"""
        search_term = f"%{query}%"
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    i.id, i.name, i.unit, i.category_id, i.created_locally, i.created_at,
                    c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.name LIKE ?
                ORDER BY i.name
                """,
                (search_term,)
            )
            
            items = []
            for row in cursor:
                items.append(Item(
                    id=row['id'],
                    name=row['name'],
                    unit=row['unit'],
                    category_id=row['category_id'],
                    category_name=row['category_name'],
                    created_locally=bool(row['created_locally']),
                    created_at=row['created_at']
                ))
            
            return items
    
    def get_items_by_category(self, category_id: int) -> List[Item]:
        """Возвращает ТМЦ по категории"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    i.id, i.name, i.unit, i.category_id, i.created_locally, i.created_at,
                    c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE i.category_id = ?
                ORDER BY i.name
                """,
                (category_id,)
            )
            
            items = []
            for row in cursor:
                items.append(Item(
                    id=row['id'],
                    name=row['name'],
                    unit=row['unit'],
                    category_id=row['category_id'],
                    category_name=row['category_name'],
                    created_locally=bool(row['created_locally']),
                    created_at=row['created_at']
                ))
            
            return items