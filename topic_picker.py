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

# ── Blacklist Keywords & Terms ────────────────────────────────────────────────
FORBIDDEN_KEYWORDS = [
    # Politics & Elections
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
    # Religion
    "god", "religion", "religious", "church", "temple", "mosque", "bible", "quran",
    "gospel", "hindu", "muslim", "christian", "islam", "buddhist", "jewish", "atheist",
    # Misinformation / Dangerous / Clickbait
    "cure for cancer", "secret conspiracy", "flat earth", "get rich overnight",
    "illuminati", "fake news", "miracle cure", "hacker password",
]

FORBIDDEN_PATTERNS = [
    r"\bvs\.?\b",                             # "team A vs team B"
    r"^\d+\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    r"\b(ebony|black|white)\b.{0,15}\b(edition|color)\b",
]

# ── Curated Topic Bank (Covering all 23 approved categories) ─────────────────
CURATED_CATEGORY_TOPICS = {
    "Artificial Intelligence": [
        "Mind-blowing artificial intelligence advancements that sound like sci-fi",
        "How neural networks actually process information like the human brain",
        "Why autonomous AI agents are transforming how software is built",
        "The surprising history of how AI evolved from 1950 to today",
    ],
    "Programming": [
        "Why Python became the most popular programming language in the world",
        "The hidden story of how Linux powers 90% of the world's servers",
        "How clean code principles save tech companies millions of dollars",
        "What actually happens inside your computer when you compile code",
    ],
    "Technology": [
        "How fiber optic cables transmit internet data across oceans at light speed",
        "How microchips are manufactured at the sub-nanometer atomic scale",
        "The fascinating engineering behind modern smartphone cameras",
        "Why battery technology is the biggest bottleneck in modern tech",
    ],
    "Psychology": [
        "Powerful psychological phenomena that explain human behavior",
        "The Baader-Meinhof Phenomenon: Why you suddenly see things everywhere",
        "Why your brain creates fake memories without you ever noticing",
        "The Spotlight Effect: Why people pay far less attention to you than you think",
    ],
    "Human Behaviour": [
        "Why humans copy each other's body language without realizing it",
        "The fascinating science behind why we yawn when seeing someone else yawn",
        "How micro-expressions reveal hidden emotions in less than a second",
        "Why social proof unconsciously influences almost every decision you make",
    ],
    "Productivity": [
        "The 2-Minute Rule that eliminates procrastination instantly",
        "How the Eisenhower Matrix helps top CEOs prioritize high-value work",
        "Why multitasking actually lowers your IQ and focus by 40%",
        "The science of deep work: How to achieve flow state in 15 minutes",
    ],
    "Science": [
        "Why liquid nitrogen instantly freezes objects and shatters them like glass",
        "The strange physics of non-Newtonian fluids that defy gravity",
        "How bioluminescent organisms generate light without producing heat",
        "The incredible science of quantum entanglement explained simply",
    ],
    "Space": [
        "What happens if an astronaut steps out of a spaceship without a spacesuit",
        "Mind-blowing facts about neutron stars where one teaspoon weighs billions of tons",
        "Why space is completely silent and freezing cold",
        "The terrifying concept of rogue planets drifting alone in deep space",
    ],
    "History": [
        "Ancient historical secrets and engineering marvels science still cannot explain",
        "How the Library of Alexandria changed human knowledge forever",
        "Fascinating historical coincidences that sound completely fake",
        "The unexpected origin of common everyday inventions",
    ],
    "Economics": [
        "Why hyperinflation caused people to burn money for warmth in 1923",
        "How central banks control the global flow of currency and interest rates",
        "The Broken Window Fallacy: Why destruction never creates real economic wealth",
        "How supply demand dynamics quietly shape market prices every day",
    ],
    "Finance": [
        "The mathematical magic of compound interest: How small savings become millions",
        "The difference between assets and liabilities explained in 30 seconds",
        "How index funds beat 90% of professional stock market investors",
        "Why emergency funds are the single most important financial safety net",
    ],
    "Geography": [
        "Why 90% of Australia's population lives along its coastline",
        "The strange border anomalies around the world created by history",
        "Why the Pacific Ocean and Atlantic Ocean don't easily mix",
        "Fascinating geography facts that completely change your perspective of Earth",
    ],
    "Nature": [
        "How trees secretly communicate and share nutrients through underground fungi networks",
        "The incredible navigation system birds use to migrate thousands of miles",
        "Why honey never spoils: 3000-year-old honey found in Egyptian tombs is still edible",
        "The unbelievable camouflage skills of octopuses in the deep ocean",
    ],
    "Health": [
        "What happens to your brain and body when you drink enough water every day",
        "The biological reason why sleep deprivation lowers immune function",
        "How walking 10 minutes after meals drastically improves blood sugar regulation",
        "Why circadian rhythms dictate your energy levels throughout the day",
    ],
    "Business": [
        "How Netflix disrupted Blockbuster by changing business model innovation",
        "The razor and blade business model: How companies profit from refills",
        "Why network effects make tech monopolies almost impossible to break",
        "The power of brand equity: Why people pay 10x more for branded items",
    ],
    "Entrepreneurship": [
        "The lean startup methodology: How to test business ideas with zero budget",
        "Why 90% of startups fail and the 1 lesson successful founders learned",
        "How bootstrap founders build million-dollar businesses without investors",
        "The secret to finding high-demand problems before building a product",
    ],
    "Startups": [
        "How Airbnb survived its early days by selling custom cereal boxes",
        "What Minimum Viable Product (MVP) actually means for tech startups",
        "Why timing is the single biggest factor in startup success",
        "How pivot strategies saved companies like Slack and Instagram",
    ],
    "Future Technologies": [
        "How solid-state batteries will revolutionize electric vehicles and gadgets",
        "What vertical farming means for the future of global food production",
        "How brain-computer interfaces could allow humans to control devices with thought",
        "The incredible promise of nuclear fusion energy",
    ],
    "Internet Facts": [
        "How undersea internet cables transport 99% of global data traffic",
        "What happens in 1 minute on the internet across the globe",
        "The history of the very first website ever created in 1991",
        "How DNS converts web URLs into IP addresses in milliseconds",
    ],
    "Mystery": [
        "The mysterious Voynich Manuscript that no linguist or codebreaker can solve",
        "What lies at the bottom of the Mariana Trench 36,000 feet down?",
        "The mystery of the Wow! signal received from deep space in 1977",
        "Unsolved historical mysteries that puzzle modern scientists",
    ],
    "Interesting Facts": [
        "Unbelievable facts about the human body you were never taught in school",
        "Crazy facts about animals that sound like fiction",
        "Mind-bending facts about time dilation and Einstein's relativity",
        "Surprising everyday items originally invented for space exploration",
    ],
    "Life Lessons": [
        "The 1% mindset rule: How micro-habits compound into massive success",
        "Lessons from ancient Stoicism that help master emotional control",
        "Why consistency always beats intensity over long periods",
        "The psychological power of adopting a growth mindset",
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
