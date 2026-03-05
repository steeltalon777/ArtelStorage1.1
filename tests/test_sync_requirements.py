import json
import tempfile
import unittest
from unittest import mock
from uuid import uuid4

import core.db as db_module
from core.db import init_database
from core.services.sync_client import SyncClient
from core.services.sync_orchestrator import SyncOrchestrator
from core.services.sync_outbox_service import SyncOutboxService
from core.services.sync_settings_service import SyncSettingsService


class SyncRequirementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        db_module._db_instance = None
        init_database(self.tmp.name)
        self.settings = SyncSettingsService(self.tmp.name)
        self.settings.save_settings(
            server_url="https://sync.example.com",
            site_uuid=str(uuid4()),
            enabled=True,
            device_token="secret-token",
            client_version="ArtelStorage/Test",
        )
        self.outbox = SyncOutboxService(self.tmp.name)

    def tearDown(self):
        db_module._db_instance = None

    def test_outbox_uses_new_event_uuid_and_qty_decimal_string(self):
        operation_id = uuid4()
        with self.outbox.db.get_connection() as conn:
            self.outbox.enqueue_operation_event(
                conn=conn,
                operation_id=operation_id,
                operation_type="writeoff",
                event_datetime="2026-01-01 10:00:00",
                comment="test",
                lines=[{"item_id": uuid4(), "qty": 1.23456}],
            )
            conn.commit()
            row = conn.execute("SELECT event_uuid, payload_json FROM sync_outbox LIMIT 1").fetchone()
        self.assertIsNotNone(row)
        self.assertNotEqual(str(operation_id), row["event_uuid"])
        payload = json.loads(row["payload_json"])
        self.assertEqual("1.235", payload["lines"][0]["qty"])

    def test_apply_push_result_deletes_delivered_and_marks_conflict(self):
        accepted_uuid = str(uuid4())
        duplicate_uuid = str(uuid4())
        conflict_uuid = str(uuid4())
        with self.outbox.db.get_connection() as conn:
            for value in [accepted_uuid, duplicate_uuid, conflict_uuid]:
                conn.execute(
                    """
                    INSERT INTO sync_outbox (
                      event_uuid, site_uuid, device_uuid, batch_uuid, event_type, event_datetime,
                      schema_version, payload_json, payload_hash, status
                    ) VALUES (?, ?, ?, ?, 'writeoff', '2026-01-01 10:00:00', 1, '{}', 'h', 'pending')
                    """,
                    (
                        value,
                        self.settings.get_settings()["site_uuid"],
                        self.settings.get_settings()["device_uuid"],
                        str(uuid4()),
                    ),
                )
            conn.commit()

        self.outbox.apply_push_result(
            {
                "accepted": [accepted_uuid],
                "duplicates": [{"event_uuid": duplicate_uuid}],
                "rejected": [{"event_uuid": conflict_uuid, "reason": "uuid_collision"}],
            }
        )

        with self.outbox.db.get_connection() as conn:
            accepted_row = conn.execute("SELECT id FROM sync_outbox WHERE event_uuid=?", (accepted_uuid,)).fetchone()
            duplicate_row = conn.execute("SELECT id FROM sync_outbox WHERE event_uuid=?", (duplicate_uuid,)).fetchone()
            conflict_row = conn.execute("SELECT status, is_conflict FROM sync_outbox WHERE event_uuid=?", (conflict_uuid,)).fetchone()
        self.assertIsNone(accepted_row)
        self.assertIsNone(duplicate_row)
        self.assertEqual("rejected", conflict_row["status"])
        self.assertEqual(1, conflict_row["is_conflict"])

    def test_client_sends_required_headers(self):
        client = SyncClient("https://sync.example.com", device_token="secret-token", client_version="v-test")

        class _Resp:
            status = 200
            headers = {"X-Request-Id": "rid-1"}

            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch("core.services.sync_client.request.urlopen", return_value=_Resp()) as mocked:
            client.get_catalog_items({"site_id": "site-1", "device_id": "dev-1", "updated_after": None, "limit": 10})
            request_obj = mocked.call_args.args[0]
            self.assertEqual("secret-token", request_obj.get_header("X-device-token"))
            self.assertEqual("site-1", request_obj.get_header("X-site-id"))
            self.assertEqual("dev-1", request_obj.get_header("X-device-id"))

    def test_sync_once_updates_since_seq_after_pull_apply(self):
        site_uuid = self.settings.get_settings()["site_uuid"]

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.pull_calls = 0

            def ping(self, payload):
                return {"server_seq_upto": 2, "backoff_seconds": 0, "_meta": {"endpoint": "/ping", "status_code": 200, "latency_ms": 1, "request_id": "r1"}}

            def push_events(self, payload):
                return {"accepted": [], "duplicates": [], "rejected": [], "_meta": {"endpoint": "/push", "status_code": 200, "latency_ms": 1, "request_id": "r2"}}

            def pull_events(self, payload):
                self.pull_calls += 1
                if self.pull_calls == 1:
                    return {
                        "events": [{"server_seq": 1, "event_uuid": str(uuid4()), "event_type": "writeoff", "event_datetime": "2026-01-01T10:00:00Z", "schema_version": 1, "payload": {}}],
                        "next_since_seq": 1,
                        "server_seq_upto": 2,
                        "_meta": {"endpoint": "/pull", "status_code": 200, "latency_ms": 1, "request_id": "r3"},
                    }
                if self.pull_calls == 2:
                    return {
                        "events": [{"server_seq": 2, "event_uuid": str(uuid4()), "event_type": "writeoff", "event_datetime": "2026-01-01T10:00:00Z", "schema_version": 1, "payload": {}}],
                        "next_since_seq": 2,
                        "server_seq_upto": 2,
                        "_meta": {"endpoint": "/pull", "status_code": 200, "latency_ms": 1, "request_id": "r4"},
                    }
                return {
                    "events": [],
                    "next_since_seq": 2,
                    "server_seq_upto": 2,
                    "_meta": {"endpoint": "/pull", "status_code": 200, "latency_ms": 1, "request_id": "r5"},
                }

            def get_catalog_categories(self, payload):
                return {"categories": [], "next_updated_after": payload.get("updated_after"), "_meta": {"endpoint": "/catalog/categories", "status_code": 200, "latency_ms": 1, "request_id": "r6"}}

            def get_catalog_items(self, payload):
                return {"items": [], "next_updated_after": payload.get("updated_after"), "_meta": {"endpoint": "/catalog/items", "status_code": 200, "latency_ms": 1, "request_id": "r7"}}

        with mock.patch("core.services.sync_orchestrator.SyncClient", FakeClient):
            SyncOrchestrator(self.tmp.name).sync_once()

        with self.outbox.db.get_connection() as conn:
            state = conn.execute("SELECT since_seq FROM sync_site_state WHERE site_uuid=?", (site_uuid,)).fetchone()
            inbox_count = conn.execute("SELECT COUNT(*) AS c FROM sync_inbox_events WHERE site_uuid=?", (site_uuid,)).fetchone()
        self.assertEqual(2, int(state["since_seq"]))
        self.assertEqual(2, int(inbox_count["c"]))


if __name__ == "__main__":
    unittest.main()
