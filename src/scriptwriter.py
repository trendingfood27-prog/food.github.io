"""
scriptwriter.py — AI-Powered Food Script Generator for the Food Making Videos Factory.

Generates professional, engaging food-making scripts via the OpenRouter AI API
(https://openrouter.ai).  Falls back to high-quality template-based generation
when the API key is unavailable, ensuring the pipeline always produces output.

Scripts include:
- Viral hooks designed for the first 3-5 seconds (curiosity gaps, pattern interrupts)
- Professional step-by-step food narration with personality
- Strategically placed CTAs at 25%, 50%, 75%, and 95% of the script
- Food-specific tags (15-30) optimised for cooking/recipe YouTube searches
- SEO-friendly descriptions with keyword placement
"""

import hashlib
import json
import logging
import os
import random
import re
import time
from typing import Any, TypedDict

import config

logger = logging.getLogger(__name__)

# Minimum / maximum acceptable word counts for the narration script
_MIN_WORDS = 70
_MAX_WORDS = 200


class ScriptData(TypedDict):
    """Structured output from the food script generator."""

    title: str
    script: str
    caption_script: str
    hook: str
    scenes: list[str]
    tags: list[str]
    description: str


# ---------------------------------------------------------------------------
# Food Hook Templates — attention-grabbing intros for the first 3-5 seconds
# ---------------------------------------------------------------------------
_HOOKS: list[str] = [
    # Curiosity gap hooks
    "This one trick will make your {topic} taste like it came from a five-star restaurant.",
    "Wait until you see what happens when you add this one secret ingredient to your {topic}.",
    "Chefs have been hiding this {topic} technique for years — until now.",
    "You have been making {topic} wrong your entire life and here is the proof.",
    "I cannot believe how easy it is to make restaurant-quality {topic} at home.",
    "The reason your {topic} never tastes as good as the restaurant version finally explained.",
    "Stop wasting money at restaurants — this {topic} recipe changes everything.",
    "Nobody told me that {topic} could be this simple until I found this technique.",
    # Pattern interrupt hooks
    "Forget everything you know about making {topic} — this method is completely different.",
    "Three ingredients. Ten minutes. The most incredible {topic} you have ever tasted.",
    "What if I told you that the secret to perfect {topic} is already in your kitchen right now.",
    "Your grandma was right about {topic} and here is the science that proves it.",
    "The most viral {topic} recipe on the internet and I finally understand why.",
    "I tried every method and this is the only {topic} technique that actually works.",
    # Emotional trigger hooks
    "This {topic} recipe will make your family think you went to culinary school.",
    "The {topic} recipe that made my guests think I hired a personal chef.",
    "If comfort food had a name it would be this {topic} recipe right here.",
    "Making {topic} at home is so much better than ordering it — and I will prove it.",
    "This is the {topic} recipe I wish someone had taught me ten years ago.",
    "Once you try this {topic} method you will never go back to the old way.",
    # How-to viral hooks
    "Here is the fastest way to make perfect {topic} every single time.",
    "Five minutes and five ingredients are all you need for this incredible {topic}.",
    "The one step everyone skips that makes {topic} taste infinitely better.",
    "How professional chefs make {topic} and why it always tastes so much better.",
    "The science behind why this {topic} technique works better than everything else.",
    # Number-based viral hooks
    "Five ingredients, zero cooking skills needed, perfect {topic} every time.",
    "Three common mistakes that are ruining your {topic} and how to fix them right now.",
    "Ten seconds of prep time changes your {topic} from good to absolutely incredible.",
    "The two-ingredient upgrade that makes any {topic} taste gourmet instantly.",
    "Only four steps stand between you and the best {topic} you have ever made.",
    # South Asian cuisine hooks
    "This {topic} technique will make your family think you flew in a chef from Lahore.",
    "The spice ratio Pakistani grandmothers swear by for the perfect {topic}.",
    "Why your {topic} never tastes like the dhaba version — and the exact fix.",
    "This is the Afghan secret that transforms ordinary {topic} into something magical.",
    "One marinade, one technique — and your {topic} will taste like a Kabul street stall.",
    "Indian grandmothers have been using this {topic} trick for generations and it still works.",
    "The dum cooking method that makes {topic} taste like it simmered all day.",
    "Street food vendors in Delhi use this one trick to make {topic} irresistible.",
    "This is the tandoor secret that makes restaurant {topic} taste so much better at home.",
    "Three spices is all you need to make your {topic} taste authentically South Asian.",
    "The layering technique that takes {topic} from bland to absolutely unforgettable.",
    "Why soaking makes all the difference when it comes to perfect {topic}.",
    "Your {topic} is missing this one ingredient that every Pakistani cook knows.",
    "How to build the deep flavor base that makes Indian {topic} so addictive.",
    "This slow-cooked {topic} method has been passed down for hundreds of years.",
]

