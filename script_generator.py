"""
script_generator.py
-------------------
Generates high-retention video scripts optimized for Facebook & Instagram Reels.
Uses Groq API (Primary) with fallback to Gemini AI or structured templates.

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
from typing import Dict, Any

import config

logger = logging.getLogger("script_generator")

SYSTEM_PROMPT = """
You are an expert viral content creator specializing in 35-55 second Facebook Reels & Instagram Reels.
Your scripts are educational, highly engaging, fast-paced, and designed for maximum retention.

RULES FOR THE SCRIPT:
1. Duration: 35 to 55 seconds when spoken naturally (approx 95 to 135 words). Must be engaging and thorough.
2. Hook: The very first sentence MUST be an irresistible hook that grabs attention immediately.
3. Flow: Use punchy, short sentences. Avoid complex jargon.
4. NO stage directions, NO brackets like [Music], NO narrator tags. Output ONLY spoken words in the script.
5. Tone: Fascinating, authoritative, warm, and engaging.

You MUST respond strictly in valid JSON with this exact schema:
{
  "title": "Short catchy title for the video",
  "script": "The full spoken text of the script from start to finish",
  "fb_reels_caption": "Engaging Facebook Reels description with call to action",
  "ig_reels_caption": "Engaging Instagram Reels caption with hashtags",
  "hashtags": ["#Reels", "#Satisfying", "#Facts"],
  "keywords": ["satisfying", "kinetic sand", "3d loop"]
}
"""

def _call_groq_api(prompt: str) -> Dict[str, Any] | None:
    if not config.GROQ_API_KEY:
        return None
    logger.info("Generating script via Groq API (%s)...", config.GROQ_MODEL)
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Create a viral Reels script about: {prompt}"},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as exc:
        logger.warning("Groq API call failed: %s", exc)
        return None

def _call_gemini_api(prompt: str) -> Dict[str, Any] | None:
    if not config.GEMINI_API_KEY:
        return None
    logger.info("Generating script via Gemini API (%s)...", config.GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser Request: Create a viral Reels script about: {prompt}"
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=25)
        resp.raise_for_status()
        text_out = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text_out)
    except Exception as exc:
        logger.warning("Gemini API call failed: %s", exc)
        return None

def _template_fallback(topic: str) -> Dict[str, Any]:
    logger.info("Using offline template script generator for: %s", topic)
    return {
        "title": f"Fascinating Facts About {topic[:30]}",
        "script": (
            f"Did you know this mind-blowing fact about {topic}? "
            "Scientists and researchers recently uncovered something that changes how we view this completely. "
            "When you look closely at the underlying patterns, the results are almost unbelievable. "
            "Share this with someone who loves learning new facts every day!"
        ),
        "fb_reels_caption": f"Explore fascinating facts about {topic}! Like and follow for daily interesting Reels. #Satisfying #Facts",
        "ig_reels_caption": f"Mind-blowing breakdown of {topic} 🧠✨ Follow @ourchannel for daily satisfying educational videos! #Reels #Satisfying #Education",
        "hashtags": ["#Reels", "#Satisfying", "#Facts", "#LearnOnReels", "#Viral"],
        "keywords": ["satisfying", "kinetic sand", "3d loop", "asmr"],
    }

def generate_script(topic: str) -> Dict[str, Any]:
    """Generate script JSON via Groq -> Gemini -> Offline fallback."""
    logger.info("Generating Reels script for topic: '%s'", topic)

    # 1. Try Groq API
    data = _call_groq_api(topic)

    # 2. Try Gemini API if Groq failed or not set
    if not data:
        data = _call_gemini_api(topic)

    # 3. Fallback to offline template
    if not data:
        data = _template_fallback(topic)

    # Clean script formatting
    script_clean = data.get("script", "")
    script_clean = re.sub(r"\[.*?\]|\(.*?\)", "", script_clean)  # remove brackets
    script_clean = re.sub(r"\s+", " ", script_clean).strip()
    data["script"] = script_clean

    logger.info("Script successfully generated (%d words). Title: '%s'",
                len(script_clean.split()), data.get("title", ""))
    return data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_script("How quantum computers work")
    print(json.dumps(res, indent=2))
