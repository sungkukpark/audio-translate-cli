import sys
from pathlib import Path

from app import config
from app.cli import parse_args
from app.dubber import dub_translation_result
from app.errors import AppError
from app.translator import load_model, translate_audio
from app.utils import (
    check_ffmpeg,
    ensure_elevenlabs_api_key,
    ensure_output_dir,
    validate_input_file,
)
from app.writers import write_all


def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    input_path: Path = args.input.resolve()
    output_dir: Path = args.output_dir.resolve()
    model_name: str = args.model
    device: str = args.device
    verbose: bool = args.verbose
    prefix: str = args.output_prefix or input_path.stem
    skip_tts: bool = args.skip_tts

    print(f"Input:            {input_path}")
    print(f"Model:            {model_name}")
    print(f"Language:         {config.DEFAULT_SOURCE_LANGUAGE} (Russian)")
    print(f"Task:             translate -> English")
    print(f"Output directory: {output_dir}")
    print(f"Output prefix:    {prefix}")
    if not skip_tts:
        print(f"TTS voice:        {args.voice_id}")
        print(f"TTS model:        {args.tts_model}")
    print()

    try:
        check_ffmpeg()
        validate_input_file(input_path)
        ensure_output_dir(output_dir)

        if not skip_tts:
            api_key = ensure_elevenlabs_api_key(config.get_elevenlabs_api_key())

        print("Loading Whisper model...")
        model = load_model(model_name, device)
        print(f"Model loaded on: {model._actual_device}")
        print()

        print("Translating...")
        result = translate_audio(
            input_path=input_path,
            model=model,
            model_name=model_name,
            device=device,
            verbose=verbose,
        )
        print("Translation done.")
        print()

        written = write_all(result, output_dir, prefix=prefix)
        print("Saved translation artifacts:")
        for path in written:
            print(f"  {path}")

        if not skip_tts:
            print()
            print("Synthesizing English audio...")
            audio_path = output_dir / f"{prefix}_en.mp3"
            dub_result = dub_translation_result(
                result=result,
                output_path=audio_path,
                voice_id=args.voice_id,
                model_id=args.tts_model,
                api_key=api_key,
            )
            print(f"Audio saved:")
            print(f"  {dub_result.output_path}")
            if dub_result.chunks_synthesized > 1:
                print(f"  (synthesized in {dub_result.chunks_synthesized} chunks)")

        print()
        print("Done.")

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
