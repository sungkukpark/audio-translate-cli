import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (or anywhere up the tree)
load_dotenv(dotenv_path=Path(__file__).parents[2] / ".env", override=False)

# Whisper defaults
DEFAULT_WHISPER_MODEL = "medium"
DEFAULT_SOURCE_LANGUAGE = "ru"
DEFAULT_TASK = "translate"

# ElevenLabs defaults
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George (English, clear, neutral)


def get_elevenlabs_api_key() -> str | None:
    return os.getenv("ELEVENLABS_API_KEY")
