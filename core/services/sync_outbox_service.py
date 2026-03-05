import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from ..db import get_db
from .sync_settings_service import SyncSettingsService


class SyncOutboxService:
    def __init__(self, db_path: Optional[str] = None):
        self.db = get_db(db_path)
        self.settings_service = SyncSettingsService(db_path)

    def enqueue_operation_event(self, conn, operation_id: UUID, operation_type: str, event_datetime, comment: str, lines: List[Dict]):
        settings = self.settings_service.get_settings()
        if not settings.get("site_uuid"):
            return
        payload = {
            "doc_id": str(operation_id),
            "doc_type": operation_type,
            "comment": comment,
            "lines": [{"item_id": str(line["item_id"]), "qty": line["qty"], "batch": None} for line in lines],
        }
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        conn.execute(
            """
            INSERT INTO sync_outbox (
              event_uuid, site_uuid, device_uuid, batch_uuid, event_type, event_datetime,
              schema_version, payload_json, payload_hash, status
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 'pending')
            """,
            (
                str(operation_id),
                settings["site_uuid"],
                settings["device_uuid"],
                str(uuid4()),
                operation_type,
                event_datetime,
                payload_json,
                hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            ),
        )

    def get_pending(self, limit: int = 200) -> List[Dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sync_outbox
                WHERE status IN ('pending','sending')
                  AND (next_try_at IS NULL OR next_try_at <= CURRENT_TIMESTAMP)
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def mark_sending(self, ids: List[int]):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        with self.db.get_connection() as conn:
            conn.execute(f"UPDATE sync_outbox SET status='sending' WHERE id IN ({placeholders})", ids)
            conn.commit()

    def apply_push_result(self, response: Dict):
        accepted = set(response.get("accepted", []))
        duplicates = set(response.get("duplicates", []))
        rejected = response.get("rejected", {})
        server_seq = response.get("server_seq_upto")

        with self.db.get_connection() as conn:
            for uuid_value in accepted:
                conn.execute("UPDATE sync_outbox SET status='acked', server_seq=?, last_error=NULL WHERE event_uuid=?", (server_seq, uuid_value))
            for uuid_value in duplicates:
                conn.execute("UPDATE sync_outbox SET status='duplicate', server_seq=?, last_error=NULL WHERE event_uuid=?", (server_seq, uuid_value))
            for uuid_value, reason in rejected.items():
                row = conn.execute("SELECT try_count FROM sync_outbox WHERE event_uuid=?", (uuid_value,)).fetchone()
                if not row:
                    continue
                try_count = int(row["try_count"]) + 1
                status = "dead" if try_count >= 20 else "pending"
                backoff_seconds = min(2 ** try_count * 5, 600)
                next_try = (datetime.now() + timedelta(seconds=backoff_seconds)).isoformat(sep=" ")
                if reason == "uuid_collision":
                    status = "rejected"
                conn.execute(
                    """
                    UPDATE sync_outbox
                    SET status=?, try_count=?, next_try_at=?, last_error=?
                    WHERE event_uuid=?
                    """,
                    (status, try_count, next_try, str(reason), uuid_value),
                )
            conn.commit()

    def list_queue(self, limit: int = 500) -> List[Dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM sync_outbox ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def pending_count(self) -> int:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM sync_outbox WHERE status IN ('pending','sending')").fetchone()
            return int(row["c"])
