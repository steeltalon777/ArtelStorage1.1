import sqlite3
import os
import time
import uuid
from pathlib import Path
from uuid import UUID
from typing import Optional


def adapt_uuid(uuid):
    """Адаптер UUID для SQLite"""
    return str(uuid)


def convert_uuid(data):
    """Конвертер UUID из SQLite"""
    return UUID(data.decode())


# Регистрируем адаптеры для UUID
sqlite3.register_adapter(UUID, adapt_uuid)
sqlite3.register_converter("UUID", convert_uuid)


class Database:
    """Класс для работы с базой данных с поддержкой транзакций и retry"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = Path(__file__).parent.parent / "db" / "storage.db"
        else:
            self.db_path = Path(db_path)
        
        os.makedirs(self.db_path.parent, exist_ok=True)
        
    def get_connection(self, max_retries: int = 3, retry_delay: float = 0.1):
        """Возвращает соединение с БД с поддержкой retry при блокировке"""
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(
                    str(self.db_path),
                    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                    timeout=10.0
                )
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.row_factory = sqlite3.Row
                return conn
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                raise
    
    def execute_in_transaction(self, func, *args, **kwargs):
        """Выполняет функцию в транзакции с поддержкой retry"""
        with self.get_connection() as conn:
            try:
                result = func(conn, *args, **kwargs)
                conn.commit()
                return result
            except Exception:
                conn.rollback()
                raise
    
    def init_schema(self):
        """Инициализирует схему базы данных"""
        with self.get_connection() as conn:
            # Включаем внешние ключи и WAL
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            
            # Таблица версии схемы
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Проверяем текущую версию схемы
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            current_version = cursor.fetchone()
            
            if current_version is None:
                # Создаем таблицы с версией 1
                self._create_v1_schema(conn)
                conn.execute("INSERT INTO schema_version (version) VALUES (1)")
                conn.commit()
                current_ver = 1
            else:
                current_ver = int(current_version["version"])

            if current_ver < 2:
                self._upgrade_to_v2(conn)
                conn.execute("INSERT INTO schema_version (version) VALUES (2)")
                conn.commit()

    def _column_exists(self, conn, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(r["name"] == column for r in rows)

    def _upgrade_to_v2(self, conn):
        """Обновляет схему БД до версии 2 (offline-first sync MVP)."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                server_url TEXT NOT NULL DEFAULT '',
                api_key TEXT,
                site_uuid UUID,
                device_uuid UUID NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_server_seq INTEGER DEFAULT 0,
                catalog_items_updated_after TIMESTAMP,
                catalog_categories_updated_after TIMESTAMP,
                last_ping_at TIMESTAMP,
                last_sync_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_uuid UUID UNIQUE NOT NULL,
                site_uuid UUID NOT NULL,
                device_uuid UUID NOT NULL,
                batch_uuid UUID NOT NULL,
                event_type TEXT NOT NULL,
                event_datetime TIMESTAMP NOT NULL,
                schema_version INTEGER DEFAULT 1,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('pending','sending','acked','duplicate','rejected','dead')),
                server_seq INTEGER,
                try_count INTEGER DEFAULT 0,
                next_try_at TIMESTAMP,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if not self._column_exists(conn, "categories", "server_uuid"):
            conn.execute("ALTER TABLE categories ADD COLUMN server_uuid UUID")
        if not self._column_exists(conn, "categories", "updated_at"):
            conn.execute("ALTER TABLE categories ADD COLUMN updated_at TIMESTAMP")
        if not self._column_exists(conn, "categories", "is_active"):
            conn.execute("ALTER TABLE categories ADD COLUMN is_active BOOLEAN DEFAULT 1")
        if not self._column_exists(conn, "categories", "parent_server_uuid"):
            conn.execute("ALTER TABLE categories ADD COLUMN parent_server_uuid UUID")

        if not self._column_exists(conn, "items", "server_uuid"):
            conn.execute("ALTER TABLE items ADD COLUMN server_uuid UUID")
        if not self._column_exists(conn, "items", "sku"):
            conn.execute("ALTER TABLE items ADD COLUMN sku TEXT")
        if not self._column_exists(conn, "items", "updated_at"):
            conn.execute("ALTER TABLE items ADD COLUMN updated_at TIMESTAMP")
        if not self._column_exists(conn, "items", "is_active"):
            conn.execute("ALTER TABLE items ADD COLUMN is_active BOOLEAN DEFAULT 1")

        if not self._column_exists(conn, "sites", "server_uuid"):
            conn.execute("ALTER TABLE sites ADD COLUMN server_uuid UUID")
        if not self._column_exists(conn, "sites", "updated_at"):
            conn.execute("ALTER TABLE sites ADD COLUMN updated_at TIMESTAMP")
        if not self._column_exists(conn, "sites", "is_active"):
            conn.execute("ALTER TABLE sites ADD COLUMN is_active BOOLEAN DEFAULT 1")

        device_uuid = str(uuid.uuid4())
        conn.execute(
            "INSERT OR IGNORE INTO sync_settings (id, device_uuid, server_url, enabled) VALUES (1, ?, '', 0)",
            (device_uuid,),
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_server_uuid ON categories(server_uuid) WHERE server_uuid IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_items_server_uuid ON items(server_uuid) WHERE server_uuid IS NOT NULL")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sites_server_uuid ON sites(server_uuid) WHERE server_uuid IS NOT NULL")
        conn.execute("INSERT OR IGNORE INTO sync_state (id) VALUES (1)")
    
    def _create_v1_schema(self, conn):
        """Создает схему версии 1"""
        # Таблица пользователей с паролями и правами администратора
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица площадок
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_local BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица категорий
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица номенклатуры
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id UUID PRIMARY KEY,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                category_id INTEGER,
                created_locally BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
            )
        """)
        
        # Таблица операций (шапка)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id UUID PRIMARY KEY,
                type TEXT NOT NULL CHECK (type IN ('incoming', 'issue', 'writeoff', 'move')),
                created_at TIMESTAMP NOT NULL,
                created_by INTEGER NOT NULL,
                source_site_id INTEGER,
                target_site_id INTEGER,
                recipient_name TEXT,
                vehicle TEXT,
                comment TEXT,
                pdf_path TEXT,
                FOREIGN KEY (created_by) REFERENCES users (id),
                FOREIGN KEY (source_site_id) REFERENCES sites (id),
                FOREIGN KEY (target_site_id) REFERENCES sites (id)
            )
        """)
        
        # Таблица строк операций
        conn.execute("""
            CREATE TABLE IF NOT EXISTS operation_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id UUID NOT NULL,
                item_id UUID NOT NULL,
                qty REAL NOT NULL CHECK (qty > 0),
                FOREIGN KEY (operation_id) REFERENCES operations (id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
        """)
        
        # Создаем пользователя по умолчанию (пароль будет установлен позже)
        conn.execute("""
            INSERT OR IGNORE INTO users (username, full_name, password_hash, is_admin) 
            VALUES ('admin', 'Administrator', '', 1)
        """)
        
        # Добавляем локальную площадку
        conn.execute("""
            INSERT OR IGNORE INTO sites (name, is_local) 
            VALUES ('Основной склад', 1)
        """)
        
        # Добавляем базовые категории
        categories = ["Электроника", "Расходники", "Инструмент", "Мебель"]
        for cat in categories:
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))


# Глобальный экземпляр базы данных
_db_instance: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    """Возвращает экземпляр базы данных"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def init_database(db_path: Optional[str] = None):
    """Инициализирует базу данных"""
    db = get_db(db_path)
    db.init_schema()
    return db
