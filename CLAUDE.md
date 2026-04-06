# CLAUDE.md

## Project Overview

Build a Python application that translates **Russian speech in MP3 files into English text** using **OpenAI Whisper** (`openai-whisper` package).

The primary target is short audio files around **5 minutes**, but the design should remain clean and extensible for longer inputs.

The project must use:

- **Python**
- **uv** for environment and dependency management
- **openai-whisper** for transcription/translation
- **ffmpeg** installed on the host system

The first deliverable should be a **CLI program**. Structure the code so that a GUI or web frontend can be added later without rewriting the core logic.

---

## Core Goal

Given an input Russian MP3 file, the program should:

1. Validate the file
2. Load the audio safely
3. Run Whisper with **English translation**
4. Save the result in useful output formats
5. Print a concise success summary to the terminal

---

## Functional Requirements

### Input
- Accept an audio file path from the command line
- Initial supported input:
  - `.mp3`
- Prefer designing the code so future support for `.wav`, `.m4a`, `.mp4` is easy

### Processing
- Use Whisper with:
  - source language: **Russian**
  - task: **translate**
  - target output: **English**
- Default model should be configurable
- Reasonable default model:
  - `small` for CPU-friendly usage
  - allow `medium` or `large` via CLI option

### Output
The program should generate at least:

- `output.txt` — full translated English text
- `output.srt` — subtitle format
- `output.json` — structured result including segments and timestamps

Optional future output:
- `output.vtt`

### CLI behavior
Example usage:

```bash
uv run python -m app.main --input sample.mp3 --model small --output-dir outputs
```

Alternative acceptable entrypoint:

```bash
uv run translate-audio --input sample.mp3 --model small --output-dir outputs
```

The CLI should show:
- input file path
- selected model
- detected/assumed source language
- output directory
- success/failure summary

---

## Non-Functional Requirements

### Code Quality
- Use clean, modular Python
- Prefer small functions with single responsibility
- Add type hints everywhere practical
- Avoid giant monolithic scripts
- Keep business logic separate from CLI parsing

### Reliability
- Handle missing files gracefully
- Handle missing `ffmpeg` with a clear error message
- Handle Whisper/model loading failures cleanly
- Handle unsupported file extensions
- Never crash with unreadable stack traces for ordinary user mistakes

### Maintainability
- Keep the project easy to extend
- Make model selection configurable
- Centralize file output logic
- Keep translation pipeline isolated in a service/module

---

## Recommended Project Structure

```text
project-root/
├─ CLAUDE.md
├─ pyproject.toml
├─ README.md
├─ .python-version
├─ src/
│  └─ app/
│     ├─ __init__.py
│     ├─ main.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ translator.py
│     ├─ writers.py
│     ├─ utils.py
│     └─ models.py
├─ tests/
│  ├─ test_cli.py
│  ├─ test_writers.py
│  └─ test_utils.py
└─ outputs/
```

Use the `src/` layout.

---

## Dependency Management with uv

Use `uv` for everything.

### Initial setup
```bash
uv init
uv venv
```

### Add dependencies
```bash
uv add openai-whisper
```

Recommended dev dependencies:
```bash
uv add --dev pytest ruff mypy
```

If needed, install package in editable mode through uv-managed workflow.

### System dependency
The machine must also have **ffmpeg** installed and available on PATH.

Examples:

```bash
ffmpeg -version
```

If `ffmpeg` is not installed, the app should explain that Whisper requires it.

---

## Implementation Requirements

### 1. CLI
Use `argparse` unless there is a strong reason to use something else.

Required arguments/options:
- `--input`
- `--output-dir`
- `--model`

Optional useful flags:
- `--device` (`cpu`, `cuda`, `auto`)
- `--verbose`
- `--overwrite`
- `--output-prefix`

### 2. Translation Service
Create a dedicated module responsible for:
- loading the Whisper model
- executing translation
- returning normalized structured data

This module should not write files directly.

Suggested high-level function:

```python
def translate_audio(
    input_path: Path,
    model_name: str = "small",
    language: str = "ru",
    task: str = "translate",
) -> TranslationResult:
    ...
```

