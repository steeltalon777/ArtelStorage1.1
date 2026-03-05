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
                    i.id, i.name, i.unit, i.category_id, i.created_locally, i.created_at, i.server_uuid,
                    c.name as category_name
                FROM items i
                LEFT JOIN categories c ON i.category_id = c.id
                WHERE COALESCE(i.is_active,1)=1
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
        if self._sync_enabled():
            raise ValueError("При включенной синхронизации создание локальных ТМЦ запрещено")
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
        if self._is_server_item(item_id):
            raise ValueError("Серверная ТМЦ доступна только для чтения")
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

    def upsert_server_items(self, items: List[dict], conn=None):
        owns_connection = conn is None
        if conn is None:
            conn = self.db.get_connection()
        try:
            for item in items:
                server_uuid = item.get("server_uuid") or item.get("id")
                category_server_uuid = item.get("category_server_uuid") or item.get("category_id")
                category_id = None
                if category_server_uuid:
                    category_row = conn.execute(
                        "SELECT id FROM categories WHERE server_uuid=?",
                        (category_server_uuid,),
                    ).fetchone()
                    if category_row:
                        category_id = category_row["id"]

                row = conn.execute("SELECT id FROM items WHERE server_uuid=?", (server_uuid,)).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE items
                        SET name=?, unit=?, category_id=?, sku=?, updated_at=?, is_active=?, created_locally=0
                        WHERE id=?
                        """,
                        (
                            item.get("name"),
                            item.get("unit") or "шт",
                            category_id,
                            item.get("sku"),
                            item.get("updated_at"),
                            1 if item.get("is_active", True) else 0,
                            row["id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO items (id, name, unit, category_id, created_locally, server_uuid, sku, updated_at, is_active)
                        VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                        """,
                        (
                            uuid4(),
                            item.get("name"),
                            item.get("unit") or "шт",
                            category_id,
                            server_uuid,
                            item.get("sku"),
                            item.get("updated_at"),
                            1 if item.get("is_active", True) else 0,
                        ),
                    )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    def _sync_enabled(self) -> bool:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT enabled FROM sync_settings WHERE id = 1").fetchone()
            return bool(row and row["enabled"])

    def _is_server_item(self, item_id: UUID) -> bool:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT server_uuid FROM items WHERE id=?", (item_id,)).fetchone()
            return bool(row and row["server_uuid"])
