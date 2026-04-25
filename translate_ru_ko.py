"""
Bulk transcribe English dubbed MP3 files to Korean SRT subtitles.

Pipeline:
  1. Whisper transcribes English audio → English text + timestamps  (task="transcribe")
  2. facebook/nllb-200-distilled-600M translates each segment English → Korean
  3. Writes .srt files mirroring the source directory structure

Usage:
  uv run python translate_ru_ko.py [--overwrite] [--model large-v3] [--verbose]
"""
import argparse
import sys
from pathlib import Path

# Ensure stdout can handle Korean characters on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import torch
import whisper
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

SOURCE_DIR = Path(r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT2")
OUTPUT_DIR = Path(r"D:\Dropbox\Lectures\CGMA\[CGMA 3D] - Level Design for Games\OUT4")
NLLB_MODEL_NAME = "facebook/nllb-200-distilled-600M"
TRANSLATE_BATCH_SIZE = 16


def format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list[dict], output_path: Path) -> None:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def translate_batch(
    texts: list[str],
    tokenizer: AutoTokenizer,
    model: AutoModelForSeq2SeqLM,
    device: str,
) -> list[str]:
    forced_bos_token_id = tokenizer.convert_tokens_to_ids("kor_Hang")
    results: list[str] = []
    for i in range(0, len(texts), TRANSLATE_BATCH_SIZE):
        batch = texts[i : i + TRANSLATE_BATCH_SIZE]
        inputs = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                num_beams=4,
                max_new_tokens=256,
                max_length=None,
            )
        decoded = tokenizer.batch_decode(output_ids, skip_special_tokens=True)
        results.extend(decoded)
    return results


def process_file(
    mp3_path: Path,
    srt_path: Path,
    whisper_model,
    nllb_tokenizer: AutoTokenizer,
    nllb_model: AutoModelForSeq2SeqLM,
    device: str,
    overwrite: bool,
    verbose: bool,
) -> bool:
    """Returns True if file was processed, False if skipped."""
    if srt_path.exists() and not overwrite:
        print(f"  Skipped (exists): {srt_path.name}")
        return False

    srt_path.parent.mkdir(parents=True, exist_ok=True)

    print("  Transcribing (en via Whisper)...")
    result = whisper_model.transcribe(
        str(mp3_path),
        language="en",
        task="transcribe",
        fp16=(device == "cuda"),
        verbose=verbose if verbose else None,
    )

    raw_segments = result.get("segments", [])
    if not raw_segments:
        print("  Warning: no segments found, skipping.")
        return False

    en_texts = [seg["text"].strip() for seg in raw_segments]
    print(f"  Translating {len(en_texts)} segments (en → ko)...")
    ko_texts = translate_batch(en_texts, nllb_tokenizer, nllb_model, device)

    ko_segments = [
        {"start": raw_segments[i]["start"], "end": raw_segments[i]["end"], "text": ko_texts[i]}
        for i in range(len(raw_segments))
    ]

    write_srt(ko_segments, srt_path)
    print(f"  Saved: {srt_path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk Russian→Korean SRT translation")
    parser.add_argument("--model", default="large-v3", choices=["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"])
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing SRT files")
    parser.add_argument("--verbose", action="store_true", help="Show Whisper segment output")
    parser.add_argument("--input", type=Path, help="Process a single MP3 file instead of the full source dir")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if args.input:
        single = args.input.resolve()
        if not single.exists():
            print(f"File not found: {single}")
            sys.exit(1)
        mp3_files = [single]
    else:
        mp3_files = sorted(SOURCE_DIR.rglob("*.mp3"))
        if not mp3_files:
            print(f"No .mp3 files found in {SOURCE_DIR}")
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Source:  {SOURCE_DIR}")
    print(f"Output:  {OUTPUT_DIR}")
    print(f"Files:   {len(mp3_files)}")
    print(f"Model:   {args.model}")
    print(f"Device:  {device}")
    print()

    print(f"Loading Whisper ({args.model})...")
    w_model = whisper.load_model(args.model, device=device)
    print("Whisper ready.")

    print(f"Loading translation model ({NLLB_MODEL_NAME})...")
    nllb_tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_NAME, src_lang="eng_Latn")
    nllb_model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_NAME).to(device)
    nllb_model.eval()
    print("Translation model ready.")
    print()

    processed = 0
    skipped = 0

    for i, mp3_path in enumerate(mp3_files, 1):
        try:
            rel = mp3_path.relative_to(SOURCE_DIR)
        except ValueError:
            rel = Path(mp3_path.name)
        srt_path = OUTPUT_DIR / rel.with_suffix(".srt")

        print(f"[{i}/{len(mp3_files)}] {rel}")
        did_process = process_file(
            mp3_path=mp3_path,
            srt_path=srt_path,
            whisper_model=w_model,
            nllb_tokenizer=nllb_tokenizer,
            nllb_model=nllb_model,
            device=device,
            overwrite=args.overwrite,
            verbose=args.verbose,
        )
        if did_process:
            processed += 1
        else:
            skipped += 1
        print()

    print(f"Done. Processed: {processed}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
