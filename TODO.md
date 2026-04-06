# TODO.md

## Goal

Implement an end-to-end Python application that:

1. takes a **Russian MP3** input,
2. translates it to **English text** with **openai-whisper**,
3. synthesizes **English speech** with **ElevenLabs**,
4. saves structured outputs for debugging and future extension.

The project should remain small enough for study purposes, but the implementation should be organized so it can later grow into a more robust media-processing pipeline.

---

## Design Principles

- Keep the first version **simple, synchronous, and debuggable**
- Separate **translation**, **TTS**, **file writing**, and **CLI orchestration**
- Keep **data models explicit**
- Treat **subtitle output** and **TTS output** as different products
- Make room for future features without overengineering now
- Prefer **clear interfaces** over clever abstractions

---

## Architecture Direction

### Proposed modules

```text
src/app/
├─ __init__.py
├─ main.py                # CLI entrypoint
├─ cli.py                 # argument parsing
├─ config.py              # env/config loading
├─ errors.py              # custom user-facing exceptions
├─ models.py              # dataclasses for normalized data
├─ translator.py          # Whisper translation service
├─ elevenlabs_client.py   # ElevenLabs SDK wrapper
├─ dubber.py              # translation result -> English audio
├─ writers.py             # txt/srt/json output writers
├─ utils.py               # validation and helper functions
└─ logging_utils.py       # optional logging setup
```

### Data flow

```text
CLI
→ validate input / environment
→ Whisper translate
→ save translation artifacts
→ ElevenLabs TTS
→ save dubbed audio
→ print final summary
```

### Core design decision

The app should use a **normalized internal result model** so that:
- Whisper output is converted once into project-specific dataclasses
- file writers do not depend on raw third-party response shapes
- ElevenLabs integration only consumes normalized text/chunks
- future frontends do not need to understand SDK-specific payloads

---

## Phase 1 — Project Setup

### TODO
- [ ] Create the repository with a final name
- [ ] Initialize project with `uv`
- [ ] Use `src/` layout
- [ ] Create `.python-version`
- [ ] Create `pyproject.toml`
- [ ] Add runtime dependencies
- [ ] Add dev dependencies
- [ ] Add a basic `.gitignore`
- [ ] Add `README.md`
- [ ] Add this `TODO.md`
- [ ] Add `.env.example`

### Dependencies
- [ ] Add `openai-whisper`
- [ ] Add `elevenlabs`
- [ ] Add `python-dotenv` if using `.env`
- [ ] Add `pytest`
- [ ] Add `ruff`
- [ ] Add `mypy`

### Acceptance criteria
- [ ] `uv run python -V` works inside the project
- [ ] `uv run python -m app.main --help` is available
- [ ] dependency installation is reproducible from project files

---

## Phase 2 — Core Domain Models

### Objective
Create stable internal models before wiring services together.

### TODO
- [ ] Create `Segment` dataclass
- [ ] Create `TranslationResult` dataclass
- [ ] Create `DubResult` dataclass
- [ ] Define a stable output contract for file writers
- [ ] Add helper methods only where they genuinely improve readability

### Suggested model sketch

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Segment:
    start: float
    end: float
    text: str

@dataclass
class TranslationResult:
    input_path: Path
    model_name: str
    source_language: str
    task: str
    text: str
    segments: list[Segment]

@dataclass
class DubResult:
    text_source: str
    voice_id: str
    model_id: str
    output_path: Path
