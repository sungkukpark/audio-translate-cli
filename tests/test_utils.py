import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.errors import ValidationError
from app.utils import validate_input_file, ensure_output_dir


def test_validate_missing_file(tmp_path):
    with pytest.raises(ValidationError, match="not found"):
        validate_input_file(tmp_path / "missing.mp3")


def test_validate_unsupported_extension(tmp_path):
    f = tmp_path / "audio.xyz"
    f.write_bytes(b"")
    with pytest.raises(ValidationError, match="Unsupported"):
        validate_input_file(f)


def test_validate_valid_mp3(tmp_path):
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"")
    validate_input_file(f)  # should not raise


def test_ensure_output_dir_creates(tmp_path):
    out = tmp_path / "a" / "b" / "c"
    ensure_output_dir(out)
    assert out.is_dir()
