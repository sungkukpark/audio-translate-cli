import sys
from pathlib import Path

from app.cli import parse_args
from app.translator import translate_audio
from app.utils import check_ffmpeg, ensure_output_dir, validate_input_file
from app.writers import write_all


def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    input_path: Path = args.input.resolve()
    output_dir: Path = args.output_dir.resolve()
    model_name: str = args.model
    device: str = args.device
    verbose: bool = args.verbose
    overwrite: bool = args.overwrite
    prefix: str = args.output_prefix or input_path.stem

    print(f"Input:            {input_path}")
    print(f"Model:            {model_name}")
    print(f"Language:         ru (Russian)")
    print(f"Task:             translate -> English")
    print(f"Output directory: {output_dir}")
    print(f"Output prefix:    {prefix}")
    print()

    check_ffmpeg()
    validate_input_file(input_path)
    ensure_output_dir(output_dir)

    # Check for existing outputs if not overwriting
    if not overwrite:
        existing = [
            p for ext in (".txt", ".srt", ".json")
            if (p := output_dir / f"{prefix}{ext}").exists()
        ]
        if existing:
            print("Warning: Output files already exist (use --overwrite to replace):")
            for p in existing:
                print(f"  {p}")
            sys.exit(0)

    print("Translating...")
    result = translate_audio(
        input_path=input_path,
        model_name=model_name,
        device=device,
        verbose=verbose,
    )

    written = write_all(result, output_dir, prefix=prefix)

    print("Done.")
    print()
    print("Saved:")
    for path in written:
        print(f"  {path}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
