"""
script_generator.py
-------------------
Generates high-retention video scripts optimised for Facebook & Instagram Reels.

Model priority chain (automatic fallback):
  1. Groq: groq/compound
  2. Groq: qwen/qwen3.6-27b
  3. Groq: openai/gpt-oss-120b
  4. Gemini: gemini-3.6-flash  (if GEMINI_API_KEY is set)
  5. Rich curated offline template

Public API:
    result = generate_script(topic="Mind-blowing AI facts")
    # Returns dict: {
    #   "title": str,
    #   "script": str,
    #   "fb_reels_caption": str,
    #   "ig_reels_caption": str,
    #   "hashtags": list[str],
    #   "keywords": list[str]
    # }
"""

from __future__ import annotations

import json
import logging
import re
import requests
from typing import Dict, Any, List, Optional

import config

logger = logging.getLogger("script_generator")

# ── Model Priority List ───────────────────────────────────────────────────────
GROQ_MODELS = [
    config.GROQ_MODEL,          # primary (from .env, defaults to groq/compound)
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
]

SYSTEM_PROMPT = """\
You are an elite viral content creator for Facebook & Instagram Reels with proven 10M+ view videos
in Science, AI, Psychology, Space, History, and Human Behaviour niches.

Your scripts are educational, deeply engaging, fast-paced, and designed for maximum scroll-stopping retention.

SCRIPT RULES (critical — follow exactly):
1. Duration: Exactly 35-55 seconds spoken naturally (95-135 words). Must be educational and punchy.
2. HOOK (first 15 words): One irresistible sentence that creates a CURIOSITY GAP or a SHOCKING FACT.
   - "Scientists discovered your brain makes decisions 7 seconds before you're aware of it."
   - "The Roman Empire fell for the exact same reason most businesses fail today."
3. CORE (words 15-100): 3 fast, specific insight points. Short sentences. No filler. Every word earns its place.
4. CLOSE (words 100-135): Memorable takeaway + strong CTA. e.g. "Like for more facts that rewire how you think."
5. NO stage directions. NO [Music]. NO (pause). NO narrator tags. ONLY spoken words.
6. Tone: Authoritative, warm, and genuinely fascinating — like a brilliant friend sharing a secret.

You MUST respond with ONLY a valid JSON object matching this exact schema (no markdown, no extra text):
{
  "title": "<Short catchy title under 70 chars>",
  "script": "<The full spoken text — 95 to 135 words. Count carefully.>",
  "fb_reels_caption": "<Facebook Reels caption. Hook line + 2 bullet highlights + CTA. Under 300 chars.>",
  "ig_reels_caption": "<Instagram Reels caption. Engaging + 5-8 specific hashtags. Under 300 chars.>",
  "hashtags": ["#Reels", "#Facts", "#LearnOnReels", "<4-8 topic-specific tags>"],
  "keywords": ["<4-6 SPECIFIC visual search terms for stock footage — not generic>"]
}

KEYWORDS RULES (critical for video quality):
  BAD:  "science", "brain", "nature", "technology"
  GOOD: "neurons firing brain scan", "roman forum ruins", "deep ocean bioluminescence", "quantum chip lab"
"""


def _call_groq_api(prompt: str) -> Optional[Dict[str, Any]]:
    """Try Groq models in priority order; return parsed dict or None."""
    if not config.GROQ_API_KEY:
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for model_name in GROQ_MODELS:
        logger.info("Generating script via Groq (%s)...", model_name)
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Create a viral Reels script about: {prompt}"},
            ],
            "temperature": 0.8,
            "max_tokens": 1024,
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=25)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            # Strip thinking blocks from models that add reasoning
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"```$", "", raw).strip()
            if not raw:
                logger.warning("Groq model %s returned empty response.", model_name)
                continue
            data = json.loads(raw)
            if data.get("script") and len(data["script"].split()) >= 60:
                logger.info("Groq model %s succeeded.", model_name)
                return data
        except Exception as exc:
            logger.warning("Groq model %s failed: %s", model_name, exc)

    return None


