"""
main.py
-------
CLI Entry Point & Pipeline Orchestrator for Navi-FBI-Automation.
Generates Facebook & Instagram Reels with satisfying video backgrounds,
high-retention Groq AI scripts, Edge-TTS voiceovers, and animated viral captions.

Usage:
  python main.py "Mind-blowing AI facts" --no-upload
  python main.py --category "Space" --no-upload
  python main.py "How quantum computers work" --voice en-US-JennyNeural
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import config
from topic_picker import get_trending_topics
from config import ALLOWED_CATEGORIES
from script_generator import generate_script
from voice_generator import generate_voiceover
from video_composer import compose_video
from uploader_meta import upload_to_meta

# Force UTF-8 encoding on Windows terminal output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Navi-FBI-Automation — Facebook & Instagram Reels Satisfying Video Pipeline"
    )
    parser.add_argument("command_or_topic", nargs="?", help="Command (test, post, schedule) or video topic")
    parser.add_argument("--topic", help="Explicit video topic")
    parser.add_argument("--category", choices=config.ALLOWED_CATEGORIES, help="Target category")
    parser.add_argument("--no-upload", action="store_true", help="Skip Meta Graph API upload step")
    parser.add_argument("--voice", help="Edge-TTS voice (default: en-US-ChristopherNeural)")
    parser.add_argument("--output-dir", help="Override output directory")
    parser.add_argument("--keep-files", action="store_true", help="Keep intermediate audio/video files")
    parser.add_argument("--interval-hours", type=float, help="Hours between scheduled posts (default: from .env or 6.0)")
    return parser.parse_args()


def run_pipeline(
    topic: str | None = None,
    category: str | None = None,
    no_upload: bool = False,
    voice: str | None = None,
    output_dir: str | None = None,
    keep_files: bool = False,
) -> Path:
    logger.info("==================================================")
    logger.info("  🚀 Starting Navi-FBI-Automation Reels Pipeline  ")
    logger.info("==================================================")

    # 1. Validate environment configuration
    config.validate()

    # 2. Topic discovery & selection
    if not topic:
        logger.info("No topic provided. Discovering safe trending topic...")
        discovered = get_trending_topics(n=1, category=category)
        if not discovered:
            raise RuntimeError("Could not find suitable topic.")
        selected_topic = discovered[0]["topic"]
        selected_category = discovered[0].get("category", category or "General")
    else:
        selected_topic = topic
        selected_category = category or "Custom"

    logger.info("📌 Target Topic: '%s' [Category: %s]", selected_topic, selected_category)

    # 3. Generate script via Groq / Gemini AI
    script_data = generate_script(selected_topic)
    title = script_data.get("title", selected_topic)
    script_text = script_data.get("script", "")
    fb_caption = script_data.get("fb_reels_caption", "")
    ig_caption = script_data.get("ig_reels_caption", "")
    keywords = script_data.get("keywords", ["satisfying", "kinetic sand"])

    logger.info("📜 Script Title: '%s'", title)
    logger.info("📝 Script Preview: '%s...'", script_text[:80])

    # 4. Generate TTS voiceover & word timing boundaries
    out_dir = Path(output_dir) if output_dir else config.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "voiceover.mp3"
    video_path = out_dir / "final_video.mp4"

    audio_file, word_timings = generate_voiceover(
        text=script_text,
        output_path=audio_path,
        voice=voice or config.TTS_VOICE,
    )

    # 5. Composite satisfying video background + voiceover + dynamic captions
    final_video = compose_video(
        audio_path=audio_file,
        word_timings=word_timings,
        script_text=script_text,
        keywords=keywords,
        output_path=video_path,
    )

    # 6. Upload to Meta (Facebook & Instagram Reels)
    caption_to_use = ig_caption or fb_caption or title
    upload_res = upload_to_meta(
        video_path=final_video,
        title=title,
        caption=caption_to_use,
        no_upload=no_upload,
    )

    logger.info("==================================================")
    logger.info("  ✨ Pipeline Completed Successfully!             ")
    logger.info("  🎬 Final Video: %s", final_video.resolve())
    logger.info("==================================================")

    return final_video


def run_scheduler_loop(interval_hours: float, category: str | None = None, voice: str | None = None):
    import time
    interval_sec = interval_hours * 3600
    logger.info("⏰ Starting Reels Automation Scheduler (Posting every %.1f hours)", interval_hours)
    logger.info("Press Ctrl+C to stop.")

    while True:
        try:
            logger.info("--- Triggering Scheduled Reel Pipeline ---")
            run_pipeline(category=category, no_upload=False, voice=voice)
        except Exception as exc:
            logger.error("Scheduled run error: %s", exc)

        logger.info("Sleeping for %.1f hours until next run...", interval_hours)
        time.sleep(interval_sec)


def main():
    args = parse_args()
    cmd_or_topic = args.command_or_topic

    # Determine command mode vs direct topic execution
    if cmd_or_topic == "test":
        logger.info("🧪 TEST MODE — Generating reel locally (No Meta Upload)")
        topic = args.topic
        run_pipeline(
            topic=topic,
            category=args.category,
            no_upload=True,
            voice=args.voice,
            output_dir=args.output_dir,
            keep_files=args.keep_files,
        )
    elif cmd_or_topic == "post":
        logger.info("⚡ POST MODE — Generating and posting reel to FB & Instagram NOW")
        topic = args.topic
        run_pipeline(
            topic=topic,
            category=args.category,
            no_upload=args.no_upload,
            voice=args.voice,
            output_dir=args.output_dir,
            keep_files=args.keep_files,
        )
    elif cmd_or_topic == "schedule":
        interval = args.interval_hours or config.POST_EVERY_HOURS
        run_scheduler_loop(interval_hours=interval, category=args.category, voice=args.voice)
    else:
        # Standard execution where argument is either topic or omitted
        topic = args.topic or cmd_or_topic
        no_up = args.no_upload or config.DRY_RUN
        run_pipeline(
            topic=topic,
            category=args.category,
            no_upload=no_up,
            voice=args.voice,
            output_dir=args.output_dir,
            keep_files=args.keep_files,
        )


if __name__ == "__main__":
    main()

