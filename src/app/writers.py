import json
from pathlib import Path

from app.models import TranslationResult


def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_txt(result: TranslationResult, output_path: Path) -> None:
    output_path.write_text(result.text, encoding="utf-8")


def write_srt(result: TranslationResult, output_path: Path) -> None:
    lines = []
    for seg in result.segments:
        lines.append(str(seg.index))
        lines.append(f"{_format_srt_time(seg.start)} --> {_format_srt_time(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(result: TranslationResult, output_path: Path) -> None:
    data = {
        "input_file": result.input_path.name,
        "model": result.model_name,
        "detected_language": result.detected_language,
        "duration": result.duration,
        "text": result.text,
        "segments": [
            {
                "index": seg.index,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
            }
            for seg in result.segments
        ],
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_all(result: TranslationResult, output_dir: Path, prefix: str = "output") -> list[Path]:
    written = []
    for suffix, writer in [
        (".txt", write_txt),
        (".srt", write_srt),
        (".json", write_json),
    ]:
        path = output_dir / f"{prefix}{suffix}"
        writer(result, path)
        written.append(path)
    return written