def _call_gemini_api(prompt: str) -> Optional[Dict[str, Any]]:
    """Fallback: Gemini REST API."""
    if not config.GEMINI_API_KEY:
        return None
    logger.info("Generating script via Gemini (%s)...", config.GEMINI_MODEL)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    )
    headers = {"Content-Type": "application/json"}
    full_prompt = f"{SYSTEM_PROMPT}\n\nCreate a viral Reels script about: {prompt}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(raw)
        if data.get("script"):
            logger.info("Gemini fallback succeeded.")
            return data
    except Exception as exc:
        logger.warning("Gemini API call failed: %s", exc)
    return None


def _rich_template_fallback(topic: str) -> Dict[str, Any]:
    """High-quality curated template used only when all APIs fail."""
    logger.info("Using rich offline template for: %s", topic)
    return {
        "title": f"Mind-Blowing Facts About {topic[:35]}",
        "script": (
            f"Here is something about {topic} that will permanently change how you see the world. "
            "For centuries, scientists assumed this was impossible. Then in the last decade, "
            "three independent research teams proved the opposite. "
            "The first discovery: the mechanism is far more ancient than we imagined. "
            "The second: human intuition consistently predicted it before formal proof. "
            "The third — and most shocking — it scales perfectly to explain things happening right now. "
            "When you understand this, every headline starts making a different kind of sense. "
            "Like and follow for facts that genuinely expand how you understand reality."
        ),
        "fb_reels_caption": (
            f"🧠 {topic} facts that will expand your mind!\n"
            "• Backed by research\n"
            "• Explained simply\n"
            "Like & follow for daily mind-expanding Reels. #Facts #LearnOnReels"
        ),
        "ig_reels_caption": (
            f"Mind-blowing breakdown of {topic} 🔬✨\n"
            "Follow for daily educational Reels!\n"
            "#Reels #Facts #LearnOnReels #Education #Science #Knowledge #Viral #MindBlown"
        ),
        "hashtags": [
            "#Reels", "#Facts", "#LearnOnReels", "#Education",
            "#Science", "#Knowledge", "#Viral", "#MindBlown", "#Interesting",
        ],
        "keywords": [
            "science laboratory close-up", "researcher microscope",
            "knowledge education concept", "human brain neurons"
        ],
    }


def generate_script(topic: str) -> Dict[str, Any]:
    """Generate script JSON via Groq → Gemini → Rich offline fallback."""
    logger.info("Generating Reels script for topic: '%s'", topic)

    # 1. Try Groq (priority model chain)
    data = _call_groq_api(topic)

    # 2. Try Gemini
    if not data:
        data = _call_gemini_api(topic)

    # 3. Rich offline fallback
    if not data:
        data = _rich_template_fallback(topic)

    # ── Clean script text ─────────────────────────────────────────────────────
    script_text = data.get("script", "")
    script_text = re.sub(r"\[.*?\]|\(.*?\)", "", script_text)   # remove stage directions
    script_text = re.sub(r"<think>.*?</think>", "", script_text, flags=re.DOTALL)
    script_text = re.sub(r"\s+", " ", script_text).strip()
    data["script"] = script_text

    # ── Enforce limits ────────────────────────────────────────────────────────
    words = data["script"].split()
    if len(words) > 140:
        data["script"] = " ".join(words[:140])

    data["title"] = data.get("title", topic)[:70]
    data["fb_reels_caption"] = data.get("fb_reels_caption", "")[:300]
    data["ig_reels_caption"] = data.get("ig_reels_caption", "")[:300]
    data["hashtags"] = data.get("hashtags", ["#Reels", "#Facts"])[:12]
    data.setdefault("keywords", ["science laboratory", "knowledge concept"])

    logger.info(
        "Script ready (%d words). Title: '%s'",
        len(data["script"].split()), data.get("title", ""),
    )
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_script("How quantum computers will change encryption")
    print(json.dumps(res, indent=2, ensure_ascii=False))
