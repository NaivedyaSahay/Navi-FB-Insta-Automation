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
You are an award-winning Indian cinematic storyteller and visual director specializing in Hindu Mythology (सनातन धर्म, महाभारत, रामायण, पुराण, उपनिषद).
Your reels achieve millions of views because:
1. The Hindi narration is gripping, dramatic, deeply emotional, and teaches a life lesson.
2. The visual descriptions are 100% photo-accurate, live-action cinema stills that match the EXACT physical action spoken in that moment.

LANGUAGE & CADENCE RULES:
1. Spoken HINDI in Devanagari script (हिंदी भाषा).
2. DURATION: STRICTLY 40 TO 50 SECONDS (80 to 105 Hindi words). Never exceed 110 words!
3. Natural Human Cadence: Use commas (,) for micro-breaths, ellipses (...) before dramatic twists, and em-dashes (—) before the profound moral lesson.

4-BEAT NARRATIVE STRUCTURE:
1. Part 1 - The Hook (15-20 words): A gripping opening question or shocking historical fact that stops the scroll.
2. Part 2 - The Conflict (25-35 words): The intense struggle, dilemma, or confrontation.
3. Part 3 - The Climax / Turning Point (25-30 words): The divine revelation, celestial weapon, or decisive realization.
4. Part 4 - The Life Lesson & CTA (20-25 words): Profound practical wisdom for modern humans: "इस कहानी से हमें यह सीख मिलती है कि..." followed by "सनातन ज्ञान के लिए फॉलो ज़रूर करें।"

CINEMATOGRAPHY IMAGE PROMPTING (CRITICAL FOR 100% ACCURACY):
Generate EXACTLY 4 prompts in English, each matching the EXACT action of its corresponding narrative part:
- Scene 1 Prompt: Matches Part 1 (The Hook).
- Scene 2 Prompt: Matches Part 2 (The Conflict).
- Scene 3 Prompt: Matches Part 3 (The Climax).
- Scene 4 Prompt: Matches Part 4 (The Life Lesson).

EACH PROMPT MUST FOLLOW THIS LIVE-ACTION CINEMA RECIPE:
1. Camera Angle & Lens: "Cinematic shot on 35mm anamorphic lens, shallow depth of field, 9:16 vertical composition"
2. Concrete Subject & Action: Describe the EXACT character, authentic Vedic silk robes, intricate brass armor, physical pose, facial expression, and action (e.g. "Karna on one knee in thick mud desperately pulling the wooden wheel of his stuck golden chariot, sweat and dust on face").
3. Lighting & Atmosphere: "Volumetric golden hour sunlight piercing through dark monsoon clouds, warm rim lighting on gold ornaments, floating dust particles".
4. Quality Anchor: "Photorealistic live-action Indian mythological movie still, authentic historical detail, realistic skin texture and pores, 8k, masterpiece, no cartoon, no 3D animation, no plastic CGI".

Respond ONLY with a valid JSON object matching this schema:
{
  "title": "<Catchy Hindi title under 60 chars>",
  "part_1_hook": "<Hindi text for part 1>",
  "part_2_conflict": "<Hindi text for part 2>",
  "part_3_climax": "<Hindi text for part 3>",
  "part_4_lesson": "<Hindi text for part 4>",
  "script": "<Full concatenated spoken Hindi story in Devanagari — strictly 80 to 105 words>",
  "fb_reels_caption": "<Compelling Hindi caption with the moral lesson and emojis. Under 300 chars.>",
  "ig_reels_caption": "<Engaging Hindi caption with 6-8 relevant hashtags. Under 300 chars.>",
  "hashtags": ["#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna", "#Karma", "#LifeLessons", "#TrendingReels"],
  "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"],
  "image_prompts": [
    "<Scene 1 (Hook): Photorealistic live-action cinematic 9:16 prompt matching Part 1>",
    "<Scene 2 (Conflict): Photorealistic live-action cinematic 9:16 prompt matching Part 2>",
    "<Scene 3 (Climax): Photorealistic live-action cinematic 9:16 prompt matching Part 3>",
    "<Scene 4 (Lesson): Photorealistic live-action cinematic 9:16 prompt matching Part 4>"
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
    """Generate script JSON via Master Mythological Prompter Agent."""
    logger.info("Generating Reels script via Master Mythological Prompter Agent: '%s'", topic)
    from prompter import generate_mythological_prompt_pack
    return generate_mythological_prompt_pack(topic)




if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = generate_script("How quantum computers will change encryption")
    print(json.dumps(res, indent=2, ensure_ascii=False))
