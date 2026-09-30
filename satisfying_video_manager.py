"""
satisfying_video_manager.py
---------------------------
High-definition, 100% Free AI Mythological Video Visuals Generator.
Generates scene-by-scene 9:16 vertical mythological concept art matching
the narrative using FLUX.1-schnell via Hugging Face.

Applies 3D Ken Burns continuous motion (slow cinematic zoom) and smooth
crossfade transitions between scenes to create stunning, ultra-high-quality
AI-generated reels.

Public API:
    video_clip = get_video_background(target_duration, keywords, image_prompts)
    video_clip = get_satisfying_background(...) # Alias
"""

from __future__ import annotations

import logging
import random
import time
import urllib.parse
from pathlib import Path
from typing import List, Optional

import numpy as np
import requests
from moviepy import (
    VideoFileClip,
    ColorClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw

import config
import video_engine

logger = logging.getLogger("visual_manager")

W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT  # 1080 x 1920
FPS  = config.VIDEO_FPS


def _build_default_mythological_prompts(keywords: List[str] = None) -> List[str]:
    """Generates 4 rich default scene prompts if none were provided by the script."""
    kw_str = ", ".join(keywords) if keywords else "ancient Vedic sanctity"
    return [
        f"Ancient Indian temple sanctum, glowing diya oil lamps, sacred yagna fire, divine golden light rays, {kw_str}",
        f"Epic mythological warrior on golden chariot, celestial bows and arrows, storm clouds, lightning energy, {kw_str}",
        f"Divine cosmic manifestation, radiant golden aura, third eye energy, majestic Himalayan snow peaks, {kw_str}",
        f"Serene peaceful sunrise over the sacred Ganges river, ancient stone temple ghats, timeless spiritual wisdom, {kw_str}",
    ]


def _fetch_ai_mythological_scenes(image_prompts: List[str], count: int = 5) -> List[Path]:
    """
    Generates high-definition 9:16 AI mythological scenes using Hugging Face (FLUX.1-schnell)
    or high-quality Pollinations FLUX fallback.
    """
    saved: List[Path] = []
    prompts = [p.strip() for p in image_prompts if p.strip()][:count]
    if not prompts:
        prompts = _build_default_mythological_prompts()[:count]

    # Ensure output directory exists
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Primary: Hugging Face Inference API with FLUX.1-schnell
    if config.HF_TOKEN:
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=config.HF_TOKEN)
            logger.info("Generating %d AI mythological scenes via Hugging Face (%s)...",
                        len(prompts), config.HF_IMAGE_MODEL)

            for i, p in enumerate(prompts):
                dest = config.OUTPUT_DIR / f"ai_scene_{i}.jpg"
                enhanced_prompt = (
                    f"{p}, cinematic 9:16 vertical mythological concept art, "
                    f"hyperrealistic, 8k resolution, divine golden hour volumetric lighting, "
                    f"dramatic atmosphere, highly detailed ornaments and facial features, "
                    f"Unreal Engine 5 render, masterpiece"
                )
                try:
                    logger.info("🎨 Generating AI Scene #%d: '%s'...", i + 1, p[:60] + "...")
                    img = client.text_to_image(
                        prompt=enhanced_prompt,
                        model=config.HF_IMAGE_MODEL,
                        width=768,
                        height=1344,
                    )
                    img.save(str(dest), quality=95)
                    if dest.exists() and dest.stat().st_size > 5000:
                        saved.append(dest)
                except Exception as exc:
                    logger.warning("HF Scene #%d attempt 1 failed (%s). Retrying...", i + 1, exc)
                    time.sleep(1.0)
                    try:
                        # Retry with shorter prompt
                        img = client.text_to_image(
                            prompt=f"{p}, cinematic vertical 9:16 divine Indian mythology art, 8k, golden light",
                            model=config.HF_IMAGE_MODEL,
                            width=768,
                            height=1344,
                        )
                        img.save(str(dest), quality=95)
                        if dest.exists() and dest.stat().st_size > 5000:
                            saved.append(dest)
                    except Exception as retry_err:
                        logger.warning("HF Scene #%d retry failed: %s", i + 1, retry_err)

            if len(saved) >= 2:
                logger.info("Successfully generated %d AI scenes via Hugging Face FLUX.", len(saved))
                return saved
        except Exception as hf_err:
            logger.warning("Hugging Face client error: %s", hf_err)

    # 2. Free Pollinations FLUX endpoint fallback
    if len(saved) < 2:
        logger.info("Attempting AI scene generation via Pollinations FLUX...")
        for i, p in enumerate(prompts):
            if i < len(saved):
                continue
            dest = config.OUTPUT_DIR / f"ai_scene_{i}.jpg"
            try:
                clean_p = f"{p}, vertical 9:16 divine indian mythology wallpaper, cinematic 8k"
                enc = urllib.parse.quote(clean_p)
                url = f"https://image.pollinations.ai/prompt/{enc}?width=768&height=1344&model=flux&nologo=true"
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    dest.write_bytes(resp.content)
                    saved.append(dest)
            except Exception as exc:
                logger.debug("Pollinations scene error: %s", exc)

    logger.info("Total AI mythological scenes ready: %d", len(saved))
    return saved


