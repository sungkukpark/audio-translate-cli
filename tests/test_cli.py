import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.cli import parse_args


def test_defaults(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"")
    args = parse_args(["--input", str(f)])
    assert args.model == "medium"
    assert args.device == "cuda"
    assert not args.overwrite
    assert not args.verbose


def test_model_override(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"")
    args = parse_args(["--input", str(f), "--model", "medium"])
    assert args.model == "medium"


def test_output_dir(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"")
    args = parse_args(["--input", str(f), "--output-dir", str(tmp_path / "out")])
    assert args.output_dir == tmp_path / "out"


def test_output_prefix(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"")
    args = parse_args(["--input", str(f), "--output-prefix", "lecture1"])
    assert args.output_prefix == "lecture1"
