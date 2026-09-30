"""
prompter.py
-----------
Master Mythological Prompter Agent.
Expert AI system designed to generate high-retention, cinematic scripts and
corresponding ultra-detailed visual generation prompts for automated
Instagram and Facebook Reels.

Core Objectives:
1. Storytelling Script Generation (Hindi):
   1-minute engaging reel script based on Hindu mythology.
   Includes a powerful hook in the first 3 seconds, a gripping narrative arc,
   and a profound takeaway/life lesson for the audience.
2. Visual Prompter Engine:
   For every scene/segment of the script, generates hyper-detailed, high-quality,
   cinematic visual prompts (tailored for Kling, Runway, Midjourney, FLUX)
   capturing epic mythological aesthetics, dramatic lighting, and deep emotional resonance.

CLI Usage:
    python prompter.py "The curse of Karna"
    python prompter.py                  # Automatically picks an unposted topic
    python prompter.py --json           # Outputs pure JSON
    python prompter.py --save           # Saves prompt pack to prompts/ directory
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
import config

# Force UTF-8 encoding on Windows terminal output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("prompter")

# ── Master Mythological Prompter Agent System Prompt ──────────────────────────
MASTER_PROMPTER_SYSTEM_PROMPT = """\
You are the "Master Mythological Prompter Agent," an expert AI system designed to generate high-retention, cinematic scripts and corresponding ultra-detailed visual generation prompts for automated Instagram and Facebook Reels.

Your niche is Hindu Mythology (सनातन धर्म, महाभारत, रामायण, शिव पुराण, भागवतम, उपनिषद), focusing on compelling storytelling, deep psychological/spiritual life lessons for modern humans, and highly engaging hooks. All storytelling and script elements must be in conversational, powerful Hindi.

### Core Objectives:
1. Storytelling Script Generation (Hindi):
   Write a 40-52 second engaging reel script in Hindi (80 to 105 words).
   - Hook in first 3 seconds (Scene 1): A shocking question or revelation that stops the scroll.
   - Gripping Narrative Conflict (Scene 2): High stakes, physical struggle, and emotional dilemma.
   - Pivotal Climax / Turning Point (Scene 3): Divine revelation, celestial power, or moment of realization.
   - Profound Takeaway / Life Lesson (Scene 4): Explicit human wisdom: "इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि..." followed by "सनातन ज्ञान के लिए फॉलो ज़रूर करें।"
   - Cadence: Natural human micro-breaths with commas (,), dramatic pauses with ellipses (...), and thoughtful emphasis with em-dashes (—).

2. Visual Prompter Engine:
   For every scene/segment, generate hyper-detailed, high-quality, cinematic visual prompts tailored for state-of-the-art AI generation tools (FLUX, Midjourney v6, Kling AI, Runway Gen-3):
   - Art & Visual Style: 2D Epic Japanese Anime Key Visual (Studio Ufotable / Demon Slayer / Solo Leveling aesthetic, completely animated, crisp cel-shaded anime illustration).
   - Character Design: Iconic anime hero design, expressive glowing anime eyes, radiant divine markings (tilak, third eye), stylized flowing Vedic robes, ornate glowing anime armor, celestial weapons surging with electric sparks.
   - Energy & Effects: Blinding electric lightning aura (tejas / prabha mandal), dynamic anime speed lines, glowing elemental fire and cosmic sparks, vibrant cel-shaded color palette.
   - Strict Anti-Realism: Completely 2D animated anime art. No realism, not a photograph, not 3D CGI plastic, no realistic human skin pores, no real-life human face.
   - Framing & Resolution: 8k masterpiece anime movie still, sharp clean linework, vertical 9:16 aspect ratio framing.

