"""Signed Twilio webhook + bidirectional Media Streams WebSocket server."""

import asyncio
import logging
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from settings import ROOT, env_value, public_origin, require_voice_settings

load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)
app = FastAPI(title="Clinic voice receptionist", docs_url=None, redoc_url=None)


def twilio_settings() -> tuple[str, str]:
    origin = public_origin()
    token = env_value("TWILIO_AUTH_TOKEN")
    if not token or not env_value("TWILIO_ACCOUNT_SID"):
        raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required for phone mode")
    return origin, token


def valid_signature(
    url: str, params, signature: str | None, token: str, *, websocket=False
) -> bool:
    if not signature:
        return False
    validator = RequestValidator(token)
    urls = [url, url.rstrip("/") + "/"] if websocket else [url]
    return any(validator.validate(candidate, params, signature) for candidate in urls)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "clinic-voice-receptionist"}


@app.post("/twiml")
async def twiml(request: Request):
    try:
        origin, token = twilio_settings()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    params = await request.form()
    url = origin + "/twiml" + ("?" + request.url.query if request.url.query else "")
    if not valid_signature(url, params, request.headers.get("x-twilio-signature"), token):
        raise HTTPException(403, "Invalid Twilio signature")
    if params.get("AccountSid") != env_value("TWILIO_ACCOUNT_SID"):
        raise HTTPException(403, "Unexpected Twilio account")
    if not re.fullmatch(r"CA[0-9a-fA-F]{32}", str(params.get("CallSid", ""))):
        raise HTTPException(400, "Missing or invalid CallSid")
    try:
        require_voice_settings()
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=origin.replace("https://", "wss://", 1) + "/ws")
    response.append(connect)
    response.hangup()
    return Response(str(response), media_type="application/xml")


@app.websocket("/ws")
async def media_stream(websocket: WebSocket):
    try:
        origin, token = twilio_settings()
    except ValueError:
        await websocket.close(code=1008)
        return
    stream_url = origin.replace("https://", "wss://", 1) + "/ws"
    if websocket.url.query:
        stream_url += "?" + websocket.url.query
    if not valid_signature(
        stream_url, {}, websocket.headers.get("x-twilio-signature"), token, websocket=True
    ):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        # Lazy imports keep webhook tests network-free and startup lightweight.
        from pipecat.runner.types import WebSocketRunnerArguments
        from pipecat.runner.utils import parse_telephony_websocket

        from bot import bot

        # Bound the initial handshake. create_transport reuses the cached parse.
        provider, call_data = await asyncio.wait_for(parse_telephony_websocket(websocket), 10)
        if provider != "twilio" or not call_data.call_id or not call_data.stream_id:
            await websocket.close(code=1008)
            return
        args = WebSocketRunnerArguments(websocket=websocket, call_data=call_data)
        await bot(args)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Phone session ended with %s", type(exc).__name__)
    finally:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()


if __name__ == "__main__":
    import uvicorn

    from bot import configure_logging

    configure_logging()
    twilio_settings()
    require_voice_settings()
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
