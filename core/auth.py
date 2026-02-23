"""Аутентификация и авторизация"""

import bcrypt
import sqlite3
from typing import Optional, Tuple
from dataclasses import dataclass

from .db import get_db
from .schema import User


@dataclass
class AuthResult:
    """Результат аутентификации"""
    success: bool
    user: Optional[User] = None
    error: Optional[str] = None


class AuthManager:
    """Менеджер аутентификации"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
        self.current_user: Optional[User] = None
    
    def hash_password(self, password: str) -> str:
        """Хеширует пароль с использованием bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Проверяет пароль"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except (ValueError, TypeError):
            return False
    
    def authenticate(self, username: str, password: str) -> AuthResult:
        """Аутентифицирует пользователя"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, username, full_name, password_hash, is_admin, created_at
                FROM users WHERE username = ?
                """,
                (username,)
            )
            row = cursor.fetchone()
            
            if row is None:
                return AuthResult(success=False, error="Пользователь не найден")
            
            if not self.verify_password(password, row['password_hash']):
                return AuthResult(success=False, error="Неверный пароль")
            
            user = User(
                id=row['id'],
                username=row['username'],
                full_name=row['full_name'],
                password_hash=row['password_hash'],
                is_admin=bool(row['is_admin']),
                created_at=row['created_at']
            )
            
            self.current_user = user
            return AuthResult(success=True, user=user)
    
    def logout(self):
        """Выход из системы"""
        self.current_user = None
    
    def get_current_user(self) -> Optional[User]:
        """Возвращает текущего пользователя"""
        return self.current_user
    
    def is_admin(self) -> bool:
        """Проверяет, является ли текущий пользователь администратором"""
        return self.current_user is not None and self.current_user.is_admin
    
    def create_user(self, username: str, full_name: str, password: str, 
                   is_admin: bool = False) -> AuthResult:
        """Создает нового пользователя"""
        password_hash = self.hash_password(password)
        
        with self.db.get_connection() as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO users (username, full_name, password_hash, is_admin)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, full_name, password_hash, 1 if is_admin else 0)
                )
                conn.commit()
                
                user = User(
                    id=cursor.lastrowid,
                    username=username,
                    full_name=full_name,
                    password_hash=password_hash,
                    is_admin=is_admin
                )
                
                return AuthResult(success=True, user=user)
            except sqlite3.IntegrityError:
                return AuthResult(success=False, error="Пользователь с таким именем уже существует")
    
    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """Обновляет пароль пользователя"""
        password_hash = self.hash_password(new_password)
        
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_user_admin_status(self, user_id: int, is_admin: bool) -> bool:
        """Обновляет статус администратора"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_admin = ? WHERE id = ?",
                (1 if is_admin else 0, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def initialize_admin_user(self):
        """Инициализирует пользователя admin с паролем 'админ'"""
        with self.db.get_connection() as conn:
            # Проверяем, есть ли уже пароль у пользователя admin
            cursor = conn.execute(
                "SELECT password_hash FROM users WHERE username = 'admin'"
            )
            row = cursor.fetchone()
            
            if row and row['password_hash']:
                # Пароль уже установлен
                return
            
            # Устанавливаем пароль 'админ'
            password_hash = self.hash_password('админ')
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = 'admin'",
                (password_hash,)
            )
            conn.commit()


# Глобальный экземпляр менеджера аутентификации
_auth_manager: Optional[AuthManager] = None


def get_auth_manager(db_path: Optional[str] = None) -> AuthManager:
    """Возвращает экземпляр менеджера аутентификации"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager(db_path)
    return _auth_manager


def authenticate(username: str, password: str) -> AuthResult:
    """Аутентифицирует пользователя"""
    return get_auth_manager().authenticate(username, password)


def get_current_user() -> Optional[User]:
    """Возвращает текущего пользователя"""
    return get_auth_manager().get_current_user()


def is_admin() -> bool:
    """Проверяет, является ли текущий пользователь администратором"""
    return get_auth_manager().is_admin()


def logout():
    """Выход из системы"""
    get_auth_manager().logout()


def require_admin() -> bool:
    """Проверяет права администратора, возвращает True если пользователь - админ"""
    return get_auth_manager().is_admin()
