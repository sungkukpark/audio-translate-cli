import shutil
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4"}


def validate_input_file(path: Path) -> None:
    if not path.exists():
        print(f"Error: Input file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        print(
            f"Error: Unsupported input format '{path.suffix}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            file=sys.stderr,
        )
        sys.exit(1)


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        print(
            "Error: ffmpeg is not installed or not available on PATH.\n"
            "Whisper requires ffmpeg to decode audio files.\n"
            "Install it from https://ffmpeg.org/download.html",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
