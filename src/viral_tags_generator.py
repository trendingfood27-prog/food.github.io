"""
viral_tags_generator.py — Advanced multi-tier tagging system for the Food Making
Videos Factory.

Generates 30–50 optimised YouTube tags using a five-tier strategy:

  **Tier 1 — Broad**: Universal food/cooking tags that cover the widest audience.
  **Tier 2 — Niche**: Ingredient-specific and cuisine-type tags.
  **Tier 3 — Trending**: High-engagement food formats and trending hashtags.
  **Tier 4 — Long-tail**: Specific technique/method multi-word phrases.
  **Tier 5 — Seasonal/Topical**: Month/season and occasion-based tags.

Usage::

    from src.viral_tags_generator import generate_viral_tags
    tags = generate_viral_tags("pasta carbonara", existing_tags=["pasta", "recipe"])
    # Returns 30-50 deduplicated, YouTube-safe tag strings
"""

from __future__ import annotations

import calendar
import datetime
import re
import time

# ---------------------------------------------------------------------------
# Tier 1 — Broad universal food/cooking tags (always included)
# ---------------------------------------------------------------------------
_TIER1_BROAD: list[str] = [
    "food", "recipe", "cooking", "foodie", "homemade", "easyrecipe",
    "shorts", "viral", "trending", "kitchen", "chef", "cook",
    "delicious", "yummy", "tasty", "eat", "foodlover", "instafood",
]

# ---------------------------------------------------------------------------
# Tier 3 — High-engagement trending food formats
# ---------------------------------------------------------------------------
_TIER3_TRENDING: list[str] = [
    "airfryer", "instantpot", "mealprep", "onepot", "5ingredients",
    "under10minutes", "quickrecipe", "easymeals", "budgetcooking",
    "healthyrecipe", "highprotein", "lowcarb", "veganrecipe", "keto",
    "glutenfree", "foodhack", "cookinghack", "kitchentips", "cheftips",
    "restaurantstyle", "streetfood", "comfortfood", "weeknightdinner",
    "mealideas", "cookwithme", "whatieatinaday",
]

# ---------------------------------------------------------------------------
# Tier 5 — Seasonal / monthly tags (auto-generated based on current date)
# ---------------------------------------------------------------------------
_MONTH_TAGS: dict[int, list[str]] = {
    1:  ["january", "newyear", "winterrecipe", "coldweatherfood"],
    2:  ["february", "valentinesday", "valentinesdayfood", "romantic dinner"],
    3:  ["march", "spring", "springrecipe", "st patricks day food"],
    4:  ["april", "easter", "easterrecipe", "springeats"],
    5:  ["may", "mothersday", "mothersdayfood", "springmeals"],
    6:  ["june", "summer", "summerrecipe", "bbq", "grilling"],
    7:  ["july", "4thofjuly", "summereats", "grillingseason"],
    8:  ["august", "summervibes", "outdoorcooking", "backtoschool"],
    9:  ["september", "fall", "autumnrecipe", "backtoschool meals"],
    10: ["october", "halloween", "pumpkin", "halloweenfood", "fallrecipe"],
    11: ["november", "thanksgiving", "thanksgivingrecipe", "holidaycooking"],
    12: ["december", "christmas", "christmasfood", "holidayrecipe", "newyearseve"],
}

