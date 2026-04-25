from __future__ import annotations

import unittest

from h_mesh_gateway.health import BrokerState, ProcessState, RadioState, initial_health_snapshot


class HealthTests(unittest.TestCase):
    def test_initial_health_snapshot_defaults(self) -> None:
        health = initial_health_snapshot("ag01", "a")

        self.assertEqual(health.gateway_id, "ag01")
        self.assertEqual(health.process_state, ProcessState.STARTING)
        self.assertEqual(health.radio_state, RadioState.UNKNOWN)
        self.assertEqual(health.broker_state, BrokerState.UNKNOWN)

    def test_state_update_changes_timestamp_and_values(self) -> None:
        health = initial_health_snapshot("ag01", "a")
        updated = health.with_states(
            process_state=ProcessState.READY,
            radio_state=RadioState.MISSING,
            broker_state=BrokerState.DISCONNECTED,
            queue_depth=2,
        )

        self.assertEqual(updated.process_state, ProcessState.READY)
        self.assertEqual(updated.radio_state, RadioState.MISSING)
        self.assertEqual(updated.broker_state, BrokerState.DISCONNECTED)
        self.assertEqual(updated.queue_depth, 2)
        self.assertGreaterEqual(updated.observed_at, health.observed_at)