# ---------------------------------------------------------------------------
# Food Script Body Templates
# ---------------------------------------------------------------------------

# Pattern 1: Step-by-step tutorial with personality
_BODIES_TUTORIAL: list[str] = [
    (
        "Here is everything you need to know. Start with the freshest ingredients "
        "you can find — this is non-negotiable for {topic} because quality goes "
        "directly from your ingredients to your plate. The first step most people "
        "skip is proper prep, and this is where all the flavor magic actually "
        "happens. Take your time here. Now for the technique that changes "
        "everything: high heat, patience, and the right seasoning at the right "
        "moment. Professional chefs know that timing is the real secret ingredient. "
        "And here is the final touch that elevates {topic} from good to "
        "restaurant-worthy — do not skip this step, it takes thirty seconds and "
        "makes all the difference. Hit like if this helped."
    ),
    (
        "Making perfect {topic} at home is easier than you think. Step one is "
        "all about building your flavor base — this is where most home cooks "
        "lose the plot, so pay attention here. The key is low and slow at this "
        "stage; rushing it gives you flat, one-dimensional flavor. Step two is "
        "the technique that separates good cooks from great ones: proper "
        "temperature control and knowing when to add each ingredient. Step three "
        "is the secret finishing technique that restaurant chefs use every single "
        "time. Your {topic} is about to go from ordinary to extraordinary. "
        "Subscribe for more pro kitchen techniques."
    ),
]

# Pattern 2: Secret reveal with curiosity gap
_BODIES_REVEAL: list[str] = [
    (
        "Here is the secret that changed everything for me. Most people think "
        "{topic} is complicated but the truth is there is one technique that "
        "simplifies the entire process. The ingredient you are probably skipping "
        "is the difference between something that tastes okay and something that "
        "makes people ask for the recipe. Professional kitchens use this method "
        "because it locks in flavor while saving time — a double win. The moment "
        "you taste {topic} made this way you will understand why restaurant food "
        "always hits differently. Comment below with your results because I want "
        "to see how yours turns out."
    ),
    (
        "I tested twelve different methods for making {topic} and the winner "
        "surprised even me. The conventional way that most recipes teach you "
        "actually works against the natural chemistry of the ingredients. Here "
        "is what actually happens at the molecular level when you cook {topic} "
        "correctly: the proteins interact differently, the flavors develop in "
        "layers rather than all at once, and the texture ends up completely "
        "different. This is not food science trivia — it directly affects how "
        "your {topic} tastes. Once you understand this you will apply it to "
        "every dish you make. Share this with someone who loves cooking."
    ),
]