```

### Design notes
- `TranslationResult` should be the canonical handoff between Whisper and writers
- `DubResult` should be small and focused on synthesis metadata
- Avoid storing raw SDK responses in these dataclasses

### Acceptance criteria
- [ ] services can exchange data using internal models only
- [ ] writers do not access raw Whisper/ELEVENLABS payloads directly

---

## Phase 3 — Validation and Environment Checks

### Objective
Fail early with clear, actionable messages.

### TODO
- [ ] Validate input file exists
- [ ] Validate input extension
- [ ] Validate output directory creation
- [ ] Validate `ffmpeg` availability
- [ ] Validate `ELEVENLABS_API_KEY` presence before TTS
- [ ] Add user-facing exceptions in `errors.py`
- [ ] Add readable error messages in CLI

### Suggested validations
- [ ] `ensure_file_exists(path)`
- [ ] `ensure_supported_audio_extension(path)`
- [ ] `ensure_ffmpeg_installed()`
- [ ] `ensure_output_dir(path)`
- [ ] `ensure_elevenlabs_api_key()`

### Design notes
- Validation belongs in shared utilities or dedicated validators, not inside `main.py`
- CLI should catch custom exceptions and print concise messages
- Reserve full stack traces for a `--verbose` mode

### Acceptance criteria
- [ ] missing input file yields a clean failure
- [ ] missing `ffmpeg` yields a clean failure
- [ ] missing API key yields a clean failure
- [ ] common user mistakes do not show raw internals by default

---

## Phase 4 — CLI Contract

### Objective
Lock down the first command-line interface.

### TODO
- [ ] Implement `argparse` CLI
- [ ] Add `--input`
- [ ] Add `--output-dir`
- [ ] Add `--model`
- [ ] Add `--voice-id`
- [ ] Add `--tts-model`
- [ ] Add `--output-prefix`
- [ ] Add `--verbose`
- [ ] Add `--skip-tts` for translation-only runs
- [ ] Add sensible defaults

### Recommended first CLI

```bash
uv run python -m app.main \
  --input sample.mp3 \
  --output-dir outputs \
  --model small \
  --voice-id JBFqnCBsd6RMkjVDRZzb \
  --tts-model eleven_multilingual_v2
```

### Design notes
- `--skip-tts` is useful for isolating Whisper work during debugging
- `--output-prefix` avoids hardcoded names like `output.txt`
- Keep CLI arguments stable; add new options carefully later

### Acceptance criteria
- [ ] `--help` output is readable
- [ ] all required values are obvious from help text
- [ ] default behavior is useful without excessive flags

---

## Phase 5 — Whisper Translation Service

### Objective
Implement a clean Whisper integration layer.

### TODO
- [ ] Create `translator.py`
- [ ] Implement model loading function
- [ ] Implement translation function
- [ ] Normalize raw Whisper response into `TranslationResult`
- [ ] Force `language="ru"` for the first version
- [ ] Force `task="translate"` for the first version
- [ ] Keep model selection configurable via CLI

### Suggested public interface

```python
def translate_audio(
    input_path: Path,
    model_name: str = "small",
    language: str = "ru",
    task: str = "translate",
) -> TranslationResult:
    ...
```

### Internal steps
- [ ] load Whisper model
- [ ] call `model.transcribe(...)`
- [ ] extract full text
- [ ] extract segment timestamps
- [ ] normalize into internal dataclasses

### Design notes
- `translator.py` should not write files
- `translator.py` should not know about ElevenLabs
- avoid mixing CLI printing into service code

### Acceptance criteria
- [ ] a Russian MP3 produces English text
- [ ] `TranslationResult.text` is populated
- [ ] segment timestamps are preserved
- [ ] failures are wrapped in clean app-level exceptions

---

## Phase 6 — Translation Artifact Writers

### Objective
Persist Whisper output in formats useful for debugging and reuse.

### TODO
- [ ] Implement TXT writer
- [ ] Implement SRT writer
- [ ] Implement JSON writer
- [ ] Centralize output path creation
- [ ] Ensure UTF-8 writing
- [ ] Ensure predictable filenames

### Suggested functions
- [ ] `write_txt(result: TranslationResult, path: Path) -> Path`
- [ ] `write_srt(result: TranslationResult, path: Path) -> Path`
- [ ] `write_json(result: TranslationResult, path: Path) -> Path`

### File naming plan
Given `--output-prefix sample`:
- `sample.txt`
- `sample.srt`
- `sample.json`
- later: `sample_en.mp3`

### Design notes
- JSON should be the most complete debug artifact
- SRT formatting should be isolated in helper functions
- Writers should be deterministic and easy to test

### Acceptance criteria
- [ ] TXT contains full translated text
- [ ] SRT numbering and timestamps are valid
- [ ] JSON includes metadata and segments
- [ ] paths are returned after successful writes

---

## Phase 7 — ElevenLabs SDK Wrapper

### Objective
Create a minimal but clean wrapper around the ElevenLabs client.

### TODO
- [ ] Create `elevenlabs_client.py`
- [ ] Read API key from environment/config
- [ ] Initialize official ElevenLabs SDK client
- [ ] Implement `synthesize_to_mp3(...)`
- [ ] Write streamed audio chunks to file
- [ ] Wrap API failures into app-level exceptions

### Suggested public interface

```python
class ElevenLabsTTS:
    def __init__(self, api_key: str | None, voice_id: str, model_id: str) -> None:
        ...

    def synthesize_to_mp3(self, text: str, output_path: Path) -> Path:
        ...
