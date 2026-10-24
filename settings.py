"""Environment validation; importing modules never requires credentials."""

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def env_value(name: str, default: str = "", env: Mapping[str, str] | None = None) -> str:
    return (os.environ if env is None else env).get(name, default).strip()


def require_voice_settings(env: Mapping[str, str] | None = None) -> None:
    provider = env_value("TTS_PROVIDER", "cartesia", env)
    if provider not in {"cartesia", "elevenlabs"}:
        raise ValueError("TTS_PROVIDER must be cartesia or elevenlabs")
    names = ["DEEPGRAM_API_KEY", "OPENAI_API_KEY"]
    names += (
        ["CARTESIA_API_KEY", "CARTESIA_VOICE_ID"]
        if provider == "cartesia"
        else ["ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"]
    )
    missing = [name for name in names if not env_value(name, env=env)]
    if missing:
        raise ValueError("Missing voice settings: " + ", ".join(missing) + ". See .env.example.")


def public_origin(env: Mapping[str, str] | None = None) -> str:
    value = env_value("PUBLIC_BASE_URL", env=env).rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("PUBLIC_BASE_URL must be an HTTPS origin, e.g. https://demo.example.com")
    return value


def local_path(name: str, default: str) -> Path:
    path = Path(env_value(name, default)).expanduser()
    return path if path.is_absolute() else ROOT / path


def max_call_seconds() -> int:
    value = int(env_value("MAX_CALL_SECONDS", "600"))
    if not 30 <= value <= 3600:
        raise ValueError("MAX_CALL_SECONDS must be between 30 and 3600")
    return value
