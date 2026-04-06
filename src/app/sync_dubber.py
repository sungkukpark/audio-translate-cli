"""
Segment-synchronized dubbing.

Reads translation segments from a JSON file, synthesizes each one with
ElevenLabs, pads with silence to match original timestamps, and concatenates
into a single MP3 that stays roughly in sync with the original video.
"""

import json
import subprocess
import tempfile
from pathlib import Path

from app.elevenlabs_client import ElevenLabsTTS
from app.errors import TTSGenerationError


def _load_segments(json_path: Path) -> list[dict]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data.get("segments", [])


def _get_audio_duration(path: Path) -> float:
    """Return duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _create_silence(duration: float, output_path: Path) -> None:
    """Write a silent MP3 of the given duration (44100 Hz, mono)."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{duration:.3f}",
            "-acodec", "libmp3lame", "-b:a", "128k",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )


def synthesize_synced(
    json_path: Path,
    output_path: Path,
    tts: ElevenLabsTTS,
    min_segment_chars: int = 2,
    verbose: bool = False,
) -> int:
    """
    Synthesize each segment in json_path and write a time-aligned MP3 to output_path.
    Returns the number of segments processed.
    """
    segments = _load_segments(json_path)
    if not segments:
        raise TTSGenerationError(f"No segments found in {json_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pieces: list[Path] = []
        current_time = 0.0

        for seg in segments:
            idx = seg["index"]
            start = float(seg["start"])
            end = float(seg["end"])
            text = seg["text"].strip()
            slot_duration = end - start

            if verbose:
                print(f"    segment {idx}: [{start:.2f}s -> {end:.2f}s] {text[:60]}")

            # Fill any gap before this segment with silence
            gap = start - current_time
            if gap > 0.05:
                gap_path = tmp / f"gap_{idx}.mp3"
                _create_silence(gap, gap_path)
                pieces.append(gap_path)

            # Skip segments with no usable text
            if len(text) < min_segment_chars:
                silence_path = tmp / f"empty_{idx}.mp3"
                _create_silence(slot_duration, silence_path)
                pieces.append(silence_path)
                current_time = end
                continue

            # Synthesize this segment
            seg_path = tmp / f"seg_{idx}.mp3"
            try:
                tts.synthesize_to_mp3(text, seg_path)
            except Exception as e:
                raise TTSGenerationError(
                    f"Synthesis failed for segment {idx}: {e}"
                )

            synth_duration = _get_audio_duration(seg_path)
            pieces.append(seg_path)

            # Pad with silence if synthesized audio is shorter than the original slot
            padding = slot_duration - synth_duration
            if padding > 0.1:
                pad_path = tmp / f"pad_{idx}.mp3"
                _create_silence(padding, pad_path)
                pieces.append(pad_path)

            current_time = end

        if not pieces:
            raise TTSGenerationError("No audio pieces generated.")

        # Write ffmpeg concat list
        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in pieces),
            encoding="utf-8",
        )

        # Concatenate all pieces into final output
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-acodec", "libmp3lame", "-b:a", "128k",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )

    return len(segments)