def _generate_fallback_sacred_background(duration: float):
    """Generate dynamic colorful gradient clips as last-resort fallback."""
    logger.info("Generating animated sacred temple gradient fallback background...")
    palettes = [
        ((25, 10, 5), (95, 35, 10)),     # Deep Saffron / Sacred Flame
        ((15, 10, 45), (65, 20, 95)),    # Celestial Night / Rudra
        ((10, 25, 60), (20, 75, 135)),   # Sacred Waters / Yamuna
        ((35, 15, 10), (110, 45, 15)),   # Sacred Sandalwood / Surya
    ]

    clip_dur = max(4.0, duration / len(palettes))
    clips = []

    for top_col, bot_col in palettes:
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            fill_col = (
                int(top_col[0] * (1 - t) + bot_col[0] * t),
                int(top_col[1] * (1 - t) + bot_col[1] * t),
                int(top_col[2] * (1 - t) + bot_col[2] * t),
            )
            draw.line([(0, y), (W, y)], fill=fill_col)
        clip_arr = np.array(img)
        clips.append(ImageClip(clip_arr, duration=clip_dur).with_fps(FPS))

    combined = concatenate_videoclips(clips)
    if combined.duration < duration:
        loops = int(np.ceil(duration / combined.duration))
        combined = concatenate_videoclips([combined] * loops)

    return combined.subclipped(0, duration)


def get_video_background(
    target_duration: float,
    keywords: List[str] = None,
    image_prompts: List[str] = None,
):
    """
    Fetch and stitch topic-relevant visuals for background:
    100% AI-Generated Mythological Scenes with continuous 3D Ken Burns motion
    and smooth crossfades.
    """
    # 1. Ensure we have scene prompts
    prompts = image_prompts
    if not prompts or len(prompts) < 3:
        logger.info("Building tailored mythological scene prompts for keywords: %s", keywords)
        prompts = _build_default_mythological_prompts(keywords)

    # 2. Generate high-quality vertical AI scenes
    clip_paths = _fetch_ai_mythological_scenes(prompts, count=5)

    # 3. If AI generation succeeded, stitch with Ken Burns 3D motion and crossfade
    if clip_paths:
        try:
            logger.info("Rendering %d AI scenes with Ken Burns slow zoom and cinematic crossfades...", len(clip_paths))
            return video_engine.stitch_video_sequence(
                media_items=clip_paths,
                target_duration=target_duration,
                max_clip_duration=8.0,
                transition_duration=0.5,
                crossfade=True,
                mode="crop_cover",
            )
        except Exception as exc:
            logger.warning("Failed to stitch clips via video engine (%s). Using fallback background.", exc)

    logger.warning("No visual assets retrieved. Using sacred fallback background.")
    return _generate_fallback_sacred_background(target_duration)


# Alias for backward compatibility
get_satisfying_background = get_video_background


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bg = get_video_background(
        target_duration=12.0,
        keywords=["Lord Shiva", "Himalayas", "meditation"],
        image_prompts=[
            "Lord Shiva meditating on snow peaks of Mount Kailash, crescent moon, glowing third eye, vertical 9:16",
            "Sacred River Ganga flowing through ancient stone temples at sunrise, golden light, vertical 9:16",
        ]
    )
    print(f"Video background duration: {bg.duration}s")
