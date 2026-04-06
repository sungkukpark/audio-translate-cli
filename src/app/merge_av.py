"""
Merge an MP3 audio file into an MP4 video file, replacing the original audio track.

Usage:
    uv run merge-av --video input.mp4 --audio input_en.mp3 --output output.mp4
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="merge-av",
        description="Replace the audio track of an MP4 with an MP3 file.",
    )
    parser.add_argument("--video", "-v", required=True, type=Path, help="Input MP4 video file")
    parser.add_argument("--audio", "-a", required=True, type=Path, help="Input MP3 audio file")
    parser.add_argument("--output", "-o", default=None, type=Path, help="Output MP4 file (default: <video stem>_en.mp4)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists")
    return parser.parse_args(argv)


def merge(video: Path, audio: Path, output: Path, overwrite: bool = False) -> None:
    if not video.exists():
        print(f"Error: video file not found: {video}", file=sys.stderr)
        sys.exit(1)
    if not audio.exists():
        print(f"Error: audio file not found: {audio}", file=sys.stderr)
        sys.exit(1)
    if output.exists() and not overwrite:
        print(f"Error: output already exists: {output}  (use --overwrite to replace)", file=sys.stderr)
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i", str(video),
        "-i", str(audio),
        "-c:v", "copy",       # keep original video stream as-is
        "-map", "0:v:0",      # video from first input
        "-map", "1:a:0",      # audio from second input
        "-shortest",          # trim to the shorter of the two
        str(output),
    ]

    print(f"Video: {video}")
    print(f"Audio: {audio}")
    print(f"Output: {output}")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: ffmpeg failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print("Done.")


def main() -> None:
    args = parse_args()
    video = args.video.resolve()
    output = args.output.resolve() if args.output else video.with_stem(video.stem + "_en")
    merge(
        video=video,
        audio=args.audio.resolve(),
        output=output,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
