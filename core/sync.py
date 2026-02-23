"""Интерфейс синхронизации"""

from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from .schema import Snapshot
from .services.export_service import ExportService
from .services.import_service import ImportService


class SyncProvider(ABC):
    """Абстрактный класс провайдера синхронизации"""
    
    @abstractmethod
    def export_snapshot(self) -> Snapshot:
        """Экспортирует снимок данных"""
        pass
    
    @abstractmethod
    def import_snapshot(self, snapshot: Snapshot) -> bool:
        """Импортирует снимок данных"""
        pass


class FileSyncProvider(SyncProvider):
    """Провайдер синхронизации через файлы"""
    
    def __init__(self, db_path: Optional[str] = None, export_dir: Optional[str] = None):
        self.db_path = db_path
        self.export_dir = Path(export_dir) if export_dir else Path.cwd() / "exports"
        self.export_service = ExportService(db_path)
        self.import_service = ImportService(db_path)
    
    def export_snapshot(self) -> Snapshot:
        """Экспортирует снимок данных"""
        return self.export_service.export_snapshot()
    
    def export_to_file(self, filename: Optional[str] = None) -> str:
        """Экспортирует снимок в файл"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"snapshot_{timestamp}.json"
        
        filepath = self.export_dir / filename
        self.export_service.export_to_file(str(filepath))
        return str(filepath)
    
    def import_snapshot(self, snapshot: Snapshot) -> bool:
        """Импортирует снимок данных"""
        return self.import_service.import_snapshot(snapshot)
    
    def import_from_file(self, filepath: str) -> bool:
        """Импортирует снимок из файла"""
        return self.import_service.import_from_file(filepath)


class ApiSyncProvider(SyncProvider):
    """Провайдер синхронизации через API (заглушка)"""
    
    def __init__(self, api_url: str, api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key
        # TODO: Реализовать подключение к API
    
    def export_snapshot(self) -> Snapshot:
        """Экспортирует снимок данных через API"""
        # TODO: Реализовать экспорт через API
        raise NotImplementedError("API синхронизация еще не реализована")
    
    def import_snapshot(self, snapshot: Snapshot) -> bool:
        """Импортирует снимок данных через API"""
        # TODO: Реализовать импорт через API
        raise NotImplementedError("API синхронизация еще не реализована")


class SyncManager:
    """Менеджер синхронизации"""
    
    def __init__(self, provider: SyncProvider):
        self.provider = provider
    
    def export(self) -> Snapshot:
        """Экспортирует данные"""
        return self.provider.export_snapshot()
    
    def import_data(self, snapshot: Snapshot) -> bool:
        """Импортирует данные"""
        return self.provider.import_snapshot(snapshot)
    
    @classmethod
    def create_file_sync(cls, db_path: Optional[str] = None) -> 'SyncManager':
        """Создает менеджер синхронизации через файлы"""
        provider = FileSyncProvider(db_path)
        return cls(provider)
    
    @classmethod
    def create_api_sync(cls, api_url: str, api_key: Optional[str] = None) -> 'SyncManager':
        """Создает менеджер синхронизации через API"""
        provider = ApiSyncProvider(api_url, api_key)
        return cls(provider)