# Pattern 3: Problem-solution with before/after narrative
_BODIES_PROBLEM_SOLUTION: list[str] = [
    (
        "If your {topic} never comes out right this is exactly why. The most "
        "common mistake is rushing the process, which means the ingredients "
        "never have time to develop the depth of flavor you are looking for. "
        "The second mistake is the wrong heat — either too high and you burn "
        "the outside before the inside cooks, or too low and you steam instead "
        "of sear. The third mistake, and this one is controversial, is adding "
        "the wrong ingredients at the wrong time. Fix these three things and "
        "your {topic} will transform completely. Follow for more cooking fixes "
        "that actually work."
    ),
    (
        "Why does {topic} from a restaurant always taste better than when you "
        "make it at home? The answer is not a secret expensive ingredient or "
        "professional equipment. It comes down to three things: temperature "
        "management, the right fat, and timing. Restaurants do not rush these "
        "steps. They also do something at the end that most home recipes do not "
        "tell you about, and that finishing touch is everything. Try it once "
        "the right way and the difference will genuinely shock you. Like and "
        "save this video so you can come back to it when you cook."
    ),
]

# Pattern 4: Comparison and hack format
_BODIES_HACK: list[str] = [
    (
        "Here is the {topic} hack that took me from a mediocre home cook to "
        "someone my whole family now asks to make dinner for special occasions. "
        "The upgrade costs nothing extra and uses something already in your "
        "pantry. Step one changes the prep process entirely. Step two is the "
        "heat trick that professional cooks swear by. Step three is the garnish "
        "and plating technique that makes any {topic} look like it belongs on "
        "a tasting menu. Your plate, your rules — but trust me on these three "
        "steps. Tag someone who needs to see this."
    ),
    (
        "Five-dollar ingredient, ten-minute prep, result that looks like you "
        "spent fifty dollars on a restaurant meal. That is the {topic} hack I "
        "am about to show you. The key insight is that most of what makes "
        "restaurant food taste expensive is technique, not cost. The specific "
        "technique for {topic} that restaurants use and home cooks ignore "
        "involves building flavor in layers rather than all at once. It sounds "
        "simple because it is — once you know it. Subscribe and save this "
        "because you will want to make {topic} this way every single time."
    ),
]

# Combine all body patterns
_ALL_BODIES: list[str] = (
    _BODIES_TUTORIAL
    + _BODIES_REVEAL
    + _BODIES_PROBLEM_SOLUTION
    + _BODIES_HACK
)

# ---------------------------------------------------------------------------
# CTA Templates — placed strategically throughout the script
# ---------------------------------------------------------------------------
_CTA_EARLY: list[str] = [  # ~25% mark — like CTA
    "Hit like if this is already blowing your mind.",
    "Tap the like button if you are taking notes right now.",
    "Give this a like — this technique deserves it.",
]
_CTA_MID: list[str] = [  # ~50% mark — subscribe CTA
    "Subscribe so you never miss a recipe like this.",
    "Follow for more professional kitchen secrets like this one.",
    "Subscribe because there is so much more where this came from.",
]
_CTA_LATE: list[str] = [  # ~75% mark — comment CTA
    "Comment below what dish you want me to master next.",
    "Let me know in the comments if you tried this technique.",
    "Drop a comment with your results — I read every single one.",
]
_PUNCHLINES: list[str] = [  # Near end — share CTA
    "Share this with someone who loves food as much as you do and follow for daily recipes.",
    "Save this video and share it — you are going to want to come back to this recipe.",
    "Follow for more recipes that change how you cook forever, and share this with your foodie friends.",
    "Tag the person you are going to cook this for and subscribe for more food secrets.",
    "Share this with someone who thinks cooking is too complicated — this proves otherwise.",
]