# ---------------------------------------------------------------------------
# Ingredient / cuisine keyword → niche + long-tail tag banks
# ---------------------------------------------------------------------------
_INGREDIENT_TAG_MAP: dict[str, list[str]] = {
    # Proteins
    "chicken": ["chickenrecipe", "crispychicken", "grilledchicken", "chickendinnerideas",
                "airfryerchicken", "chickentenders", "chickenthighs", "chickenwings"],
    "beef": ["beefrecipe", "groundbeef", "steakrecipe", "beefstew", "beeftacos"],
    "pork": ["porkrecipe", "porkbelly", "pulledpork", "porkribs", "baconrecipe"],
    "fish": ["fishrecipe", "salmonrecipe", "friedfish", "seafoodrecipe", "tilapia"],
    "salmon": ["salmonrecipe", "bakedSalmon", "grilledsalmon", "salmonpasta"],
    "shrimp": ["shrimprecipe", "garlicshrimp", "shrimpscampi", "friedshrimp"],
    "egg": ["eggrecipe", "scrambledeggs", "eggs", "boiledegg", "friedegg", "eggdish"],
    "tofu": ["tofurecipe", "crispytofu", "veganprotein", "tofustirfry"],

    # Pasta / Grains
    "pasta": ["pastarecipe", "easypasta", "italianfood", "pastanight",
              "spaghettirecipe", "pennepasta", "carbonara", "aglio e olio"],
    "rice": ["ricerecipe", "friedrice", "ricebowl", "jasmine rice", "basmatirice"],
    "noodles": ["noodlerecipe", "stirfrynoodles", "ramennoodles", "lo mein"],
    "bread": ["breadrecipe", "homemadebread", "sourdough", "garlicbread", "baking"],
    "pizza": ["pizzarecipe", "homemadepizza", "pizzadough", "pizzanight"],

    # Vegetables
    "avocado": ["avocadorecipe", "avocadotoast", "guacamole", "healthyfat"],
    "potato": ["potatorecipe", "mashedpotatoes", "roastedpotatoes", "frenchfries"],
    "mushroom": ["mushroomrecipe", "sauteedmushrooms", "stuffedmushrooms"],
    "tomato": ["tomatosauce", "freshTomatoes", "tomatobasil"],

    # Baking / Desserts
    "cake": ["cakerecipe", "homemadecake", "layercake", "cakeideas", "baking"],
    "cookies": ["cookierecipe", "chocolatechipcookies", "homemadecookies", "baking"],
    "chocolate": ["chocolaterecipe", "chocolatedessert", "darkchocolate"],
    "cheesecake": ["cheesecakerecipe", "nobakedcheesecake", "easydessert"],

    # Cuisines
    "italian": ["italianrecipe", "italianfood", "authenticitalian", "italianstyle"],
    "mexican": ["mexicanrecipe", "mexicanfood", "tacos", "burritos", "enchiladas"],
    "indian": ["indianrecipe", "indianfood", "currylover", "spicyfood"],
    "chinese": ["chineserecipe", "chinesefood", "stirfry", "chinesetakeout"],
    "japanese": ["japaneserecipe", "japanesefood", "sushirecipe", "ramen"],
    "thai": ["thairecipe", "thaifood", "padthai", "thaicurry"],
    "korean": ["koreanrecipe", "koreanfood", "koreanbbq", "bibimbap"],
    "mediterranean": ["mediterraneanrecipe", "mediterraneanfood", "greekfood"],
    "south asian": ["southasianfood", "desi", "pakistanifood", "indianfood"],
    "pakistani": ["pakistanirecipe", "desikhana", "biryani", "karahi"],
    "afghan": ["afghanirecipe", "afghanikhana", "kabuli", "qabuli"],
}

# ---------------------------------------------------------------------------
# Tier 4 — Long-tail technique / method tags
# ---------------------------------------------------------------------------
_TIER4_LONG_TAIL: list[str] = [
    "how to make at home", "easy recipe for beginners", "restaurant style at home",
    "step by step recipe", "quick and easy dinner", "5 minute recipe",
    "best way to cook", "homemade from scratch", "no special equipment",
    "budget friendly meal", "healthy dinner ideas", "family dinner recipe",
    "meal prep for the week", "one pan dinner", "one pot recipe",
    "crispy texture secret", "flavor building technique", "sauce from scratch",
    "marinade tips", "seasoning secrets", "temperature control cooking",
    "professional chef technique", "cooking tips and tricks",
]


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_viral_tags(
    topic: str,
    existing_tags: list[str] | None = None,
    target_count: int = 45,
) -> list[str]:
    """Generate 30–50 optimised YouTube tags using a five-tier tagging strategy.

    Args:
        topic:         The food topic (e.g. ``'crispy air fryer chicken'``).
        existing_tags: Tags already generated by the scriptwriter (will be
                       merged and deduplicated).
        target_count:  Desired number of tags (clamped to 30–50).

    Returns:
        A deduplicated list of YouTube-safe tag strings, with the most
        important tags first (broad → niche → trending → long-tail → seasonal).
    """
    target_count = max(30, min(50, target_count))
    topic_lower = topic.lower().strip()
    seen: set[str] = set()
    result: list[str] = []

    def _add(tag: str) -> None:
        clean = _clean_tag(tag)
        if clean and clean not in seen and len(seen) < target_count:
            seen.add(clean)
            result.append(clean)

    # --- Tier 1: Broad ---
    for t in _TIER1_BROAD:
        _add(t)

    # --- Tier 2: Niche — ingredient / topic-specific ---
    topic_words = re.findall(r"\b\w+\b", topic_lower)
    # Add the raw topic as a tag (single string, spaces → spaces — YouTube allows)
    _add(topic_lower)
    # Also add each meaningful word from the topic
    for word in topic_words:
        if len(word) > 3:
            _add(word)
    # Match against ingredient tag map
    for keyword, ingredient_tags in _INGREDIENT_TAG_MAP.items():
        if keyword in topic_lower:
            for t in ingredient_tags:
                _add(t)

    # --- Merge existing tags early so they get priority ---
    for t in (existing_tags or []):
        _add(t)

    # --- Tier 3: Trending ---
    for t in _TIER3_TRENDING:
        _add(t)

    # --- Tier 4: Long-tail ---
    # Add the most relevant long-tail phrases
    for phrase in _TIER4_LONG_TAIL[:15]:
        _add(phrase)

    # --- Tier 5: Seasonal ---
    month = datetime.datetime.now().month
    for seasonal_tag in _MONTH_TAGS.get(month, []):
        _add(seasonal_tag)

    # Pad if still short
    if len(result) < 30:
        extras = [
            "foodshorts", "recipeideas", "cookingvideo", "kitchenvlog",
            "foodphotography", "eatwell", "mealtime", "foodcritic",
            "recipeblog", "dinnerideas",
        ]
        for e in extras:
            _add(e)
            if len(result) >= 30:
                break

    return result[:target_count]


