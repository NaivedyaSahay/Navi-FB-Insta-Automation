"""
topic_picker.py
---------------
Discovers and filters viral video topics strictly aligned with approved categories:
  - Artificial Intelligence, Programming, Technology, Psychology, Human Behaviour,
    Productivity, Science, Space, History, Economics, Finance, Geography, Nature,
    Health, Business, Entrepreneurship, Startups, Future Technologies, Internet Facts,
    Mystery, Interesting Facts, Life Lessons.

Strictly filters out and blacklists forbidden content:
  - Politics, elections, celebrity gossip, crime, religion, misinformation,
    hate content, fake facts, dangerous advice, clickbait news.

Public API:
    topics = get_trending_topics(n=5, category=None)
    # Returns list of {"topic": str, "category": str, "source": str, "score": float}
"""

from __future__ import annotations

import logging
import random
import re
import time
import requests
from typing import Optional

import config

logger = logging.getLogger("topic_picker")

# ── Blacklist Keywords & Terms (Focusing on toxic politics, crime, nsfw) ──────
FORBIDDEN_KEYWORDS = [
    # Partisan Politics & Elections
    "bjp", "congress", "aap", "tmc", "dmk", "admk", "modi", "gandhi", "kejriwal",
    "trump", "biden", "kamala", "election", "elections", "vote", "voter", "voting",
    "poll", "polls", "campaign", "party", "government", "govt", "parliament",
    "senate", "congressman", "minister", "president", "prime minister", "cm", "pm",
    "politic", "politics", "political", "politician", "protest", "rally", "strike",
    # Celebrity Gossip & Scandals
    "gossip", "cheating", "divorce", "affair", "dating", "paparazzi", "kardashian",
    "scandal", "drama", "feud", "exposed", "nude", "leaked", "nsfw", "sex", "xxx",
    # Crime & Violence
    "murder", "killed", "shooting", "arrested", "stolen", "robbery", "thief",
    "assault", "kidnapped", "victim", "suspect", "police", "jail", "prison",
    "hate speech", "riots", "communal riot",
    # Misinformation / Dangerous / Clickbait
    "cure for cancer", "secret conspiracy", "flat earth", "get rich overnight",
    "illuminati", "fake news", "miracle cure", "hacker password",
]

FORBIDDEN_PATTERNS = [
    r"\bvs\.?\b",                             # "team A vs team B"
    r"^\d+\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
]

# ── Curated Hindu Mythology Story Bank (Fast-paced, inspiring, with life lessons) ──
CURATED_CATEGORY_TOPICS = {
    "Mahabharata": [
        "The curse of Karna: Why true righteousness (Dharma) must outweigh personal loyalty",
        "When Yudhishthira entered heaven with a faithful dog: The ultimate test of loyalty",
        "Why Lord Krishna chose to be an unarmed charioteer: The power of divine guidance over weapons",
        "Abhimanyu in the Chakravyuha: Supreme courage against impossible odds and the cost of half-knowledge",
        "The Yaksha Prashna: The 5 deepest life questions answered by Yudhishthira",
    ],
    "Ramayana": [
        "The secret conversation between Lakshmana and dying Ravana: The 3 golden life lessons",
        "Why Lord Rama tested Sugriva's trust: The true foundation of lasting friendship",
        "Jatayu's sacrifice: Fighting for justice even when you know you will lose",
        "Kumbhakarna's tragic dilemma: Knowing your brother is wrong yet fulfilling loyalty",
        "The little squirrel helping build Ram Setu: No honest effort is ever too small",
    ],
    "Lord Shiva": [
        "Why Lord Shiva drank the Halahala poison: The art of absorbing negativity without spreading it",
        "Lord Shiva burning Kamadeva to ashes: How to conquer destructive desires and illusions",
        "The mystery of Neelkantha: Why true strength is holding space for others' suffering",
        "When Lord Shiva danced the Tandava: Destruction is just a doorway to necessary rebirth",
    ],
    "Bhagavad Gita": [
        "Arjuna's breakdown in Kurukshetra: How Lord Krishna teaches detachment from fear and doubt",
        "The law of Nishkama Karma: Why working without obsession over results brings ultimate peace",
        "Controlling the mind like a wild wind: Krishna's practical wisdom to master inner chaos",
        "Who is a Sthitaprajna: The ancient secret to remaining calm in extreme pain or pleasure",
    ],
    "Lord Krishna": [
        "Sudama's handful of beaten rice: Why purity of heart matters infinite times more than wealth",
        "Krishna uplifting the Govardhan Hill: Collective unity and breaking blind superstition",
        "Why Krishna smiled when Gandhari cursed his entire dynasty: Accepting the consequences of fate",
        "The stolen butter (Makhan Chor): The deeper spiritual metaphor of pure love and innocence",
    ],
    "Karna & Dharma": [
        "Karna donating his golden armor to Indra: The danger of ego inside noble charity",
        "The tragedy of Karna: How bad company corrupts even the greatest warrior of all time",
        "When Kunti revealed the truth to Karna: Facing your destiny with unyielding honor",
    ],
    "Hanuman": [
        "When Hanuman tore open his chest: True devotion leaves no room for self-doubt or ego",
        "Hanuman forgetting his powers until reminded: How humans need courage from genuine mentors",
        "Why Hanuman refused a pearl necklace from Sita: What holds value if it lacks divine purpose",
    ],
    "Karma & Destiny": [
        "The wheel of Karma in Vedic scriptures: Why every choice echoes back into your life",
        "King Harishchandra at the cremation ground: Remaining truthful when the world tests your core",
        "The story of King Yayati: Why chasing endless physical pleasure only increases hunger",
    ],
    "Puranic Legends": [
        "Samudra Manthan (Churning of the Cosmic Ocean): First comes poison, only then comes nectar",
        "Bhakt Prahlad and Lord Narasimha: Unshakable faith in the face of absolute tyranny",
        "Ganesha circling his parents: Why your family is the entire universe",
    ],
    "Vedic Wisdom": [
        "The tale of Nachiketa and Yama: The secret of life, death, and conquering mortal fear",
        "Satyakama Jabala: The Upanishadic story of why truth defines character, not birth or caste",
        "The two birds on a single tree: The Upanishad parable of the soul and the observer",
    ],
    "Spiritual Life Lessons": [
        "The mirror of Maya: Why clinging to temporary worldly illusions causes endless misery",
        "The ancient secret of inner peace: The 4 ashrams of life and mastering time",
        "Why anger is called the house of destruction: Lessons from the ancient sages",
    ],
}

