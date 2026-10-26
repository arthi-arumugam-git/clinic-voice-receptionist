"""Tests for urgency detection and escalation features."""

from datetime import UTC, datetime

import httpx
import pytest

from config import load_config
from notify import format_escalation, send_escalation_alert
from store import Store
from tools import TOOL_SCHEMAS, ClinicTools, detect_urgency

NOW = datetime(2027, 1, 4, 13, tzinfo=UTC)


@pytest.fixture
def clinic_tools():
    with Store(":memory:") as store:
        yield ClinicTools(load_config(), store, "test-call", now=lambda: NOW)


class TestUrgencyDetection:
    @pytest.mark.parametrize(
        "text,expected_urgent",
        [
            ("I'm having chest pain", True),
            ("This is an emergency", True),
            ("I need help urgently", True),
            ("Someone is choking", True),
            ("I can't breathe", True),
            ("Call 911", True),
            ("Call 999", True),
            ("I think I'm having a heart attack", True),
            ("I need a dental cleaning", False),
            ("What are your hours?", False),
            ("I'd like to book an appointment", False),
        ],
    )
    def test_detect_urgency(self, text, expected_urgent):
        is_urgent, keyword = detect_urgency(text)
        assert is_urgent == expected_urgent
        if expected_urgent:
            assert keyword is not None


class TestEscalationTool:
    def test_escalate_urgent_schema_exists(self):
        schemas = {s["function"]["name"] for s in TOOL_SCHEMAS}
        assert "escalate_urgent" in schemas

    def test_escalate_urgent_success(self, clinic_tools):
        result = clinic_tools.dispatch(
            "escalate_urgent",
            {
                "caller_phone": "+14155550100",
                "reason": "Chest pain",
                "urgency_level": "emergency",
            },
        )

        assert result["ok"] is True
        assert result["status"] == "escalated"
        assert result["urgency_level"] == "emergency"
        assert "emergency services" in result["next_step"]
        assert clinic_tools.escalation_sent is True

    def test_escalate_urgent_stores_in_database(self, clinic_tools):
        clinic_tools.dispatch(
            "escalate_urgent",
            {
                "caller_phone": "+14155550100",
                "reason": "Severe allergic reaction",
                "urgency_level": "emergency",
            },
        )

        escalations = clinic_tools.store.list_escalations("test-call")
        assert len(escalations) == 1
        assert escalations[0]["reason"] == "Severe allergic reaction"
        assert escalations[0]["urgency_level"] == "emergency"

    def test_escalate_urgent_invalid_level(self, clinic_tools):
        result = clinic_tools.dispatch(
            "escalate_urgent",
            {
                "caller_phone": "+14155550100",
                "reason": "Test",
                "urgency_level": "low",
            },
        )

        assert result["ok"] is False
        assert "urgency_level" in result["message"]

    def test_escalate_urgent_high_priority(self, clinic_tools):
        result = clinic_tools.dispatch(
            "escalate_urgent",
            {
                "caller_phone": "+14155550100",
                "reason": "Need callback today",
                "urgency_level": "high_priority",
            },
        )

        assert result["ok"] is True
        assert "contact" in result["next_step"].lower() or "callback" in result["next_step"].lower()

    def test_escalate_urgent_triggers_callback(self):
        escalations_received = []

        def on_escalation(escalation):
            escalations_received.append(escalation)

        with Store(":memory:") as store:
            tools = ClinicTools(
                load_config(),
                store,
                "callback-test",
                now=lambda: NOW,
                on_escalation=on_escalation,
            )
            tools.dispatch(
                "escalate_urgent",
                {
                    "caller_phone": "+14155550100",
                    "reason": "Urgent callback needed",
                    "urgency_level": "urgent",
                },
            )

        assert len(escalations_received) == 1
        assert escalations_received[0]["reason"] == "Urgent callback needed"
        assert escalations_received[0]["caller_phone"] == "+14155550100"

    def test_escalate_blocked_after_end_call(self, clinic_tools):
        clinic_tools.dispatch("end_call", {"reason": "Emergency handled"})

        result = clinic_tools.dispatch(
            "escalate_urgent",
            {
                "caller_phone": "+14155550100",
                "reason": "Test",
                "urgency_level": "urgent",
            },
        )

        assert result["ok"] is False
        assert result["error"] == "call_ending"


