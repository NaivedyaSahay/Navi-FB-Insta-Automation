# 🎬 Navi-FBI-Automation — Facebook & Instagram Reels Satisfying Video Pipeline

An automated Python pipeline built specifically for **Facebook Reels & Instagram Reels**. It generates high-retention educational/curiosity scripts using **Groq AI** (or Gemini AI), pairs them with **multiple satisfying background videos** (kinetic sand, 3D loops, soap cutting, ASMR, marble runs), synthesizes natural voiceovers with **Microsoft Edge TTS**, renders dynamic high-contrast animated captions, and publishes to **Meta Graph API (Facebook & Instagram)**.

---

## 📁 Project Architecture

```
Navi-FBI-Automation/
├── main.py                     # CLI entry point & pipeline orchestrator
├── config.py                   # Environment loader & category/topic rules
├── topic_picker.py             # Allowed category topic picker & safety filter
├── script_generator.py         # Groq API / Gemini AI script & caption generator
├── voice_generator.py          # Edge-TTS voiceover synthesis & word timing extractor
├── satisfying_video_manager.py # Stitches multiple satisfying visual clips
├── video_composer.py           # MoviePy video composition with dynamic viral captions
├── uploader_meta.py            # Meta Graph API uploader (Facebook & Instagram Reels)
├── scheduler.py                # Periodic scheduled runner
├── satisfying_clips/           # (Optional) Drop pre-downloaded local satisfying MP4s here
├── output/                     # Generated audio and video output folder
├── requirements.txt            # Python dependencies
├── .env.example                # Template configuration file
└── .env                        # Local API key configuration
```

---

## 🎯 Approved Categories & Safety Rules

### 23 Allowed Categories:
- Artificial Intelligence, Programming, Technology, Psychology, Human Behaviour, Productivity, Science, Space, History, Economics, Finance, Geography, Nature, Health, Business, Entrepreneurship, Startups, Future Technologies, Internet Facts, Mystery, Interesting Facts, Life Lessons.

### Forbidden / Blacklisted (Automatic Rejection):
- Politics, elections, celebrity gossip, crime, religion, misinformation, hate content, fake facts, dangerous advice, clickbait news.

---

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Keys

Open `.env` and add your Groq API key:

```ini
GROQ_API_KEY=your_groq_api_key_here
```

---

## 🚀 Usage Commands

Matching the simple interface from `Navi-Threads-Automation`, you can control the bot with simple commands:

### 1. Test Mode (Generate & Preview Locally — Safe, No Upload)
```bash
python main.py test
```
*Or specify a custom topic:*
```bash
python main.py test --topic "Mind-blowing AI facts that sound like sci-fi"
```

### 2. Post Mode (Generate & Post Directly to FB & Instagram NOW)
```bash
python main.py post
```
*Or with a specific category:*
```bash
python main.py post --category "Space"
```

### 3. Schedule Mode (Automated Posting Loop)
```bash
python main.py schedule
```
*Or via dedicated scheduler script:*
```bash
python scheduler.py --interval-hours 6
```

---

## 🔑 Meta API (Facebook & Instagram) Credentials Setup

To enable direct automatic posting to Facebook Reels & Instagram Reels, update `.env`:

```ini
META_ACCESS_TOKEN=your_facebook_page_access_token
META_FB_PAGE_ID=your_facebook_page_id
META_IG_USER_ID=your_instagram_business_account_id
```

### How Instagram Posting Works Automatically:
Meta's Instagram Reels API requires a publicly accessible HTTPS video URL. The bot includes **built-in automatic video hosting** (via `Catbox.moe` with `Litterbox` fallback). When you run `python main.py post`, the bot will automatically host the video temporarily online and submit it to Instagram's media container API—requiring zero manual cloud configuration!

