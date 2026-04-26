from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.storage import (
    DedupeRecord,
    GatewayObservationRecord,
    GatewayStorage,
    MessageEventRecord,
    OutboundQueueRecord,
)


class StorageTests(unittest.TestCase):
    def make_storage(self) -> GatewayStorage:
        temp_dir = Path(tempfile.mkdtemp())
        return GatewayStorage(temp_dir / "queue.sqlite3")

    def test_initialize_creates_expected_tables(self) -> None:
        storage = self.make_storage()

        tables = storage.initialize()

        self.assertEqual(
            tables,
            [
                "dedupe_cache",
                "gateway_observations",
                "message_events",
                "outbound_queue",
            ],
        )

    def test_queue_depth_tracks_pending_queue_rows(self) -> None:
        storage = self.make_storage()
        storage.initialize()
        storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id="ops-test-0001",
                topic="mesh/v1/site-a/ops/up",
                payload_json="{}",
            )
        )

        self.assertEqual(storage.queue_depth(), 1)

    def test_records_message_and_observation_rows(self) -> None:
        storage = self.make_storage()
        storage.initialize()

        observation_id = storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id="ag01",
                kind="service_initialized",
                detail="test detail",
            )
        )
        event_id = storage.record_message_event(
            MessageEventRecord(
                msg_id="ops-test-0001",
                msg_type="ops_broadcast",
                source="ar01",
                source_site="a",
                channel="ops",
                captured_at="2026-04-26T10:00:00+00:00",
                observed_by="ag01",
                direction="rf_in",
                payload_json="{}",
                status="recorded",
            )
        )

        self.assertGreater(observation_id, 0)
        self.assertGreater(event_id, 0)

    def test_dedupe_cache_tracks_seen_message_ids(self) -> None:
        storage = self.make_storage()
        storage.initialize()

        storage.remember_seen_message(
            DedupeRecord(
                msg_id="ops-test-0001",
                source_path="mqtt:site-a->site-b",
                expires_at="2026-04-26T12:15:00+00:00",
            )
        )

        self.assertTrue(storage.has_seen_message("ops-test-0001"))
        self.assertFalse(storage.has_seen_message("ops-test-9999"))

    def test_pending_outbound_events_track_attempt_and_publish_state(self) -> None:
        storage = self.make_storage()
        storage.initialize()
        storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id="ops-test-0001",
                topic="mesh/v1/site-a/ops/up",
                payload_json='{"msg_id":"ops-test-0001"}',
            )
        )

        first_pending = storage.list_pending_outbound_events()
        self.assertEqual(len(first_pending), 1)
        self.assertEqual(first_pending[0]["attempt_count"], 0)
        self.assertEqual(first_pending[0]["status"], "pending")

        storage.mark_outbound_attempt("ops-test-0001")
        second_pending = storage.list_pending_outbound_events()
        self.assertEqual(second_pending[0]["attempt_count"], 1)
        self.assertEqual(second_pending[0]["status"], "retrying")

        storage.mark_outbound_published("ops-test-0001")
        self.assertEqual(storage.queue_depth(), 0)
        self.assertEqual(storage.list_pending_outbound_events(), [])

    def test_expired_outbound_events_leave_audit_row_but_exit_pending_queue(self) -> None:
        storage = self.make_storage()
        storage.initialize()
        storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id="ops-test-0002",
                topic="mesh/v1/site-a/ops/up",
                payload_json='{"msg_id":"ops-test-0002"}',
                expires_at="2026-04-26T12:15:00+00:00",
            )
        )

        storage.mark_outbound_expired("ops-test-0002")

        self.assertEqual(storage.queue_depth(), 0)
        self.assertEqual(storage.list_pending_outbound_events(), [])