### 3. Result Model
Use a typed structure such as `dataclass` for normalized results.

Suggested models:
- `Segment`
- `TranslationResult`

Example fields:
- full text
- segments
- detected language
- model used
- duration if available

### 4. Writers
Create separate writer functions for:
- TXT
- SRT
- JSON

Do not mix formatting and inference logic.

### 5. Validation Utilities
Utility functions should cover:
- input file existence
- extension checks
- ffmpeg availability
- output directory creation

---

## Whisper Usage Guidance

Use the Python API rather than shelling out to the CLI.

Preferred flow:

1. `whisper.load_model(model_name)`
2. `model.transcribe(...)`
3. Set:
   - `task="translate"`
   - `language="ru"`

The implementation should explicitly favor deterministic and understandable behavior over premature optimization.

Example intent:

```python
result = model.transcribe(
    str(input_path),
    language="ru",
    task="translate",
)
```

Do not assume GPU is available.

---

## Output Format Expectations

### TXT
- Save the full translated English text only
- UTF-8 encoding

### SRT
- Use segment timestamps
- Proper `HH:MM:SS,mmm` formatting
- Number each subtitle block correctly

### JSON
Include structured metadata such as:
- input file name
- model name
- source language
- output text
- segments with:
  - start
  - end
  - text

---

## Error Handling Requirements

Provide clear, actionable messages for cases like:

### Missing input
- "Input file not found: ..."

### Invalid extension
- "Unsupported input format. Expected .mp3"

### Missing ffmpeg
- "ffmpeg is not installed or not available on PATH"

### Whisper load failure
- Explain model loading failed
- Suggest checking Python environment and dependencies

### Runtime failure
- Show concise error summary
- Exit with non-zero status code

Do not dump raw internals unless `--verbose` is enabled.

---

## Testing Expectations

Add tests for the parts that can be tested without expensive model execution.

Minimum tests:
- file validation
- SRT formatting
- JSON writing
- output directory creation
- CLI argument parsing

Do not require model inference in unit tests unless explicitly creating integration tests.

If integration tests are added later, gate them behind a marker and make them optional.

---

## Style and Tooling

Use:
- `ruff` for linting
- `mypy` for type checking where practical
- `pytest` for tests

Suggested commands:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

---

## Performance Guidance

This is not a premature optimization project.

Priorities:
1. correctness
2. clarity
3. useful output
4. extensibility

Because target files are around 5 minutes, simple synchronous processing is acceptable for the first version.

Do not add multiprocessing, queues, or async code unless there is a real need.

---

## UX Expectations

The tool should feel straightforward for a solo developer.

A good terminal run should look conceptually like:

```text
Input: sample.mp3
Model: small
Language: ru
Task: translate
Output directory: outputs

Translating...
Done.

Saved:
- outputs/output.txt
- outputs/output.srt
- outputs/output.json
```

---

## Future Extensions

Design so the following can be added later with minimal refactor:

- batch processing of multiple files
- drag-and-drop desktop GUI
- simple web UI
- VTT export
- speaker segmentation
- optional English voice synthesis
- automatic language detection mode
- video file support

---

## Coding Preferences

When implementing this project:

- prefer explicit code over clever abstractions
- keep functions short
- use descriptive names
- avoid hidden global state
- avoid unnecessary classes
- use dataclasses where they simplify structured data
- keep side effects isolated

---

## Deliverable Priority Order

1. `pyproject.toml` configured for uv project
2. clean `src/app` package
3. working CLI translator
4. TXT/SRT/JSON writers
5. validation and error handling
6. tests
7. README usage instructions

---

## Acceptance Criteria

The implementation is acceptable when all of the following are true:

- `uv run python -m app.main --input some.mp3 --model small --output-dir outputs` works
- a Russian MP3 file is translated into English
- TXT, SRT, and JSON files are created
- user-facing errors are clear
- code is modular and readable
- project is ready for incremental extension

---

## Notes for the Implementing Assistant

Do not drift into unrelated architecture work.

Build the smallest solid version first.

If a design choice is ambiguous, choose the option that:
- reduces hidden complexity
- improves debuggability
- keeps the CLI usable
- preserves easy extension later
