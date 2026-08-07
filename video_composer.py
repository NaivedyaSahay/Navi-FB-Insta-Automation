"""
video_composer.py
------------------
Assembles final 9:16 (1080x1920) Facebook & Instagram Reels video.
Combines:
  1. Stitched satisfying background video (kinetic sand, 3D loops, ASMR, etc.)
  2. Synthesized voiceover audio
  3. Dynamic high-contrast animated viral captions (Impact font + thick stroke)

Public API:
    output_path = compose_video(audio_path, word_timings, script_text, keywords)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from moviepy import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
)
from PIL import Image, ImageDraw, ImageFont

import config
from satisfying_video_manager import get_satisfying_background

logger = logging.getLogger("video_composer")

W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT  # 1080 x 1920
FPS  = config.VIDEO_FPS

def _get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Find available Impact or Arial system font."""
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/ariblk.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        if font.getbbox(test)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines

def _group_words_into_caption_chunks(
    word_timings: List[Dict[str, Any]], words_per_chunk: int = 4
) -> List[Dict[str, Any]]:
    """Group individual word timestamps into short 3-4 word caption phrases."""
    if not word_timings:
        return []
    chunks = []
    for i in range(0, len(word_timings), words_per_chunk):
        group = word_timings[i : i + words_per_chunk]
        chunks.append({
            "text": " ".join(w["word"] for w in group),
            "start": group[0]["start"],
            "end": group[-1]["end"],
        })
    return chunks

def _render_viral_caption_rgba(text: str) -> np.ndarray:
    """
    Renders text in viral Reels style:
    - Large Impact font (76px)
    - White fill with 8-direction thick black stroke
    - Yellow accent (#FFE632) for emphasis
    - Transparent RGBA canvas (cap_h x W x 4)
    """
    cap_h = 320
    img = Image.new("RGBA", (W, cap_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if text:
        font = _get_font(78, bold=True)
        lines = _wrap_text(text.upper(), font, W - 100)
        line_h = 90
        tot_h = len(lines) * line_h
        text_y = (cap_h - tot_h) // 2

        stroke = 8  # thick black outline
        offsets = [
            (-stroke, -stroke), (0, -stroke), (stroke, -stroke),
            (-stroke, 0),                      (stroke, 0),
            (-stroke, stroke),  (0, stroke),  (stroke, stroke),
        ]

        for i, line in enumerate(lines):
            bbox = font.getbbox(line)
            x = (W - (bbox[2] - bbox[0])) // 2
            y = text_y + i * line_h

            # Draw black stroke outline
            for ox, oy in offsets:
                draw.text((x + ox, y + oy), line, font=font, fill=(0, 0, 0, 255))

            # Alternate between bright yellow and crisp white fill
            fill_color = (255, 230, 50, 255) if i % 2 == 0 else (255, 255, 255, 255)
            draw.text((x, y), line, font=font, fill=fill_color)

    return np.array(img)

def compose_video(
    audio_path: Path,
    word_timings: List[Dict[str, Any]] = None,
    script_text: str = "",
    keywords: List[str] = None,
    output_path: Path | None = None,
) -> Path:
    """
    Compose final video with satisfying visuals, audio, and dynamic captions.
    """
    output_path = Path(output_path or config.VIDEO_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Load audio
    audio_clip = AudioFileClip(str(audio_path))
    duration = audio_clip.duration
    logger.info("Audio duration: %.2f seconds", duration)

    # 1. Fetch stitched satisfying video background
    bg_clip = get_satisfying_background(target_duration=duration, keywords=keywords)

    # 2. Build caption overlay clips
    caption_chunks = _group_words_into_caption_chunks(word_timings or [], words_per_chunk=4)
    if not caption_chunks:
        caption_chunks = [{"text": script_text[:60], "start": 0.0, "end": duration}]

    caption_clips = []
    cap_h = 320
    cap_y = (H - cap_h) // 2  # Dead center of the screen

    for chunk in caption_chunks:
        c_start = max(0.0, chunk["start"])
        c_end = min(duration, chunk["end"])
        c_dur = max(0.15, c_end - c_start)

        cap_arr = _render_viral_caption_rgba(chunk["text"])
        cap_clip = (
            ImageClip(cap_arr)
            .with_position((0, cap_y))
            .with_start(c_start)
            .with_duration(c_dur)
        )
        caption_clips.append(cap_clip)

    # 3. Composite background + captions + audio
    logger.info("Compositing satisfying video background with %d caption chunks...", len(caption_clips))
    composite = CompositeVideoClip([bg_clip] + caption_clips, size=(W, H))
    final_video = composite.subclipped(0, duration).with_audio(audio_clip)

    # 4. Render & write final MP4 video file
    logger.info("Exporting Reels video -> %s [%dx%d @ %dfps]...", output_path, W, H, FPS)
    try:
        final_video.write_videofile(
            str(output_path),
            fps=FPS,
            codec=config.VIDEO_CODEC,
            audio_codec=config.AUDIO_CODEC,
            bitrate=config.VIDEO_BITRATE,
            audio_bitrate="128k",
            threads=4,
            preset="fast",
            logger="bar",
            ffmpeg_params=[
                "-pix_fmt", "yuv420p",       # Instagram requires yuv420p
                "-profile:v", "baseline",    # H.264 baseline profile for compatibility
                "-level", "3.1",             # H.264 level 3.1
                "-movflags", "+faststart",   # Move moov atom for streaming
                "-ar", "44100",              # Audio sample rate 44.1kHz
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Video export failed: {exc}") from exc
    finally:
        try:
            audio_clip.close()
            final_video.close()
        except Exception:
            pass

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Exported video missing or 0 bytes: {output_path}")

    logger.info("Final Reels video successfully created: %s (%.1f MB)",
                output_path, output_path.stat().st_size / (1024 * 1024))

    return output_path

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Video composer module ready.")
