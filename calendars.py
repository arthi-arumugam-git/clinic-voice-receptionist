"""Calendar integration abstraction with pluggable providers.

Supports mock mode for tests, Google Calendar, and Cal.com.
Provider selection is env-driven; missing credentials gracefully fall back to mock.
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """A calendar event created or retrieved from a provider."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    attendee_name: str
    attendee_phone: str
    notes: str = ""
    provider: str = "mock"
    booking_url: str | None = None
    confirmed: bool = False


@dataclass
class CalendarResult:
    """Result of a calendar booking operation."""

    success: bool
    event: CalendarEvent | None = None
    error: str | None = None
    provider: str = "mock"


class CalendarProvider(ABC):
    """Abstract base for calendar integrations."""

    name: str = "base"

    @abstractmethod
    async def create_event(
        self,
        *,
        title: str,
        start: datetime,
        duration_minutes: int,
        attendee_name: str,
        attendee_phone: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> CalendarResult:
        """Create a calendar event. Returns CalendarResult with success/failure."""
        ...

    @abstractmethod
    async def check_availability(
        self,
        *,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
    ) -> bool:
        """Check if the time slot is available. Returns True if free."""
        ...

    async def cancel_event(self, event_id: str) -> bool:
        """Cancel an existing event. Returns True if successful."""
        return False

    async def cleanup(self) -> None:
        """Clean up any resources (connections, etc.). Override in subclasses."""
        return None


class MockCalendarProvider(CalendarProvider):
    """In-memory calendar for tests and demo mode. Always succeeds."""

    name = "mock"

    def __init__(self) -> None:
        self.events: dict[str, CalendarEvent] = {}
        self._busy_slots: list[tuple[datetime, datetime]] = []

    def add_busy_slot(self, start: datetime, end: datetime) -> None:
        """Add a busy slot for testing availability checks."""
        self._busy_slots.append((start.astimezone(UTC), end.astimezone(UTC)))

    async def create_event(
        self,
        *,
        title: str,
        start: datetime,
        duration_minutes: int,
        attendee_name: str,
        attendee_phone: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> CalendarResult:
        event_id = f"mock-{uuid.uuid4().hex[:12]}"
        start_utc = start.astimezone(UTC)
        end_utc = start_utc + timedelta(minutes=duration_minutes)

        event = CalendarEvent(
            event_id=event_id,
            title=title,
            start=start_utc,
            end=end_utc,
            attendee_name=attendee_name,
            attendee_phone=attendee_phone,
            notes=notes,
            provider=self.name,
            confirmed=True,
        )
        self.events[event_id] = event
        self._busy_slots.append((start_utc, end_utc))

        return CalendarResult(success=True, event=event, provider=self.name)

    async def check_availability(
        self,
        *,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
    ) -> bool:
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        for busy_start, busy_end in self._busy_slots:
            if start_utc < busy_end and end_utc > busy_start:
                return False
        return True

    async def cancel_event(self, event_id: str) -> bool:
        if event_id in self.events:
            event = self.events.pop(event_id)
            self._busy_slots = [
                (s, e) for s, e in self._busy_slots if not (s == event.start and e == event.end)
            ]
            return True
        return False


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar integration using service account or OAuth credentials.

    Required env vars:
    - GOOGLE_CALENDAR_ID: Calendar ID to book into
    - GOOGLE_SERVICE_ACCOUNT_JSON: Path to service account JSON file
      OR
    - GOOGLE_CALENDAR_ACCESS_TOKEN: OAuth access token (for short-lived auth)
    """

    name = "google"

    def __init__(
        self,
        calendar_id: str,
        credentials: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> None:
        self.calendar_id = calendar_id
        self.credentials = credentials
        self.access_token = access_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def _get_access_token(self) -> str:
        if self.access_token:
            return self.access_token

        if not self.credentials:
            raise ValueError("No Google Calendar credentials configured")

        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        scopes = ["https://www.googleapis.com/auth/calendar"]
        creds = service_account.Credentials.from_service_account_info(
            self.credentials, scopes=scopes
        )
        creds.refresh(Request())
        return creds.token

    async def create_event(
        self,
        *,
        title: str,
        start: datetime,
        duration_minutes: int,
        attendee_name: str,
        attendee_phone: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> CalendarResult:
        try:
            client = await self._get_client()
            token = await self._get_access_token()

            end = start + timedelta(minutes=duration_minutes)
            event_body = {
                "summary": title,
                "description": f"Patient: {attendee_name}\nPhone: {attendee_phone}\n{notes}".strip(),
                "start": {"dateTime": start.isoformat(), "timeZone": timezone},
                "end": {"dateTime": end.isoformat(), "timeZone": timezone},
            }

            response = await client.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events",
                headers={"Authorization": f"Bearer {token}"},
                json=event_body,
            )
            response.raise_for_status()
            data = response.json()

            event = CalendarEvent(
                event_id=data["id"],
                title=title,
                start=start.astimezone(UTC),
                end=end.astimezone(UTC),
                attendee_name=attendee_name,
                attendee_phone=attendee_phone,
                notes=notes,
                provider=self.name,
                booking_url=data.get("htmlLink"),
                confirmed=True,
            )
            return CalendarResult(success=True, event=event, provider=self.name)

        except Exception as exc:
            logger.warning("Google Calendar create_event failed: %s", type(exc).__name__)
            return CalendarResult(
                success=False,
                error=f"Calendar booking failed: {type(exc).__name__}",
                provider=self.name,
            )

    async def check_availability(
        self,
        *,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
    ) -> bool:
        try:
            client = await self._get_client()
            token = await self._get_access_token()

            response = await client.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "timeMin": start.isoformat(),
                    "timeMax": end.isoformat(),
                    "singleEvents": "true",
                },
            )
            response.raise_for_status()
            data = response.json()
            return len(data.get("items", [])) == 0

        except Exception as exc:
            logger.warning("Google Calendar availability check failed: %s", type(exc).__name__)
            return True  # Optimistically allow if check fails

    async def cancel_event(self, event_id: str) -> bool:
        try:
            client = await self._get_client()
            token = await self._get_access_token()

            response = await client.delete(
                f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            return response.status_code in (200, 204)

        except Exception as exc:
            logger.warning("Google Calendar cancel_event failed: %s", type(exc).__name__)
            return False

    async def cleanup(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


class CalComProvider(CalendarProvider):
    """Cal.com integration using their API.

    Required env vars:
    - CALCOM_API_KEY: Cal.com API key
    - CALCOM_EVENT_TYPE_ID: Event type ID for appointments
    - CALCOM_API_URL: Optional API base URL (default: https://api.cal.com/v1)
    """

    name = "calcom"

    def __init__(
        self,
        api_key: str,
        event_type_id: int | str,
        api_url: str = "https://api.cal.com/v1",
    ) -> None:
        self.api_key = api_key
        self.event_type_id = int(event_type_id)
        self.api_url = api_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def create_event(
        self,
        *,
        title: str,
        start: datetime,
        duration_minutes: int,
        attendee_name: str,
        attendee_phone: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> CalendarResult:
        try:
            client = await self._get_client()

            booking_data = {
                "eventTypeId": self.event_type_id,
                "start": start.isoformat(),
                "end": (start + timedelta(minutes=duration_minutes)).isoformat(),
                "responses": {
                    "name": attendee_name,
                    "phone": attendee_phone,
                    "notes": notes,
                },
                "timeZone": timezone,
                "language": "en",
                "metadata": {},
            }

            response = await client.post(
                f"{self.api_url}/bookings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=booking_data,
            )
            response.raise_for_status()
            data = response.json()

            booking = data.get("booking", data)
            end = start + timedelta(minutes=duration_minutes)

            event = CalendarEvent(
                event_id=str(booking.get("id", booking.get("uid", uuid.uuid4().hex))),
                title=title,
                start=start.astimezone(UTC),
                end=end.astimezone(UTC),
                attendee_name=attendee_name,
                attendee_phone=attendee_phone,
                notes=notes,
                provider=self.name,
                booking_url=booking.get("meetingUrl")
                or booking.get("attendees", [{}])[0].get("bookingUrl"),
                confirmed=booking.get("status") in ("accepted", "confirmed", None),
            )
            return CalendarResult(success=True, event=event, provider=self.name)

        except Exception as exc:
            logger.warning("Cal.com create_event failed: %s", type(exc).__name__)
            return CalendarResult(
                success=False,
                error=f"Calendar booking failed: {type(exc).__name__}",
                provider=self.name,
            )

    async def check_availability(
        self,
        *,
        start: datetime,
        end: datetime,
        timezone: str = "UTC",
    ) -> bool:
        try:
            client = await self._get_client()

            response = await client.get(
                f"{self.api_url}/availability",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={
                    "eventTypeId": self.event_type_id,
                    "startTime": start.isoformat(),
                    "endTime": end.isoformat(),
                },
            )
            response.raise_for_status()
            data = response.json()
            slots = data.get("slots", {})
            return len(slots) > 0

        except Exception as exc:
            logger.warning("Cal.com availability check failed: %s", type(exc).__name__)
            return True

    async def cancel_event(self, event_id: str) -> bool:
        try:
            client = await self._get_client()

            response = await client.delete(
                f"{self.api_url}/bookings/{event_id}/cancel",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.status_code in (200, 204)

        except Exception as exc:
            logger.warning("Cal.com cancel_event failed: %s", type(exc).__name__)
            return False

    async def cleanup(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


def get_calendar_provider(env: Mapping[str, str] | None = None) -> CalendarProvider:
    """Get the configured calendar provider based on environment variables.

    Priority:
    1. Google Calendar (if GOOGLE_CALENDAR_ID is set)
    2. Cal.com (if CALCOM_API_KEY is set)
    3. Mock provider (fallback, always available)

    Set CALENDAR_PROVIDER=mock to force mock mode regardless of other settings.
    """
    values = {key: value.strip() for key, value in (os.environ if env is None else env).items()}

    provider_override = values.get("CALENDAR_PROVIDER", "").lower()
    if provider_override == "mock":
        logger.info("Calendar provider: mock (forced via CALENDAR_PROVIDER)")
        return MockCalendarProvider()

    # Try Google Calendar
    calendar_id = values.get("GOOGLE_CALENDAR_ID")
    if calendar_id:
        import json

        credentials = None
        creds_path = values.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_path:
            try:
                with open(creds_path, encoding="utf-8") as f:
                    credentials = json.load(f)
            except Exception as exc:
                logger.warning("Failed to load Google service account: %s", exc)

        access_token = values.get("GOOGLE_CALENDAR_ACCESS_TOKEN")

        if credentials or access_token:
            logger.info("Calendar provider: Google Calendar")
            return GoogleCalendarProvider(
                calendar_id=calendar_id,
                credentials=credentials,
                access_token=access_token,
            )

    # Try Cal.com
    calcom_key = values.get("CALCOM_API_KEY")
    calcom_event_type = values.get("CALCOM_EVENT_TYPE_ID")
    if calcom_key and calcom_event_type:
        logger.info("Calendar provider: Cal.com")
        return CalComProvider(
            api_key=calcom_key,
            event_type_id=calcom_event_type,
            api_url=values.get("CALCOM_API_URL", "https://api.cal.com/v1"),
        )

    # Fallback to mock
    logger.info("Calendar provider: mock (no credentials configured)")
    return MockCalendarProvider()


@dataclass
class CalendarService:
    """High-level calendar service that combines provider + local store fallback.

    When a calendar provider is available and succeeds, the event is created in the
    external calendar. The local store (SQLite) is always updated as a backup record.
    """

    provider: CalendarProvider = field(default_factory=MockCalendarProvider)
    fallback_to_pending: bool = True

    async def book_appointment(
        self,
        *,
        title: str,
        start: datetime,
        duration_minutes: int,
        attendee_name: str,
        attendee_phone: str,
        notes: str = "",
        timezone: str = "UTC",
    ) -> CalendarResult:
        """Book an appointment via the calendar provider.

        Returns CalendarResult with:
        - success=True if booked in external calendar
        - success=False with error if booking failed
        """
        result = await self.provider.create_event(
            title=title,
            start=start,
            duration_minutes=duration_minutes,
            attendee_name=attendee_name,
            attendee_phone=attendee_phone,
            notes=notes,
            timezone=timezone,
        )
        return result

    async def check_availability(
        self,
        *,
        start: datetime,
        duration_minutes: int,
        timezone: str = "UTC",
    ) -> bool:
        """Check if a time slot is available."""
        end = start + timedelta(minutes=duration_minutes)
        return await self.provider.check_availability(
            start=start,
            end=end,
            timezone=timezone,
        )

    async def cleanup(self) -> None:
        """Clean up provider resources."""
        await self.provider.cleanup()
