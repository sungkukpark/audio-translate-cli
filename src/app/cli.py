import argparse
from pathlib import Path

from app import config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="translate-audio",
        description="Translate Russian MP3 audio to English text and speech using Whisper + ElevenLabs.",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Path to the input audio file (.mp3, .wav, .m4a, .mp4)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("outputs"),
        help="Directory to save output files (default: outputs/)",
    )
    parser.add_argument(
        "--model", "-m",
        default=config.DEFAULT_WHISPER_MODEL,
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help=f"Whisper model to use (default: {config.DEFAULT_WHISPER_MODEL})",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        choices=["cpu", "cuda", "auto"],
        help="Device for Whisper inference (default: cuda)",
    )
    parser.add_argument(
        "--voice-id",
        default=config.DEFAULT_VOICE_ID,
        help=f"ElevenLabs voice ID (default: {config.DEFAULT_VOICE_ID})",
    )
    parser.add_argument(
        "--tts-model",
        default=config.DEFAULT_TTS_MODEL,
        help=f"ElevenLabs TTS model ID (default: {config.DEFAULT_TTS_MODEL})",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Prefix for output filenames (default: input filename stem)",
    )
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Run Whisper translation only; skip ElevenLabs synthesis",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress including Whisper segment output",
    )
    return parser.parse_args(argv)