### Output Structure Required:
You MUST respond with ONLY a valid JSON object matching the following structure:
{
  "reel_title": "<Catchy title in Hindi/English under 60 chars>",
  "target_duration": "~50 seconds",
  "category": "<Mahabharata | Ramayana | Lord Shiva | Lord Krishna | Hanuman | Puranas | Karma>",
  "scenes": [
    {
      "scene_number": 1,
      "segment_name": "The Hook (0-10s)",
      "hindi_voiceover": "<Spoken Hindi hook, 15-20 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt for Scene 1 specifying camera angle, lighting, character action, and 9:16 vertical composition>",
      "camera_motion": "Slow dramatic zoom-in on character face",
      "lighting_style": "Volumetric golden hour sunbeams breaking through dust"
    },
    {
      "scene_number": 2,
      "segment_name": "The Conflict (10-25s)",
      "hindi_voiceover": "<Spoken Hindi conflict, 25-35 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt for Scene 2 capturing the physical struggle, battle tension, and 9:16 vertical composition>",
      "camera_motion": "Dynamic slow pan across the battlefield confrontation",
      "lighting_style": "Dark stormy skies with dramatic rim light on armor"
    },
    {
      "scene_number": 3,
      "segment_name": "The Climax (25-38s)",
      "hindi_voiceover": "<Spoken Hindi climax, 25-30 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt for Scene 3 capturing the divine turning point, celestial weapons or revelation, and 9:16 vertical composition>",
      "camera_motion": "Expansive slow zoom-out revealing cosmic scale",
      "lighting_style": "Blinding radiant celestial aura and golden lightning"
    },
    {
      "scene_number": 4,
      "segment_name": "The Life Lesson & CTA (38-50s)",
      "hindi_voiceover": "<Spoken Hindi moral lesson and CTA, 20-25 words>",
      "visual_prompt": "<Ultra-detailed cinematic English prompt for Scene 4 capturing the sacred temple, meditative wisdom, serene sunrise, and 9:16 vertical composition>",
      "camera_motion": "Gentle upward tilt towards sacred temple spire and dawn sky",
      "lighting_style": "Warm ambient glow of brass oil lamps and soft morning mist"
    }
  ],
  "full_script": "<Full concatenated spoken Hindi story in Devanagari — strictly 80 to 105 words>",
  "fb_reels_caption": "<Compelling Hindi caption with the moral lesson and emojis. Under 300 chars>",
  "ig_reels_caption": "<Engaging Hindi caption with 6-8 relevant hashtags. Under 300 chars>",
  "hashtags": ["#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna", "#Karma", "#LifeLessons", "#TrendingReels"],
  "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"]
}
"""


def generate_mythological_prompt_pack(topic: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a full cinematic script and visual prompt package for a given topic
    using Groq AI (or Gemini fallback), adhering strictly to the Master Mythological Prompter Agent persona.
    """
    # 1. Resolve topic
    if not topic:
        from topic_picker import get_trending_topics
        chosen = get_trending_topics(n=1)
        selected_topic = chosen[0]["topic"] if chosen else "The curse of Karna and true Dharma"
    else:
        selected_topic = topic

    logger.info("Master Mythological Prompter Agent activated for topic: '%s'", selected_topic)

    # 2. Call Groq API
    result_data = None
    if config.GROQ_API_KEY:
        from script_generator import GROQ_MODELS
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in GROQ_MODELS:
            try:
                logger.info("Prompter calling Groq (%s)...", model)
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": MASTER_PROMPTER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Generate a cinematic reel script and visual prompts for: {selected_topic}"}
                    ],
                    "temperature": 0.75,
                    "max_tokens": 3200,
                    "response_format": {"type": "json_object"},
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=35)
                if resp.status_code == 200:
                    raw = resp.json()["choices"][0]["message"]["content"]
                    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
                    raw = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE)
                    raw = re.sub(r"```$", "", raw.strip())
                    data = json.loads(raw)
                    if data.get("scenes") and len(data["scenes"]) >= 3:
                        result_data = data
                        break
            except Exception as exc:
                logger.warning("Groq model %s error: %s", model, exc)

    # 3. Fallback to Gemini if Groq failed
    if not result_data and config.GEMINI_API_KEY:
        try:
            logger.info("Prompter calling Gemini fallback...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
            full_prompt = f"{MASTER_PROMPTER_SYSTEM_PROMPT}\n\nGenerate for: {selected_topic}"
            payload = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
            }
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            if resp.status_code == 200:
                raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw)
                if data.get("scenes"):
                    result_data = data
        except Exception as exc:
            logger.warning("Gemini prompter fallback error: %s", exc)

    # 4. Built-in Master Prompter Offline Fallback
    if not result_data:
        logger.info("Using built-in master prompter template for: %s", selected_topic)
        result_data = _get_default_prompter_pack(selected_topic)

    # 5. Normalize and adapt fields for downstream video pipeline compatibility
    _normalize_prompter_data(result_data, selected_topic)
    return result_data


