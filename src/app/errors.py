class AppError(Exception):
    """Base class for all user-facing application errors."""


class ValidationError(AppError):
    """Invalid input, missing file, bad extension, etc."""


class DependencyError(AppError):
    """Required system dependency (ffmpeg, API key) is missing."""


class TranslationError(AppError):
    """Whisper model loading or transcription failed."""


class TTSGenerationError(AppError):
    """ElevenLabs synthesis failed."""


class OutputWriteError(AppError):
    """Writing an output file failed."""