```

### Design notes
- This module should only know about TTS mechanics
- It should not know about Whisper models or translation logic
- It should be possible to replace ElevenLabs later with another TTS provider behind a similar interface

### Acceptance criteria
- [ ] English text can be synthesized into an MP3
- [ ] output file is created successfully
- [ ] missing API key fails cleanly
- [ ] SDK/API errors are translated into readable app errors

---

## Phase 8 — Dubbing Orchestration

### Objective
Bridge translated text into TTS output without coupling services too tightly.

### TODO
- [ ] Create `dubber.py`
- [ ] Accept `TranslationResult`
- [ ] Extract the text to synthesize
- [ ] Call `ElevenLabsTTS`
- [ ] Return a `DubResult`
- [ ] Keep this orchestration separate from CLI

### Suggested interface

```python
def dub_translation_result(
    result: TranslationResult,
    output_path: Path,
    voice_id: str,
    model_id: str,
) -> DubResult:
    ...
```

### Design notes
- `dubber.py` should remain thin
- first version should synthesize `result.text` directly
- future chunk-based TTS can replace internals without changing CLI contract

### Acceptance criteria
- [ ] dubbed audio can be generated from a `TranslationResult`
- [ ] caller gets a normalized `DubResult`
- [ ] future chunking can be added without large refactors

---

## Phase 9 — Main Orchestration Flow

### Objective
Compose the full pipeline in one readable entrypoint.

### TODO
- [ ] Parse CLI args
- [ ] Validate environment and inputs
- [ ] Run Whisper translation
- [ ] Write translation artifacts
- [ ] Conditionally run ElevenLabs TTS
- [ ] Print final file summary
- [ ] Exit non-zero on failure

### Suggested flow in `main.py`
- [ ] get config and args
- [ ] ensure prerequisites
- [ ] call `translate_audio(...)`
- [ ] write `.txt`, `.srt`, `.json`
- [ ] if not `--skip-tts`, call dubbing
- [ ] print saved file paths

### Design notes
- `main.py` should orchestrate, not implement business logic
- keep it short enough that the whole flow is visible on one screen if possible

### Acceptance criteria
- [ ] one command runs the whole pipeline
- [ ] translation-only mode works
- [ ] translation+TTS mode works
- [ ] terminal output is concise and understandable

---

## Phase 10 — Error Model and Logging

### Objective
Make failures predictable and easy to debug.

### TODO
- [ ] Create app-specific exception classes
- [ ] Distinguish validation errors from runtime integration errors
- [ ] Add optional `--verbose` mode
- [ ] Log major pipeline steps
- [ ] Avoid noisy logging in normal mode

### Suggested exception types
- [ ] `AppError`
- [ ] `ValidationError`
- [ ] `DependencyError`
- [ ] `TranslationError`
- [ ] `TTSGenerationError`
- [ ] `OutputWriteError`

### Design notes
- use app-specific exceptions at module boundaries
- third-party exceptions should be wrapped, not leaked blindly
- logging should aid learning, not bury the signal

### Acceptance criteria
- [ ] ordinary failures produce readable output
- [ ] verbose mode helps locate failing step
- [ ] users can tell whether failure came from input, Whisper, or ElevenLabs

---

## Phase 11 — Testing Strategy

### Objective
Test what matters without forcing expensive model/API calls.

### TODO
- [ ] Add tests for validation utilities
- [ ] Add tests for SRT formatting
- [ ] Add tests for JSON writing
- [ ] Add tests for CLI argument parsing
- [ ] Add tests for filename/path generation
- [ ] Mock ElevenLabs client in unit tests
- [ ] Avoid real Whisper inference in unit tests
- [ ] Add optional integration tests later

### Unit test targets
- [ ] `ensure_supported_audio_extension`
- [ ] `ensure_output_dir`
- [ ] `format_srt_timestamp`
- [ ] writer output contents
- [ ] config loading behavior
- [ ] dubbing orchestration with mocked client

### Integration test ideas
- [ ] one small local MP3 fixture for manual smoke tests
- [ ] optional real ElevenLabs test guarded behind env var
- [ ] optional Whisper smoke test not run by default

### Acceptance criteria
- [ ] fast tests run locally with `uv run pytest`
- [ ] most logic is covered without network calls
- [ ] regressions in writers/CLI are easy to catch

---

## Phase 12 — Configuration Hygiene

### Objective
Make configuration explicit and safe.

### TODO
- [ ] Create `config.py`
- [ ] centralize defaults for Whisper model, voice ID, and TTS model
- [ ] load environment variables in one place
- [ ] document required environment variables in `.env.example`
- [ ] avoid scattering `os.getenv(...)` throughout the codebase

### Suggested config values
- [ ] `DEFAULT_WHISPER_MODEL = "small"`
- [ ] `DEFAULT_SOURCE_LANGUAGE = "ru"`
- [ ] `DEFAULT_TASK = "translate"`
- [ ] `DEFAULT_TTS_MODEL = "eleven_multilingual_v2"`
- [ ] `DEFAULT_VOICE_ID = "<chosen default>"`

### Design notes
- central config prevents drift between modules
- first version can use simple constants or a lightweight settings dataclass

### Acceptance criteria
- [ ] runtime defaults are obvious
- [ ] API key loading happens consistently
- [ ] changing defaults requires edits in one place only

---

## Phase 13 — Documentation

### Objective
Document usage clearly enough that future-you can resume instantly.

### TODO
- [ ] Write setup instructions in `README.md`
- [ ] Document `ffmpeg` dependency
- [ ] Document environment variable setup
- [ ] Add example CLI commands
- [ ] Document output files
- [ ] Add troubleshooting notes
- [ ] Add a short architecture section

### README topics
- [ ] what the tool does
- [ ] how to install dependencies with `uv`
- [ ] how to install/check `ffmpeg`
- [ ] how to set `ELEVENLABS_API_KEY`
- [ ] how to run translation only
- [ ] how to run translation + dubbing
- [ ] what files are produced

### Acceptance criteria
- [ ] a new clone of the repo can be set up from README alone
- [ ] common failures have obvious fixes

---

## Phase 14 — Study-Oriented Enhancements After MVP

These are not required for first completion, but the architecture should leave room for them.

### Nice next steps
- [ ] split long translated text into TTS chunks
- [ ] keep separate `subtitle_text` and `tts_text`
- [ ] add pronunciation dictionary support
- [ ] add `.vtt` writer
- [ ] add support for `.wav`, `.m4a`, `.mp4`
- [ ] add batch processing
- [ ] add voice selection listing
- [ ] add retries/backoff for ElevenLabs failures
- [ ] add optional speaker-aware workflows later

### Design reminder
Do not implement these until the first end-to-end version is solid.

---

## Recommended Build Order

### Step 1
- [ ] project init
- [ ] dependencies
- [ ] package structure
- [ ] models
- [ ] errors
- [ ] validators

### Step 2
- [ ] CLI parser
- [ ] Whisper translation service
- [ ] TXT/SRT/JSON writers

### Step 3
- [ ] ElevenLabs SDK wrapper
- [ ] dubbing orchestration
- [ ] end-to-end `main.py`

### Step 4
- [ ] tests
- [ ] README
- [ ] cleanup and refactor

---

## MVP Definition

The MVP is complete when all of the following are true:

- [ ] a Russian MP3 can be translated to English with Whisper
- [ ] `.txt`, `.srt`, and `.json` are saved
- [ ] English audio can be synthesized with ElevenLabs
- [ ] the CLI can run translation-only or full dubbing
- [ ] the code is modular and readable
- [ ] common failures are handled cleanly
- [ ] the project is easy to extend without major rewrites

---

## Final Implementation Checklist

### Repository and tooling
- [ ] initialize with `uv`
- [ ] configure `pyproject.toml`
- [ ] add lint/test/type-check tools

### Core app
- [ ] implement models
- [ ] implement validators
- [ ] implement custom errors
- [ ] implement CLI parsing

### Whisper
- [ ] load model
- [ ] translate Russian MP3 to English
- [ ] normalize result
- [ ] save TXT/SRT/JSON

### ElevenLabs
- [ ] load API key
- [ ] initialize client
- [ ] synthesize English audio
- [ ] save MP3

### UX
- [ ] clear terminal summaries
- [ ] clean failures
- [ ] useful README
- [ ] sample commands documented

---

## Keep in Mind During Implementation

- Do not let `main.py` become a giant script
- Do not let writers depend on raw third-party objects
- Do not leak SDK-specific details across the whole codebase
- Do not overdesign for features you are not building yet
- Do build obvious seams for future chunking, alternate TTS providers, and richer outputs