def _normalize_prompter_data(data: Dict[str, Any], topic: str) -> None:
    """Ensures consistent fields for both human readability and automated video pipeline."""
    # Ensure full script exists
    scenes = data.get("scenes", [])
    if not data.get("full_script"):
        parts = [s.get("hindi_voiceover", "") for s in scenes]
        data["full_script"] = " ".join([p for p in parts if p]).strip()

    # Clean script for voiceover engine
    script_clean = re.sub(r"\[.*?\]|\(.*?\)", "", data["full_script"])
    script_clean = re.sub(r"\s+", " ", script_clean).strip()
    data["script"] = script_clean
    data["title"] = data.get("reel_title") or data.get("title") or topic

    # Build image_prompts list
    image_prompts = []
    for s in scenes:
        p = s.get("visual_prompt", "")
        if p:
            image_prompts.append(p)
    data["image_prompts"] = image_prompts

    # Calculate word ratios for narrative timing sync
    scene_words = [max(1, len(s.get("hindi_voiceover", "").split())) for s in scenes]
    total_w = sum(scene_words)
    data["scene_ratios"] = [w / total_w for w in scene_words] if total_w > 0 else [0.25, 0.25, 0.25, 0.25]


def _get_default_prompter_pack(topic: str) -> Dict[str, Any]:
    """Default master prompter package for Karna & Dharma."""
    return {
        "reel_title": "कर्ण का पतन और सबसे बड़ी सीख",
        "target_duration": "~50 seconds",
        "category": "Mahabharata",
        "scenes": [
            {
                "scene_number": 1,
                "segment_name": "The Hook (0-10s)",
                "hindi_voiceover": "क्या आप जानते हैं कि महाभारत के सबसे शक्तिशाली योद्धा कर्ण का वध केवल एक बाण से नहीं, बल्कि उसके अतीत के कर्मों से हुआ था?",
                "visual_prompt": "Japanese anime key visual, 2D anime style, Studio Ufotable aesthetic, warrior Karna in torn robes, divine golden armor radiating electric solar lightning, glowing fierce anime eyes, stormy battlefield sunset, crisp cel-shaded anime art, sharp line art, 8k, vertical 9:16, completely animated, no realism, not a photograph",
                "camera_motion": "Slow dramatic zoom-in on character face",
                "lighting_style": "Volumetric golden hour sunbeams breaking through dust",
            },
            {
                "scene_number": 2,
                "segment_name": "The Conflict (10-25s)",
                "hindi_voiceover": "जब कुरुक्षेत्र में कर्ण के रथ का पहिया भूमि में धंस गया, तब उसने कृष्ण से धर्म की दुहाई दी।",
                "visual_prompt": "Epic 2D anime battle scene, Studio Ufotable style, Karna down on one knee desperately pulling the glowing wooden chariot wheel out of battlefield mud, burning arrows streaking across dark stormy sky, dynamic anime speed lines, vibrant cel-shading, 8k, vertical 9:16, 2D animated illustration",
                "camera_motion": "Dynamic slow pan across the battlefield confrontation",
                "lighting_style": "Dark stormy skies with dramatic rim light on armor",
            },
            {
                "scene_number": 3,
                "segment_name": "The Climax (25-38s)",
                "hindi_voiceover": "इस पर भगवान कृष्ण ने मुस्कुराते हुए पूछा—कर्ण, जब द्रौपदी का भरी सभा में अपमान हो रहा था, तब तुम्हारा धर्म कहाँ था?",
                "visual_prompt": "Lord Krishna in breathtaking 2D Japanese anime key visual, divine dusk-blue skin, glowing peacock feather crown, serene smile, blinding cosmic Sudarshana chakra radiating golden lightning sparks and celestial particles, Studio Ufotable anime style, vertical 9:16, completely animated",
                "camera_motion": "Expansive slow zoom-out revealing cosmic scale",
                "lighting_style": "Blinding radiant celestial aura and golden lightning",
            },
            {
                "scene_number": 4,
                "segment_name": "The Life Lesson & CTA (38-50s)",
                "hindi_voiceover": "इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि अधर्म और गलत लोगों का साथ हमेशा पतन की ओर ले जाता है। सनातन ज्ञान के लिए फॉलो ज़रूर करें।",
                "visual_prompt": "Serene ancient Himalayan stone temple in beautiful 2D anime movie style, glowing brass oil lamps casting warm golden radiance, sacred incense smoke swirling in dawn air, vibrant sunrise anime sky, peaceful anime landscape, vertical 9:16, completely animated, no photo",
                "camera_motion": "Gentle upward tilt towards sacred temple spire and dawn sky",
                "lighting_style": "Warm ambient glow of brass oil lamps and soft morning mist",
            },
        ],
        "full_script": (
            "क्या आप जानते हैं कि महाभारत के सबसे शक्तिशाली योद्धा कर्ण का वध केवल एक बाण से नहीं, "
            "बल्कि उसके अतीत के कर्मों से हुआ था? जब कुरुक्षेत्र में कर्ण के रथ का पहिया भूमि में धंस गया, "
            "तब उसने कृष्ण से धर्म की दुहाई दी। इस पर भगवान कृष्ण ने मुस्कुराते हुए पूछा—कर्ण, जब द्रौपदी का भरी सभा में "
            "अपमान हो रहा था, तब तुम्हारा धर्म कहाँ था? इस कहानी से हम इंसानों को सबसे बड़ी सीख यह मिलती है कि "
            "अधर्म और गलत लोगों का साथ हमेशा पतन की ओर ले जाता है। सनातन ज्ञान के लिए फॉलो ज़रूर करें।"
        ),
        "fb_reels_caption": "🏹 महाभारत से जीवन की सबसे बड़ी सीख! गलत संगति और अधर्म का परिणाम हमेशा विनाशकारी होता है। #Mahabharata #Karma #LifeLessons",
        "ig_reels_caption": "कर्ण के जीवन से इंसान के लिए सबसे बड़ी सीख 🕉️✨ गलत संगति हमेशा पतन लाती है। #Mahabharata #SanatanDharma #Krishna #Karma #LifeLessons",
        "hashtags": ["#Mahabharata", "#SanatanDharma", "#HinduMythology", "#Krishna", "#Karma", "#LifeLessons"],
        "keywords": ["ancient indian temple", "sacred fire ritual", "himalayas meditation", "golden divine light"],
    }


