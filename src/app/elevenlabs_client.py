import re
from pathlib import Path

from app.errors import TTSGenerationError

# ElevenLabs API hard limit per request
_MAX_CHARS = 4900


def _split_into_chunks(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """Split text at sentence boundaries to stay under the API character limit."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            # Single sentence too long — hard split on word boundary
            words = sentence.split()
            for word in words:
                if len(current) + len(word) + 1 > max_chars:
                    if current:
                        chunks.append(current.strip())
                    current = word
                else:
                    current = (current + " " + word).strip()
        elif len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        chunks.append(current.strip())
    return chunks


class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str, model_id: str) -> None:
        try:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=api_key)
        except ImportError:
            raise TTSGenerationError(
                "elevenlabs package is not installed. Run: uv add elevenlabs"
            )
        self.voice_id = voice_id
        self.model_id = model_id

    def synthesize_to_mp3(self, text: str, output_path: Path) -> tuple[Path, int]:
        """Synthesize text to MP3, chunking if needed. Returns (path, chunks_count)."""
        chunks = _split_into_chunks(text)
        try:
            with open(output_path, "wb") as f:
                for chunk_text in chunks:
                    audio_stream = self._client.text_to_speech.convert(
                        voice_id=self.voice_id,
                        text=chunk_text,
                        model_id=self.model_id,
                        output_format="mp3_44100_128",
                    )
                    for audio_bytes in audio_stream:
                        f.write(audio_bytes)
        except TTSGenerationError:
            raise
        except Exception as e:
            raise TTSGenerationError(
                f"ElevenLabs synthesis failed.\nDetails: {e}"
            )
        return output_path, len(chunks)
