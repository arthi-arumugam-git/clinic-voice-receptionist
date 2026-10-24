"""Network-free business tools, with schemas usable by any LLM adapter."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from config import WEEKDAYS, ClinicConfig
from store import SlotUnavailable, Store


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


TOOL_SCHEMAS = [
    _schema(
        "get_hours",
        "Get clinic opening hours in the clinic's local timezone.",
        {
            "day": {
                "type": "string",
                "enum": list(WEEKDAYS),
                "description": "Optional weekday; omit for the full week.",
            },
        },
        [],
    ),
    _schema(
        "list_services",
        "List offered services, service IDs, prices and durations. Prices do not guarantee insurance coverage.",
        {},
        [],
    ),
    _schema(
        "book_appointment",
        "Save a LOCAL appointment REQUEST pending staff confirmation. Read back details and obtain explicit consent before confirmed=true. This does not book a live clinic calendar.",
        {
            "patient_name": {"type": "string", "description": "Caller-provided patient name."},
            "phone": {
                "type": "string",
                "description": "Caller-provided callback phone, including country code when available.",
            },
            "service_id": {"type": "string", "description": "An ID from list_services."},
            "appointment_date": {
                "type": "string",
                "description": "Clinic-local date in YYYY-MM-DD, confirmed with the caller.",
            },
            "appointment_time": {
                "type": "string",
                "description": "Clinic-local time in 24-hour HH:MM, confirmed with the caller.",
            },
            "confirmed": {
                "type": "boolean",
                "description": "True only after the caller explicitly consents to saving the read-back details.",
            },
            "notes": {
                "type": "string",
                "description": "Optional brief administrative note. Do not request clinical details.",
            },
        },
        [
            "patient_name",
            "phone",
            "service_id",
            "appointment_date",
            "appointment_time",
            "confirmed",
        ],
    ),
    _schema(
        "take_message",
        "Save a brief administrative message for clinic staff after explicit caller consent. Never solicit medical history or symptoms.",
        {
            "name": {"type": "string"},
            "phone": {"type": "string"},
            "message": {"type": "string"},
            "confirmed": {
                "type": "boolean",
                "description": "True only after reading back the message and callback details and obtaining permission to save.",
            },
        },
        ["name", "phone", "message", "confirmed"],
    ),
    _schema(
        "end_call",
        "End after saying a brief goodbye or giving emergency instructions. Do not claim to have transferred or dispatched help.",
        {
            "reason": {
                "type": "string",
                "description": "Brief administrative reason, without sensitive clinical details.",
            },
        },
        [],
    ),
]


def _text(value: Any, field: str, maximum: int = 120, minimum: int = 1) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{field} must be text between {minimum} and {maximum} characters")
    return value.strip()


def _phone(value: Any) -> str:
    value = _text(value, "phone", maximum=40)
    if not re.fullmatch(r"\+?[0-9() .-]+", value):
        raise ValueError(
            "phone must be a callback number using digits and optional +, spaces, parentheses or hyphens"
        )
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        raise ValueError("phone must contain 7 to 15 digits")
    return ("+" if value.startswith("+") else "") + digits


class ClinicTools:
    """One instance per call; the model never chooses or changes the call ID."""

    def __init__(
        self,
        config: ClinicConfig,
        store: Store,
        call_id: str,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.config, self.store, self.call_id = config, store, call_id
        self._zone = ZoneInfo(config.timezone)
        self._now = now or (lambda: datetime.now(UTC))
        self.end_requested = False
        self.end_reason: str | None = None
        store.create_call(call_id)

    def dispatch(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return JSON-safe success/errors for untrusted model-supplied arguments."""
        schema = next(
            (item["function"] for item in TOOL_SCHEMAS if item["function"]["name"] == name), None
        )
        if schema is None:
            return {"ok": False, "error": "unknown_tool", "message": "That tool is not available."}
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return {
                "ok": False,
                "error": "invalid_arguments",
                "message": "Tool arguments must be an object.",
            }
        parameters = schema["parameters"]
        if set(arguments) - set(parameters["properties"]) or set(parameters["required"]) - set(
            arguments
        ):
            return {
                "ok": False,
                "error": "invalid_arguments",
                "message": "Arguments contain unknown fields or omit required fields.",
            }
        if self.end_requested and name in {"book_appointment", "take_message"}:
            return {
                "ok": False,
                "error": "call_ending",
                "message": "The call is ending; no more details can be saved.",
            }
        try:
            return {"ok": True, **getattr(self, name)(**arguments)}
        except SlotUnavailable as exc:
            return {"ok": False, "error": "slot_unavailable", "message": str(exc)}
        except (ValueError, TypeError, OverflowError) as exc:
            return {"ok": False, "error": "invalid_arguments", "message": str(exc)}
        except sqlite3.Error:
            return {
                "ok": False,
                "error": "storage_unavailable",
                "message": "The request could not be saved. Please ask the caller to contact clinic staff.",
            }

    def get_hours(self, day: str | None = None) -> dict[str, Any]:
        if day is not None and day not in WEEKDAYS:
            raise ValueError("day must be a lowercase weekday name")
        days = [day] if day else WEEKDAYS
        return {
            "clinic_name": self.config.name,
            "timezone": self.config.timezone,
            "hours": {
                key: self.config.hours[key].model_dump() if self.config.hours[key] else None
                for key in days
            },
            "note": "Regular hours only; staff must confirm holidays and actual availability.",
        }

    def list_services(self) -> dict[str, Any]:
        return {
            "currency": self.config.currency,
            "services": [service.model_dump() for service in self.config.services],
            "note": "Listed prices are estimates; staff must confirm pricing and insurance coverage.",
        }

    def book_appointment(
        self,
        patient_name: str,
        phone: str,
        service_id: str,
        appointment_date: str,
        appointment_time: str,
        confirmed: bool,
        notes: str = "",
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError(
                "Explicit caller consent is required; read back the details and ask before saving."
            )
        patient_name, phone = _text(patient_name, "patient_name"), _phone(phone)
        service_id = _text(service_id, "service_id", maximum=80)
        service = next((item for item in self.config.services if item.id == service_id), None)
        if service is None:
            raise ValueError("Unknown service_id; use list_services to see available services.")
        notes = _text(notes, "notes", maximum=500, minimum=0)
        appointment_date = _text(appointment_date, "appointment_date", maximum=10)
        appointment_time = _text(appointment_time, "appointment_time", maximum=5)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", appointment_date) or not re.fullmatch(
            r"\d{2}:\d{2}", appointment_time
        ):
            raise ValueError("Use YYYY-MM-DD for the date and HH:MM for the time.")
        naive = datetime.fromisoformat(f"{appointment_date}T{appointment_time}")
        start = naive.replace(tzinfo=self._zone)
        # A round trip detects clock-change gaps; differing valid folds indicate
        # ambiguous local times that should be clarified instead of guessed.
        roundtrip = start.astimezone(UTC).astimezone(self._zone)
        if roundtrip.replace(tzinfo=None) != naive:
            raise ValueError(
                "That local time does not exist because of a clock change. Choose another time."
            )
        alternate = start.replace(fold=1)
        if start.utcoffset() != alternate.utcoffset():
            raise ValueError(
                "That local time is ambiguous because of a clock change. Choose another time."
            )
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("The booking clock must be timezone-aware.")
        if start <= now:
            raise ValueError("Appointment requests must be in the future.")
        hours = self.config.hours[WEEKDAYS[start.weekday()]]
        if hours is None:
            raise ValueError("The clinic is closed that day. Use get_hours to choose another day.")
        opening = datetime.combine(start.date(), time.fromisoformat(hours.open), self._zone)
        closing = datetime.combine(start.date(), time.fromisoformat(hours.close), self._zone)
        end = (start.astimezone(UTC) + timedelta(minutes=service.duration_minutes)).astimezone(
            self._zone
        )
        if start < opening or end > closing:
            raise ValueError("The full appointment must fit within clinic opening hours.")
        appointment = self.store.create_appointment(
            call_id=self.call_id,
            patient_name=patient_name,
            phone=phone,
            service_id=service_id,
            starts_at=start,
            duration_minutes=service.duration_minutes,
            notes=notes,
        )
        return {
            "status": "pending_confirmation",
            "appointment": appointment,
            "local_start": start.isoformat(),
            "timezone": self.config.timezone,
            "message": "Appointment request saved locally, pending confirmation by clinic staff. This is not a confirmed booking.",
        }

    def take_message(self, name: str, phone: str, message: str, confirmed: bool) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError(
                "Explicit caller consent is required before saving the message and callback details."
            )
        saved = self.store.create_message(
            call_id=self.call_id,
            name=_text(name, "name"),
            phone=_phone(phone),
            message=_text(message, "message", maximum=2000),
        )
        return {
            "status": "saved",
            "message": saved,
            "note": "Message saved for staff; delivery and response are not guaranteed.",
        }

    def end_call(self, reason: str = "Caller finished the conversation") -> dict[str, Any]:
        reason = _text(reason, "reason", maximum=500)
        if not self.end_requested:
            self.end_requested, self.end_reason = True, reason
        return {"status": "ending", "should_end": True, "reason": self.end_reason}
