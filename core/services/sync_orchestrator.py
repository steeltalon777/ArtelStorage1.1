import json
import random
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Optional
from uuid import uuid4

from ..db import get_db
from .categories_service import CategoriesService
from .items_service import ItemsService
from .sync_client import SyncClient, SyncHttpError
from .sync_outbox_service import SyncOutboxService
from .sync_settings_service import SyncSettingsService


class SyncOrchestrator:
    MAX_PUSH_EVENTS = 500
    PULL_PAGE_LIMIT = 200
    CATALOG_PAGE_LIMIT = 200
    RETRY_ATTEMPTS = 5

    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
        self.settings_service = SyncSettingsService(db_path)
        self.outbox_service = SyncOutboxService(db_path)
        self.items_service = ItemsService(db_path)
        self.categories_service = CategoriesService(db_path)

    def sync_once(self):
        settings = self.settings_service.get_settings()
        if not settings.get("enabled"):
            raise ValueError("Синхронизация выключена")
        if not settings.get("device_token"):
            raise ValueError("Не задан токен устройства (X-Device-Token)")

        client = SyncClient(
            settings["server_url"],
            device_token=settings.get("device_token"),
            client_version=settings.get("client_version"),
        )

        self._enforce_ping_rate_limit()
        ping_response = self._call_with_retry("/ping", lambda: self._ping(client, settings))
        server_seq_upto = int(ping_response.get("server_seq_upto", self._get_since_seq(settings["site_uuid"])))

        self._push_outbox(client, settings)
        self._pull_events(client, settings, server_seq_upto)
        self._pull_catalog_categories(client, settings)
        self._pull_catalog_items(client, settings)

        backoff_seconds = int(ping_response.get("backoff_seconds") or 0)
        if backoff_seconds > 0:
            time.sleep(backoff_seconds)

        with self.db.get_connection() as conn:
            conn.execute("UPDATE sync_state SET last_sync_at=CURRENT_TIMESTAMP WHERE id=1")
            conn.commit()

    def _ping(self, client: SyncClient, settings: dict) -> Dict:
        payload = {
            "site_id": settings["site_uuid"],
            "device_id": settings["device_uuid"],
            "last_server_seq": self._get_since_seq(settings["site_uuid"]),
            "outbox_count": self.outbox_service.pending_count(),
            "client_time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
        response = client.ping(payload)
        self._log_http_result(response, batch_size=0)
        with self.db.get_connection() as conn:
            conn.execute("UPDATE sync_state SET last_ping_at=CURRENT_TIMESTAMP WHERE id=1")
            conn.commit()
        return response

    def _push_outbox(self, client: SyncClient, settings: dict):
        while True:
            events = self.outbox_service.get_pending(limit=self.MAX_PUSH_EVENTS)
            if not events:
                break
            event_ids = [row["id"] for row in events]
            self.outbox_service.mark_sending(event_ids)
            payload = {
                "site_id": settings["site_uuid"],
                "device_id": settings["device_uuid"],
                "batch_id": str(uuid4()),
                "events": [
                    {
                        "event_uuid": row["event_uuid"],
                        "event_type": row["event_type"],
                        "event_datetime": self._to_utc_iso(row["event_datetime"]),
                        "schema_version": row["schema_version"],
                        "payload": json.loads(row["payload_json"]),
                    }
                    for row in events
                ],
            }
            try:
                response = self._call_with_retry("/push", lambda: client.push_events(payload), batch_size=len(events))
                self.outbox_service.apply_push_result(response)
            except Exception as exc:
                self.outbox_service.mark_batch_failed(event_ids, str(exc))
                raise
            time.sleep(1.0)

    def _pull_events(self, client: SyncClient, settings: dict, server_seq_upto: int):
        since_seq = self._get_since_seq(settings["site_uuid"])
        while True:
            payload = {
                "site_id": settings["site_uuid"],
                "device_id": settings["device_uuid"],
                "since_seq": since_seq,
                "limit": self.PULL_PAGE_LIMIT,
            }
            response = self._call_with_retry("/pull", lambda: client.pull_events(payload), batch_size=self.PULL_PAGE_LIMIT)
            events = response.get("events", [])
            next_since_seq = int(response.get("next_since_seq", since_seq))
            server_seq_upto = int(response.get("server_seq_upto", server_seq_upto))
            self._apply_pull_page(settings["site_uuid"], events, next_since_seq)

            if not events and next_since_seq >= server_seq_upto:
                break
            if next_since_seq == since_seq and not events:
                break
            since_seq = next_since_seq

    def _pull_catalog_categories(self, client: SyncClient, settings: dict):
        updated_after = self._get_site_state(settings["site_uuid"], "catalog_categories_updated_after")
        while True:
            payload = {
                "site_id": settings["site_uuid"],
                "device_id": settings["device_uuid"],
                "updated_after": updated_after,
                "limit": self.CATALOG_PAGE_LIMIT,
            }
            response = self._call_with_retry(
                "/catalog/categories",
                lambda: client.get_catalog_categories(payload),
                batch_size=self.CATALOG_PAGE_LIMIT,
            )
            categories = response.get("categories", [])
            next_updated_after = response.get("next_updated_after") or updated_after
            self._apply_catalog_categories_page(settings["site_uuid"], categories, next_updated_after)
            if not categories or next_updated_after == updated_after:
                break
            updated_after = next_updated_after

    def _pull_catalog_items(self, client: SyncClient, settings: dict):
        updated_after = self._get_site_state(settings["site_uuid"], "catalog_items_updated_after")
        while True:
            payload = {
                "site_id": settings["site_uuid"],
                "device_id": settings["device_uuid"],
                "updated_after": updated_after,
                "limit": self.CATALOG_PAGE_LIMIT,
            }
            response = self._call_with_retry(
                "/catalog/items",
                lambda: client.get_catalog_items(payload),
                batch_size=self.CATALOG_PAGE_LIMIT,
            )
            items = response.get("items", [])
            next_updated_after = response.get("next_updated_after") or updated_after
            self._apply_catalog_items_page(settings["site_uuid"], items, next_updated_after)
            if not items or next_updated_after == updated_after:
                break
            updated_after = next_updated_after

    def _call_with_retry(self, endpoint: str, fn: Callable[[], Dict], batch_size: int = 0) -> Dict:
        last_exc: Optional[Exception] = None
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                response = fn()
                self._log_http_result(response, batch_size=batch_size)
                return response
            except SyncHttpError as exc:
                last_exc = exc
                self._log_http_error(endpoint, exc, batch_size=batch_size)
                if exc.status_code in {403, 422}:
                    raise
                if exc.status_code == 429:
                    delay = float(exc.retry_after or self._calc_backoff_seconds(attempt + 1))
                    time.sleep(delay)
                    continue
                if exc.status_code == 0 or exc.status_code >= 500:
                    time.sleep(self._calc_backoff_seconds(attempt + 1))
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                self._log_http_error(endpoint, exc, batch_size=batch_size)
                time.sleep(self._calc_backoff_seconds(attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError(f"Sync call failed: {endpoint}")

    def _apply_pull_page(self, site_uuid: str, events: list, next_since_seq: int):
        with self.db.get_connection() as conn:
            for event in events:
                payload_json = json.dumps(event.get("payload", {}), ensure_ascii=False, separators=(",", ":"))
                conn.execute(
                    """
                    INSERT OR IGNORE INTO sync_inbox_events (
                        site_uuid, server_seq, event_uuid, event_type, event_datetime, schema_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        site_uuid,
                        int(event.get("server_seq", 0)),
                        event.get("event_uuid"),
                        event.get("event_type"),
                        event.get("event_datetime"),
                        event.get("schema_version"),
                        payload_json,
                    ),
                )
            self._set_since_seq_conn(conn, site_uuid, next_since_seq)
            conn.commit()

    def _apply_catalog_categories_page(self, site_uuid: str, categories: list, next_updated_after):
        with self.db.get_connection() as conn:
            self.categories_service.upsert_server_categories(categories, conn=conn)
            self._set_site_state_conn(conn, site_uuid, "catalog_categories_updated_after", next_updated_after)
            conn.commit()

    def _apply_catalog_items_page(self, site_uuid: str, items: list, next_updated_after):
        with self.db.get_connection() as conn:
            self.items_service.upsert_server_items(items, conn=conn)
            self._set_site_state_conn(conn, site_uuid, "catalog_items_updated_after", next_updated_after)
            conn.commit()

    def _get_since_seq(self, site_uuid: str) -> int:
        row = self._get_site_state_row(site_uuid)
        return int(row["since_seq"]) if row else 0

    def _set_since_seq_conn(self, conn, site_uuid: str, value: int):
        self._ensure_site_state_row(conn, site_uuid)
        conn.execute(
            "UPDATE sync_site_state SET since_seq=?, updated_at=CURRENT_TIMESTAMP WHERE site_uuid=?",
            (int(value), site_uuid),
        )

    def _get_site_state(self, site_uuid: str, column: str):
        row = self._get_site_state_row(site_uuid)
        return row[column] if row else None

    def _set_site_state_conn(self, conn, site_uuid: str, column: str, value):
        self._ensure_site_state_row(conn, site_uuid)
        conn.execute(
            f"UPDATE sync_site_state SET {column}=?, updated_at=CURRENT_TIMESTAMP WHERE site_uuid=?",
            (value, site_uuid),
        )

    def _get_site_state_row(self, site_uuid: str):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM sync_site_state WHERE site_uuid=?", (site_uuid,)).fetchone()
            return row

    def _ensure_site_state_row(self, conn, site_uuid: str):
        conn.execute("INSERT OR IGNORE INTO sync_site_state (site_uuid) VALUES (?)", (site_uuid,))

    def _enforce_ping_rate_limit(self):
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT last_ping_at FROM sync_state WHERE id=1").fetchone()
        if not row or not row["last_ping_at"]:
            return
        # SQLite timestamp format: YYYY-MM-DD HH:MM:SS
        try:
            last_ping = datetime.fromisoformat(str(row["last_ping_at"]).replace(" ", "T"))
        except Exception:
            return
        elapsed = (datetime.now() - last_ping).total_seconds()
        if elapsed < 5.0:
            time.sleep(5.0 - elapsed)

    def _calc_backoff_seconds(self, attempt: int) -> float:
        base = 1.0
        factor = 2.0
        max_delay = 60.0
        raw = min(base * (factor ** max(0, attempt - 1)), max_delay)
        return raw * random.uniform(0.8, 1.2)

    def _to_utc_iso(self, value) -> str:
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace(" ", "T"))
            except Exception:
                dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    def _log_http_result(self, response: Dict, batch_size: int):
        meta = response.get("_meta") or {}
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_logs (endpoint, status_code, latency_ms, request_id, batch_size, error_text)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    meta.get("endpoint"),
                    meta.get("status_code"),
                    meta.get("latency_ms"),
                    meta.get("request_id"),
                    batch_size,
                ),
            )
            conn.commit()

    def _log_http_error(self, endpoint: str, exc: Exception, batch_size: int):
        status_code = exc.status_code if isinstance(exc, SyncHttpError) else None
        request_id = exc.request_id if isinstance(exc, SyncHttpError) else None
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_logs (endpoint, status_code, latency_ms, request_id, batch_size, error_text)
                VALUES (?, ?, NULL, ?, ?, ?)
                """,
                (endpoint, status_code, request_id, batch_size, str(exc)),
            )
            conn.commit()
