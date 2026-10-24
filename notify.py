"""Best-effort post-call notifications. No credentials means no network requests."""

import asyncio
import logging
import os
import smtplib
import ssl
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def format_summary(summary: dict[str, Any], clinic_name: str, *, details: bool = False) -> str:
    """Deterministic summary of saved outcomes; never sends a raw transcript."""
    call = summary["call"]
    appointments = summary["appointments"]
    messages = summary["messages"]
    lines = [
        f"{clinic_name}: call {call['call_id']}",
        f"Status: {call['status']}",
        f"Appointment requests: {len(appointments)} (clinic confirmation required)",
        f"Messages: {len(messages)}",
    ]
    if details:
        for item in appointments:
            lines.append(
                f"Request: {item['patient_name']} | {item['phone']} | "
                f"{item['service_id']} | {item['starts_at']}"
            )
        for item in messages:
            lines.append(f"Message: {item['name']} | {item['phone']} | {item['message']}")
    else:
        lines.append("Review the local clinic database for details.")
    return "\n".join(lines)


def _send_smtp(env: Mapping[str, str], recipient: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = env["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    security = env.get("SMTP_SECURITY", "starttls").strip().lower()
    if security not in {"ssl", "starttls"}:
        raise ValueError("SMTP_SECURITY must be ssl or starttls")
    context = ssl.create_default_context()
    port = int(env.get("SMTP_PORT", "465" if security == "ssl" else "587"))
    if security == "ssl":
        connection = smtplib.SMTP_SSL(env["SMTP_HOST"], port, timeout=10, context=context)
    else:
        connection = smtplib.SMTP(env["SMTP_HOST"], port, timeout=10)
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        if env.get("SMTP_USERNAME"):
            smtp.login(env["SMTP_USERNAME"], env.get("SMTP_PASSWORD", ""))
        smtp.send_message(message)


async def send_summary(
    summary: dict[str, Any],
    clinic_name: str,
    *,
    env: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, str]:
    """Send to configured clinic staff only. Errors never fail the completed call.

    Email prefers Resend over SMTP. Return a status per channel without logging
    message contents, credentials, or provider response bodies.
    """
    values = {key: value.strip() for key, value in (os.environ if env is None else env).items()}
    status = {"sms": "skipped", "email": "skipped"}
    body = format_summary(
        summary,
        clinic_name,
        details=values.get("NOTIFY_INCLUDE_DETAILS", "false").lower() == "true",
    )
    subject = f"{clinic_name}: receptionist call summary"
    sms_keys = (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "CLINIC_NOTIFY_PHONE",
    )
    async with httpx.AsyncClient(timeout=10, transport=transport) as client:
        if all(values.get(key) for key in sms_keys):
            try:
                sid = values["TWILIO_ACCOUNT_SID"]
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    auth=(sid, values["TWILIO_AUTH_TOKEN"]),
                    data={
                        "From": values["TWILIO_PHONE_NUMBER"],
                        "To": values["CLINIC_NOTIFY_PHONE"],
                        "Body": body[:1500],
                    },
                )
                response.raise_for_status()
                status["sms"] = "sent"
            except Exception as exc:
                status["sms"] = "failed"
                logger.warning("SMS summary failed (%s)", type(exc).__name__)
        recipient = values.get("CLINIC_NOTIFY_EMAIL")
        if recipient:
            try:
                if values.get("RESEND_API_KEY") and values.get("RESEND_FROM_EMAIL"):
                    response = await client.post(
                        "https://api.resend.com/emails",
                        headers={"Authorization": f"Bearer {values['RESEND_API_KEY']}"},
                        json={
                            "from": values["RESEND_FROM_EMAIL"],
                            "to": [recipient],
                            "subject": subject,
                            "text": body,
                        },
                    )
                    response.raise_for_status()
                    status["email"] = "sent"
                elif values.get("SMTP_HOST") and values.get("SMTP_FROM"):
                    await asyncio.to_thread(_send_smtp, values, recipient, subject, body)
                    status["email"] = "sent"
            except Exception as exc:
                status["email"] = "failed"
                logger.warning("Email summary failed (%s)", type(exc).__name__)
    return status
