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
    "qwen/qwen3.8-27b",
    config.GROQ_MODEL,          # primary from .env
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

SYSTEM_PROMPT = """\
You are a master viral storyteller for Instagram Reels and YouTube Shorts specializing in Hindu Mythology (सनातन धर्म, महाभारत, रामायण, पुराण और उपनिषद).
Your storytelling is gripping, cinematic, deeply emotional, never boring, and provides timeless human life lessons.

LANGUAGE & SCRIPT RULES (CRITICAL — FOLLOW STRICTLY):
1. Language: Speak in pure, powerful, spoken HINDI written in Devanagari script (हिंदी भाषा).
2. DURATION: STRICTLY 40 TO 52 SECONDS (85 to 110 Hindi words). Never exceed 115 words so the video stays under 1 minute!
3. NATURAL HUMAN SPEECH & CADENCE (CRITICAL TO SOUND LIKE A REAL HUMAN):
   - Do NOT sound like an emotionless robotic reader. Write with intense passion, curiosity, and rhythm.
   - Insert commas (,) for natural micro-breaths.
   - Insert ellipses (...) for dramatic suspenseful pauses right before big revelations.
   - Insert em-dashes (—) right before delivering the profound life lesson so the voice slows down thoughtfully.
   - Example cadence: "क्या आप जानते हैं... महाभारत के सबसे बड़े दानी कर्ण का अंत, केवल एक बाण से नहीं हुआ था? उसके पीछे था—एक ऐसा रहस्य, जो आज भी हर इंसान की आंखें खोल देता है।"

4-PART STORYTELLING STRUCTURE:
1. HOOK (0-5 seconds / First 10-15 words): Start with an intense, curious, dramatic question or revelation that stops viewers from scrolling.
   Example: "क्या आप जानते हैं कि महाभारत के सबसे महान दानी कर्ण का वध केवल एक छल नहीं, बल्कि उसके अहंकार की कीमत थी?"
2. GRIPPING STORY (5-35 seconds / ~50-60 words): Fast-paced, cinematic storytelling with drama, high stakes, and conflict. Focus on the pivotal moment that changes everything.
3. HUMAN LIFE LESSON (35-48 seconds / ~20-25 words):
   MUST explicitly state: "इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि..." (Clear, profound lesson on Karma, ego, true righteousness/Dharma, inner strength, or loyalty).
4. CLOSING CTA (48-52 seconds / ~8-10 words):
   "सनातन धर्म के ऐसे ही गहरे ज्ञान और जीवन की सीख के लिए फॉलो ज़रूर करें।"

STRICT CONSTRAINTS:
- NO stage directions like [संगीत] or (विराम). Only spoken words.
- All keywords MUST be in ENGLISH (4-6 terms) describing sacred atmosphere.
- image_prompts MUST be in ENGLISH (4 to 5 prompts). Each must be a highly detailed, cinematic description of a 9:16 vertical digital painting showing the exact character, god, warrior, or temple mentioned in that moment (e.g. "Lord Shiva meditating in snow covered Himalayas, glowing third eye, crescent moon, cinematic 8k vertical art", "Karna on golden chariot donating divine armor, Kurukshetra battlefield, celestial light rays, vertical").
- Respond with ONLY a valid JSON object matching this schema:
{
  "title": "<Catchy Hindi title under 60 chars>",
  "script": "<Spoken Hindi story in Devanagari — strictly 85 to 110 words. Count carefully.>",
  "fb_reels_caption": "<Compelling Hindi caption with the moral lesson and emojis. Under 300 chars.>",
  "ig_reels_caption": "<Engaging Hindi caption with 6-8 relevant hashtags. Under 300 chars.>",
  "hashtags": ["#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna", "#Karma", "#LifeLessons", "#TrendingReels"],
  "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"],
  "image_prompts": [
    "<Scene 1 (Opening Hook): Detailed 9:16 vertical cinematic description of the opening scene/god/warrior>",
    "<Scene 2 (Story Conflict): Detailed 9:16 vertical cinematic description of the dramatic conflict>",
    "<Scene 3 (Pivotal Climax): Detailed 9:16 vertical cinematic description of the divine revelation or turning point>",
    "<Scene 4 (Moral / Wisdom): Detailed 9:16 vertical cinematic description of sacred wisdom, temple, or cosmic peace>"
  ]
}
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
    """High-quality curated Hindi mythology template used when APIs are unreachable."""
    logger.info("Using rich offline Hindi mythology template for: %s", topic)
    return {
        "title": "कर्ण का पतन और सबसे बड़ी सीख",
        "script": (
            "क्या आप जानते हैं कि महाभारत के सबसे शक्तिशाली योद्धा कर्ण का वध केवल एक बाण से नहीं, "
            "बल्कि उसके अतीत के कर्मों से हुआ था? जब कुरुक्षेत्र में कर्ण के रथ का पहिया भूमि में धंस गया, "
            "तब उसने कृष्ण से धर्म की दुहाई दी। इस पर भगवान कृष्ण ने मुस्कुराते हुए पूछा—कर्ण, जब द्रौपदी का भरी सभा में "
            "अपमान हो रहा था, तब तुम्हारा धर्म कहाँ था? इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि "
            "आप कितने भी गुणी और वीर क्यों न हों, यदि आप अधर्म और गलत लोगों का साथ देंगे, तो आपका विनाश निश्चित है। "
            "सनातन धर्म की ऐसी ही अमर सीख के लिए हमें फॉलो ज़रूर करें।"
        ),
        "fb_reels_caption": (
            "🏹 महाभारत से जीवन की सबसे बड़ी सीख!\n"
            "चाहे आप कितने भी शक्तिशाली हों, अधर्म का साथ हमेशा पतन की ओर ले जाता है।\n"
            "सनातन ज्ञान के लिए फॉलो करें। #Mahabharata #Karma #LifeLessons"
        ),
        "ig_reels_caption": (
            "कर्ण के जीवन से इंसान के लिए सबसे बड़ी सीख 🕉️✨\n"
            "गलत संगति और अधर्म का परिणाम हमेशा विनाशकारी होता है।\n"
            "#Mahabharata #SanatanDharma #Krishna #Karma #HinduMythology #LifeLessons #ReelsIndia"
        ),
        "hashtags": [
            "#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna",
            "#Karma", "#LifeLessons", "#TrendingReels", "#Bhakti",
        ],
        "keywords": [
            "ancient indian temple", "sacred fire ritual", "himalayas meditation",
            "cosmic galaxy universe", "golden divine light"
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

    # ── Enforce strict limits (Under 1 minute / 85-110 words) ─────────────────
    words = data["script"].split()
    if len(words) > 115:
        truncated = " ".join(words[:115])
        # Find last full sentence punctuation (।, ., ?, !) to avoid cut-off words
        match = re.search(r"^(.*[।\.\?!])", truncated, flags=re.DOTALL)
        if match and len(match.group(1).split()) >= 70:
            data["script"] = match.group(1).strip()
        else:
            data["script"] = truncated

    data["title"] = data.get("title", topic)[:60]
    data["fb_reels_caption"] = data.get("fb_reels_caption", "")[:300]
    data["ig_reels_caption"] = data.get("ig_reels_caption", "")[:300]
    data["hashtags"] = data.get("hashtags", ["#SanatanDharma", "#LifeLessons"])[:10]
    data.setdefault("keywords", ["ancient indian temple", "sacred fire ritual", "himalayas meditation"])
    data.setdefault("image_prompts", [
        f"{topic} ancient Indian mythology, cinematic lighting, 8k vertical art",
        "sacred fire ritual in ancient temple, golden divine light rays, spiritual atmosphere, 8k vertical",
        "epic mythological revelation, celestial clouds, sacred aura, cinematic 9:16 vertical art",
        "ancient sacred temple in Himalayas under starry night sky, burning brass diyas, spiritual wisdom, vertical"
    ])

    logger.info(
        "Script ready (%d words). Title: '%s'",
        len(data["script"].split()), data.get("title", ""),
    )
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_script("How quantum computers will change encryption")
    print(json.dumps(res, indent=2, ensure_ascii=False))
