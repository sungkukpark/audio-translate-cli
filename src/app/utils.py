import shutil
import sys
from pathlib import Path

from app.errors import DependencyError, ValidationError

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4"}


def validate_input_file(path: Path) -> None:
    if not path.exists():
        raise ValidationError(f"Input file not found: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported input format '{path.suffix}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "ffmpeg is not installed or not available on PATH.\n"
            "Whisper requires ffmpeg to decode audio files.\n"
            "Install it from https://ffmpeg.org/download.html"
        )


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def ensure_elevenlabs_api_key(api_key: str | None) -> str:
    if not api_key:
        raise DependencyError(
            "ELEVENLABS_API_KEY is not set.\n"
            "Add it to your .env file or set it as an environment variable.\n"
            "Get a key at https://elevenlabs.io"
        )
    return api_key
