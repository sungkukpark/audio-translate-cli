"""
Batch translate Russian MP3/MP4 files to Korean SRT subtitles.

Two-pass pipeline to avoid GPU OOM when both models are large:

  Pass 1 (Whisper)  — Russian audio → English segments → *.en.json cache
  Pass 2 (NLLB)     — *.en.json → Korean text → *.ko.srt

Output files are written alongside the source files in the same folder.
The *.en.json cache survives crashes so transcription is never repeated.

Usage:
    uv run python batch_translate_ko.py                      # full run
    uv run python batch_translate_ko.py --only-first         # smoke-test one file
    uv run python batch_translate_ko.py --overwrite          # redo everything
    uv run python batch_translate_ko.py --trans-model facebook/nllb-200-distilled-1.3B
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.translator import load_model, resolve_device
from app.utils import check_ffmpeg

SRC_ROOT = Path(r"D:\temp\CGMA - Level Design for Games")

INITIAL_PROMPT = (
    "This is a lecture on 3D level design for games. "
    "Topics include geometry, lighting, composition, Unreal Engine, Unity, "
    "gameplay spaces, blockout, greybox, environment art, and game design theory."
)

DEFAULT_WHISPER_MODEL = "large-v3"
DEFAULT_TRANS_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_SRC_LANG = "eng_Latn"
NLLB_TGT_LANG = "kor_Hang"
TRANSLATION_BATCH = 16


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch-translate Russian MP3/MP4 lectures to Korean SRT subtitles."
    )
    p.add_argument("--model", default=DEFAULT_WHISPER_MODEL,
                   choices=["medium", "large", "large-v2", "large-v3"],
                   help=f"Whisper model (default: {DEFAULT_WHISPER_MODEL})")
    p.add_argument("--device", default="cuda", choices=["cpu", "cuda"],
                   help="Inference device (default: cuda)")
    p.add_argument("--trans-model", default=DEFAULT_TRANS_MODEL,
                   help=f"HuggingFace NLLB translation model (default: {DEFAULT_TRANS_MODEL})")
    p.add_argument("--source", type=Path, default=SRC_ROOT,
                   help=f"Root directory to search for audio files (default: {SRC_ROOT})")
    p.add_argument("--only-first", action="store_true",
                   help="Process only the first file (smoke test)")
    p.add_argument("--translate-only", action="store_true",
                   help="Skip Pass 1 (Whisper) and only run Pass 2 (NLLB translation)")
    p.add_argument("--overwrite", action="store_true",
                   help="Re-transcribe and re-translate files that already have outputs")
    p.add_argument("--verbose", action="store_true",
                   help="Show per-segment Whisper output and tracebacks on failure")
    return p.parse_args()


# ---------------------------------------------------------------------------
# SRT writer
# ---------------------------------------------------------------------------

def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_ko_srt(segments: list[dict], ko_texts: list[str], out_path: Path) -> None:
    lines: list[str] = []
    for idx, (seg, text) in enumerate(zip(segments, ko_texts), 1):
        lines.append(str(idx))
        lines.append(f"{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}")
        lines.append(text.strip())
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pass 1 — Whisper transcription (Russian → English)
# ---------------------------------------------------------------------------

def transcribe_pass(audio_files: list[Path], args: argparse.Namespace) -> None:
    """Translate each Russian audio file to English and save segments to .en.json."""
    import torch

    todo = [f for f in audio_files
            if args.overwrite or not f.with_suffix(".en.json").exists()]

    if not todo:
        print("Pass 1: all .en.json caches already exist, skipping transcription.")
        return

    print(f"Pass 1 — Whisper transcription ({len(todo)} file(s) to process)")
    print(f"Loading Whisper model ({args.model}, downloads once if not cached) ...")
    try:
        whisper_model = load_model(args.model, args.device)
    except Exception as e:
        print(f"Error loading Whisper: {e}", file=sys.stderr)
        sys.exit(1)
    actual_device = getattr(whisper_model, "_actual_device", resolve_device(args.device))
    print(f"Whisper ready on: {actual_device}")
    print()

    done = failed = 0
    src_root: Path = args.source.resolve()

    for idx, audio in enumerate(todo, 1):
        json_path = audio.with_suffix(".en.json")
        try:
            rel = audio.relative_to(src_root)
        except ValueError:
            rel = Path(audio.name)

        print(f"  [{idx}/{len(todo)}] {rel}")
        try:
            result = whisper_model.transcribe(
                str(audio),
                language="ru",
                task="translate",
                verbose=args.verbose,
                fp16=(actual_device == "cuda"),
                initial_prompt=INITIAL_PROMPT,
            )
            segments = [
                {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                for s in result.get("segments", [])
            ]
            json_path.write_text(
                json.dumps({"segments": segments}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"    -> {json_path.name}  ({len(segments)} segments)")
            done += 1
        except Exception as e:
            failed += 1
            print(f"    -> FAILED: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()

    del whisper_model
    import torch
    torch.cuda.empty_cache()

    print()
    print(f"Pass 1 done — transcribed: {done}, failed: {failed}")
    print()


# ---------------------------------------------------------------------------
# Pass 2 — NLLB translation (English → Korean)
# ---------------------------------------------------------------------------

class NLLBTranslator:
    def __init__(self, model_name: str, device: str) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.device = torch.device(
            "cuda" if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        )
        print(f"Loading translation model: {model_name} (device={self.device}) ...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self._tgt_id = self.tokenizer.convert_tokens_to_ids(NLLB_TGT_LANG)
        print("Translation model ready.")

    def translate(self, texts: list[str]) -> list[str]:
        import torch

        with torch.no_grad():
            enc = self.tokenizer(
                texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
                src_lang=NLLB_SRC_LANG,
            ).to(self.device)
            out = self.model.generate(
                **enc,
                forced_bos_token_id=self._tgt_id,
                max_length=512,
                num_beams=4,
            )
        return self.tokenizer.batch_decode(out, skip_special_tokens=True)


def translate_texts(translator: NLLBTranslator, texts: list[str]) -> list[str]:
    results: list[str] = []
    for i in range(0, len(texts), TRANSLATION_BATCH):
        chunk = texts[i : i + TRANSLATION_BATCH]
        results.extend(translator.translate(chunk))
    return results


def translate_pass(audio_files: list[Path], args: argparse.Namespace) -> int:
    """Read .en.json caches, translate to Korean, write .ko.srt files."""
    todo = [f for f in audio_files
            if f.with_suffix(".en.json").exists()
            and (args.overwrite or not f.with_suffix(".ko.srt").exists())]

    if not todo:
        print("Pass 2: nothing to translate.")
        return 0

    print(f"Pass 2 — NLLB translation ({len(todo)} file(s))")
    try:
        translator = NLLBTranslator(args.trans_model, resolve_device(args.device))
    except Exception as e:
        print(f"Error loading translation model: {e}", file=sys.stderr)
        sys.exit(1)
    print()

    done = failed = 0
    src_root: Path = args.source.resolve()

    for idx, audio in enumerate(todo, 1):
        json_path = audio.with_suffix(".en.json")
        out_srt = audio.with_suffix(".ko.srt")
        try:
            rel = audio.relative_to(src_root)
        except ValueError:
            rel = Path(audio.name)

        print(f"  [{idx}/{len(todo)}] {rel}")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            segments = data["segments"]
            if not segments:
                print("    -> No segments, skipping.")
                continue
            en_texts = [s["text"] for s in segments]
            ko_texts = translate_texts(translator, en_texts)
            write_ko_srt(segments, ko_texts, out_srt)
            print(f"    -> {out_srt.name}  ({len(segments)} segments)")
            done += 1
        except Exception as e:
            failed += 1
            print(f"    -> FAILED: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()

    print()
    print(f"Pass 2 done — translated: {done}, failed: {failed}")
    return failed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    src_root: Path = args.source.resolve()

    if not src_root.is_dir():
        print(f"Error: Source directory not found: {src_root}", file=sys.stderr)
        sys.exit(1)

    check_ffmpeg()

    audio_files = sorted(src_root.rglob("*.mp3")) + sorted(src_root.rglob("*.mp4"))
    audio_files = sorted(set(audio_files))

    if not audio_files:
        print(f"No *.mp3 or *.mp4 files found under: {src_root}")
        sys.exit(0)

    if args.only_first:
        audio_files = audio_files[:1]
        print("[--only-first] Processing single file for testing.\n")

    total = len(audio_files)
    print(f"Source   : {src_root}")
    print(f"Output   : alongside source files")
    print(f"Whisper  : {args.model}  |  Device: {args.device}")
    print(f"NLLB     : {args.trans_model}")
    print(f"Files    : {total}")
    print()

    if not args.translate_only:
        transcribe_pass(audio_files, args)
    failures = translate_pass(audio_files, args)

    print("=" * 60)
    ko_srt_count = sum(1 for f in audio_files if f.with_suffix(".ko.srt").exists())
    print(f"Korean SRTs present: {ko_srt_count} / {total}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
