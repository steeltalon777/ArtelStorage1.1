from typing import Dict, Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from ..db import get_db


class SyncSettingsService:
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)

    def get_settings(self) -> Dict:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM sync_settings WHERE id = 1").fetchone()
            if row is None:
                device = str(uuid4())
                conn.execute(
                    """
                    INSERT INTO sync_settings (id, server_url, device_uuid, enabled, client_version)
                    VALUES (1, '', ?, 0, 'ArtelStorage/1.1')
                    """,
                    (device,),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM sync_settings WHERE id = 1").fetchone()

            device_token = row["device_token"] if "device_token" in row.keys() else None
            if not device_token:
                device_token = row["api_key"]
            client_version = row["client_version"] if "client_version" in row.keys() else None
            if not client_version:
                client_version = "ArtelStorage/1.1"
            return {
                "server_url": row["server_url"],
                "api_key": row["api_key"],
                "device_token": device_token or "",
                "client_version": client_version,
                "site_uuid": str(row["site_uuid"]) if row["site_uuid"] else "",
                "device_uuid": str(row["device_uuid"]),
                "enabled": bool(row["enabled"]),
                "updated_at": row["updated_at"],
            }

    def save_settings(
        self,
        server_url: str,
        site_uuid: str,
        enabled: bool,
        device_token: Optional[str] = None,
        client_version: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._validate(server_url, site_uuid)
        current = self.get_settings()
        effective_token = device_token if device_token is not None else (api_key if api_key is not None else current["device_token"])
        effective_client_version = (client_version or current.get("client_version") or "ArtelStorage/1.1").strip()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE sync_settings
                SET server_url = ?, site_uuid = ?, api_key = ?, device_token = ?, client_version = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (
                    server_url.strip(),
                    site_uuid.strip(),
                    effective_token,
                    effective_token,
                    effective_client_version,
                    1 if enabled else 0,
                ),
            )
            conn.execute(
                "UPDATE sites SET server_uuid = ? WHERE is_local = 1",
                (site_uuid.strip(),),
            )
            conn.commit()
        return {
            **current,
            "server_url": server_url.strip(),
            "site_uuid": site_uuid.strip(),
            "enabled": enabled,
            "device_token": effective_token or "",
            "client_version": effective_client_version,
            "api_key": effective_token or "",
        }

    def reset_device_uuid(self) -> str:
        value = str(uuid4())
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE sync_settings SET device_uuid = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (value,),
            )
            conn.commit()
        return value

    def _validate(self, server_url: str, site_uuid: str):
        parsed = urlparse(server_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Server URL должен быть корректным http/https URL")
        try:
            UUID(site_uuid.strip())
        except Exception as exc:
            raise ValueError("Site UUID должен быть корректным UUID") from exc
