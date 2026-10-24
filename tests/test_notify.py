import json
from unittest.mock import patch

import httpx
import pytest

from notify import format_summary, send_summary


@pytest.fixture
def summary():
    return {
        "call": {"call_id": "demo-call", "status": "completed"},
        "appointments": [
            {
                "patient_name": "Alex Demo",
                "phone": "+15555550123",
                "service_id": "cleaning",
                "starts_at": "2030-10-28T14:00:00+00:00",
            }
        ],
        "messages": [
            {"name": "Alex Demo", "phone": "+15555550123", "message": "Please call tomorrow."}
        ],
    }


def test_default_summary_omits_personal_details(summary):
    body = format_summary(summary, "Demo Clinic")
    assert "Appointment requests: 1" in body
    assert "Messages: 1" in body
    assert "Alex" not in body
    assert "1555" not in body
    assert "tomorrow" not in body
    assert "Alex Demo" in format_summary(summary, "Demo Clinic", details=True)


async def test_absent_keys_skip_without_requests(summary):
    def reject(request):
        pytest.fail("A missing notification configuration must not make a request")

    result = await send_summary(
        summary, "Demo Clinic", env={}, transport=httpx.MockTransport(reject)
    )
    assert result == {"sms": "skipped", "email": "skipped"}


async def test_sms_failure_does_not_prevent_email(summary):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "api.twilio.com":
            return httpx.Response(503, text="temporary provider error")
        assert json.loads(request.content)["to"] == ["staff@example.com"]
        return httpx.Response(200, json={"id": "email-test"})

    result = await send_summary(
        summary,
        "Demo Clinic",
        env={
            "TWILIO_ACCOUNT_SID": "ACtest",
            "TWILIO_AUTH_TOKEN": "not-real",
            "TWILIO_PHONE_NUMBER": "+15555550100",
            "CLINIC_NOTIFY_PHONE": "+15555550101",
            "CLINIC_NOTIFY_EMAIL": "staff@example.com",
            "RESEND_API_KEY": "not-real",
            "RESEND_FROM_EMAIL": "bot@example.com",
        },
        transport=httpx.MockTransport(respond),
    )
    assert result == {"sms": "failed", "email": "sent"}
    assert len(requests) == 2


async def test_smtp_uses_tls_and_configured_staff_destination(summary):
    with patch("notify.smtplib.SMTP") as smtp:
        result = await send_summary(
            summary,
            "Demo Clinic",
            env={
                "SMTP_HOST": "smtp.example.com",
                "SMTP_FROM": "bot@example.com",
                "SMTP_USERNAME": "bot",
                "SMTP_PASSWORD": "not-real",
                "CLINIC_NOTIFY_EMAIL": "staff@example.com",
            },
        )
        connection = smtp.return_value.__enter__.return_value
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with("bot", "not-real")
        message = connection.send_message.call_args.args[0]
        assert message["To"] == "staff@example.com"
        assert result == {"sms": "skipped", "email": "sent"}


async def test_email_exception_is_nonfatal(summary):
    with patch("notify._send_smtp", side_effect=OSError("offline")):
        result = await send_summary(
            summary,
            "Demo Clinic",
            env={
                "SMTP_HOST": "smtp.example.com",
                "SMTP_FROM": "bot@example.com",
                "CLINIC_NOTIFY_EMAIL": "staff@example.com",
            },
        )
    assert result["email"] == "failed"
