"""
CGMA Level Design course — Russian MP3 → English SRT + MP4 copy.

Source tree:  srcs/<week N>/<file>.mp3  (+ .mp4)
Output tree:  OUT5/<week N>/<file>.srt  (+ copied .mp4)

Usage:
    uv run python cgma_translate.py [--only-first] [--overwrite] [--model large-v3]
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.translator import load_model, translate_audio
from app.utils import check_ffmpeg, ensure_output_dir
from app.writers import write_srt  # write_srt(result, file_path)

SRC_ROOT = Path(r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\srcs")
OUT_ROOT = Path(r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT5")

# Domain hint — helps Whisper stay on topic and use correct terminology
INITIAL_PROMPT = (
    "This is a lecture on 3D level design for games. "
    "Topics include geometry, lighting, composition, Unreal Engine, Unity, "
    "gameplay spaces, blockout, greybox, environment art, and game design theory."
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Translate CGMA MP3 lectures to English SRT.")
    p.add_argument("--model", default="large-v3",
                   choices=["medium", "large", "large-v2", "large-v3"],
                   help="Whisper model (default: large-v3)")
    p.add_argument("--device", default="cuda", choices=["cpu", "cuda"],
                   help="Inference device (default: cuda)")
    p.add_argument("--only-first", action="store_true",
                   help="Process only the first file (for testing)")
    p.add_argument("--overwrite", action="store_true",
                   help="Re-translate files that already have a .srt")
    p.add_argument("--verbose", action="store_true",
                   help="Show per-segment Whisper output")
    return p.parse_args()


def srt_path(mp3: Path) -> Path:
    relative = mp3.relative_to(SRC_ROOT)
    return OUT_ROOT / relative.parent / (mp3.stem + ".srt")


def mp4_dst(mp3: Path) -> Path:
    relative = mp3.relative_to(SRC_ROOT)
    return OUT_ROOT / relative.parent / (mp3.stem + ".mp4")


def main() -> None:
    args = parse_args()
    check_ffmpeg()

    mp3_files = sorted(SRC_ROOT.rglob("*.mp3"))
    if not mp3_files:
        print(f"No *.mp3 files found under: {SRC_ROOT}")
        sys.exit(0)

    if args.only_first:
        mp3_files = mp3_files[:1]
        print("[--only-first] Processing single file for test.")

    total = len(mp3_files)
    print(f"Source:  {SRC_ROOT}")
    print(f"Output:  {OUT_ROOT}")
    print(f"Model:   {args.model}  |  Device: {args.device}")
    print(f"Files:   {total}")
    print()

    print("Loading Whisper model (this may download ~3 GB for large-v3)...")
    try:
        model = load_model(args.model, args.device)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Model loaded on: {model._actual_device}")
    print()

    done = skipped = failed = 0

    for idx, mp3 in enumerate(mp3_files, 1):
        out_srt = srt_path(mp3)
        out_mp4_dst = mp4_dst(mp3)
        src_mp4 = mp3.with_suffix(".mp4")

        print(f"[{idx}/{total}] {mp3.relative_to(SRC_ROOT)}")

        if not args.overwrite and out_srt.exists():
            print("  -> Skipped (SRT exists; use --overwrite to redo)")
            skipped += 1
            continue

        ensure_output_dir(out_srt.parent)

        # Translate
        try:
            result = translate_audio(
                input_path=mp3,
                model=model,
                model_name=args.model,
                device=args.device,
                verbose=args.verbose,
            )
            write_srt(result, out_srt)
            print(f"  -> SRT: {out_srt}")
        except Exception as e:
            failed += 1
            print(f"  -> FAILED: {e}", file=sys.stderr)
            continue

        # Copy MP4
        if src_mp4.exists():
            if not out_mp4_dst.exists() or args.overwrite:
                shutil.copy2(src_mp4, out_mp4_dst)
                print(f"  -> MP4: {out_mp4_dst}")
            else:
                print(f"  -> MP4: already exists, skipped")
        else:
            print(f"  -> MP4: source not found ({src_mp4.name}), skipped")

        done += 1
        print()

    print("=" * 60)
    print(f"Total:   {total}")
    print(f"Done:    {done}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