# ---------------------------------------------------------------------------
# Food-focused Title Templates
# ---------------------------------------------------------------------------
_TITLES: list[str] = [
    "The Secret to Perfect {topic} Nobody Is Talking About \U0001f373",
    "Why Your {topic} Never Tastes Right (And How To Fix It) \U0001f525",
    "5-Minute {topic} That Tastes Like A Restaurant Made It \u2764\ufe0f",
    "I Tested Every {topic} Method — Here Is The Only One That Works \U0001f4af",
    "Professional Chef's Secret {topic} Technique Finally Revealed \U0001f468\u200d\U0001f373",
    "This {topic} Hack Will Change How You Cook Forever \U0001f92f",
    "The Easiest {topic} Recipe That Tastes Incredibly Gourmet \U0001f60d",
    "Stop Making {topic} The Wrong Way — Do This Instead \u2757",
    "How To Make {topic} Better Than Any Restaurant Version \U0001f3e0",
    "The One Ingredient That Makes {topic} Perfect Every Time \u2728",
    "{topic} Secrets Only Professional Chefs Know About \U0001f9d1\u200d\U0001f373",
    "Why This {topic} Recipe Is Going Viral Right Now \U0001f4c8",
    "Make {topic} At Home In Minutes — Better Than Takeout \U0001f6d2",
    "The {topic} Recipe I Wish I Knew Ten Years Ago \u23f0",
    "This Is Why Your {topic} Never Tastes As Good \U0001f62d\U0001f373",
    "Budget {topic} That Tastes Like Fine Dining \U0001f4b0\U0001f37d\ufe0f",
    "The Crispy {topic} Secret Restaurants Do Not Want You To Know \U0001f914",
    "From Basic to Gourmet: Transform Your {topic} Tonight \u2b50",
    "Three Mistakes You Are Making With {topic} Right Now \u26a0\ufe0f",
    "How To Make The Most Delicious {topic} Of Your Life \U0001f929",
]

# ---------------------------------------------------------------------------
# Food-specific scene descriptions for video assembly
# ---------------------------------------------------------------------------
_SCENE_POOLS: dict[str, list[str]] = {
    "intro": [
        "Close-up overhead shot of fresh ingredients laid out on a clean kitchen counter",
        "Slow-motion pour of sauce over a beautifully plated dish with steam rising",
        "Hands chopping fresh vegetables with expert knife skills on a wooden cutting board",
        "Golden crispy food sizzling in a well-seasoned cast iron pan",
        "Overhead flat lay of colorful fresh ingredients arranged artistically",
        "Chef's hands adding a finishing garnish to a restaurant-quality dish",
    ],
    "middle": [
        "Ingredient being added to a hot pan with a satisfying sizzle and steam",
        "Close-up of perfectly caramelized golden-brown surface forming in real time",
        "Hand stirring a rich, glossy sauce with a wooden spoon in a deep pot",
        "Fresh herbs being torn and scattered over a vibrant, colorful dish",
        "Side-by-side comparison of ingredients before and after proper preparation",
        "Overhead time-lapse of a dish coming together step by step",
        "Slow drizzle of olive oil catching the light as it hits a hot pan",
        "Cross-section cut of a perfectly cooked piece of meat showing ideal doneness",
        "Bubbling sauce in a pot with rising steam and rich amber color",
        "Hands plating food with precision, adding layers and texture to a white plate",
    ],
    "punchline": [
        "Final plated dish from overhead angle looking restaurant-quality and photo-perfect",
        "Fork cutting into the finished dish revealing perfect texture and color inside",
        "First bite reaction showing genuine satisfaction and flavor impact",
        "The finished dish displayed against a beautiful backdrop with perfect lighting",
        "Steam rising dramatically from a just-finished hot dish ready to be served",
        "Close-up of the perfect golden-brown, crispy surface of the finished food",
    ],
}

# ---------------------------------------------------------------------------
# Food-specific base tags — SEO-optimised for YouTube food content
# ---------------------------------------------------------------------------
_BASE_TAGS: list[str] = [
    "food recipe",
    "cooking tips",
    "easy recipes",
    "homemade cooking",
    "recipe ideas",
    "food hacks",
    "cooking tutorial",
    "quick meals",
    "kitchen tips",
    "food secrets",
    "cooking techniques",
    "meal ideas",
    "food video",
    "recipe video",
    "cooking shorts",
    "easy cooking",
    "food inspiration",
    "delicious recipes",
    "cooking hacks",
    "food channel",
]

