"""
satisfying_video_manager.py
---------------------------
Fetches, processes, and stitches MULTIPLE topic-relevant background video clips
(e.g., matching script keywords like AI, space, oceans, brain, psychology, tech)
for Facebook & Instagram Reels.

Prioritizes:
  1. Pexels stock API (Searches topic-relevant keywords from the generated script)
  2. Pixabay stock API (Searches topic-relevant keywords from the generated script)
  3. Local offline clip pool in /satisfying_clips folder (if user placed files there)
  4. Animated colorful particle/gradient fallback background generator

Public API:
    video_clip = get_video_background(target_duration=35.0, keywords=["space", "black hole"])
    video_clip = get_satisfying_background(target_duration=35.0, keywords=[...]) # Alias
"""

from __future__ import annotations

import logging
import random
import urllib.request
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


def _download_clip(url: str, dest: Path, headers: dict = None) -> bool:
    try:
        req_headers = headers or {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        dl = requests.get(url, headers=req_headers, stream=True, timeout=60)
        dl.raise_for_status()
        with open(str(dest), "wb") as f:
            for chunk in dl.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
        return dest.stat().st_size > 10_000
    except Exception as exc:
        logger.debug("Clip download error (%s): %s", url, exc)
        return False


def _fetch_ai_mythological_scenes(image_prompts: List[str], count: int = 5) -> List[Path]:
    """
    Generates high-definition 9:16 AI mythological scenes using Hugging Face (FLUX.1-schnell)
    or Pollinations fallback for 100% free cinematic art.
    """
    saved: List[Path] = []
    prompts = [p.strip() for p in image_prompts if p.strip()][:count]
    if not prompts:
        return []

    # 1. Try Hugging Face Inference API if HF_TOKEN is provided
    if config.HF_TOKEN:
        try:
            from huggingface_hub import InferenceClient
            client = InferenceClient(token=config.HF_TOKEN)
            logger.info("Generating %d AI mythological scenes via Hugging Face (%s)...",
                        len(prompts), config.HF_IMAGE_MODEL)
            for i, p in enumerate(prompts):
                dest = config.OUTPUT_DIR / f"ai_scene_{i}.jpg"
                try:
                    logger.info("Generating AI Scene #%d: '%s'...", i + 1, p[:60] + "...")
                    img = client.text_to_image(
                        prompt=p + ", cinematic 8k vertical mythological wallpaper, masterpiece, divine lighting",
                        model=config.HF_IMAGE_MODEL,
                        width=768,
                        height=1344,
                    )
                    img.save(str(dest))
                    if dest.exists() and dest.stat().st_size > 5000:
                        saved.append(dest)
                except Exception as exc:
                    logger.warning("HF Scene #%d error: %s", i + 1, exc)
            if saved:
                logger.info("Successfully generated %d scenes via Hugging Face.", len(saved))
                return saved
        except Exception as hf_err:
            logger.warning("Hugging Face client initialization failed: %s", hf_err)

    # 2. Free Pollinations endpoint fallback
    import urllib.parse
    logger.info("Attempting free AI scene generation via Pollinations...")
    for i, p in enumerate(prompts):
        dest = config.OUTPUT_DIR / f"ai_scene_{i}.jpg"
        try:
            enc = urllib.parse.quote(p)
            url = f"https://image.pollinations.ai/prompt/{enc}?width=768&height=1344&nologo=true"
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and len(resp.content) > 5000:
                dest.write_bytes(resp.content)
                saved.append(dest)
        except Exception as exc:
            logger.debug("Pollinations scene error: %s", exc)

    logger.info("Retrieved %d AI mythological scenes.", len(saved))
    return saved


def _fetch_pexels_relevant_clips(keywords: List[str], count: int = 5) -> List[Path]:
    """Fetch topic-relevant portrait video clips from Pexels in Full HD (1080p)."""
    if not config.PEXELS_API_KEY:
        return []

    headers = {"Authorization": config.PEXELS_API_KEY}
    saved: List[Path] = []

    # Prepare search queries from script keywords
    queries = [kw.strip() for kw in keywords if kw.strip()]
    if not queries:
        queries = ["ancient temple", "sacred fire", "himalayas", "meditation", "golden divine light"]

    # Deduplicate queries while preserving order
    queries = list(dict.fromkeys(queries))

    for i, q in enumerate(queries):
        if len(saved) >= count:
            break
        try:
            logger.info("Searching Pexels for topic-relevant clip: '%s'...", q)
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": q, "orientation": "portrait", "size": "large", "per_page": 5},
                timeout=12,
            )
            if resp.status_code != 200:
                continue
            videos = resp.json().get("videos", [])
            for vid in videos:
                files = vid.get("video_files", [])
                portrait = [f for f in files if f.get("height", 0) >= f.get("width", 1)] or files
                if portrait:
                    # Sort descending to pick Full HD (1080p) instead of 360p
                    portrait.sort(key=lambda f: f.get("width", 0) * f.get("height", 0), reverse=True)
                    best_file = None
                    for f in portrait:
                        if f.get("width") == 1080 or f.get("height") == 1920:
                            best_file = f
                            break
                    if not best_file:
                        candidates = [f for f in portrait if f.get("width", 0) <= 1080 and f.get("height", 0) <= 1920]
                        best_file = candidates[0] if candidates else portrait[0]

                    url = best_file["link"]
                    dest = config.OUTPUT_DIR / f"rel_pexels_{i}_{len(saved)}.mp4"
                    logger.info("Downloading Pexels Full HD clip #%d ['%s']: %s", len(saved) + 1, q, url)
                    if _download_clip(url, dest, headers):
                        saved.append(dest)
                        break
        except Exception as exc:
            logger.debug("Pexels search failed for '%s': %s", q, exc)

    logger.info("Fetched %d topic-relevant clips from Pexels.", len(saved))
    return saved


