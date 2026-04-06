# audio-translate-cli

Translates Russian MP3 audio files into English text and English speech.

**Pipeline:**
```
Russian MP3  →  Whisper (translation)  →  .txt / .srt / .json
                                       →  ElevenLabs (TTS)  →  English MP3
```

---

## Requirements

| Dependency | Purpose |
|---|---|
| Python 3.10+ | Runtime |
| [uv](https://docs.astral.sh/uv/) | Package and environment manager |
| [ffmpeg](https://ffmpeg.org/download.html) | Audio decoding (required by Whisper) |
| NVIDIA GPU + CUDA 12.8 | Optional but strongly recommended for speed |
| ElevenLabs API key | Required for TTS synthesis |

### Verify requirements

```bash
uv --version
ffmpeg -version
nvidia-smi          # optional — confirms GPU driver
```

---

## Installation

```bash
git clone <repo-url>
cd audio-translate-cli
uv sync
```

This installs all Python dependencies including `openai-whisper`, `torch` (cu128), and `elevenlabs`.

---

## Configuration

Copy `.env.example` to `.env` and add your ElevenLabs API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
ELEVENLABS_API_KEY=sk_your_key_here
```

Get a key at [elevenlabs.io](https://elevenlabs.io).

---

## GPU Setup (CUDA)

By default the project uses `torch+cu128` (CUDA 12.8).  
If your machine does not have an NVIDIA GPU, reinstall CPU-only torch:

```bash
uv pip install torch torchvision torchaudio
```

To force CPU inference, pass `--device cpu` to any command.

---

## Single-file usage

### Translation only (no audio synthesis)

```bash
uv run python -m app.main \
  --input sample.mp3 \
  --output-dir outputs \
  --model medium \
  --skip-tts
```

Outputs:
```
outputs/
  sample.txt    ← full English text
  sample.srt    ← subtitles with timestamps
  sample.json   ← structured segments + metadata
```

### Translation + English audio

```bash
uv run python -m app.main \
  --input sample.mp3 \
  --output-dir outputs \
  --model medium
```

Additional output:
```
outputs/
  sample_en.mp3   ← English speech, time-aligned to original
```

### All CLI options

```
--input           Input audio file (.mp3 .wav .m4a .mp4)
--output-dir      Output directory (default: outputs/)
--model           Whisper model: tiny base small medium large large-v2 large-v3 (default: medium)
--device          cpu | cuda | auto (default: cuda)
--voice-id        ElevenLabs voice ID
--tts-model       ElevenLabs TTS model (default: eleven_multilingual_v2)
--output-prefix   Filename prefix for outputs (default: input stem)
--skip-tts        Run Whisper only, skip ElevenLabs
--overwrite       Overwrite existing output files
--verbose         Show Whisper segment progress and full tracebacks
```

---

## Whisper models

All models are free and run locally. Downloaded once and cached.

| Model | Size | Speed on CPU | Quality |
|---|---|---|---|
| `tiny` | 39 MB | ~32× realtime | lowest |
| `base` | 74 MB | ~16× realtime | low |
| `small` | 244 MB | ~6× realtime | good |
| `medium` | 769 MB | ~2× realtime | better |
| `large-v3` | 1550 MB | ~1× realtime | best |

**Recommended:** `medium` on CPU, `large-v3` on GPU.

---

## Batch translation (Russian MP3 → text artifacts)

Translates all `*.mp3` files under a directory tree and writes `.txt`, `.srt`, `.json` per file into a mirrored output tree.

```bash
uv run python batch_translate.py
```

Defaults:
- **Source:** `D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games`
- **Output root:** `...same...\OUT`
- **Model:** `medium`

Override defaults:

```bash
uv run python batch_translate.py \
  --source "D:\path\to\mp3s" \
  --output-root "D:\path\to\out" \
  --model large-v3 \
  --overwrite
```

Output structure:
```
OUT/
  week 1/
    lecture01.txt
    lecture01.srt
    lecture01.json
  week 2/
    ...
```

Already-translated files are skipped on re-runs. Safe to interrupt and resume.

---

## Batch dubbing (text → English MP3)

Reads the `.json` translation files produced by `batch_translate.py`, synthesizes each segment individually with ElevenLabs, and writes a time-aligned English MP3 per file.

```bash
uv run python batch_dub.py
```

Defaults:
- **Source:** `...CGMA...\OUT`
- **Output root:** `...CGMA...\OUT_2`
- **Voice:** `JBFqnCBsd6RMkjVDRZzb` (ElevenLabs — George)
- **TTS model:** `eleven_multilingual_v2`

Override defaults:

```bash
uv run python batch_dub.py \
  --source "D:\path\to\OUT" \
  --output-root "D:\path\to\OUT_2" \
  --voice-id <voice_id> \
  --overwrite
```

Output structure:
```
OUT_2/
  week 1/
    lecture01_en.mp3
  week 2/
    ...
```

### How time-alignment works

Each `.json` file contains segments with original timestamps (e.g. `[12.5s → 15.0s]`).  
For each segment:
1. Text is synthesized to audio via ElevenLabs
2. If synthesized audio is shorter than the original slot → padded with silence
3. Gaps between segments are also filled with silence
4. All pieces are concatenated with `ffmpeg` into a single MP3

The resulting audio plays in sync with the original video.

---

## Full end-to-end workflow

```
1. Run batch_translate.py   →  produces OUT/ with .txt .srt .json per file
2. Run batch_dub.py         →  produces OUT_2/ with _en.mp3 per file
```

```bash
uv run python batch_translate.py
uv run python batch_dub.py
```

---

## Project structure

```
audio-translate-cli/
├── .env.example             ← copy to .env and add API key
├── pyproject.toml
├── batch_translate.py       ← batch Whisper translation
├── batch_dub.py             ← batch ElevenLabs TTS synthesis
└── src/app/
    ├── main.py              ← single-file CLI entrypoint
    ├── cli.py               ← argument parsing
    ├── config.py            ← defaults and env loading
    ├── errors.py            ← typed exception hierarchy
    ├── models.py            ← Segment / TranslationResult / DubResult
    ├── translator.py        ← Whisper wrapper
    ├── sync_dubber.py       ← segment-synchronized TTS orchestration
    ├── elevenlabs_client.py ← ElevenLabs SDK wrapper
    ├── dubber.py            ← simple (non-synced) TTS orchestration
    ├── writers.py           ← TXT / SRT / JSON file writers
    └── utils.py             ← validation helpers
```

---

## Running tests

```bash
uv run pytest
```

```bash
uv run ruff check .
uv run mypy src
```

---

## Troubleshooting

**`ffmpeg is not installed`**  
Install ffmpeg and make sure it is on your PATH.  
Windows: download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add the `bin/` folder to PATH.

**`CUDA requested but not available`**  
Install the CUDA-enabled torch build:
```bash
uv pip install "torch==2.11.0+cu128" "torchvision==0.26.0+cu128" "torchaudio==2.11.0+cu128" \
  --index-url https://download.pytorch.org/whl/cu128 --force-reinstall
```

**`ELEVENLABS_API_KEY is not set`**  
Create a `.env` file in the project root with `ELEVENLABS_API_KEY=sk_...`.

**Whisper model download is slow or fails**  
Models are cached in `~/.cache/whisper`. Delete that folder to force a clean re-download.

**ElevenLabs synthesis fails mid-batch**  
Re-run `batch_dub.py` — completed files are skipped automatically.
