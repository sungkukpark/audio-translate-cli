"""
Bulk merge MP4 video files with corresponding MP3 audio (English TTS).

Video source : D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\<week>\*.mp4
Audio source : ...OUT2\<week>\*_en.mp3
Output       : ...OUT3\<week>\*_en.mp4  (original files are NEVER modified)
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games")
OUT2_DIR = BASE_DIR / "OUT2"
OUT3_DIR = BASE_DIR / "OUT3"

SKIP_DIRS = {"OUT2", "OUT3"}


def find_video_files() -> list[Path]:
    videos = []
    for mp4 in BASE_DIR.rglob("*.mp4"):
        # Skip anything inside OUT2 or OUT3
        relative = mp4.relative_to(BASE_DIR)
        if relative.parts[0] in SKIP_DIRS:
            continue
        videos.append(mp4)
    return sorted(videos)


def audio_path_for(video: Path) -> Path:
    relative = video.relative_to(BASE_DIR)          # e.g. week 1/foo.mp4
    stem = relative.stem                             # foo
    parent = relative.parent                         # week 1
    return OUT2_DIR / parent / f"{stem}_en.mp3"


def output_path_for(video: Path) -> Path:
    relative = video.relative_to(BASE_DIR)
    stem = relative.stem
    parent = relative.parent
    return OUT3_DIR / parent / f"{stem}_en.mp4"


def merge(video: Path, audio: Path, output: Path) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(video),
        "-i", str(audio),
        "-c:v", "copy",          # copy video stream — no re-encode
        "-c:a", "aac",           # encode MP3 → AAC for MP4 container
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] ffmpeg failed:\n{result.stderr[-500:]}", file=sys.stderr)
        return False
    return True


def main() -> None:
    videos = find_video_files()
    total = len(videos)
    print(f"Found {total} video file(s).\n")

    skipped = 0
    done = 0
    failed = 0
    no_audio = 0

    for i, video in enumerate(videos, 1):
        audio = audio_path_for(video)
        output = output_path_for(video)

        prefix = f"[{i:3d}/{total}]"

        if output.exists():
            print(f"{prefix} SKIP (already exists)  {output.name}")
            skipped += 1
            continue

        if not audio.exists():
            print(f"{prefix} SKIP (no audio found)  {video.relative_to(BASE_DIR)}")
            no_audio += 1
            continue

        print(f"{prefix} Merging {output.relative_to(BASE_DIR)} ...", end=" ", flush=True)
        if merge(video, audio, output):
            print("OK")
            done += 1
        else:
            print("FAILED")
            failed += 1

    print(f"\nDone. merged={done}  skipped={skipped}  no_audio={no_audio}  failed={failed}")


if __name__ == "__main__":
    main()