_TOPIC_TAG_MAP: list[tuple[list[str], list[str]]] = [
    (["pasta", "spaghetti", "noodle", "linguine"], ["pasta recipe", "homemade pasta", "Italian cooking"]),
    (["chicken", "poultry", "breast", "thigh"], ["chicken recipe", "easy chicken", "crispy chicken"]),
    (["beef", "steak", "burger", "ground beef"], ["beef recipe", "steak cooking", "homemade burger"]),
    (["fish", "salmon", "tuna", "seafood", "shrimp"], ["seafood recipe", "fish cooking", "healthy seafood"]),
    (["vegetable", "veggie", "vegan", "plant", "salad"], ["vegetarian recipe", "vegan cooking", "healthy vegetables"]),
    (["dessert", "cake", "cookie", "chocolate", "sweet"], ["dessert recipe", "baking tips", "homemade dessert"]),
    (["bread", "baking", "dough", "yeast", "flour"], ["homemade bread", "baking recipe", "bread making"]),
    (["breakfast", "egg", "pancake", "waffle", "oat"], ["breakfast recipe", "easy breakfast", "morning meals"]),
    (["soup", "stew", "broth", "chowder", "bisque"], ["soup recipe", "homemade soup", "easy stew"]),
    (["sauce", "gravy", "marinade", "dressing", "dip"], ["sauce recipe", "homemade sauce", "cooking sauce"]),
    (["air fryer", "airfryer"], ["air fryer recipe", "air fryer cooking", "crispy air fryer"]),
    (["slow cooker", "crockpot", "instant pot"], ["slow cooker recipe", "easy slow cooker", "hands off cooking"]),
    (["healthy", "diet", "nutrition", "protein", "low calorie"], ["healthy recipe", "weight loss food", "nutritious meals"]),
    (["budget", "cheap", "affordable", "frugal"], ["budget cooking", "cheap meals", "affordable recipes"]),
    # Pakistani cuisine tags
    (["biryani", "karahi", "nihari", "haleem", "korma", "keema"], ["Pakistani food", "biryani recipe", "South Asian cooking"]),
    (["samosa", "pakora", "seekh kabab", "chapli kabab", "tikka"], ["Pakistani street food", "desi snacks", "kebab recipe"]),
    (["naan", "paratha", "roti", "chapati", "puri"], ["Pakistani bread", "desi bread", "homemade naan"]),
    (["daal", "dal", "lentil", "chana", "chole"], ["lentil recipe", "daal recipe", "vegetarian Indian"]),
    # Afghan cuisine tags
    (["kabuli palaw", "qabuli pulao", "bolani", "mantu", "aushak", "qorma", "shorwa"], ["Afghan food", "Afghan recipe", "Central Asian cooking"]),
    # Indian cuisine tags
    (["butter chicken", "tikka masala", "paneer", "palak", "dal makhani"], ["Indian food", "Indian recipe", "curry recipe"]),
    (["dosa", "idli", "sambar", "rasam", "uttapam", "vada"], ["South Indian food", "dosa recipe", "idli recipe"]),
    (["tandoori", "tandoor", "dum", "biryani", "hyderabadi"], ["tandoori recipe", "dum cooking", "Indian biryani"]),
    (["chai", "masala chai", "lassi", "mango lassi", "raita"], ["Indian drinks", "masala chai recipe", "lassi recipe"]),
    (["chaat", "pani puri", "bhel puri", "pav bhaji", "gol gappa"], ["Indian street food", "chaat recipe", "street food at home"]),
]


def _topic_seed(topic: str) -> int:
    """Generate a stable integer seed from a topic string.

    Uses MD5 (non-security use) to produce a consistent numeric seed.
    """
    digest = hashlib.md5(topic.encode("utf-8")).hexdigest()  # noqa: S324
    return int(digest[:8], 16)


def _pick(seq: list, rng: random.Random) -> str:
    """Pick a random element from a list using the provided RNG."""
    return rng.choice(seq)


