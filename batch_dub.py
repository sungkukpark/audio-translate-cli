"""
Batch synthesize time-aligned English MP3s from translated *.json files.

Reads *.json translation files from --source (the OUT folder), synthesizes
each segment individually with ElevenLabs, pads with silence to match original
timestamps, and writes a single synchronized *.mp3 per file to --output-root
(OUT_2), mirroring the source directory tree.

Usage:
    uv run python batch_dub.py [--source <dir>] [--output-root <dir>] [--overwrite]

Defaults:
    --source       D:/Dropbox/Lectures/CGMA/[CGMA 3D] - Level Design for Games/OUT
    --output-root  D:/Dropbox/Lectures/CGMA/[CGMA 3D] - Level Design for Games/OUT_2
    --voice-id     RGb96Dcl0k5eVje8EBch
    --tts-model    eleven_multilingual_v2
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app import config
from app.elevenlabs_client import ElevenLabsTTS
from app.errors import AppError
from app.sync_dubber import synthesize_synced
from app.utils import ensure_elevenlabs_api_key, ensure_output_dir

DEFAULT_SOURCE = r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT"
DEFAULT_OUTPUT_ROOT = r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT_2"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch synthesize time-aligned English MP3s from translated JSON files."
    )
    p.add_argument(
        "--source",
        type=Path,
        default=Path(DEFAULT_SOURCE),
        help="Root directory containing translated *.json files",
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path(DEFAULT_OUTPUT_ROOT),
        help="Root directory for synthesized *.mp3 output (mirrors source tree)",
    )
    p.add_argument(
        "--voice-id",
        default=config.DEFAULT_VOICE_ID,
        help=f"ElevenLabs voice ID (default: {config.DEFAULT_VOICE_ID})",
    )
    p.add_argument(
        "--tts-model",
        default=config.DEFAULT_TTS_MODEL,
        help=f"ElevenLabs TTS model (default: {config.DEFAULT_TTS_MODEL})",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-synthesize files that already have output MP3s",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print each segment as it is synthesized",
    )
    return p.parse_args()


def output_path_for(json_path: Path, source_root: Path, output_root: Path) -> Path:
    relative = json_path.parent.relative_to(source_root)
    return output_root / relative / (json_path.stem + "_en.mp3")


def main() -> None:
    args = parse_args()
    source: Path = args.source.resolve()
    output_root: Path = args.output_root.resolve()

    if not source.is_dir():
        print(f"Error: Source directory not found: {source}", file=sys.stderr)
        sys.exit(1)

    try:
        api_key = ensure_elevenlabs_api_key(config.get_elevenlabs_api_key())
    except AppError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    json_files = sorted(source.rglob("*.json"))
    if not json_files:
        print(f"No *.json files found under: {source}")
        sys.exit(0)

    total = len(json_files)
    print(f"Found {total} JSON file(s) under: {source}")
    print(f"Output root:  {output_root}")
    print(f"Voice:        {args.voice_id}")
    print(f"TTS model:    {args.tts_model}")
    print(f"Mode:         segment-synchronized (Option B)")
    print()

    tts = ElevenLabsTTS(api_key=api_key, voice_id=args.voice_id, model_id=args.tts_model)

    skipped = 0
    failed = 0

    for idx, json_path in enumerate(json_files, start=1):
        out_path = output_path_for(json_path, source, output_root)
        print(f"[{idx}/{total}] {json_path.relative_to(source)}")

        if not args.overwrite and out_path.exists():
            print("  -> Skipped (already exists; use --overwrite to redo)")
            skipped += 1
            continue

        ensure_output_dir(out_path.parent)

        try:
            n_segments = synthesize_synced(
                json_path=json_path,
                output_path=out_path,
                tts=tts,
                verbose=args.verbose,
            )
            size_kb = out_path.stat().st_size / 1024
            print(f"  -> Done: {n_segments} segments | {size_kb:.0f} KB")
            print(f"     {out_path}")
        except AppError as e:
            failed += 1
            print(f"  -> FAILED: {e}", file=sys.stderr)
            continue
        except Exception as e:
            failed += 1
            print(f"  -> FAILED: {e}", file=sys.stderr)
            continue

        print()

    print("=" * 60)
    print(f"Total:   {total}")
    print(f"Done:    {total - skipped - failed}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