class TestEscalationNotification:
    def test_format_escalation_emergency(self):
        escalation = {
            "caller_phone": "+14155550100",
            "reason": "Chest pain",
            "urgency_level": "emergency",
            "timestamp": "2027-01-04T13:00:00+00:00",
            "emergency_numbers": ["911", "999"],
        }

        text = format_escalation(escalation, "Test Clinic")

        assert "EMERGENCY" in text
        assert "+14155550100" in text
        assert "Chest pain" in text
        assert "911, 999" in text

    def test_format_escalation_urgent(self):
        escalation = {
            "caller_phone": "+14155550100",
            "reason": "Needs same-day appointment",
            "urgency_level": "urgent",
        }

        text = format_escalation(escalation, "Test Clinic")

        assert "URGENT" in text
        assert "same-day" in text

    async def test_send_escalation_alert_skipped_without_credentials(self):
        escalation = {
            "caller_phone": "+14155550100",
            "reason": "Test",
            "urgency_level": "urgent",
        }

        def reject(request):
            pytest.fail("Should not make requests without credentials")

        result = await send_escalation_alert(
            escalation,
            "Test Clinic",
            env={},
            transport=httpx.MockTransport(reject),
        )

        assert result == {"sms": "skipped", "email": "skipped"}

    async def test_send_escalation_alert_sends_sms(self):
        escalation = {
            "caller_phone": "+14155550100",
            "reason": "Emergency test",
            "urgency_level": "emergency",
        }

        requests_made = []

        def respond(request):
            requests_made.append(request)
            return httpx.Response(200, json={"sid": "SM123"})

        result = await send_escalation_alert(
            escalation,
            "Test Clinic",
            env={
                "TWILIO_ACCOUNT_SID": "ACtest",
                "TWILIO_AUTH_TOKEN": "token",
                "TWILIO_PHONE_NUMBER": "+15555550100",
                "CLINIC_NOTIFY_PHONE": "+15555550101",
            },
            transport=httpx.MockTransport(respond),
        )

        assert result["sms"] == "sent"
        assert len(requests_made) == 1
        assert "EMERGENCY" in requests_made[0].content.decode()


class TestStoreEscalation:
    def test_create_and_list_escalations(self):
        with Store(":memory:") as store:
            store.create_call("call-1")

            esc = store.create_escalation(
                call_id="call-1",
                caller_phone="+14155550100",
                reason="Emergency test",
                urgency_level="emergency",
            )

            assert esc["reason"] == "Emergency test"
            assert esc["urgency_level"] == "emergency"

            escalations = store.list_escalations("call-1")
            assert len(escalations) == 1

    def test_escalation_idempotent(self):
        with Store(":memory:") as store:
            store.create_call("call-1")

            first = store.create_escalation(
                call_id="call-1",
                caller_phone="+14155550100",
                reason="Same emergency",
                urgency_level="emergency",
            )

            second = store.create_escalation(
                call_id="call-1",
                caller_phone="+14155550100",
                reason="Same emergency",
                urgency_level="emergency",
            )

            assert first["id"] == second["id"]
            assert len(store.list_escalations()) == 1

    def test_call_summary_includes_escalations(self):
        with Store(":memory:") as store:
            store.create_call("call-1")
            store.create_escalation(
                call_id="call-1",
                caller_phone="+14155550100",
                reason="Test",
                urgency_level="urgent",
            )
            store.finish_call("call-1", "completed")

            summary = store.get_call_summary("call-1")
            assert "escalations" in summary
            assert len(summary["escalations"]) == 1
