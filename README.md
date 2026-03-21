# 🍳 Food Making Videos Factory

> Fully automated pipeline that creates **engaging food-making YouTube Shorts**.
> Uses AI-powered professional scripts (OpenRouter), female neural TTS voices,
> multi-source food stock footage with cinematic grading.
> **Designed for English-speaking audiences.**

[![Tests](https://github.com/itsShahAmar/annimation.github.io/actions/workflows/tests.yml/badge.svg)](https://github.com/itsShahAmar/annimation.github.io/actions/workflows/tests.yml)
[![Pipeline](https://github.com/itsShahAmar/annimation.github.io/actions/workflows/automation.yml/badge.svg)](https://github.com/itsShahAmar/annimation.github.io/actions/workflows/automation.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🍽️ What It Does

The **Food Making Videos Factory** automatically:

1. 🔥 **Finds Viral Food Topics** — Scans Google Trends + YouTube Trends + food niche pools and applies a food-awareness scoring heuristic to pick the most engaging recipe/cooking premise
2. 🤖 **AI Script Writing** — Professional scripts via [OpenRouter AI](https://openrouter.ai) (GPT-4o-mini) with viral hooks, step-by-step food narration, and strategic CTAs at 25%, 50%, 75%, and 95% of the script. Falls back to high-quality templates when the API key is not set.
3. 🎙️ **Female Professional Narration** — 12 female Microsoft Edge Neural TTS voices rotating each run for variety (Sara, Aria, Jenny, Michelle, Cora, Elizabeth, Sonia, Libby, Natasha, Clara, Neerja, Emily)
4. 🎬 **Food Video Assembly** — Stock footage from Pexels (primary), Pixabay (secondary), and Unsplash (image fallback) with warm food colour grading and bold captions
5. 🚀 **Uploads & Goes Viral** — Direct to your YouTube channel via the official API (category: Howto & Style)

All 100% automated — runs every 6 hours via GitHub Actions.

---

## 🚀 Quick Start

### Prerequisites

- A **YouTube channel** with a Google Cloud project and OAuth2 client secret
- A **Pexels API key** (free at [pexels.com/api](https://www.pexels.com/api/))
- An **OpenRouter API key** (for AI script generation — get yours at [openrouter.ai](https://openrouter.ai/keys))
- A **GitHub account** to fork this repo and set Secrets
- _(Optional)_ A **Pixabay API key** (free at [pixabay.com/api/docs](https://pixabay.com/api/docs/)) for additional stock footage
- _(Optional)_ An **Unsplash Access Key** (free at [unsplash.com/developers](https://unsplash.com/developers)) for food photography fallback
- _(Optional)_ A **NewsAPI key** for trending headline topics

### Step 1 — Fork the Repository

Click **Fork** at the top of this page, then clone your fork:

```bash
git clone https://github.com/<your-username>/annimation.github.io
cd annimation.github.io
pip install -r requirements.txt
```

### Step 2 — Create a Google Cloud OAuth2 Client Secret

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable the **YouTube Data API v3**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Choose **Desktop app**, download the JSON file

### Step 3 — Authorise Your YouTube Channel

Run the one-time authorisation flow locally:

```bash
python -c "
import json, os
from google_auth_oauthlib.flow import InstalledAppFlow

secret = json.loads(open('client_secret.json').read())
flow = InstalledAppFlow.from_client_config(
    secret,
    scopes=['https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube']
)
creds = flow.run_local_server(port=0)
print(creds.to_json())
"
```

Copy the JSON output — you'll need it for `YOUTUBE_TOKEN` secret.

### Step 4 — Set GitHub Secrets

Go to **Settings → Secrets → Actions** in your fork and add:

| Secret | Value | Source |
|--------|-------|--------|
| `YOUTUBE_CLIENT_SECRET` | JSON content of your OAuth2 client file | Step 2 above |
| `YOUTUBE_TOKEN` | JSON token from the auth flow | Step 3 above |
| `PEXELS_API_KEY` | Your Pexels API key | [pexels.com/api](https://www.pexels.com/api/) |
| `OPENROUTER_API_KEY` | Your OpenRouter API key | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `PIXABAY_API_KEY` | _(Optional)_ Your Pixabay key | [pixabay.com/api/docs](https://pixabay.com/api/docs/) |
| `UNSPLASH_ACCESS_KEY` | _(Optional)_ Your Unsplash key | [unsplash.com/developers](https://unsplash.com/developers) |
| `NEWSAPI_KEY` | _(Optional)_ Your NewsAPI key | [newsapi.org](https://newsapi.org/) |
| `FREESOUND_API_KEY` | _(Optional)_ Your Freesound key | [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply/) |

### Step 5 — Enable GitHub Actions

Go to **Actions** tab in your fork and click **"I understand my workflows, go ahead and enable them"**.

The pipeline will automatically run every 6 hours and upload a new food video to your channel.

---

## 🎵 Free Music Sources & Fallbacks

Background music is sourced automatically using a **multi-source fallback chain** — no single point of failure. Each source is tried in order until one succeeds:

| Priority | Source | API Key | Notes |
|----------|--------|---------|-------|
| 1️⃣ Primary | [Pixabay Music](https://pixabay.com/api/docs/) | `PIXABAY_API_KEY` _(optional)_ | High-quality royalty-free tracks |
| 2️⃣ Secondary | [Free Music Archive](https://freemusicarchive.org) | None required | Creative Commons licensed music |
| 3️⃣ Optional | [Freesound](https://freesound.org/apiv2/apply/) | `FREESOUND_API_KEY` _(optional)_ | Large community sound library |
| 4️⃣ Fallback | Silence Generator | None required | Always succeeds — guarantees an audio track |

**How it works:**
- If `PIXABAY_API_KEY` is set, Pixabay Music is tried first (highest quality).
- Free Music Archive is always tried next — no API key needed.
- If `FREESOUND_API_KEY` is set, Freesound is tried as an additional source.
- If all network sources fail, a silent audio track is generated locally so the pipeline never fails due to missing music.

> **No music secrets?** The pipeline still works. Free Music Archive requires no key, and the silence generator ensures the pipeline always has an audio track.

---

## 🧠 AI Script Generation (OpenRouter)

Scripts are generated using [OpenRouter AI](https://openrouter.ai) which gives you access to GPT-4o-mini, Claude, Llama, and more via a single API.

### How to Get Your OpenRouter API Key

1. Sign up at [openrouter.ai](https://openrouter.ai)
2. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
3. Click **"Create Key"** and copy the key
4. Add it as `OPENROUTER_API_KEY` in GitHub Secrets

### What the AI Generates

Each AI-generated script includes:
- **Viral hook** (first 3-5 seconds): curiosity gap or shocking food fact
- **Professional food narration**: step-by-step technique with personality
- **Strategic CTAs**: like (25%), subscribe (50%), comment (75%), share (end)
- **15-25 SEO-optimised tags**: mix of broad and niche food keywords
- **SEO-friendly description**: with main keyword in first line + timestamps

> **No API key?** The pipeline falls back to high-quality template-based scripts automatically — no configuration needed.

---

## 🎙️ Female Voice Rotation

12 professional female neural voices rotate across runs for channel variety:

| Voice | Accent | Style |
|-------|--------|-------|
| Sara Neural | US English | Cheerful, energetic |
| Aria Neural | US English | Friendly, conversational |
| Jenny Neural | US English | Professional, clear |
| Michelle Neural | US English | Natural, warm |
| Cora Neural | US English | Engaging, friendly |
| Elizabeth Neural | US English | Clear, authoritative |
| Sonia Neural | British English | Professional |
| Libby Neural | British English | Friendly |
| Natasha Neural | Australian English | Energetic |
| Clara Neural | Canadian English | Warm |
| Neerja Neural | Indian English | Professional |
| Emily Neural | Irish English | Charming |

All voices use +5% speed rate for energetic food content delivery.

---

## 📊 Viral Optimization Features

Every video is automatically optimised for maximum engagement:

### Hook Strategy
- First 1-3 seconds must grab attention (curiosity gap or shocking food fact)
- Pattern interrupts to prevent scroll-past
- Emotional trigger in the opening

### CTA Placement
- **25% mark**: Like CTA
- **50% mark**: Subscribe CTA  
- **75% mark**: Comment CTA
- **Near end**: Share CTA

### Tags Strategy (15-30 tags)
- Broad tags: `cooking`, `recipes`, `food`
- Niche tags: topic-specific ingredients and techniques
- Trending hashtags: `#FoodHacks`, `#CookingTips`, `#RecipeIdeas`

## 🗂️ Project Structure

```
annimation.github.io/
├── config.py                  # Central configuration (API keys, settings)
├── requirements.txt           # Python dependencies
├── src/
│   ├── pipeline.py            # Main orchestrator
│   ├── trending.py            # Food topic discovery
│   ├── scriptwriter.py        # OpenRouter AI + template script generation
│   ├── tts.py                 # Female-only Edge TTS with voice rotation
│   ├── video_creator.py       # Multi-source food video assembly
│   └── uploader.py            # YouTube upload
├── tests/
│   ├── test_scriptwriter.py   # Script generation tests
│   └── test_uploader.py       # Upload tests
└── .github/workflows/
    ├── automation.yml         # Pipeline: runs every 6 hours
    └── tests.yml              # CI: runs on every push
```

---

## ⚙️ Configuration

All settings are in `config.py`. Key settings:

```python
YOUTUBE_CATEGORY_ID = "26"      # Howto & Style
VIDEO_DURATION_TARGET = 55      # seconds (optimal for Shorts retention)
TTS_VOICE_ROTATE = True         # rotate female voices each run
TTS_RATE = "+5%"                # slightly faster for energy
OPENROUTER_MODEL = "openai/gpt-4o-mini"  # cost-effective AI model
```

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `edge-tts` | Microsoft neural TTS (female voices) |
| `moviepy` | Video assembly and editing |
| `requests` | Stock media API calls (Pexels, Pixabay, Unsplash) |
| `httpx` | OpenRouter AI API calls |
| `pydub` | Audio normalization |
| `google-api-python-client` | YouTube upload |

---

## �� License

MIT — see [LICENSE](LICENSE).
