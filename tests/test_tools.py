from datetime import UTC, datetime

import pytest

from config import ClinicConfig, load_config
from store import Store
from tools import TOOL_SCHEMAS, ClinicTools

NOW = datetime(2027, 1, 4, 13, tzinfo=UTC)  # Monday, 08:00 in New York.
REQUEST = dict(
    patient_name="Demo Patient",
    phone="+1 (415) 555-0100",
    service_id="cleaning",
    appointment_date="2027-01-04",
    appointment_time="10:00",
    confirmed=True,
)


@pytest.fixture
def clinic_tools():
    with Store(":memory:") as store:
        yield ClinicTools(load_config(), store, "server-call", now=lambda: NOW)


def test_hours_and_services(clinic_tools):
    hours = clinic_tools.dispatch("get_hours", {"day": "monday"})
    assert hours["hours"] == {"monday": {"open": "09:00", "close": "17:00"}}
    assert hours["timezone"] == "America/New_York"
    assert clinic_tools.dispatch("get_hours", {"day": "sunday"})["hours"]["sunday"] is None
    services = clinic_tools.dispatch("list_services")
    assert services["currency"] == "USD"
    assert services["services"][1]["id"] == "cleaning"


def test_booking_is_pending_consent_based_and_idempotent(clinic_tools):
    result = clinic_tools.dispatch("book_appointment", REQUEST)
    assert result["ok"] is True
    assert result["status"] == "pending_confirmation"
    assert result["appointment"]["phone"] == "+14155550100"
    assert result["appointment"]["starts_at"].startswith("2027-01-04T15:00:00")
    assert result["appointment"]["call_id"] == "server-call"
    assert (
        clinic_tools.dispatch("book_appointment", REQUEST)["appointment"]["id"]
        == result["appointment"]["id"]
    )
    assert len(clinic_tools.store.list_appointments()) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"confirmed": False},
        {"confirmed": "true"},
        {"confirmed": 1},
        {"service_id": "root_canal"},
        {"patient_name": " "},
        {"phone": "555"},
        {"phone": "15550100000 ext 2"},
        {"phone": 1234567890},
        {"appointment_date": "2027-01-03"},  # Past.
        {"appointment_date": "2027-01-09"},  # Closed Saturday.
        {"appointment_date": "2027-02-30"},
        {"appointment_time": "08:00"},
        {"appointment_time": "16:30"},
        {"appointment_time": "10:00:00"},
        {"appointment_date": "20270104"},
        {"call_id": "caller-controlled"},
        {"notes": None},
    ],
)
def test_invalid_booking_never_writes(clinic_tools, change):
    result = clinic_tools.dispatch("book_appointment", {**REQUEST, **change})
    assert result["ok"] is False
    assert clinic_tools.store.list_appointments() == []


def test_booking_must_be_strictly_future(clinic_tools):
    clinic_tools._now = lambda: datetime(2027, 1, 4, 15, tzinfo=UTC)
    assert clinic_tools.dispatch("book_appointment", REQUEST)["ok"] is False


def test_slot_collision_returns_recoverable_error(clinic_tools):
    clinic_tools.dispatch("book_appointment", REQUEST)
    other = ClinicTools(clinic_tools.config, clinic_tools.store, "other-call", now=lambda: NOW)
    result = other.dispatch("book_appointment", {**REQUEST, "appointment_time": "10:30"})
    assert result["error"] == "slot_unavailable"


def test_message_consent_and_idempotence(clinic_tools):
    args = dict(name="Demo", phone="+14155550100", message="Please call me about opening hours.")
    assert clinic_tools.dispatch("take_message", {**args, "confirmed": False})["ok"] is False
    assert clinic_tools.store.list_messages() == []
    result = clinic_tools.dispatch("take_message", {**args, "confirmed": True})
    assert result["ok"] is True
    assert result == clinic_tools.dispatch("take_message", {**args, "confirmed": True})
    assert len(clinic_tools.store.list_messages()) == 1


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("missing_tool", {}),
        ("get_hours", {"day": "Funday"}),
        ("get_hours", {"day": []}),
        ("list_services", {"extra": 1}),
        ("book_appointment", {}),
        ("get_hours", "not-an-object"),
    ],
)
def test_untrusted_arguments_return_errors(clinic_tools, name, arguments):
    assert clinic_tools.dispatch(name, arguments)["ok"] is False


def test_end_call_is_idempotent_and_leaves_actual_transport_finalization_to_bot(clinic_tools):
    result = clinic_tools.dispatch("end_call", {"reason": "Caller finished"})
    assert result["should_end"] is True
    assert clinic_tools.end_requested is True
    assert clinic_tools.dispatch("end_call", {"reason": "Retry"}) == result
    assert clinic_tools.dispatch("book_appointment", REQUEST)["error"] == "call_ending"
    assert clinic_tools.store.get_call_summary("server-call")["call"]["status"] == "active"


@pytest.mark.parametrize(
    ("date", "expected"), [("2027-03-14", "does not exist"), ("2027-11-07", "ambiguous")]
)
def test_clock_change_times_are_not_guessed(date, expected):
    data = load_config().model_dump()
    data["hours"]["sunday"] = {"open": "00:00", "close": "06:00"}
    with Store(":memory:") as store:
        logic = ClinicTools(ClinicConfig.model_validate(data), store, "dst", now=lambda: NOW)
        clock = "02:30" if "03-14" in date else "01:30"
        result = logic.dispatch(
            "book_appointment", {**REQUEST, "appointment_date": date, "appointment_time": clock}
        )
        assert result["ok"] is False
        assert expected in result["message"]


def test_tool_schemas_have_no_caller_controlled_session_id():
    assert {item["function"]["name"] for item in TOOL_SCHEMAS} == {
        "get_hours",
        "list_services",
        "book_appointment",
        "take_message",
        "escalate_urgent",
        "end_call",
    }
    for item in TOOL_SCHEMAS:
        parameters = item["function"]["parameters"]
        assert parameters["additionalProperties"] is False
        assert "call_id" not in parameters["properties"]


def test_real_duration_crossing_clock_change_still_fits_opening_hours():
    data = load_config().model_dump()
    data["hours"]["sunday"] = {"open": "00:00", "close": "03:00"}
    with Store(":memory:") as store:
        logic = ClinicTools(
            ClinicConfig.model_validate(data), store, "dst-duration", now=lambda: NOW
        )
        result = logic.dispatch(
            "book_appointment",
            {**REQUEST, "appointment_date": "2027-03-14", "appointment_time": "01:30"},
        )
        assert result["ok"] is False
        assert "full appointment" in result["message"]
        assert store.list_appointments() == []