def _fill(template: str, topic: str) -> str:
    """Replace ``{topic}`` placeholder in *template* with the actual *topic*."""
    filled = template.replace("{topic}", topic)
    filled = re.sub(r"\s+", " ", filled).strip()
    return filled


def _build_scenes(rng: random.Random) -> list[str]:
    """Build a list of food-friendly scene descriptions."""
    intro = _pick(_SCENE_POOLS["intro"], rng)
    middle1 = _pick(_SCENE_POOLS["middle"], rng)
    remaining_middle = [s for s in _SCENE_POOLS["middle"] if s != middle1]
    middle2 = _pick(remaining_middle, rng) if remaining_middle else middle1
    punchline = _pick(_SCENE_POOLS["punchline"], rng)
    return [intro, middle1, middle2, punchline]


def _build_tags(topic: str, rng: random.Random) -> list[str]:
    """Generate a de-duplicated list of food/recipe tags for the topic.

    When ``VIRAL_TAGS_ENABLED`` is set in config, delegates to
    :func:`src.viral_tags_generator.generate_viral_tags` for 30–50 optimised
    multi-tier tags.  Falls back to the local template approach otherwise.
    """
    # Try viral tags generator first (produces 30-50 tags across 5 tiers)
    if getattr(config, "VIRAL_TAGS_ENABLED", True):
        try:
            from src.viral_tags_generator import generate_viral_tags  # noqa: PLC0415
            base_template_tags = _build_tags_from_template(topic, rng)
            target = getattr(config, "VIRAL_TAGS_TARGET_COUNT", 45)
            return generate_viral_tags(topic, existing_tags=base_template_tags, target_count=target)
        except Exception as exc:  # noqa: BLE001
            logger.warning("viral_tags_generator failed: %s — using template tags", exc)

    return _build_tags_from_template(topic, rng)


def _build_tags_from_template(topic: str, rng: random.Random) -> list[str]:
    """Generate a de-duplicated list of food/recipe tags using local templates."""
    tags: list[str] = list(_BASE_TAGS)

    topic_lower = topic.lower()
    for keywords, extra_tags in _TOPIC_TAG_MAP:
        if any(kw in topic_lower for kw in keywords):
            tags.extend(extra_tags)

    # Add the raw topic words as tags (up to 3 words)
    words = re.sub(r"[^a-zA-Z0-9 ]", "", topic).split()
    tags.extend(w.lower() for w in words[:3] if len(w) > 3)

    # Add trending food hashtag tags
    tags.extend(["FoodHacks", "CookingTips", "RecipeIdeas", "FoodLovers", "HomeCooking"])

    seen: set[str] = set()
    deduped: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)

    return deduped[:30]


def _build_title(topic: str, rng: random.Random) -> str:
    """Generate a clickbait-food style title capped at 100 characters."""
    template = _pick(_TITLES, rng)
    title = _fill(template, topic)
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def _build_description(title: str, topic: str, tags: list[str]) -> str:
    """Build an SEO-friendly YouTube description with hashtags and a subscribe CTA.

    When ``VIRAL_TAGS_ENABLED`` is set, delegates to
    :func:`src.viral_tags_generator.generate_viral_description` for a richer,
    keyword-dense description.  Falls back to the local template otherwise.
    """
    if getattr(config, "VIRAL_TAGS_ENABLED", True):
        try:
            from src.viral_tags_generator import generate_viral_description  # noqa: PLC0415
            return generate_viral_description(topic, title, tags)
        except Exception as exc:  # noqa: BLE001
            logger.warning("viral_tags_generator description failed: %s — using template", exc)

    return _build_description_from_template(title, topic, tags)