def print_formatted_prompter_pack(pack: Dict[str, Any]) -> None:
    """Prints a beautiful, highly readable output for human inspection or prompt copying."""
    title = pack.get("reel_title") or pack.get("title", "Mythology Reel")
    duration = pack.get("target_duration", "~50 seconds")
    category = pack.get("category", "Sanatan Dharma")

    print("\n" + "=" * 70)
    print(f"  🕉️  MASTER MYTHOLOGICAL PROMPTER AGENT")
    print("=" * 70)
    print(f"🎬 Reel Title:      {title}")
    print(f"⏱️  Target Duration: {duration}")
    print(f"🏷️  Category:        {category}")
    print("-" * 70)

    scenes = pack.get("scenes", [])
    for s in scenes:
        num = s.get("scene_number", 1)
        seg = s.get("segment_name", f"Scene {num}")
        hindi = s.get("hindi_voiceover", "")
        prompt = s.get("visual_prompt", "")
        motion = s.get("camera_motion", "Ken Burns slow motion")
        lighting = s.get("lighting_style", "Cinematic golden hour")

        print(f"\n--- [SCENE {num}: {seg}] ---")
        print(f"🎙️  Hindi Voiceover:")
        print(f"    \"{hindi}\"")
        print(f"🎥  Automated Video / Image Prompt (English):")
        print(f"    {prompt}")
        print(f"📹  Camera Motion:  {motion}")
        print(f"💡  Lighting Style: {lighting}")

    print("\n" + "-" * 70)
    print("📜 FULL SPOKEN SCRIPT (HINDI):")
    print(f"   {pack.get('full_script', pack.get('script', ''))}")
    print("\n📱 INSTAGRAM CAPTION:")
    print(f"   {pack.get('ig_reels_caption', '')}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Master Mythological Prompter Agent CLI")
    parser.add_argument("topic", nargs="?", help="Specific topic or story title (e.g. 'The curse of Karna')")
    parser.add_argument("--json", action="store_true", help="Output raw JSON format only")
    parser.add_argument("--save", action="store_true", help="Save prompt pack to prompts/ directory as JSON")
    args = parser.parse_args()

    pack = generate_mythological_prompt_pack(args.topic)

    if args.save:
        out_dir = Path(__file__).parent / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\-]", "_", (args.topic or pack.get("reel_title", "prompt_pack"))[:40])
        file_path = out_dir / f"{safe_name}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved prompt pack to: {file_path}")

    if args.json:
        print(json.dumps(pack, indent=2, ensure_ascii=False))
    else:
        print_formatted_prompter_pack(pack)


if __name__ == "__main__":
    main()
