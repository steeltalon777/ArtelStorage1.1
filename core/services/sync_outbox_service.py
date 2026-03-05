import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from ..db import get_db
from .sync_settings_service import SyncSettingsService


class SyncOutboxService:
    MAX_RETRIES = 10

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
            "lines": [
                {
                    "item_id": str(line["item_id"]),
                    "qty": self._format_qty(line["qty"]),
                    "batch": None,
                }
                for line in lines
            ],
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
                str(uuid4()),
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
                  AND COALESCE(is_conflict, 0) = 0
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
        accepted = self._extract_event_uuids(response.get("accepted", []))
        duplicates = self._extract_event_uuids(response.get("duplicates", []))
        rejected = self._extract_rejected(response.get("rejected", {}))

        with self.db.get_connection() as conn:
            for uuid_value in accepted:
                conn.execute("DELETE FROM sync_outbox WHERE event_uuid=?", (uuid_value,))
            for uuid_value in duplicates:
                conn.execute("DELETE FROM sync_outbox WHERE event_uuid=?", (uuid_value,))
            for uuid_value, reason in rejected.items():
                row = conn.execute("SELECT try_count FROM sync_outbox WHERE event_uuid=?", (uuid_value,)).fetchone()
                if not row:
                    continue
                try_count = int(row["try_count"]) + 1
                status = "dead" if try_count >= self.MAX_RETRIES else "pending"
                next_try = self._calc_next_try_at(try_count)
                is_conflict = 0
                if reason == "uuid_collision":
                    status = "rejected"
                    next_try = None
                    is_conflict = 1
                conn.execute(
                    """
                    UPDATE sync_outbox
                    SET status=?, try_count=?, next_try_at=?, last_error=?, is_conflict=?
                    WHERE event_uuid=?
                    """,
                    (status, try_count, next_try, str(reason), is_conflict, uuid_value),
                )
            conn.commit()

    def mark_batch_failed(self, ids: List[int], reason: str):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        with self.db.get_connection() as conn:
            rows = conn.execute(
                f"SELECT id, try_count FROM sync_outbox WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
            for row in rows:
                try_count = int(row["try_count"]) + 1
                status = "dead" if try_count >= self.MAX_RETRIES else "pending"
                conn.execute(
                    """
                    UPDATE sync_outbox
                    SET status=?, try_count=?, next_try_at=?, last_error=?
                    WHERE id=?
                    """,
                    (status, try_count, self._calc_next_try_at(try_count), reason, row["id"]),
                )
            conn.commit()

    def list_queue(self, limit: int = 500) -> List[Dict]:
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM sync_outbox ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def pending_count(self) -> int:
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM sync_outbox WHERE status IN ('pending','sending') AND COALESCE(is_conflict,0)=0"
            ).fetchone()
            return int(row["c"])

    def _calc_next_try_at(self, try_count: int) -> str:
        base = 1.0
        factor = 2.0
        max_delay = 60.0
        jitter = random.uniform(0.8, 1.2)
        delay = min(base * (factor ** max(0, try_count - 1)), max_delay) * jitter
        return (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat(sep=" ")

    def _format_qty(self, value) -> str:
        quantized = Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        return f"{quantized:.3f}"

    def _extract_event_uuids(self, events) -> set:
        uuids = set()
        if isinstance(events, list):
            for value in events:
                if isinstance(value, str):
                    uuids.add(value)
                elif isinstance(value, dict):
                    event_uuid = value.get("event_uuid") or value.get("uuid")
                    if event_uuid:
                        uuids.add(str(event_uuid))
        return uuids

    def _extract_rejected(self, rejected) -> Dict[str, str]:
        result: Dict[str, str] = {}
        if isinstance(rejected, dict):
            for key, value in rejected.items():
                result[str(key)] = str(value)
            return result
        if isinstance(rejected, list):
            for value in rejected:
                if isinstance(value, dict):
                    event_uuid = value.get("event_uuid") or value.get("uuid")
                    reason = value.get("reason") or value.get("error") or "rejected"
                    if event_uuid:
                        result[str(event_uuid)] = str(reason)
        return result
