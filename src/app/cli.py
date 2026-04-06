import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="translate-audio",
        description="Translate Russian MP3 audio files to English text using Whisper.",
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
        default="small",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model to use (default: small)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "auto"],
        help="Device for inference (default: cpu)",
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Prefix for output filenames (default: input filename stem)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show Whisper transcription progress",
    )
    return parser.parse_args(argv)
