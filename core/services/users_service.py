"""Сервис для работы с пользователями"""

from typing import List, Optional
from ..db import get_db
from ..schema import User
from ..auth import AuthManager


class UsersService:
    """Сервис управления пользователями"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
        self.auth = AuthManager(db_path)
    
    def get_all_users(self) -> List[User]:
        """Возвращает всех пользователей"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, username, full_name, password_hash, is_admin, created_at
                FROM users
                ORDER BY username
                """
            )
            
            users = []
            for row in cursor:
                users.append(User(
                    id=row['id'],
                    username=row['username'],
                    full_name=row['full_name'],
                    password_hash=row['password_hash'],
                    is_admin=bool(row['is_admin']),
                    created_at=row['created_at']
                ))
            
            return users
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Возвращает пользователя по ID"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, username, full_name, password_hash, is_admin, created_at
                FROM users WHERE id = ?
                """,
                (user_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return User(
                    id=row['id'],
                    username=row['username'],
                    full_name=row['full_name'],
                    password_hash=row['password_hash'],
                    is_admin=bool(row['is_admin']),
                    created_at=row['created_at']
                )
            return None
    
    def create_user(self, username: str, full_name: str, password: str, 
                   is_admin: bool = False) -> User:
        """Создает нового пользователя"""
        result = self.auth.create_user(username, full_name, password, is_admin)
        if not result.success:
            raise ValueError(result.error)
        return result.user
    
    def update_user(self, user_id: int, full_name: Optional[str] = None, 
                   is_admin: Optional[bool] = None) -> bool:
        """Обновляет данные пользователя"""
        updates = []
        params = []
        
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        
        if is_admin is not None:
            updates.append("is_admin = ?")
            params.append(1 if is_admin else 0)
        
        if not updates:
            return False
        
        params.append(user_id)
        
        with self.db.get_connection() as conn:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Изменяет пароль пользователя"""
        return self.auth.update_user_password(user_id, new_password)
    
    def toggle_admin_status(self, user_id: int) -> bool:
        """Переключает статус администратора"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        new_status = not user.is_admin
        return self.auth.update_user_admin_status(user_id, new_status)
    
    def can_delete_user(self, user_id: int) -> bool:
        """Проверяет, можно ли удалить пользователя"""
        with self.db.get_connection() as conn:
            # Проверяем, участвует ли пользователь в операциях
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM operations WHERE created_by = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row['count'] == 0
    
    def delete_user(self, user_id: int) -> bool:
        """Удаляет пользователя"""
        if not self.can_delete_user(user_id):
            return False
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def search_users(self, query: str) -> List[User]:
        """Ищет пользователей по имени или username"""
        search_term = f"%{query}%"
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, username, full_name, password_hash, is_admin, created_at
                FROM users
                WHERE username LIKE ? OR full_name LIKE ?
                ORDER BY username
                """,
                (search_term, search_term)
            )
            
            users = []
            for row in cursor:
                users.append(User(
                    id=row['id'],
                    username=row['username'],
                    full_name=row['full_name'],
                    password_hash=row['password_hash'],
                    is_admin=bool(row['is_admin']),
                    created_at=row['created_at']
                ))
            
            return users