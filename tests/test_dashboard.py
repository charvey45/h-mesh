from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from h_mesh_gateway.dashboard import ManagementRepository, render_dashboard_html
from h_mesh_gateway.storage import (
    GatewayHealthSnapshotRecord,
    GatewayObservationRecord,
    GatewayStorage,
    MessageEventRecord,
    OutboundQueueRecord,
)


class DashboardTests(unittest.TestCase):
    def make_state_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_management_snapshot_aggregates_gateway_state_and_failures(self) -> None:
        state_dir = self.make_state_dir()
        db_path = state_dir / "ag01-queue.sqlite3"
        storage = GatewayStorage(db_path)
        storage.initialize()
        storage.enqueue_outbound_event(
            OutboundQueueRecord(
                msg_id="ops-test-0001",
                topic="mesh/v1/site-a/ops/up",
                payload_json="{}",
            )
        )
        storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id="ag01",
                kind="publish_failed",
                detail="broker unavailable",
                observed_at="2026-04-26T18:45:00+00:00",
            )
        )
        storage.record_gateway_observation(
            GatewayObservationRecord(
                gateway_id="ag01",
                kind="service_initialized",
                detail="startup",
                observed_at="2026-04-26T18:44:00+00:00",
            )
        )
        storage.record_message_event(
            MessageEventRecord(
                msg_id="sensor-as01-0001",
                msg_type="sensor_report",
                source="as01",
                source_site="a",
                channel="sensor",
                captured_at="2026-04-26T18:44:30+00:00",
                observed_by="ag01",
                direction="rf_in",
                payload_json=(
                    '{"payload":{"sensor_set":"clock","metrics":['
                    '{"name":"epoch_s","value":1714157070,"unit":"s"},'
                    '{"name":"second_of_minute","value":30,"unit":"s"}]}}'
                ),
                status="recorded",
            )
        )
        storage.record_gateway_health_snapshot(
            GatewayHealthSnapshotRecord(
                gateway_id="ag01",
                site_code="a",
                process_state="ready",
                broker_state="disconnected",
                radio_state="healthy",
                queue_depth=1,
                topic="mesh/v1/site-a/gateway/ag01/state",
                delivery_state="local_only",
                observed_at="2026-04-26T18:45:00+00:00",
            )
        )

        repo = ManagementRepository(state_dir=state_dir)
        snapshot = repo.management_snapshot()

        self.assertEqual(snapshot["gateway_count"], 1)
        self.assertEqual(snapshot["queue_depth_total"], 1)
        self.assertEqual(snapshot["queue_status_totals"]["pending"], 1)
        self.assertEqual(snapshot["failure_counts"]["publish_failed"], 1)
        self.assertNotIn("service_initialized", snapshot["failure_counts"])
        self.assertEqual(snapshot["gateways"][0]["gateway_id"], "ag01")
        self.assertEqual(snapshot["recent_failures"][0]["kind"], "publish_failed")
        self.assertEqual(snapshot["recent_sensor_events"][0]["source"], "as01")
        self.assertEqual(snapshot["recent_sensor_events"][0]["sensor_set"], "clock")

    def test_recent_logs_reads_latest_lines(self) -> None:
        state_dir = self.make_state_dir()
        log_path = state_dir / "ag01.log"
        log_path.write_text("line1\nline2\nline3\n", encoding="utf-8")

        repo = ManagementRepository(state_dir=state_dir)
        logs = repo.recent_logs(max_lines=2)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["lines"], ["line2", "line3"])

    def test_render_dashboard_html_includes_metrics_and_logs(self) -> None:
        snapshot = {
            "gateway_count": 1,
            "queue_depth_total": 2,
            "queue_status_totals": {"pending": 1, "retrying": 1},
            "failure_counts": {"publish_failed": 2, "gateway_state_publish_failed": 1},
            "gateways": [
                {
                    "gateway_id": "ag01",
                    "site_code": "a",
                    "process_state": "ready",
                    "broker_state": "connected",
                    "radio_state": "healthy",
                    "queue_depth": 2,
                    "delivery_state": "published",
                    "observed_at": "2026-04-26T18:45:00+00:00",
                    "queue_depth_points": [0, 1, 2],
                }
            ],
            "recent_failures": [
                {
                    "observed_at": "2026-04-26T18:45:00+00:00",
                    "gateway_id": "ag01",
                    "kind": "publish_failed",
                    "detail": "broker unavailable",
                }
            ],
            "recent_sensor_events": [
                {
                    "captured_at": "2026-04-26T18:45:00+00:00",
                    "source": "as01",
                    "sensor_set": "clock",
                    "metric_summary": "epoch_s=1714157100s, second_of_minute=0s",
                    "observed_by": "ag01",
                }
            ],
        }
        html = render_dashboard_html(
            snapshot,
            [{"name": "ag01.log", "lines": ["line1", "line2"]}],
        )

        self.assertIn("h-mesh management dashboard", html)
        self.assertIn("publish_failed", html)
        self.assertIn("line1", html)
        self.assertIn("Recent sensor traffic", html)
        self.assertIn("second_of_minute", html)
