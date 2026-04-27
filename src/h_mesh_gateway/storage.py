from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    # Store all timestamps in UTC ISO 8601 so logs, SQLite records, and JSON payloads line up cleanly.
    return datetime.now(timezone.utc).isoformat()


def parse_iso_timestamp(value: str) -> datetime:
    # Normalize timestamps to timezone-aware UTC values before comparing them.
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


SCHEMA_STATEMENTS = (
    # message_events is the historical record of traffic the gateway observed or relayed.
    """
    CREATE TABLE IF NOT EXISTS message_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id TEXT NOT NULL,
        msg_type TEXT NOT NULL,
        source TEXT NOT NULL,
        source_site TEXT NOT NULL,
        target TEXT,
        target_scope TEXT,
        channel TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        observed_by TEXT NOT NULL,
        direction TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL,
        stored_at TEXT NOT NULL
    )
    """,
    # gateway_observations captures notable events such as duplicate suppression,
    # publish failures, timeouts, and successful emits.
    """
    CREATE TABLE IF NOT EXISTS gateway_observations (
        observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_id TEXT NOT NULL,
        observed_at TEXT NOT NULL,
        kind TEXT NOT NULL,
        detail TEXT NOT NULL,
        related_msg_id TEXT
    )
    """,
    # gateway_health_snapshots stores the operator-facing state view used by the dashboard.
    """
    CREATE TABLE IF NOT EXISTS gateway_health_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        gateway_id TEXT NOT NULL,
        site_code TEXT NOT NULL,
        process_state TEXT NOT NULL,
        broker_state TEXT NOT NULL,
        radio_state TEXT NOT NULL,
        queue_depth INTEGER NOT NULL,
        topic TEXT NOT NULL,
        delivery_state TEXT NOT NULL,
        observed_at TEXT NOT NULL
    )
    """,
    # outbound_queue is the durable replay path for traffic that should reach MQTT.
    """
    CREATE TABLE IF NOT EXISTS outbound_queue (
        queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id TEXT NOT NULL UNIQUE,
        topic TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        queued_at TEXT NOT NULL,
        expires_at TEXT,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        status TEXT NOT NULL
    )
    """,
    # dedupe_cache bounds replay loops and duplicate reinjection across the bridge.
    """
    CREATE TABLE IF NOT EXISTS dedupe_cache (
        msg_id TEXT PRIMARY KEY,
        first_seen_at TEXT NOT NULL,
        source_path TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
)


@dataclass(slots=True)
class MessageEventRecord:
    # This record shape closely mirrors the normalized application protocol envelope plus
    # gateway-specific observation metadata.
    msg_id: str
    msg_type: str
    source: str
    source_site: str
    channel: str
    captured_at: str
    observed_by: str
    direction: str
    payload_json: str
    status: str
    target: str | None = None
    target_scope: str | None = None


@dataclass(slots=True)
class GatewayObservationRecord:
    # Observations are intentionally free-form enough to capture operator-relevant events
    # without needing a schema migration for every new detail string.
    gateway_id: str
    kind: str
    detail: str
    related_msg_id: str | None = None
    observed_at: str = ""

    def normalize(self) -> "GatewayObservationRecord":
        # Fill in observed_at lazily so callers can supply a specific timestamp only when needed.
        if self.observed_at:
            return self
        return GatewayObservationRecord(
            gateway_id=self.gateway_id,
            kind=self.kind,
            detail=self.detail,
            related_msg_id=self.related_msg_id,
            observed_at=utc_now_iso(),
        )


@dataclass(slots=True)
class OutboundQueueRecord:
    # Outbound queue records model the broker delivery work that may need to survive restarts.
    msg_id: str
    topic: str
    payload_json: str
    status: str = "pending"
    expires_at: str | None = None
    queued_at: str = ""

    def normalize(self) -> "OutboundQueueRecord":
        # queued_at defaults to "now" when the caller is simply enqueueing fresh work.
        if self.queued_at:
            return self
        return OutboundQueueRecord(
            msg_id=self.msg_id,
            topic=self.topic,
            payload_json=self.payload_json,
            status=self.status,
            expires_at=self.expires_at,
            queued_at=utc_now_iso(),
        )


@dataclass(slots=True)
class GatewayHealthSnapshotRecord:
    # Health snapshots are stored locally even if broker publication later fails.
    gateway_id: str
    site_code: str
    process_state: str
    broker_state: str
    radio_state: str
    queue_depth: int
    topic: str
    delivery_state: str
    observed_at: str = ""

    def normalize(self) -> "GatewayHealthSnapshotRecord":
        # Like the other record types, default timestamps are filled in at write time.
        if self.observed_at:
            return self
        return GatewayHealthSnapshotRecord(
            gateway_id=self.gateway_id,
            site_code=self.site_code,
            process_state=self.process_state,
            broker_state=self.broker_state,
            radio_state=self.radio_state,
            queue_depth=self.queue_depth,
            topic=self.topic,
            delivery_state=self.delivery_state,
            observed_at=utc_now_iso(),
        )


@dataclass(slots=True)
class DedupeRecord:
    # The dedupe cache remembers a message id long enough to prevent replay loops but not forever.
    msg_id: str
    source_path: str
    expires_at: str
    first_seen_at: str = ""

    def normalize(self) -> "DedupeRecord":
        # first_seen_at defaults to the local write time when not supplied by the caller.
        if self.first_seen_at:
            return self
        return DedupeRecord(
            msg_id=self.msg_id,
            source_path=self.source_path,
            expires_at=self.expires_at,
            first_seen_at=utc_now_iso(),
        )


class GatewayStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        # Create the parent directory on demand so a clean gateway host can bootstrap itself.
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        # Use a short-lived connection per operation. That keeps the storage layer simple and
        # avoids sharing one SQLite handle across unrelated CLI runs or tests.
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> list[str]:
        with self._connection() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()
            rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def record_message_event(self, record: MessageEventRecord) -> int:
        # Message events are append-only historical records.
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO message_events (
                    msg_id,
                    msg_type,
                    source,
                    source_site,
                    target,
                    target_scope,
                    channel,
                    captured_at,
                    observed_by,
                    direction,
                    payload_json,
                    status,
                    stored_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.msg_id,
                    record.msg_type,
                    record.source,
                    record.source_site,
                    record.target,
                    record.target_scope,
                    record.channel,
                    record.captured_at,
                    record.observed_by,
                    record.direction,
                    record.payload_json,
                    record.status,
                    utc_now_iso(),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def record_gateway_observation(self, record: GatewayObservationRecord) -> int:
        normalized = record.normalize()
        # Normalize before insert so observed_at is always present in storage.
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO gateway_observations (
                    gateway_id,
                    observed_at,
                    kind,
                    detail,
                    related_msg_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalized.gateway_id,
                    normalized.observed_at,
                    normalized.kind,
                    normalized.detail,
                    normalized.related_msg_id,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def enqueue_outbound_event(self, record: OutboundQueueRecord) -> int:
        normalized = record.normalize()
        # Queue records are inserted before broker publish so a replay path already exists on failure.
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO outbound_queue (
                    msg_id,
                    topic,
                    payload_json,
                    queued_at,
                    expires_at,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized.msg_id,
                    normalized.topic,
                    normalized.payload_json,
                    normalized.queued_at,
                    normalized.expires_at,
                    normalized.status,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def record_gateway_health_snapshot(self, record: GatewayHealthSnapshotRecord) -> int:
        normalized = record.normalize()
        # Health snapshots are append-only so operators can inspect historical state transitions later.
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO gateway_health_snapshots (
                    gateway_id,
                    site_code,
                    process_state,
                    broker_state,
                    radio_state,
                    queue_depth,
                    topic,
                    delivery_state,
                    observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized.gateway_id,
                    normalized.site_code,
                    normalized.process_state,
                    normalized.broker_state,
                    normalized.radio_state,
                    normalized.queue_depth,
                    normalized.topic,
                    normalized.delivery_state,
                    normalized.observed_at,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def queue_depth(self) -> int:
        # Only count work that still needs broker delivery attention.
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS queue_depth
                FROM outbound_queue
                WHERE status IN ('pending', 'retrying')
                """
            ).fetchone()
        return int(row["queue_depth"])

    def queue_status_counts(self) -> dict[str, int]:
        # This powers dashboard summary cards and gives operators a quick queue-state breakdown.
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS status_count
                FROM outbound_queue
                GROUP BY status
                ORDER BY status ASC
                """
            ).fetchall()
        return {str(row["status"]): int(row["status_count"]) for row in rows}

    def remember_seen_message(self, record: DedupeRecord) -> None:
        normalized = record.normalize()
        # Update expiry on conflict so a re-observed message can extend its suppression window.
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO dedupe_cache (
                    msg_id,
                    first_seen_at,
                    source_path,
                    expires_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(msg_id) DO UPDATE SET
                    source_path = excluded.source_path,
                    expires_at = excluded.expires_at
                """,
                (
                    normalized.msg_id,
                    normalized.first_seen_at,
                    normalized.source_path,
                    normalized.expires_at,
                ),
            )
            connection.commit()

    def has_seen_message(self, msg_id: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT expires_at
                FROM dedupe_cache
                WHERE msg_id = ?
                LIMIT 1
                """,
                (msg_id,),
            ).fetchone()
            if row is None:
                return False
            # Expired de-dupe entries should not suppress new traffic, so prune them as they are noticed.
            if parse_iso_timestamp(str(row["expires_at"])) <= datetime.now(timezone.utc):
                connection.execute(
                    """
                    DELETE FROM dedupe_cache
                    WHERE msg_id = ?
                    """,
                    (msg_id,),
                )
                connection.commit()
                return False
        return True

    def list_pending_outbound_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        # Pending and retrying are the queue states that still need operational attention.
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    queue_id,
                    msg_id,
                    topic,
                    payload_json,
                    queued_at,
                    expires_at,
                    attempt_count,
                    last_attempt_at,
                    status
                FROM outbound_queue
                WHERE status IN ('pending', 'retrying')
                ORDER BY queue_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_gateway_health(self) -> dict[str, Any] | None:
        # The dashboard usually wants only the latest state view for each database.
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    gateway_id,
                    site_code,
                    process_state,
                    broker_state,
                    radio_state,
                    queue_depth,
                    topic,
                    delivery_state,
                    observed_at
                FROM gateway_health_snapshots
                ORDER BY observed_at DESC
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else dict(row)

    def list_gateway_health_snapshots(self, *, limit: int = 100) -> list[dict[str, Any]]:
        # Historical snapshots back queue-depth graphs and timeline inspection.
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    gateway_id,
                    site_code,
                    process_state,
                    broker_state,
                    radio_state,
                    queue_depth,
                    topic,
                    delivery_state,
                    observed_at
                FROM gateway_health_snapshots
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_recent_gateway_observations(
        self,
        *,
        limit: int = 100,
        kinds: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        # Optional kind filtering keeps the dashboard focused on the subset of observations it is summarizing.
        with self._connection() as connection:
            if kinds:
                placeholders = ",".join("?" for _ in kinds)
                rows = connection.execute(
                    f"""
                    SELECT
                        observation_id,
                        gateway_id,
                        observed_at,
                        kind,
                        detail,
                        related_msg_id
                    FROM gateway_observations
                    WHERE kind IN ({placeholders})
                    ORDER BY observed_at DESC
                    LIMIT ?
                    """,
                    (*kinds, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        observation_id,
                        gateway_id,
                        observed_at,
                        kind,
                        detail,
                        related_msg_id
                    FROM gateway_observations
                    ORDER BY observed_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def count_gateway_observations_by_kind(self) -> dict[str, int]:
        # Counting by kind is cheaper for dashboards than pulling every observation row.
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT kind, COUNT(*) AS kind_count
                FROM gateway_observations
                GROUP BY kind
                ORDER BY kind ASC
                """
            ).fetchall()
        return {str(row["kind"]): int(row["kind_count"]) for row in rows}

    def list_recent_message_events(
        self,
        *,
        limit: int = 100,
        channels: tuple[str, ...] | None = None,
        msg_types: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        # Build the WHERE clause dynamically so callers can filter by channel, type, both, or neither.
        where_clauses: list[str] = []
        params: list[Any] = []

        if channels:
            where_clauses.append(",".join("channel = ?" for _ in channels))
            params.extend(channels)
        if msg_types:
            where_clauses.append(",".join("msg_type = ?" for _ in msg_types))
            params.extend(msg_types)

        where_sql = ""
        if where_clauses:
            normalized = [f"({clause.replace(',', ' OR ')})" for clause in where_clauses]
            where_sql = f"WHERE {' AND '.join(normalized)}"

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    event_id,
                    msg_id,
                    msg_type,
                    source,
                    source_site,
                    target,
                    target_scope,
                    channel,
                    captured_at,
                    observed_by,
                    direction,
                    payload_json,
                    status,
                    stored_at
                FROM message_events
                {where_sql}
                ORDER BY captured_at DESC, event_id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_outbound_attempt(
        self,
        msg_id: str,
        *,
        status: str = "retrying",
        attempted_at: str | None = None,
    ) -> None:
        # Every publish attempt increments the counter so replay and failure analysis can see churn.
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE outbound_queue
                SET attempt_count = attempt_count + 1,
                    last_attempt_at = ?,
                    status = ?
                WHERE msg_id = ?
                """,
                (attempted_at or utc_now_iso(), status, msg_id),
            )
            connection.commit()

    def mark_outbound_published(self, msg_id: str, *, published_at: str | None = None) -> None:
        # A freshly published record should show at least one attempt even if it succeeded on the first try.
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE outbound_queue
                SET attempt_count = CASE
                        WHEN attempt_count = 0 THEN 1
                        ELSE attempt_count
                    END,
                    last_attempt_at = ?,
                    status = 'published'
                WHERE msg_id = ?
                """,
                (published_at or utc_now_iso(), msg_id),
            )
            connection.commit()

    def mark_outbound_expired(self, msg_id: str) -> None:
        # Expiration is modeled as a terminal queue state rather than deleting the row outright.
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE outbound_queue
                SET status = 'expired'
                WHERE msg_id = ?
                """,
                (msg_id,),
            )
            connection.commit()
