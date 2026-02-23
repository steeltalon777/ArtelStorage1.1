"""
ArtelStorage Core Module

Основной модуль системы с аутентификацией, сервисами и синхронизацией.
"""

from .db import Database, get_db, init_database
from .schema import User, Site, Category, Item, Operation, OperationLine, Snapshot, SnapshotData
from .auth import AuthManager, get_auth_manager, authenticate, get_current_user, is_admin, logout, require_admin
from .sync import SyncProvider, FileSyncProvider, ApiSyncProvider, SyncManager

# Импорт сервисов
from .services.users_service import UsersService
from .services.items_service import ItemsService
from .services.categories_service import CategoriesService
from .services.export_service import ExportService
from .services.import_service import ImportService

__all__ = [
    # Database
    'Database', 'get_db', 'init_database',

    # Schema
    'User', 'Site', 'Category', 'Item', 'Operation', 'OperationLine', 'Snapshot', 'SnapshotData',

    # Auth
    'AuthManager', 'get_auth_manager', 'authenticate', 'get_current_user', 'is_admin', 'logout', 'require_admin',

    # Sync
    'SyncProvider', 'FileSyncProvider', 'ApiSyncProvider', 'SyncManager',

    # Services
    'UsersService', 'ItemsService', 'CategoriesService', 'ExportService', 'ImportService',
]