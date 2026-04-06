from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Segment:
    index: int
    start: float
    end: float
    text: str


@dataclass
class TranslationResult:
    input_path: Path
    model_name: str
    detected_language: str
    text: str
    segments: list[Segment] = field(default_factory=list)
    duration: float | None = None
