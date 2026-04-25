"""
CGMA Level Design — English MP4 → Korean SRT.

Two-pass pipeline to avoid GPU OOM when both models are large:

  Pass 1 (Whisper) — transcribe each *.mp4 → save segments to *.en.json
  Pass 2 (NLLB)   — read *.en.json, translate to Korean, write *.ko.srt

The *.en.json cache survives a crash so transcription never has to be repeated.

Usage:
    uv run python cgma_translate_ko.py                      # full run
    uv run python cgma_translate_ko.py --only-first         # smoke-test
    uv run python cgma_translate_ko.py --overwrite          # redo everything
    uv run python cgma_translate_ko.py --trans-model facebook/nllb-200-distilled-1.3B
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.translator import load_model, resolve_device
from app.utils import check_ffmpeg

SRC_ROOT = Path(r"D:\temp\CGMA - Level Design for Games")

# Domain hint — keeps Whisper on-topic and using correct game-dev terminology
INITIAL_PROMPT = (
    "This is a lecture on 3D level design for games. "
    "Topics include geometry, lighting, composition, Unreal Engine, Unity, "
    "gameplay spaces, blockout, greybox, environment art, and game design theory."
)

DEFAULT_WHISPER_MODEL = "large-v3"
# facebook/nllb-200-distilled-600M  (~2.3 GB, good quality)
# facebook/nllb-200-distilled-1.3B  (~5 GB, higher quality)
DEFAULT_TRANS_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_SRC_LANG = "eng_Latn"
NLLB_TGT_LANG = "kor_Hang"
TRANSLATION_BATCH = 4   # segments per NLLB batch (lower = less VRAM)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Transcribe CGMA English MP4 lectures and produce Korean SRT subtitles."
    )
    p.add_argument("--input", type=Path,
                   help="Process a single MP4 file instead of scanning SRC_ROOT")
    p.add_argument("--src-root", type=Path,
                   help="Root directory to scan for *.mp4 (overrides built-in SRC_ROOT)")
    p.add_argument("--model", default=DEFAULT_WHISPER_MODEL,
                   choices=["medium", "large", "large-v2", "large-v3"],
                   help=f"Whisper model (default: {DEFAULT_WHISPER_MODEL})")
    p.add_argument("--device", default="cuda", choices=["cpu", "cuda"],
                   help="Inference device (default: cuda)")
    p.add_argument("--trans-model", default=DEFAULT_TRANS_MODEL,
                   help=f"HuggingFace NLLB translation model (default: {DEFAULT_TRANS_MODEL})")
    p.add_argument("--only-first", action="store_true",
                   help="Process only the first file (smoke test)")
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
# Pass 1 — Whisper transcription
# ---------------------------------------------------------------------------

def transcribe_pass(mp4_files: list[Path], args: argparse.Namespace, src_root: Path = SRC_ROOT) -> None:
    """Transcribe each MP4 and save segments to a .en.json cache file."""
    import torch

    todo = [f for f in mp4_files
            if args.overwrite or not f.with_suffix(".en.json").exists()]

    if not todo:
        print("Pass 1: all .en.json caches already exist, skipping transcription.")
        return

    print(f"Pass 1 — Whisper transcription ({len(todo)} files to process)")
    print("Loading Whisper model (large-v3 ~3 GB, downloads once) ...")
    try:
        whisper_model = load_model(args.model, args.device)
    except Exception as e:
        print(f"Error loading Whisper: {e}", file=sys.stderr)
        sys.exit(1)
    actual_device = getattr(whisper_model, "_actual_device", resolve_device(args.device))
    print(f"Whisper ready on: {actual_device}")
    print()

    done = failed = 0
    for idx, mp4 in enumerate(todo, 1):
        json_path = mp4.with_suffix(".en.json")
        try:
            label = mp4.relative_to(src_root)
        except ValueError:
            label = mp4
        print(f"  [{idx}/{len(todo)}] {label}")
        try:
            result = whisper_model.transcribe(
                str(mp4),
                language="en",
                task="transcribe",
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

    # Free GPU memory before loading the translation model
    del whisper_model
    torch.cuda.empty_cache()

    print()
    print(f"Pass 1 done — transcribed: {done}, failed: {failed}")
    print()


# ---------------------------------------------------------------------------
# Pass 2 — NLLB translation
# ---------------------------------------------------------------------------

class NLLBTranslator:
    """Wraps NLLB-200 for batched English → Korean translation."""

    def __init__(self, model_name: str, device: str) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.device = torch.device(
            "cuda" if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        )
        print(f"Loading translation model: {model_name} (device={self.device}) ...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        dtype = torch.float16 if self.device.type == "cuda" else torch.float32
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=dtype).to(self.device)
        self.model.eval()
        self._tgt_id = self.tokenizer.convert_tokens_to_ids(NLLB_TGT_LANG)
        print(f"Translation model ready (dtype={dtype}).")

    def translate(self, texts: list[str], num_beams: int = 2) -> list[str]:
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
                num_beams=num_beams,
            )
        return self.tokenizer.batch_decode(out, skip_special_tokens=True)


def translate_texts(translator: NLLBTranslator, texts: list[str]) -> list[str]:
    import torch

    results: list[str] = []
    batch = TRANSLATION_BATCH
    num_beams = 2
    i = 0
    while i < len(texts):
        chunk = texts[i : i + batch]
        try:
            translated = translator.translate(chunk, num_beams=num_beams)
            results.extend(translated)
            end = min(i + batch, len(texts))
            print(f"    [{end}/{len(texts)}] {texts[i][:60].strip()!r}", flush=True)
            i += batch
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            if "out of memory" not in str(e).lower() and not isinstance(e, torch.cuda.OutOfMemoryError):
                raise
            torch.cuda.empty_cache()
            if batch > 1:
                batch = max(1, batch // 2)
                print(f"    [OOM] reducing batch to {batch}, retrying ...")
            elif num_beams > 1:
                num_beams = 1
                print(f"    [OOM] switching to greedy (num_beams=1), retrying ...")
            else:
                raise
    return results


def translate_pass(mp4_files: list[Path], args: argparse.Namespace, src_root: Path = SRC_ROOT) -> int:
    """Read .en.json caches, translate to Korean, write .ko.srt files."""
    todo = [f for f in mp4_files
            if f.with_suffix(".en.json").exists()
            and (args.overwrite or not f.with_suffix(".ko.srt").exists())]

    if not todo:
        print("Pass 2: nothing to translate.")
        return 0

    print(f"Pass 2 — NLLB translation ({len(todo)} files)")
    try:
        translator = NLLBTranslator(args.trans_model, resolve_device(args.device))
    except Exception as e:
        print(f"Error loading translation model: {e}", file=sys.stderr)
        sys.exit(1)
    print()

    done = failed = 0
    for idx, mp4 in enumerate(todo, 1):
        json_path = mp4.with_suffix(".en.json")
        out_srt = mp4.with_suffix(".ko.srt")
        try:
            label = mp4.relative_to(src_root)
        except ValueError:
            label = mp4
        print(f"  [{idx}/{len(todo)}] {label}")
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
    check_ffmpeg()

    src_root = args.src_root.resolve() if args.src_root else SRC_ROOT
    if args.input:
        mp4_files = [args.input.resolve()]
        if not mp4_files[0].exists():
            print(f"Input file not found: {mp4_files[0]}", file=sys.stderr)
            sys.exit(1)
    else:
        mp4_files = sorted(src_root.rglob("*.mp4"))
    if not mp4_files:
        print(f"No *.mp4 files found under: {src_root}")
        sys.exit(0)

    if args.only_first:
        mp4_files = mp4_files[:1]
        print("[--only-first] Processing single file for testing.\n")

    total = len(mp4_files)
    print(f"Source root  : {src_root}")
    print(f"Whisper      : {args.model}  |  Device: {args.device}")
    print(f"Translator   : {args.trans_model}")
    print(f"Files        : {total}")
    print()

    transcribe_pass(mp4_files, args, src_root)
    failures = translate_pass(mp4_files, args, src_root)

    print("=" * 60)
    srt_count = sum(1 for f in mp4_files if f.with_suffix(".ko.srt").exists())
    print(f"Korean SRTs present : {srt_count} / {total}")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