def _build_description_from_template(title: str, topic: str, tags: list[str]) -> str:
    """Build a basic SEO-friendly YouTube description using local templates."""
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in tags[:10])
    return (
        f"{title}\n\n"
        f"Welcome to the Food Making Videos Factory — where we share professional "
        f"cooking secrets, viral recipes, and food hacks for home cooks who want "
        f"restaurant-quality results! Today's recipe: {topic}.\n\n"
        f"We use AI-powered research and professional culinary techniques to create "
        f"engaging food content designed for the English-speaking YouTube audience. "
        f"Subscribe and hit the bell so you never miss a recipe!\n\n"
        f"📌 TIMESTAMPS:\n"
        f"0:00 - The hook that changes everything\n"
        f"0:10 - Key ingredients revealed\n"
        f"0:25 - The professional technique\n"
        f"0:45 - The secret finishing touch\n"
        f"0:52 - Final result reveal\n\n"
        f"{hashtags}\n\n"
        f"#Shorts #FoodShorts #CookingShorts #FoodHacks #RecipeIdeas"
    )


# ---------------------------------------------------------------------------
# OpenRouter AI script generation
# ---------------------------------------------------------------------------

_OPENROUTER_SYSTEM_PROMPT = """You are a professional YouTube food content scriptwriter specializing in viral
food Shorts for English-speaking audiences. Your scripts must be:
- 150-180 words (55 second narration target)
- Structured with: viral hook (first 3-5 seconds) → professional food tips/recipe → strategic CTAs
- Designed to maximize watch time, likes, and subscriptions
- Written in an engaging, conversational American English tone with food expertise
- Include cooking tips, techniques, or food science that genuinely educates and delights
- Natural speech patterns optimized for female voice TTS narration

IMPORTANT: Return ONLY a valid JSON object (no markdown fences, no extra text) with these exact keys:
{
    "title": "YouTube title (max 100 chars, include food emoji, power words)",
    "hook": "First 1-2 sentences — viral hook with curiosity gap or shocking fact",
    "script": "Full 150-180 word narration script as plain text (no markup, no SSML tags)",
    "scenes": ["scene1 food visual description", "scene2 food visual description", "scene3 food visual description", "scene4 food visual description"],
    "tags": ["tag1", "tag2", "tag3 up to 25 food/cooking tags"],
    "description": "SEO-friendly YouTube description with main keyword in first line, 150-200 words"
}
Respond with the JSON object only. Do not include any explanation, preamble, or markdown code blocks."""


