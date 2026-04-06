import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.models import Segment, TranslationResult
from app.writers import write_json, write_srt, write_txt, _format_srt_time


def make_result(tmp_path: Path) -> TranslationResult:
    return TranslationResult(
        input_path=tmp_path / "test.mp3",
        model_name="small",
        detected_language="ru",
        text="Hello world.",
        segments=[
            Segment(index=1, start=0.0, end=2.5, text="Hello world."),
            Segment(index=2, start=2.5, end=5.0, text="Goodbye."),
        ],
        duration=5.0,
    )


def test_format_srt_time():
    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(3661.5) == "01:01:01,500"
    assert _format_srt_time(90.123) == "00:01:30,123"


def test_write_txt(tmp_path):
    result = make_result(tmp_path)
    out = tmp_path / "output.txt"
    write_txt(result, out)
    assert out.read_text(encoding="utf-8") == "Hello world."


def test_write_srt(tmp_path):
    result = make_result(tmp_path)
    out = tmp_path / "output.srt"
    write_srt(result, out)
    content = out.read_text(encoding="utf-8")
    assert "1\n" in content
    assert "00:00:00,000 --> 00:00:02,500" in content
    assert "Hello world." in content
    assert "2\n" in content
    assert "Goodbye." in content


def test_write_json(tmp_path):
    result = make_result(tmp_path)
    out = tmp_path / "output.json"
    write_json(result, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["model"] == "small"
    assert data["detected_language"] == "ru"
    assert data["text"] == "Hello world."
    assert len(data["segments"]) == 2
    assert data["segments"][0]["start"] == 0.0
