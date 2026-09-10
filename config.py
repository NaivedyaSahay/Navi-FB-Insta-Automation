"""
config.py
---------
Centralised configuration loader for Navi-FBI-Automation (Facebook & Instagram Reels).
Reads all settings from a .env file and exposes them as typed constants.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Locate and load the .env file ────────────────────────────────────────────
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("config")

# ── API Keys ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str     = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str   = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY: str   = os.getenv("PEXELS_API_KEY", "")      # optional
PIXABAY_API_KEY: str  = os.getenv("PIXABAY_API_KEY", "")     # optional

# ── Cloudinary (for reliable Instagram video hosting) ─────────────────────────
CLOUDINARY_CLOUD_NAME: str  = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY: str     = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET: str  = os.getenv("CLOUDINARY_API_SECRET", "")

# ── Meta (FB & Instagram) API Credentials ────────────────────────────────────
META_ACCESS_TOKEN: str   = os.getenv("META_ACCESS_TOKEN", "")    # Page Access Token
META_IG_USER_ID: str     = os.getenv("META_IG_USER_ID", "")      # Instagram Business User ID
META_FB_PAGE_ID: str     = os.getenv("META_FB_PAGE_ID", "")      # Facebook Page ID

# ── AI Model Settings ─────────────────────────────────────────────────────────
# groq/compound is the current primary model (llama-3.3-70b-versatile is retired)
GROQ_MODEL: str   = os.getenv("GROQ_MODEL", "groq/compound")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# ── TTS Voice Settings ────────────────────────────────────────────────────────
TTS_VOICE: str  = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
TTS_RATE: str   = os.getenv("TTS_RATE", "+0%")   # e.g. "+10%" to speed up
TTS_VOLUME: str = os.getenv("TTS_VOLUME", "+0%")

# ── Video Settings (Reels 9:16 Format) ───────────────────────────────────────
VIDEO_WIDTH: int  = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS: int    = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_CODEC: str  = os.getenv("VIDEO_CODEC", "libx264")
AUDIO_CODEC: str  = os.getenv("AUDIO_CODEC", "aac")
VIDEO_BITRATE: str = os.getenv("VIDEO_BITRATE", "4000k")
BACKGROUND_COLOR: tuple = (18, 18, 30)   # dark fallback background

# ── Output Paths ──────────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_SATISFYING_CLIPS_DIR: Path = Path(__file__).parent / "satisfying_clips"
LOCAL_SATISFYING_CLIPS_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_FILE: Path     = OUTPUT_DIR / "voiceover.mp3"
VIDEO_FILE: Path     = OUTPUT_DIR / "final_video.mp4"
BG_VIDEO_FILE: Path  = OUTPUT_DIR / "background.mp4"

# ── Allowed & Blacklisted Topics ──────────────────────────────────────────────
ALLOWED_CATEGORIES = [
    "Artificial Intelligence",
    "Programming",
    "Technology",
    "Psychology",
    "Human Behaviour",
    "Productivity",
    "Science",
    "Space",
    "History",
    "Economics",
    "Finance",
    "Geography",
    "Nature",
    "Health",
    "Business",
    "Entrepreneurship",
    "Startups",
    "Future Technologies",
    "Internet Facts",
    "Mystery",
    "Interesting Facts",
    "Life Lessons",
]

FORBIDDEN_TOPICS = [
    "politics",
    "elections",
    "celebrity gossip",
    "crime",
    "religion",
    "misinformation",
    "hate content",
    "fake facts",
    "dangerous advice",
    "clickbait news",
]

# ── Automation & Execution Settings ──────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
POST_EVERY_HOURS: float = float(os.getenv("POST_EVERY_HOURS", "6"))

# ── Validation helper ──────────────────────────────────────────────────────────
def validate() -> None:
    """Warn about missing critical environment variables without crashing."""
    if not GROQ_API_KEY and not GEMINI_API_KEY:
        logger.warning("Neither GROQ_API_KEY nor GEMINI_API_KEY is set — script generation may fail.")
    if not PEXELS_API_KEY and not PIXABAY_API_KEY:
        logger.warning(
            "Neither PEXELS_API_KEY nor PIXABAY_API_KEY is set. "
            "The system will rely on local satisfying clips in /satisfying_clips or generated fallbacks."
        )
    if not META_ACCESS_TOKEN:
        logger.warning(
            "META_ACCESS_TOKEN is missing in .env — automatic posting to Facebook and Instagram will be skipped."
        )
    else:
        if META_FB_PAGE_ID:
            logger.info("Facebook Page posting configured (Page ID: %s)", META_FB_PAGE_ID)
        else:
            logger.warning("META_FB_PAGE_ID is missing — Facebook Reels upload will be skipped.")

        if META_IG_USER_ID:
            logger.info("Instagram Business posting configured (User ID: %s)", META_IG_USER_ID)
        else:
            logger.warning("META_IG_USER_ID is missing — Instagram Reels upload will be skipped.")

    if DRY_RUN:
        logger.info("⚠️ DRY_RUN is enabled in .env — generated videos will not be uploaded to Meta.")

    logger.info("Configuration loaded successfully.")

