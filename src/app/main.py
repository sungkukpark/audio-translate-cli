import sys
from pathlib import Path

from app import config
from app.cli import parse_args
from app.dubber import dub_translation_result
from app.elevenlabs_client import ElevenLabsTTS
from app.errors import AppError
from app.sync_dubber import synthesize_synced
from app.translator import load_model, translate_audio
from app.utils import (
    check_ffmpeg,
    ensure_elevenlabs_api_key,
    ensure_output_dir,
    validate_input_file,
)
from app.writers import write_all


def process_file(
    input_path: Path,
    output_dir: Path,
    model,
    model_name: str,
    device: str,
    verbose: bool,
    skip_tts: bool,
    sync_dub: bool,
    voice_id: str,
    tts_model: str,
    api_key: str | None,
    prefix: str | None = None,
) -> None:
    resolved = input_path.resolve()
    file_prefix = prefix or resolved.stem

    print(f"--- {resolved.name} ---")
    validate_input_file(resolved)

    print("Translating...")
    result = translate_audio(
        input_path=resolved,
        model=model,
        model_name=model_name,
        device=device,
        verbose=verbose,
    )
    print("Translation done.")

    written = write_all(result, output_dir, prefix=file_prefix)
    print("Saved:")
    for path in written:
        print(f"  {path}")

    if not skip_tts:
        audio_path = output_dir / f"{file_prefix}_en.mp3"
        if sync_dub:
            print("Synthesizing (segment-synchronized)...")
            json_path = output_dir / f"{file_prefix}.json"
            tts = ElevenLabsTTS(api_key=api_key, voice_id=voice_id, model_id=tts_model)
            n = synthesize_synced(json_path=json_path, output_path=audio_path, tts=tts, verbose=verbose)
            print(f"  {audio_path}  ({n} segments)")
        else:
            print("Synthesizing...")
            dub_result = dub_translation_result(
                result=result,
                output_path=audio_path,
                voice_id=voice_id,
                model_id=tts_model,
                api_key=api_key,
            )
            print(f"  {dub_result.output_path}")
            if dub_result.chunks_synthesized > 1:
                print(f"  ({dub_result.chunks_synthesized} chunks)")

    print()


def run_tts_only(
    json_path: Path,
    output_dir: Path,
    sync_dub: bool,
    voice_id: str,
    tts_model: str,
    api_key: str | None,
    verbose: bool,
    input_dir: Path | None = None,
    overwrite: bool = False,
) -> None:
    print(f"--- {json_path.name} ---")
    if not json_path.exists():
        print(f"  Skipped: file not found", file=sys.stderr)
        return

    prefix = json_path.stem
    if input_dir is not None:
        rel = json_path.parent.relative_to(input_dir)
        file_output_dir = output_dir / rel
        file_output_dir.mkdir(parents=True, exist_ok=True)
    else:
        file_output_dir = output_dir
    audio_path = file_output_dir / f"{prefix}_en.mp3"
    tts = ElevenLabsTTS(api_key=api_key, voice_id=voice_id, model_id=tts_model)

    if audio_path.exists() and not overwrite:
        print(f"  Skipped (already exists): {audio_path}")
        return

    if sync_dub:
        print("Synthesizing (segment-synchronized)...")
        n = synthesize_synced(json_path=json_path, output_path=audio_path, tts=tts, verbose=verbose)
        print(f"  {audio_path}  ({n} segments)")
    else:
        import json as _json
        text = _json.loads(json_path.read_text(encoding="utf-8")).get("text", "")
        if not text:
            print(f"  Skipped: no text in JSON", file=sys.stderr)
            return
        print("Synthesizing...")
        _, chunks = tts.synthesize_to_mp3(text, audio_path)
        print(f"  {audio_path}")
        if chunks > 1:
            print(f"  ({chunks} chunks)")

    print()


def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    output_dir: Path = args.output_dir.resolve()
    model_name: str = args.model
    device: str = args.device
    verbose: bool = args.verbose
    skip_tts: bool = args.skip_tts
    sync_dub: bool = args.sync_dub
    tts_only: bool = args.tts_only

    # Collect input files
    if args.input_dir:
        input_dir = args.input_dir.resolve()
        if not input_dir.is_dir():
            print(f"Error: input-dir not found: {input_dir}", file=sys.stderr)
            sys.exit(1)
        pattern = "*.json" if tts_only else "*.mp3"
        input_files = sorted(input_dir.rglob(pattern))
        if not input_files:
            print(f"Error: no {pattern} files found in {input_dir}", file=sys.stderr)
            sys.exit(1)
        prefix_override = None
    else:
        input_files = [args.input]
        prefix_override = args.output_prefix

    print(f"Files:            {len(input_files)}")
    if not tts_only:
        print(f"Model:            {model_name}")
    print(f"Output directory: {output_dir}")
    if not skip_tts:
        print(f"TTS voice:        {args.voice_id}")
        print(f"TTS model:        {args.tts_model}")
        if sync_dub:
            print(f"TTS mode:         segment-synchronized")
    if tts_only:
        print(f"Mode:             TTS only (from existing JSON)")
    print()

    try:
        check_ffmpeg()
        ensure_output_dir(output_dir)

        api_key = None
        if not skip_tts:
            api_key = ensure_elevenlabs_api_key(config.get_elevenlabs_api_key())

        model = None
        if not tts_only:
            print("Loading Whisper model...")
            model = load_model(model_name, device)
            print(f"Model loaded on: {model._actual_device}")
            print()

        for i, input_path in enumerate(input_files, 1):
            if len(input_files) > 1:
                print(f"[{i}/{len(input_files)}] ", end="")
            if tts_only:
                run_tts_only(
                    json_path=input_path.resolve(),
                    output_dir=output_dir,
                    sync_dub=sync_dub,
                    voice_id=args.voice_id,
                    tts_model=args.tts_model,
                    api_key=api_key,
                    verbose=verbose,
                    input_dir=input_dir,
                    overwrite=args.overwrite,
                )
            else:
                process_file(
                    input_path=input_path,
                    output_dir=output_dir,
                    model=model,
                    model_name=model_name,
                    device=device,
                    verbose=verbose,
                    skip_tts=skip_tts,
                    sync_dub=sync_dub,
                    voice_id=args.voice_id,
                    tts_model=args.tts_model,
                    api_key=api_key,
                    prefix=prefix_override,
                )

        print("All done.")

    except AppError as e:
        print(f"Error: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
