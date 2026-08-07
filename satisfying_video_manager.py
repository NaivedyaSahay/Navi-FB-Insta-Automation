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


def _fetch_pexels_relevant_clips(keywords: List[str], count: int = 5) -> List[Path]:
    """Fetch topic-relevant portrait video clips from Pexels."""
    if not config.PEXELS_API_KEY:
        return []

    headers = {"Authorization": config.PEXELS_API_KEY}
    saved: List[Path] = []

    # Prepare search queries from script keywords
    queries = [kw.strip() for kw in keywords if kw.strip()]
    if not queries:
        queries = ["technology", "space", "nature", "science"]

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
                params={"query": q, "orientation": "portrait", "size": "medium", "per_page": 5},
                timeout=12,
            )
            if resp.status_code != 200:
                continue
            videos = resp.json().get("videos", [])
            for vid in videos:
                files = vid.get("video_files", [])
                portrait = [f for f in files if f.get("height", 0) >= f.get("width", 1)] or files
                if portrait:
                    url = portrait[0]["link"]
                    dest = config.OUTPUT_DIR / f"rel_pexels_{i}_{len(saved)}.mp4"
                    logger.info("Downloading Pexels clip #%d ['%s']: %s", len(saved) + 1, q, url)
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
        queries = ["nature", "technology", "abstract", "science"]

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
    """Check satisfying_clips/ folder for local MP4/MOV files."""
    clips_dir = config.LOCAL_SATISFYING_CLIPS_DIR
    if not clips_dir.exists():
        return []
    valid_exts = {".mp4", ".mov", ".mkv", ".webm"}
    return [f for f in clips_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]


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


def get_video_background(target_duration: float, keywords: List[str] = None):
    """
    Fetch and stitch topic-relevant video clips matching script keywords.
    """
    kw = keywords or ["technology", "space", "nature", "science"]
    logger.info("Preparing topic-relevant visual background for keywords: %s (Duration: %.2fs)...",
                kw, target_duration)
    clip_paths: List[Path] = []

    # 1. Search Pexels for script keywords
    p_clips = _fetch_pexels_relevant_clips(kw, count=5)
    clip_paths.extend(p_clips)

    # 2. Search Pixabay for script keywords if more clips needed
    if len(clip_paths) < 4:
        px_clips = _fetch_pixabay_relevant_clips(kw, count=4)
        clip_paths.extend(px_clips)

    # 3. Check local clips folder if stock API returned nothing
    if not clip_paths:
        local_clips = _get_local_clips()
        if local_clips:
            logger.info("Found %d local clips in satisfying_clips/ folder.", len(local_clips))
            clip_paths.extend(local_clips)

    if not clip_paths:
        logger.warning("No video clips retrieved for keywords. Using animated fallback background.")
        return _generate_fallback_gradient_background(target_duration)

    # Process and stitch clips together
    loaded_clips = []
    max_single_clip_dur = 6.0  # switch clip every 6 seconds for fast-paced Reels retention

    for p in clip_paths:
        try:
            clip = VideoFileClip(str(p), audio=False).resized((W, H)).with_fps(FPS)
            sub_dur = min(clip.duration, max_single_clip_dur)
            clip = clip.subclipped(0, sub_dur)
            loaded_clips.append(clip)
        except Exception as exc:
            logger.warning("Could not load video clip '%s': %s", p, exc)

    if not loaded_clips:
        return _generate_fallback_gradient_background(target_duration)

    logger.info("Stitching %d topic-relevant video clips together...", len(loaded_clips))
    combined = concatenate_videoclips(loaded_clips)

    # Loop sequence if total duration is shorter than target_duration
    if combined.duration < target_duration:
        loops = int(np.ceil(target_duration / combined.duration))
        combined = concatenate_videoclips([combined] * loops)

    return combined.subclipped(0, target_duration)


# Alias for backward compatibility
get_satisfying_background = get_video_background


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bg = get_video_background(target_duration=10.0, keywords=["space", "galaxy"])
    print(f"Video background duration: {bg.duration}s")
