from pathlib import Path

from app.elevenlabs_client import ElevenLabsTTS
from app.models import DubResult, TranslationResult


def dub_translation_result(
    result: TranslationResult,
    output_path: Path,
    voice_id: str,
    model_id: str,
    api_key: str,
) -> DubResult:
    tts = ElevenLabsTTS(api_key=api_key, voice_id=voice_id, model_id=model_id)
    _, chunks = tts.synthesize_to_mp3(result.text, output_path)
    return DubResult(
        text_source=result.text,
        voice_id=voice_id,
        model_id=model_id,
        output_path=output_path,
        chunks_synthesized=chunks,
    )
