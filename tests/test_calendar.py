"""Tests for calendar integration module."""

from datetime import UTC, datetime, timedelta

import pytest

from calendars import (
    CalComProvider,
    CalendarEvent,
    CalendarResult,
    CalendarService,
    MockCalendarProvider,
    get_calendar_provider,
)

NOW = datetime(2027, 1, 4, 13, tzinfo=UTC)
START = NOW + timedelta(hours=2)


@pytest.fixture
def mock_provider():
    return MockCalendarProvider()


@pytest.fixture
def calendar_service(mock_provider):
    return CalendarService(provider=mock_provider)


async def test_mock_provider_creates_event(mock_provider):
    result = await mock_provider.create_event(
        title="Dental Cleaning",
        start=START,
        duration_minutes=60,
        attendee_name="Test Patient",
        attendee_phone="+14155550100",
        notes="First visit",
        timezone="America/New_York",
    )

    assert result.success is True
    assert result.event is not None
    assert result.event.title == "Dental Cleaning"
    assert result.event.attendee_name == "Test Patient"
    assert result.event.provider == "mock"
    assert result.event.confirmed is True
    assert result.event.event_id.startswith("mock-")


async def test_mock_provider_availability_check(mock_provider):
    assert (
        await mock_provider.check_availability(
            start=START,
            end=START + timedelta(hours=1),
        )
        is True
    )

    await mock_provider.create_event(
        title="Existing Appointment",
        start=START,
        duration_minutes=60,
        attendee_name="Another Patient",
        attendee_phone="+14155550101",
    )

    assert (
        await mock_provider.check_availability(
            start=START,
            end=START + timedelta(hours=1),
        )
        is False
    )

    assert (
        await mock_provider.check_availability(
            start=START + timedelta(hours=1),
            end=START + timedelta(hours=2),
        )
        is True
    )


async def test_mock_provider_cancel_event(mock_provider):
    result = await mock_provider.create_event(
        title="To Cancel",
        start=START,
        duration_minutes=30,
        attendee_name="Patient",
        attendee_phone="+14155550100",
    )

    assert result.event is not None
    event_id = result.event.event_id

    assert len(mock_provider.events) == 1
    assert await mock_provider.cancel_event(event_id) is True
    assert len(mock_provider.events) == 0

    assert await mock_provider.cancel_event("nonexistent") is False


async def test_calendar_service_book_appointment(calendar_service):
    result = await calendar_service.book_appointment(
        title="General Consultation",
        start=START,
        duration_minutes=30,
        attendee_name="John Doe",
        attendee_phone="+14155550100",
        notes="Follow-up",
        timezone="America/New_York",
    )

    assert result.success is True
    assert result.event is not None
    assert result.event.title == "General Consultation"


async def test_calendar_service_check_availability(calendar_service):
    assert (
        await calendar_service.check_availability(
            start=START,
            duration_minutes=60,
        )
        is True
    )

    await calendar_service.book_appointment(
        title="Booked Slot",
        start=START,
        duration_minutes=60,
        attendee_name="Someone",
        attendee_phone="+14155550100",
    )

    assert (
        await calendar_service.check_availability(
            start=START,
            duration_minutes=60,
        )
        is False
    )


def test_get_calendar_provider_mock_fallback():
    provider = get_calendar_provider(env={})
    assert isinstance(provider, MockCalendarProvider)


def test_get_calendar_provider_mock_forced():
    provider = get_calendar_provider(
        env={
            "CALENDAR_PROVIDER": "mock",
            "GOOGLE_CALENDAR_ID": "test@calendar.google.com",
        }
    )
    assert isinstance(provider, MockCalendarProvider)


def test_get_calendar_provider_google_without_credentials():
    provider = get_calendar_provider(
        env={
            "GOOGLE_CALENDAR_ID": "test@calendar.google.com",
        }
    )
    assert isinstance(provider, MockCalendarProvider)


def test_get_calendar_provider_calcom_configured():
    provider = get_calendar_provider(
        env={
            "CALCOM_API_KEY": "test-key",
            "CALCOM_EVENT_TYPE_ID": "123",
        }
    )
    assert isinstance(provider, CalComProvider)
    assert provider.api_key == "test-key"
    assert provider.event_type_id == 123


def test_calendar_event_dataclass():
    event = CalendarEvent(
        event_id="test-123",
        title="Test Event",
        start=START,
        end=START + timedelta(hours=1),
        attendee_name="Test",
        attendee_phone="+1234567890",
    )
    assert event.event_id == "test-123"
    assert event.provider == "mock"
    assert event.confirmed is False


def test_calendar_result_success():
    event = CalendarEvent(
        event_id="test-123",
        title="Test",
        start=START,
        end=START + timedelta(hours=1),
        attendee_name="Test",
        attendee_phone="+1234567890",
    )
    result = CalendarResult(success=True, event=event)
    assert result.success is True
    assert result.event is not None
    assert result.error is None


def test_calendar_result_failure():
    result = CalendarResult(success=False, error="API error")
    assert result.success is False
    assert result.event is None
    assert result.error == "API error"


async def test_mock_provider_busy_slots(mock_provider):
    mock_provider.add_busy_slot(START, START + timedelta(hours=1))

    assert (
        await mock_provider.check_availability(
            start=START,
            end=START + timedelta(hours=1),
        )
        is False
    )

    assert (
        await mock_provider.check_availability(
            start=START + timedelta(hours=2),
            end=START + timedelta(hours=3),
        )
        is True
    )


async def test_calendar_service_cleanup(calendar_service):
    await calendar_service.cleanup()