def _clean_tag(tag: str) -> str:
    """Normalise a tag string to a YouTube-safe format.

    Strips leading ``#`` characters, lowercases, trims whitespace, and
    removes characters that aren't word characters or spaces.

    Args:
        tag: Raw tag string.

    Returns:
        Cleaned tag, or an empty string if the result is empty.
    """
    tag = tag.strip().lstrip("#").strip()
    tag = tag.lower()
    # Remove non-word non-space characters
    tag = re.sub(r"[^\w\s-]", "", tag)
    tag = tag.strip()
    return tag if len(tag) >= 2 else ""


# ---------------------------------------------------------------------------
# Enhanced description template
# ---------------------------------------------------------------------------

def generate_viral_description(
    topic: str,
    title: str,
    tags: list[str],
    steps: list[str] | None = None,
    cook_time_minutes: int | None = None,
    tips: list[str] | None = None,
) -> str:
    """Generate an SEO-optimised YouTube description with strong keyword placement.

    Args:
        topic:               Food topic string.
        title:               Video title (used in the opening line).
        tags:                Tag list (first 5 used as inline keywords).
        steps:               Optional list of step-by-step instructions for
                             timestamps section.
        cook_time_minutes:   Estimated total cook time (displayed in opener).
        tips:                Optional list of pro tips to include.

    Returns:
        Multi-section description string ready for YouTube upload.
    """
    today = datetime.datetime.now()
    month_name = calendar.month_name[today.month]
    year = today.year

    # Opening — keyword-rich first line (YouTube shows ~120 chars before "more")
    time_str = f"in {cook_time_minutes} minutes" if cook_time_minutes else "at home"
    opener = (
        f"🍳 Learn how to make the BEST {topic.upper()} {time_str}! "
        f"This {topic} recipe is easy, quick, and absolutely delicious. "
        f"Perfect for beginners and food lovers alike!"
    )

    # Benefit statements
    benefits = (
        "✅ No special equipment needed\n"
        "✅ Budget-friendly ingredients\n"
        "✅ Restaurant-quality results at home\n"
        "✅ Step-by-step instructions included"
    )

    # Timestamps
    timestamp_section = ""
    if steps:
        timestamp_lines = ["⏱️ TIMESTAMPS:"]
        seconds_per_step = 60 // max(len(steps), 1)
        for i, step in enumerate(steps[:8]):
            m, s = divmod(i * seconds_per_step, 60)
            ts = f"{m:02d}:{s:02d}"
            short_step = step[:60] + "…" if len(step) > 60 else step
            timestamp_lines.append(f"  {ts} — {short_step}")
        timestamp_section = "\n".join(timestamp_lines)

    # Tips section
    tips_section = ""
    if tips:
        tips_lines = ["💡 PRO TIPS:"] + [f"  • {tip}" for tip in tips[:5]]
        tips_section = "\n".join(tips_lines)

    # Engagement prompt
    engagement = (
        "👇 Let me know in the comments how your dish turned out!\n"
        "👍 LIKE this video if it helped you cook something amazing.\n"
        "🔔 SUBSCRIBE for daily recipes that will level up your cooking!\n"
        "📤 SHARE with a friend who loves great food!"
    )

    # Internal links suggestion
    channel_links = (
        "📺 More recipes on this channel:\n"
        "  → Quick weeknight dinners\n"
        "  → Restaurant-style food at home\n"
        "  → Healthy meal prep ideas"
    )

    # Hashtag block — first 10 tags as inline hashtags
    hashtag_block = " ".join(f"#{t.replace(' ', '')}" for t in tags[:15] if t)

    # Keyword-rich footer
    footer = (
        f"🍽️ {title} | Food Making Videos Factory | {month_name} {year}\n"
        f"© Food Making Videos Factory — Homemade recipes for everyone."
    )

    sections = [
        opener,
        "",
        benefits,
    ]
    if timestamp_section:
        sections += ["", timestamp_section]
    if tips_section:
        sections += ["", tips_section]
    sections += [
        "",
        engagement,
        "",
        channel_links,
        "",
        hashtag_block,
        "",
        footer,
    ]

    return "\n".join(sections)
