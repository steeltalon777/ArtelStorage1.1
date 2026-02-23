"""Модели данных для ArtelStorage"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import UUID


@dataclass
class User:
    """Пользователь системы"""
    id: Optional[int] = None
    username: str = ""
    full_name: str = ""
    password_hash: str = ""
    is_admin: bool = False
    created_at: Optional[datetime] = None


@dataclass
class Site:
    """Площадка (склад)"""
    id: Optional[int] = None
    name: str = ""
    is_local: bool = False
    created_at: Optional[datetime] = None


@dataclass
class Category:
    """Категория ТМЦ"""
    id: Optional[int] = None
    name: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Item:
    """Товарно-материальная ценность"""
    id: Optional[UUID] = None
    name: str = ""
    unit: str = ""
    category_id: Optional[int] = None
    category_name: Optional[str] = None  # Для удобства
    created_locally: bool = True
    created_at: Optional[datetime] = None


@dataclass
class Operation:
    """Операция с ТМЦ"""
    id: Optional[UUID] = None
    type: str = ""  # 'incoming', 'issue', 'writeoff', 'move'
    created_at: datetime = datetime.now()
    created_by: int = 0
    created_by_username: Optional[str] = None  # Для удобства
    source_site_id: Optional[int] = None
    source_site_name: Optional[str] = None  # Для удобства
    target_site_id: Optional[int] = None
    target_site_name: Optional[str] = None  # Для удобства
    recipient_name: Optional[str] = None
    vehicle: Optional[str] = None
    comment: Optional[str] = None
    pdf_path: Optional[str] = None
    lines: List['OperationLine'] = None  # type: ignore

    def __post_init__(self):
        if self.lines is None:
            self.lines = []


@dataclass
class OperationLine:
    """Строка операции"""
    id: Optional[int] = None
    operation_id: Optional[UUID] = None
    item_id: UUID = UUID(int=0)
    item_name: Optional[str] = None  # Для удобства
    qty: float = 0.0


@dataclass
class Snapshot:
    """Снимок данных системы"""
    format: str = "artelstorage-snapshot"
    version: int = 1
    exported_at: datetime = datetime.now()
    data: 'SnapshotData' = None  # type: ignore

    def __post_init__(self):
        if self.data is None:
            self.data = SnapshotData()


@dataclass
class SnapshotData:
    """Данные снимка"""
    users: List[User] = None  # type: ignore
    sites: List[Site] = None  # type: ignore
    categories: List[Category] = None  # type: ignore
    items: List[Item] = None  # type: ignore
    operations: List[Operation] = None  # type: ignore

    def __post_init__(self):
        if self.users is None:
            self.users = []
        if self.sites is None:
            self.sites = []
        if self.categories is None:
            self.categories = []
        if self.items is None:
            self.items = []
        if self.operations is None:
            self.operations = []