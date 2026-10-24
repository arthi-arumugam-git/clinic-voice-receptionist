import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from server import app

ORIGIN = "https://demo.example.com"
TOKEN = "fake-test-token"
ACCOUNT = "AC" + "1" * 32


@pytest.fixture
def client(monkeypatch):
    for key, value in {
        "PUBLIC_BASE_URL": ORIGIN,
        "TWILIO_AUTH_TOKEN": TOKEN,
        "TWILIO_ACCOUNT_SID": ACCOUNT,
        "DEEPGRAM_API_KEY": "fake",
        "OPENAI_API_KEY": "fake",
        "CARTESIA_API_KEY": "fake",
        "CARTESIA_VOICE_ID": "fake",
        "TTS_PROVIDER": "cartesia",
    }.items():
        monkeypatch.setenv(key, value)
    return TestClient(app)


def test_health_does_not_require_provider_calls(client):
    assert client.get("/health").json()["status"] == "ok"


def test_unsigned_webhook_rejected(client):
    assert client.post("/twiml", data={"CallSid": "CA" + "2" * 32}).status_code == 403


def test_signed_twiml_has_bidirectional_stream_and_hangup(client):
    params = {"CallSid": "CA" + "2" * 32, "AccountSid": ACCOUNT, "From": "+15555550123"}
    signature = RequestValidator(TOKEN).compute_signature(ORIGIN + "/twiml", params)
    response = client.post(
        "/twiml",
        data=params,
        headers={"X-Twilio-Signature": signature, "Host": "untrusted.invalid"},
    )
    assert response.status_code == 200
    root = ET.fromstring(response.text)
    assert root.find("Connect/Stream").attrib["url"] == "wss://demo.example.com/ws"
    assert root.find("Hangup") is not None


def test_modified_signed_payload_rejected(client):
    params = {"CallSid": "CA" + "2" * 32, "AccountSid": ACCOUNT}
    signature = RequestValidator(TOKEN).compute_signature(ORIGIN + "/twiml", params)
    params["From"] = "+15555550123"
    assert (
        client.post("/twiml", data=params, headers={"X-Twilio-Signature": signature}).status_code
        == 403
    )


def test_unsigned_websocket_rejected_before_session(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws"):
            pytest.fail("Unsigned websocket must not be accepted")
    assert exc.value.code == 1008


def test_websocket_signature_uses_public_wss_url(client):
    from server import valid_signature

    url = "wss://demo.example.com/ws"
    signed = RequestValidator(TOKEN).compute_signature(url, {})
    assert valid_signature(url, {}, signed, TOKEN, websocket=True)
    slash = RequestValidator(TOKEN).compute_signature(url + "/", {})
    assert valid_signature(url, {}, slash, TOKEN, websocket=True)
    assert not valid_signature(url, {}, "forged", TOKEN, websocket=True)
