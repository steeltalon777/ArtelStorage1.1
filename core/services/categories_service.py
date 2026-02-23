"""Сервис для работы с категориями"""

import sqlite3
from typing import List, Optional

from ..db import get_db
from ..schema import Category


class CategoriesService:
    """Сервис управления категориями ТМЦ"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
    
    def get_all_categories(self) -> List[Category]:
        """Возвращает все категории"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM categories ORDER BY name"
            )
            
            categories = []
            for row in cursor:
                categories.append(Category(
                    id=row['id'],
                    name=row['name'],
                    created_at=row['created_at']
                ))
            
            return categories
    
    def get_category_by_id(self, category_id: int) -> Optional[Category]:
        """Возвращает категорию по ID"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM categories WHERE id = ?",
                (category_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return Category(
                    id=row['id'],
                    name=row['name'],
                    created_at=row['created_at']
                )
            return None
    
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """Возвращает категорию по имени"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM categories WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            
            if row:
                return Category(
                    id=row['id'],
                    name=row['name'],
                    created_at=row['created_at']
                )
            return None
    
    def create_category(self, name: str) -> Category:
        """Создает новую категорию"""
        with self.db.get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO categories (name) VALUES (?)",
                    (name,)
                )
                conn.commit()
                
                return Category(
                    id=cursor.lastrowid,
                    name=name
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"Категория с именем '{name}' уже существует")
    
    def update_category(self, category_id: int, name: str) -> bool:
        """Обновляет название категории"""
        with self.db.get_connection() as conn:
            try:
                cursor = conn.execute(
                    "UPDATE categories SET name = ? WHERE id = ?",
                    (name, category_id)
                )
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.IntegrityError:
                raise ValueError(f"Категория с именем '{name}' уже существует")
    
    def can_delete_category(self, category_id: int) -> bool:
        """Проверяет, можно ли удалить категорию"""
        with self.db.get_connection() as conn:
            # Проверяем, используется ли категория в ТМЦ
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM items WHERE category_id = ?",
                (category_id,)
            )
            row = cursor.fetchone()
            return row['count'] == 0
    
    def delete_category(self, category_id: int) -> bool:
        """Удаляет категорию"""
        if not self.can_delete_category(category_id):
            return False
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def search_categories(self, query: str) -> List[Category]:
        """Ищет категории по названию"""
        search_term = f"%{query}%"
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM categories WHERE name LIKE ? ORDER BY name",
                (search_term,)
            )
            
            categories = []
            for row in cursor:
                categories.append(Category(
                    id=row['id'],
                    name=row['name'],
                    created_at=row['created_at']
                ))
            
            return categories
    
    def get_category_stats(self) -> List[dict]:
        """Возвращает статистику по категориям"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    c.id,
                    c.name,
                    COUNT(i.id) as item_count,
                    COUNT(DISTINCT ol.operation_id) as operation_count
                FROM categories c
                LEFT JOIN items i ON c.id = i.category_id
                LEFT JOIN operation_lines ol ON i.id = ol.item_id
                GROUP BY c.id, c.name
                ORDER BY c.name
                """
            )
            
            stats = []
            for row in cursor:
                stats.append({
                    'id': row['id'],
                    'name': row['name'],
                    'item_count': row['item_count'],
                    'operation_count': row['operation_count']
                })
            
            return stats