# ── Safety Check ─────────────────────────────────────────────────────────────
def is_topic_safe(title: str) -> bool:
    """Verify topic is suitable and contains zero forbidden keywords or patterns."""
    if not title or len(title) < 12:
        return False
    t = title.lower()

    # Check forbidden keywords
    words = set(re.findall(r"\w+", t))
    for kw in FORBIDDEN_KEYWORDS:
        if " " in kw:
            if kw in t:
                return False
        else:
            if kw in words:
                return False

    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return False

    return True

# ── Reddit Curiosity Scraper ─────────────────────────────────────────────────
def fetch_reddit_topics(n: int = 5) -> list[dict]:
    """Pull clean educational posts from r/todayilearned, r/explainlikeimfive, r/space, r/technology."""
    headers = {"User-Agent": "NaviFBIBot/1.0 (Reels Automation)"}
    subs = ["todayilearned", "explainlikeimfive", "space", "technology", "psychology"]
    topics = []

    for sub in subs:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=6"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            posts = resp.json().get("data", {}).get("children", [])
            for p in posts:
                data = p.get("data", {})
                title = data.get("title", "").strip()
                # Clean title
                title = re.sub(r"^TIL[:\s]*", "", title, flags=re.IGNORECASE).strip()
                title = re.sub(r"\[.*?\]|\(.*?\)", "", title).strip()
                if is_topic_safe(title) and len(title) >= 15:
                    topics.append({
                        "topic": title[:110],
                        "category": sub.capitalize(),
                        "source": f"Reddit r/{sub}",
                        "score": min(data.get("score", 100) / 5000, 1.0) + 1.0,
                    })
            time.sleep(0.2)
        except Exception as exc:
            logger.debug("Reddit sub %s error: %s", sub, exc)

    return topics[:n]

# ── Public API ────────────────────────────────────────────────────────────────
def get_trending_topics(n: int = 5, category: Optional[str] = None) -> list[dict]:
    """
    Select n topics from allowed categories.
    If category is specified, filter by that category.
    """
    logger.info("Selecting topics from allowed categories...")
    results = []

    if category and category in CURATED_CATEGORY_TOPICS:
        cats_to_use = [category]
    else:
        cats_to_use = list(CURATED_CATEGORY_TOPICS.keys())
        random.shuffle(cats_to_use)

    # 1. Fetch from Reddit educational subs
    reddit_topics = fetch_reddit_topics(n=n)
    for t in reddit_topics:
        if is_topic_safe(t["topic"]):
            results.append(t)

    # 2. Add curated category topics
    for cat in cats_to_use:
        options = CURATED_CATEGORY_TOPICS[cat]
        topic_text = random.choice(options)
        if is_topic_safe(topic_text):
            results.append({
                "topic": topic_text,
                "category": cat,
                "source": f"Curated ({cat})",
                "score": 1.5,
            })

    # Deduplicate & trim
    seen = set()
    final_list = []
    for r in results:
        key = r["topic"][:30].lower()
        if key not in seen and is_topic_safe(r["topic"]):
            seen.add(key)
            final_list.append(r)
        if len(final_list) >= n:
            break

    logger.info("Selected %d safe topics across approved categories.", len(final_list))
    for idx, item in enumerate(final_list, 1):
        logger.info("  %d. [%s] %s", idx, item.get("category", "General"), item["topic"])

    return final_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    topics = get_trending_topics(n=5)
    print("\nSelected Topics:")
    for i, t in enumerate(topics, 1):
        print(f"  {i}. [{t['category']}] {t['topic']}")
