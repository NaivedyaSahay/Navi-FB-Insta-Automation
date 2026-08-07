"""
voice_generator.py
------------------
Converts text scripts into natural voiceovers using Microsoft Edge TTS (edge-tts).
Extracts precise word-level timing data for synced dynamic caption rendering.

Public API:
    audio_path, word_timings = generate_voiceover(text="...", output_path=None)
    # Returns (Path to mp3, list of {"word": str, "start": float, "end": float})
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any

import edge_tts

import config

logger = logging.getLogger("voice_generator")


async def _synthesize_async(
    text: str, output_path: Path, voice: str, rate: str, volume: str
) -> List[Dict[str, Any]]:
    """Synthesize audio and collect word timing boundaries from edge_tts."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    submaker = edge_tts.SubMaker()
    word_timings = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # Save word timing: start offset & duration in seconds
                w_text = chunk["text"]
                start_sec = chunk["offset"] / 10_000_000.0   # 100ns units to sec
                dur_sec   = chunk["duration"] / 10_000_000.0
                end_sec   = start_sec + dur_sec
                word_timings.append({
                    "word": w_text,
                    "start": round(start_sec, 3),
                    "end": round(end_sec, 3),
                })
            elif chunk["type"] == "sentence":
                submaker.feed(chunk)

    return word_timings


def generate_voiceover(
    text: str,
    output_path: Path | None = None,
    voice: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """
    Generate voiceover MP3 and return (audio_path, word_timings).
    """
    output_path = Path(output_path or config.AUDIO_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    v = voice or config.TTS_VOICE
    r = rate or config.TTS_RATE
    vol = volume or config.TTS_VOLUME

    logger.info("Generating voiceover via Edge-TTS [voice=%s]...", v)

    try:
        # Run async TTS synthesis
        word_timings = asyncio.run(_synthesize_async(text, output_path, v, r, vol))
    except Exception as exc:
        logger.error("Edge-TTS synthesis failed: %s", exc)
        raise RuntimeError(f"Voiceover generation failed: {exc}") from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Generated audio file missing or empty: {output_path}")

    # Fallback word timing calculation if WordBoundary was missing
    if not word_timings:
        logger.info("No WordBoundary events received; calculating estimated word timings...")
        words = text.split()
        # Estimate total duration from audio size (~16KB per sec for MP3 128k)
        est_duration = max(2.0, len(words) * 0.35)
        time_per_word = est_duration / len(words)
        for idx, w in enumerate(words):
            word_timings.append({
                "word": w,
                "start": round(idx * time_per_word, 3),
                "end": round((idx + 1) * time_per_word, 3),
            })

    logger.info("Voiceover ready: %s (%.1f KB, %d word timestamps)",
                output_path, output_path.stat().st_size / 1024, len(word_timings))

    return output_path, word_timings


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    path, timings = generate_voiceover("This is a test of the satisfying video voice generator.")
    print(f"Generated: {path}, Timings count: {len(timings)}")
