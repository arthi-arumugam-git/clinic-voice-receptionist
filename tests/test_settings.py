import pytest

from settings import public_origin, require_voice_settings


@pytest.mark.parametrize(
    "value",
    [
        "",
        "http://localhost:8000",
        "https://demo.example/path",
        "https://u:p@demo.example",
        "https://demo.example/?x=1",
    ],
)
def test_public_origin_rejects_ambiguous_or_insecure_urls(value):
    with pytest.raises(ValueError):
        public_origin({"PUBLIC_BASE_URL": value})


def test_voice_settings_are_provider_specific():
    env = {
        "DEEPGRAM_API_KEY": "fake",
        "OPENAI_API_KEY": "fake",
        "TTS_PROVIDER": "elevenlabs",
        "ELEVENLABS_API_KEY": "fake",
        "ELEVENLABS_VOICE_ID": "fake",
    }
    require_voice_settings(env)
    del env["ELEVENLABS_VOICE_ID"]
    with pytest.raises(ValueError, match="ELEVENLABS_VOICE_ID"):
        require_voice_settings(env)
