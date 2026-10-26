"""Small SQLite persistence layer. No patient records or audio are required."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


class SlotUnavailable(ValueError):
    """An existing local request overlaps the requested interval."""


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class Store:
    """Thread-safe connection with atomic, single-capacity appointment requests.

    This is deliberately not a scheduling-system integration. Pending requests
    reserve local demo capacity until staff reconcile them outside this demo.
    """

    def __init__(self, db_path: str | Path = "data/clinic.sqlite3") -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(db_path), timeout=15, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS calls (
                call_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                end_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL REFERENCES calls(call_id),
                patient_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                service_id TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending_confirmation',
                calendar_event_id TEXT,
                calendar_provider TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(call_id, service_id, starts_at)
            );
            CREATE INDEX IF NOT EXISTS appointments_interval
                ON appointments(starts_at, ends_at);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL REFERENCES calls(call_id),
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(call_id, name, phone, message)
            );
            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT NOT NULL REFERENCES calls(call_id),
                caller_phone TEXT NOT NULL,
                reason TEXT NOT NULL,
                urgency_level TEXT NOT NULL,
                notified_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(call_id, caller_phone, reason)
            );
        """)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def create_call(self, call_id: str | None = None) -> dict[str, Any]:
        call_id = call_id or str(uuid.uuid4())
        if not isinstance(call_id, str) or not call_id.strip():
            raise ValueError("call_id must be a non-empty string")
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO calls(call_id, started_at) VALUES (?, ?)",
                (call_id, _utc_text(datetime.now(UTC))),
            )
            return dict(
                self._db.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
            )

    def finish_call(
        self, call_id: str, status: str = "completed", reason: str | None = None
    ) -> dict[str, Any]:
        if status not in {"completed", "disconnected", "error", "timeout"}:
            raise ValueError("status must be completed, disconnected, error, or timeout")
        with self._lock, self._db:
            self._db.execute(
                "UPDATE calls SET ended_at = ?, status = ?, end_reason = ? "
                "WHERE call_id = ? AND ended_at IS NULL",
                (_utc_text(datetime.now(UTC)), status, reason, call_id),
            )
            row = self._db.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
            if row is None:
                raise ValueError("unknown call_id")
            return dict(row)

    def create_appointment(
        self,
        *,
        call_id: str,
        patient_name: str,
        phone: str,
        service_id: str,
        starts_at: datetime,
        duration_minutes: int,
        notes: str = "",
    ) -> dict[str, Any]:
        if (
            isinstance(duration_minutes, bool)
            or not isinstance(duration_minutes, int)
            or duration_minutes <= 0
        ):
            raise ValueError("duration_minutes must be a positive integer")
        start = _utc_text(starts_at)
        end = _utc_text(starts_at.astimezone(UTC) + timedelta(minutes=duration_minutes))
        with self._lock:
            try:
                # The write lock spans the availability check and insertion, even
                # when two independent server connections use the same database.
                self._db.execute("BEGIN IMMEDIATE")
                existing = self._db.execute(
                    "SELECT * FROM appointments WHERE call_id = ? AND service_id = ? AND starts_at = ?",
                    (call_id, service_id, start),
                ).fetchone()
                if existing is not None:
                    self._db.commit()
                    return dict(existing)
                conflict = self._db.execute(
                    "SELECT id FROM appointments WHERE status = 'pending_confirmation' "
                    "AND starts_at < ? AND ends_at > ? LIMIT 1",
                    (end, start),
                ).fetchone()
                if conflict is not None:
                    raise SlotUnavailable(
                        "That time overlaps an existing request. Please choose another time."
                    )
                cursor = self._db.execute(
                    "INSERT INTO appointments(call_id,patient_name,phone,service_id,starts_at,ends_at,notes,created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        call_id,
                        patient_name,
                        phone,
                        service_id,
                        start,
                        end,
                        notes,
                        _utc_text(datetime.now(UTC)),
                    ),
                )
                row = self._db.execute(
                    "SELECT * FROM appointments WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
                self._db.commit()
                return dict(row)
            except Exception:
                self._db.rollback()
                raise

    def create_message(
        self,
        *,
        call_id: str,
        name: str,
        phone: str,
        message: str,
    ) -> dict[str, Any]:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO messages(call_id,name,phone,message,created_at) VALUES (?,?,?,?,?)",
                (call_id, name, phone, message, _utc_text(datetime.now(UTC))),
            )
            return dict(
                self._db.execute(
                    "SELECT * FROM messages WHERE call_id = ? AND name = ? AND phone = ? AND message = ?",
                    (call_id, name, phone, message),
                ).fetchone()
            )

    def create_escalation(
        self,
        *,
        call_id: str,
        caller_phone: str,
        reason: str,
        urgency_level: str,
    ) -> dict[str, Any]:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO escalations(call_id,caller_phone,reason,urgency_level,created_at) "
                "VALUES (?,?,?,?,?)",
                (call_id, caller_phone, reason, urgency_level, _utc_text(datetime.now(UTC))),
            )
            return dict(
                self._db.execute(
                    "SELECT * FROM escalations WHERE call_id = ? AND caller_phone = ? AND reason = ?",
                    (call_id, caller_phone, reason),
                ).fetchone()
            )

    def update_appointment_calendar(
        self,
        appointment_id: int,
        *,
        calendar_event_id: str,
        calendar_provider: str,
        status: str = "confirmed",
    ) -> dict[str, Any]:
        """Update an appointment with calendar event details after successful booking."""
        with self._lock, self._db:
            self._db.execute(
                "UPDATE appointments SET calendar_event_id = ?, calendar_provider = ?, status = ? "
                "WHERE id = ?",
                (calendar_event_id, calendar_provider, status, appointment_id),
            )
            row = self._db.execute(
                "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
            ).fetchone()
            if row is None:
                raise ValueError("unknown appointment_id")
            return dict(row)

    def list_escalations(self, call_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM escalations"
                + (" WHERE call_id = ?" if call_id is not None else "")
                + " ORDER BY id",
                (call_id,) if call_id is not None else (),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_appointments(self, call_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT * FROM appointments"
            rows = self._db.execute(
                query
                + (" WHERE call_id = ?" if call_id is not None else "")
                + " ORDER BY starts_at, id",
                (call_id,) if call_id is not None else (),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_messages(self, call_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM messages"
                + (" WHERE call_id = ?" if call_id is not None else "")
                + " ORDER BY id",
                (call_id,) if call_id is not None else (),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_call_summary(self, call_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
            if row is None:
                raise ValueError("unknown call_id")
            return {
                "call": dict(row),
                "appointments": self.list_appointments(call_id),
                "messages": self.list_messages(call_id),
                "escalations": self.list_escalations(call_id),
            }