def _fetch_pixabay_relevant_clips(keywords: List[str], count: int = 4) -> List[Path]:
    """Fetch topic-relevant portrait video clips from Pixabay."""
    if not config.PIXABAY_API_KEY:
        return []

    saved: List[Path] = []
    queries = [kw.strip() for kw in keywords if kw.strip()]
    if not queries:
        queries = ["ancient temple", "sacred fire", "himalayas", "meditation"]

    queries = list(dict.fromkeys(queries))

    for i, q in enumerate(queries):
        if len(saved) >= count:
            break
        try:
            logger.info("Searching Pixabay for topic-relevant clip: '%s'...", q)
            params = {
                "key": config.PIXABAY_API_KEY,
                "q": q.replace(" ", "+"),
                "video_type": "film",
                "orientation": "vertical",
                "per_page": 5,
            }
            resp = requests.get("https://pixabay.com/api/videos/", params=params, timeout=12)
            if resp.status_code != 200:
                continue
            hits = resp.json().get("hits", [])
            if hits:
                vid_obj = hits[0].get("videos", {})
                medium_stream = vid_obj.get("medium", {}) or vid_obj.get("large", {}) or vid_obj.get("small", {})
                url = medium_stream.get("url")
                if url:
                    dest = config.OUTPUT_DIR / f"rel_pixabay_{i}_{len(saved)}.mp4"
                    logger.info("Downloading Pixabay clip #%d ['%s']...", len(saved) + 1, q)
                    if _download_clip(url, dest):
                        saved.append(dest)
        except Exception as exc:
            logger.debug("Pixabay search failed for '%s': %s", q, exc)

    logger.info("Fetched %d topic-relevant clips from Pixabay.", len(saved))
    return saved


def _get_local_clips() -> List[Path]:
    """Check satisfying_clips/ folder for local media files."""
    clips_dir = config.LOCAL_SATISFYING_CLIPS_DIR
    if not clips_dir.exists():
        return []
    return video_engine.scan_and_sort_media(clips_dir, recursive=False, sort_by="natural")


def _generate_fallback_gradient_background(duration: float):
    """Generate dynamic colorful gradient clips as fallback."""
    logger.info("Generating animated color gradient fallback background...")
    palettes = [
        ((15, 10, 55), (75, 20, 115)),
        ((10, 35, 80), (20, 85, 155)),
        ((50, 8, 8), (120, 35, 18)),
        ((10, 40, 10), (25, 105, 55)),
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
    1. Primary: 100% Free AI-Generated Mythological Scenes matching the story with Ken Burns 3D motion!
    2. Fallback 1: Local clips in satisfying_clips/
    3. Fallback 2: Pexels Full HD atmospheric clips
    4. Fallback 3: Animated dark sacred gradient
    """
    clip_paths: List[Path] = []

    # 1. Primary: Generate scene-matched AI mythological art if prompts provided
    if image_prompts:
        ai_scenes = _fetch_ai_mythological_scenes(image_prompts, count=5)
        if ai_scenes:
            logger.info("Using %d AI-generated mythological scenes for background.", len(ai_scenes))
            clip_paths.extend(ai_scenes)

    # 2. Check local clips folder if AI generation failed or wasn't requested
    if not clip_paths:
        local_clips = _get_local_clips()
        if local_clips:
            logger.info("Found %d local clips in satisfying_clips/ folder.", len(local_clips))
            clip_paths.extend(local_clips)

    # 3. Fallback to Pexels / Pixabay
    if not clip_paths:
        kw = keywords or ["ancient temple", "sacred fire", "himalayas", "meditation"]
        p_clips = _fetch_pexels_relevant_clips(kw, count=5)
        clip_paths.extend(p_clips)
        if len(clip_paths) < 4:
            px_clips = _fetch_pixabay_relevant_clips(kw, count=4)
            clip_paths.extend(px_clips)

    if not clip_paths:
        logger.warning("No visual assets retrieved. Using animated fallback background.")
        return _generate_fallback_gradient_background(target_duration)

    # Process and stitch clips together with intelligent 9:16 normalization & smooth transitions
    try:
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
        return _generate_fallback_gradient_background(target_duration)


# Alias for backward compatibility
get_satisfying_background = get_video_background


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bg = get_video_background(target_duration=10.0, keywords=["space", "galaxy"])
    print(f"Video background duration: {bg.duration}s")