def _generate_script_via_openrouter(topic: str) -> dict[str, Any] | None:
    """Call the OpenRouter AI API to generate a professional food script.

    Args:
        topic: The food topic to generate a script for.

    Returns:
        A dict with script data keys, or None if the API call fails.
    """
    api_key = getattr(config, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.info("OPENROUTER_API_KEY not set — using template-based script generation")
        return None

    try:
        import httpx  # type: ignore[import]
    except ImportError:
        logger.warning("httpx not installed — falling back to template scripts. Run: pip install httpx")
        return None

    model = getattr(config, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
    base_url = getattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    user_prompt = (
        f"Create a viral food making video script for this topic: '{topic}'\n\n"
        f"The script must:\n"
        f"1. Open with a curiosity gap or shocking food fact hook about {topic}\n"
        f"2. Include a like CTA at around 25% of the script\n"
        f"3. Include a subscribe CTA at around 50% of the script\n"
        f"4. Include a comment CTA at around 75% of the script\n"
        f"5. End with a share CTA\n"
        f"6. Mention real techniques, ingredients, or food science related to {topic}\n"
        f"7. Be enthusiastic but credible — like a knowledgeable food creator\n"
        f"8. Target: English-speaking home cooks who love food content\n\n"
        f"Return only the JSON object as specified in the system prompt."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/itsShahAmar/annimation.github.io",
        "X-Title": "Food Making Videos Factory",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _OPENROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 1200,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
            content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        script_data = json.loads(content)
        logger.info("OpenRouter script generated successfully for topic: '%s'", topic)
        return script_data

    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenRouter API call failed for '%s': %s — falling back to templates", topic, exc)
        return None


def _build_script_from_template(topic: str) -> ScriptData:
    """Generate a professional food script using deterministic templates.

    Used as fallback when OpenRouter AI is unavailable.
    """
    topic = topic.strip() or "delicious home cooking"

    seed = _topic_seed(topic) ^ (int(time.time()) // 3600)
    rng = random.Random(seed)

    # 1. Hook
    hook_template = _pick(_HOOKS, rng)
    hook = _fill(hook_template, topic)

    # 2. Body
    body_template = _pick(_ALL_BODIES, rng)
    body = _fill(body_template, topic)

    # 3. CTAs — sprinkled through the script
    cta_early = _pick(_CTA_EARLY, rng)
    cta_late = _pick(_CTA_LATE, rng)
    punchline = _fill(_pick(_PUNCHLINES, rng), topic)

    # 4. Full script with CTAs at strategic positions
    script_parts = [hook, cta_early, body, cta_late, punchline]
    script = " ".join(script_parts)

    # Trim if too long while preserving sentence boundaries
    words = script.split()
    if len(words) > _MAX_WORDS:
        trimmed = " ".join(words[:_MAX_WORDS])
        for punct in (".", "!", "?"):
            idx = trimmed.rfind(punct)
            if idx > len(trimmed) // 2:
                trimmed = trimmed[: idx + 1]
                break
        script = trimmed

    caption_script = re.sub(r"\s+", " ", script).strip()
    scenes = _build_scenes(rng)
    tags = _build_tags(topic, rng)
    title = _build_title(topic, rng)
    description = _build_description(title, topic, tags)

    return ScriptData(
        title=title,
        script=script,
        caption_script=caption_script,
        hook=hook,
        scenes=scenes,
        tags=tags,
        description=description,
    )


def generate_script(topic: str) -> ScriptData:
    """Generate a complete food script for the given *topic*.

    Tries OpenRouter AI first for professional, engaging scripts.
    Falls back to template-based generation when the API is unavailable.

    Args:
        topic: The food topic to build the script around.

    Returns:
        A :class:`ScriptData` dict with keys: ``title``, ``script``,
        ``caption_script``, ``hook``, ``scenes``, ``tags``, ``description``.
    """
    topic = topic.strip() or "delicious home cooking"

    # --- Primary: OpenRouter AI ---
    ai_result = _generate_script_via_openrouter(topic)
    if ai_result:
        try:
            title = str(ai_result.get("title", ""))[:100] or _build_title(topic, random.Random())
            script = str(ai_result.get("script", "")).strip()
            hook = str(ai_result.get("hook", "")).strip()
            scenes = ai_result.get("scenes", [])
            tags = ai_result.get("tags", [])
            description = str(ai_result.get("description", "")).strip()

            # Validation: ensure required fields are populated
            if not script or len(script.split()) < 20:
                raise ValueError("AI script too short")
            if not isinstance(scenes, list) or len(scenes) == 0:
                scenes = _build_scenes(random.Random(_topic_seed(topic)))
            if not isinstance(tags, list) or len(tags) < 5:
                tags = _build_tags(topic, random.Random(_topic_seed(topic)))
            if not description:
                description = _build_description(title, topic, tags)
            if not hook:
                hook = script.split(".")[0] + "." if "." in script else script[:100]

            caption_script = re.sub(r"\s+", " ", script).strip()

            logger.info(
                "Food script generated via OpenRouter AI for topic '%s' (%d words, %d tags)",
                topic, len(script.split()), len(tags),
            )
            return ScriptData(
                title=title,
                script=script,
                caption_script=caption_script,
                hook=hook,
                scenes=scenes,
                tags=tags,
                description=description,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter result validation failed: %s — falling back to templates", exc)

    # --- Fallback: Template-based ---
    result = _build_script_from_template(topic)
    logger.info(
        "Food script generated via templates for topic '%s' (%d words, %d tags)",
        topic, len(result["script"].split()), len(result["tags"]),
    )
    return result
