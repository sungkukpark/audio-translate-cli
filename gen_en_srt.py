"""Generate .en.srt files from existing .en.json transcription files."""

import json
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def json_to_srt(json_path: Path) -> str:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")

    return "\n".join(lines)


def main() -> None:
    base = Path("D:/Dropbox/Lectures/CGMA/CGMA - Level Design for Games")
    json_files = sorted(base.rglob("*.en.json"))

    skipped = 0
    created = 0

    for json_path in json_files:
        srt_path = json_path.with_suffix("").with_suffix(".en.srt")
        if srt_path.exists():
            skipped += 1
            continue

        srt_content = json_to_srt(json_path)
        srt_path.write_text(srt_content, encoding="utf-8")
        print(f"Created: {srt_path.relative_to(base)}")
        created += 1

    print(f"\nDone. Created: {created}, Skipped (already exist): {skipped}")


if __name__ == "__main__":
    main()
