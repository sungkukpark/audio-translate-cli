import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.elevenlabs_client import _split_into_chunks


def test_short_text_is_single_chunk():
    text = "Hello world. This is a test."
    chunks = _split_into_chunks(text, max_chars=500)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits_at_sentence_boundary():
    sentence = "This is a sentence. "
    text = sentence * 50  # ~1000 chars
    chunks = _split_into_chunks(text, max_chars=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200


def test_no_empty_chunks():
    text = "First sentence. Second sentence. Third sentence."
    chunks = _split_into_chunks(text, max_chars=30)
    assert all(len(c) > 0 for c in chunks)


def test_empty_text_returns_empty():
    chunks = _split_into_chunks("", max_chars=500)
    assert chunks == []
