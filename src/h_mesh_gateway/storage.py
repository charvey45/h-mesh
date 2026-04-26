from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


SCHEMA_STATEMENTS = (
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
    gateway_id: str
    kind: str
    detail: str
    related_msg_id: str | None = None
    observed_at: str = ""

    def normalize(self) -> "GatewayObservationRecord":
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
    msg_id: str
    topic: str
    payload_json: str
    status: str = "pending"
    expires_at: str | None = None
    queued_at: str = ""

    def normalize(self) -> "OutboundQueueRecord":
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
class DedupeRecord:
    msg_id: str
    source_path: str
    expires_at: str
    first_seen_at: str = ""

    def normalize(self) -> "DedupeRecord":
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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
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

    def queue_depth(self) -> int:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS queue_depth
                FROM outbound_queue
                WHERE status IN ('pending', 'retrying')
                """
            ).fetchone()
        return int(row["queue_depth"])

    def remember_seen_message(self, record: DedupeRecord) -> None:
        normalized = record.normalize()
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

    def mark_outbound_attempt(
        self,
        msg_id: str,
        *,
        status: str = "retrying",
        attempted_at: str | None = None,
    ) -> None:
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
