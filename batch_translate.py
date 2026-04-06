"""
Batch translate all *.mp3 files under a source directory.

Output mirrors the source tree under --output-root, so:
  <source>/week 1/lecture.mp3  ->  <output-root>/week 1/lecture.txt
                                                          lecture.srt
                                                          lecture.json

Usage:
    uv run python batch_translate.py [--source <dir>] [--output-root <dir>] [--model <name>] [--overwrite]

Defaults:
    --source       D:/Dropbox/Lectures/CGMA/[CGMA 3D] - Level Design for Games
    --output-root  D:/Dropbox/Lectures/CGMA/[CGMA 3D] - Level Design for Games/OUT
    --model        medium
"""

import argparse
import sys
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.translator import load_model, translate_audio
from app.utils import check_ffmpeg, ensure_output_dir
from app.writers import write_all

DEFAULT_SOURCE = r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games"
DEFAULT_OUTPUT_ROOT = r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch-translate MP3 files to English text.")
    p.add_argument(
        "--source",
        type=Path,
        default=Path(DEFAULT_SOURCE),
        help="Root directory to search for *.mp3 files",
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path(DEFAULT_OUTPUT_ROOT),
        help="Root directory for translated output (mirrors source tree)",
    )
    p.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        help="Whisper model (default: medium)",
    )
    p.add_argument(
        "--device",
        default="cuda",
        choices=["cpu", "cuda", "auto"],
        help="Inference device (default: cuda)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-translate files that already have output",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-segment Whisper output",
    )
    return p.parse_args()


def output_dir_for(mp3_path: Path, source_root: Path, output_root: Path) -> Path:
    """Mirror the source subdirectory structure under output_root."""
    relative = mp3_path.parent.relative_to(source_root)
    return output_root / relative


def already_done(mp3_path: Path, source_root: Path, output_root: Path) -> bool:
    out_dir = output_dir_for(mp3_path, source_root, output_root)
    prefix = mp3_path.stem
    return all((out_dir / f"{prefix}{ext}").exists() for ext in (".txt", ".srt", ".json"))


def main() -> None:
    args = parse_args()
    source: Path = args.source.resolve()
    output_root: Path = args.output_root.resolve()

    if not source.is_dir():
        print(f"Error: Source directory not found: {source}", file=sys.stderr)
        sys.exit(1)

    check_ffmpeg()

    mp3_files = sorted(source.rglob("*.mp3"))
    if not mp3_files:
        print(f"No *.mp3 files found under: {source}")
        sys.exit(0)

    total = len(mp3_files)
    print(f"Found {total} MP3 file(s) under: {source}")
    print(f"Output root:  {output_root}")
    print(f"Model: {args.model}  |  Device: {args.device}")
    print()

    print("Loading Whisper model...")
    try:
        model = load_model(args.model, args.device)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Model loaded on device: {model._actual_device}")
    print()

    skipped = 0
    failed = 0

    for idx, mp3 in enumerate(mp3_files, start=1):
        prefix = mp3.stem
        out_dir = output_dir_for(mp3, source, output_root)

        print(f"[{idx}/{total}] {mp3.relative_to(source)}")

        if not args.overwrite and already_done(mp3, source, output_root):
            print("  -> Skipped (already translated; use --overwrite to redo)")
            skipped += 1
            continue

        ensure_output_dir(out_dir)

        try:
            result = translate_audio(
                input_path=mp3,
                model=model,
                model_name=args.model,
                device=args.device,
                verbose=args.verbose,
            )
            written = write_all(result, out_dir, prefix=prefix)
            print("  -> Done:")
            for path in written:
                print(f"       {path}")
        except RuntimeError as e:
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
