from datetime import datetime
from typing import Optional

from ..db import get_db
from .items_service import ItemsService
from .categories_service import CategoriesService
from .sync_client import SyncClient
from .sync_outbox_service import SyncOutboxService
from .sync_settings_service import SyncSettingsService


class SyncOrchestrator:
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
        client = SyncClient(settings["server_url"], settings.get("api_key"))

        self._pull_categories(client)
        self._pull_items(client)
        self._push_outbox(client, settings)

        with self.db.get_connection() as conn:
            conn.execute("UPDATE sync_state SET last_sync_at=CURRENT_TIMESTAMP WHERE id=1")
            conn.commit()

    def _push_outbox(self, client: SyncClient, settings: dict):
        events = self.outbox_service.get_pending(limit=200)
        if not events:
            return
        self.outbox_service.mark_sending([row["id"] for row in events])
        payload = {
            "site_id": settings["site_uuid"],
            "device_id": settings["device_uuid"],
            "events": [
                {
                    "event_uuid": row["event_uuid"],
                    "event_type": row["event_type"],
                    "event_datetime": row["event_datetime"],
                    "schema_version": row["schema_version"],
                    "payload": __import__("json").loads(row["payload_json"]),
                }
                for row in events
            ],
        }
        response = client.push_events(payload)
        self.outbox_service.apply_push_result(response)

    def _pull_categories(self, client: SyncClient):
        updated_after = self._get_state("catalog_categories_updated_after")
        while True:
            response = client.get_catalog_categories({"updated_after": updated_after, "limit": 500})
            categories = response.get("categories", [])
            self.categories_service.upsert_server_categories(categories)
            next_updated_after = response.get("next_updated_after")
            if not next_updated_after or not categories:
                self._set_state("catalog_categories_updated_after", next_updated_after or updated_after)
                break
            updated_after = next_updated_after
            self._set_state("catalog_categories_updated_after", updated_after)

    def _pull_items(self, client: SyncClient):
        updated_after = self._get_state("catalog_items_updated_after")
        while True:
            response = client.get_catalog_items({"updated_after": updated_after, "limit": 500})
            items = response.get("items", [])
            self.items_service.upsert_server_items(items)
            next_updated_after = response.get("next_updated_after")
            if not next_updated_after or not items:
                self._set_state("catalog_items_updated_after", next_updated_after or updated_after)
                break
            updated_after = next_updated_after
            self._set_state("catalog_items_updated_after", updated_after)

    def _get_state(self, key: str):
        with self.db.get_connection() as conn:
            row = conn.execute(f"SELECT {key} as v FROM sync_state WHERE id = 1").fetchone()
            return row["v"] if row else None

    def _set_state(self, key: str, value):
        with self.db.get_connection() as conn:
            conn.execute(f"UPDATE sync_state SET {key} = ? WHERE id = 1", (value,))
            conn.commit()
