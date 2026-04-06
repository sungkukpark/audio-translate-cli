import sys
from pathlib import Path

from app.models import Segment, TranslationResult


def resolve_device(requested: str) -> str:
    """Return 'cuda' if available and requested, otherwise 'cpu'."""
    if requested in ("cpu",):
        return "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if requested == "cuda":
            print(
                "Warning: CUDA requested but torch.cuda.is_available() is False. "
                "Falling back to CPU. Install a CUDA-enabled PyTorch to use the GPU.",
                file=sys.stderr,
            )
        return "cpu"
    except ImportError:
        return "cpu"


def load_model(model_name: str, device: str):
    """Load and return a Whisper model. Raises RuntimeError on failure."""
    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "openai-whisper is not installed. Run: uv add openai-whisper"
        )

    actual_device = resolve_device(device)
    try:
        model = whisper.load_model(model_name, device=actual_device)
        model._actual_device = actual_device  # stash for transcription
        return model
    except Exception as e:
        raise RuntimeError(
            f"Failed to load Whisper model '{model_name}' on device '{actual_device}'.\n"
            f"Details: {e}"
        )


def translate_audio(
    input_path: Path,
    model=None,
    model_name: str = "small",
    language: str = "ru",
    task: str = "translate",
    device: str = "cpu",
    verbose: bool = False,
) -> TranslationResult:
    """Translate audio. Pass a pre-loaded model to avoid reloading each call."""
    if model is None:
        model = load_model(model_name, device)

    actual_device = getattr(model, "_actual_device", device)

    try:
        result = model.transcribe(
            str(input_path),
            language=language,
            task=task,
            verbose=verbose,
            fp16=(actual_device == "cuda"),
        )
    except Exception as e:
        raise RuntimeError(f"Transcription failed for '{input_path.name}'.\nDetails: {e}")

    segments = [
        Segment(
            index=i + 1,
            start=seg["start"],
            end=seg["end"],
            text=seg["text"].strip(),
        )
        for i, seg in enumerate(result.get("segments", []))
    ]

    detected_language = result.get("language", language)
    duration = segments[-1].end if segments else None

    return TranslationResult(
        input_path=input_path,
        model_name=model_name,
        detected_language=detected_language,
        text=result.get("text", "").strip(),
        segments=segments,
        duration=duration,
    )
