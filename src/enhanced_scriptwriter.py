"""
enhanced_scriptwriter.py — Step-by-step enhanced script generation module.

Wraps ``src.scriptwriter.generate_script()`` and enriches the output with:

- Detailed step-by-step cooking instructions (numbered, actionable)
- Ingredient list with quantities
- Timing annotations per step (prep / cook / total)
- Scene descriptions tied to each step for better footage selection
- Visual cues and beat markers
- Pro tips, tricks, and recipe variations
- Enhanced hooks using pattern-interrupt and curiosity-gap templates

Usage::

    from src.enhanced_scriptwriter import generate_enhanced_script
    data = generate_enhanced_script("pasta carbonara")
    # data has all keys from generate_script() PLUS:
    #   "ingredients"   : list[str]
    #   "steps"         : list[str]  (detailed step instructions)
    #   "prep_time"     : int  (minutes)
    #   "cook_time"     : int  (minutes)
    #   "total_time"    : int  (minutes)
    #   "tips"          : list[str]
    #   "variations"    : list[str]
    #   "beat_markers"  : list[dict]  (time-offset + cue text)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Any, TypedDict

import config
from src.realistic_steps_generator import generate_realistic_steps
from src.scriptwriter import (
    _fetch_preparation_steps_via_openrouter,
    _strip_markdown_fences,
    generate_script,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed output
# ---------------------------------------------------------------------------

class EnhancedScriptData(TypedDict, total=False):
    """Extended script output including step-by-step data."""

    # Base fields from generate_script()
    title: str
    script: str
    caption_script: str
    hook: str
    scenes: list[str]
    tags: list[str]
    description: str

    # Enhanced fields
    ingredients: list[str]
    steps: list[str]
    prep_time: int
    cook_time: int
    total_time: int
    tips: list[str]
    variations: list[str]
    beat_markers: list[dict[str, Any]]


# Minimum number of steps / ingredients required from an AI response before
# we consider it valid.  Mirrors the same threshold used in scriptwriter.py.
_MIN_AI_STEPS = 2
_MIN_AI_INGREDIENTS = 2

_INGREDIENT_BANKS: dict[str, list[str]] = {
    "pasta": [
        "400g pasta of choice", "3 cloves garlic, minced", "2 tbsp olive oil",
        "100ml reserved pasta water", "salt and black pepper to taste",
        "fresh parsley, chopped", "Parmesan cheese, grated",
    ],
    "chicken": [
        "500g chicken thighs or breasts", "2 tsp paprika", "1 tsp garlic powder",
        "1 tsp onion powder", "1 tbsp olive oil", "salt and pepper to taste",
        "fresh herbs (rosemary, thyme)", "lemon juice",
    ],
    "pizza": [
        "300g bread flour", "7g instant yeast", "1 tsp salt", "1 tsp sugar",
        "180ml warm water", "2 tbsp olive oil", "150g tomato passata",
        "200g mozzarella, sliced", "toppings of choice",
    ],
    "rice": [
        "300g basmati or jasmine rice", "600ml water or stock", "1 tbsp butter",
        "1 tsp salt", "aromatics (bay leaf, cardamom)", "fresh herbs to serve",
    ],
    "cake": [
        "250g all-purpose flour", "200g caster sugar", "3 large eggs",
        "120ml milk", "120g butter, softened", "2 tsp baking powder",
        "1 tsp vanilla extract", "pinch of salt",
    ],
    "curry": [
        "500g protein of choice", "2 onions, diced", "3 cloves garlic",
        "1-inch fresh ginger", "400g tinned tomatoes", "200ml coconut milk",
        "2 tbsp curry powder", "1 tsp turmeric", "1 tsp cumin seeds",
        "fresh coriander / cilantro to serve", "salt to taste",
    ],
    "default": [
        "main ingredient (as needed)", "aromatics (garlic, onion)", "cooking fat (oil or butter)",
        "seasoning (salt, pepper, herbs)", "acid (lemon juice or vinegar)",
        "finishing touch (fresh herbs, cheese, or sauce)",
    ],
}

# ---------------------------------------------------------------------------
# Step templates keyed by cooking method keyword
# ---------------------------------------------------------------------------

_STEP_TEMPLATES: dict[str, list[str]] = {
    "pasta": [
        "Bring a large pot of generously salted water to a rolling boil.",
        "Add the pasta and cook until just al dente — 1 minute less than the packet says.",
        "Meanwhile, heat olive oil in a wide pan over medium-low heat.",
        "Add minced garlic and cook gently for 60 seconds until fragrant but not brown.",
        "Reserve 100ml of starchy pasta water before draining.",
        "Drain the pasta and add it directly to the pan with the garlic.",
        "Add pasta water gradually, tossing vigorously to emulsify into a glossy sauce.",
        "Finish with Parmesan, fresh parsley, cracked black pepper, and a drizzle of olive oil.",
    ],
    "chicken": [
        "Pat the chicken completely dry with paper towels — this is the secret to crispy skin.",
        "Mix paprika, garlic powder, onion powder, salt, and pepper in a small bowl.",
        "Coat the chicken evenly with olive oil, then rub the spice mix all over.",
        "Preheat your pan over high heat until it begins to smoke slightly.",
        "Place chicken skin-side down and cook without moving for 6-7 minutes.",
        "Flip once — the skin should release naturally when properly seared.",
        "Reduce heat to medium and cook through, basting with pan juices.",
        "Rest for 5 minutes before cutting — this locks in all the juices.",
    ],
    "default": [
        "Prepare all ingredients before you start cooking — mise en place is everything.",
        "Heat your cooking vessel to the correct temperature before adding anything.",
        "Build flavor in layers: start with aromatics, then protein, then sauce.",
        "Season at every stage of cooking, not just at the end.",
        "Trust the process — resist the urge to stir constantly.",
        "Taste and adjust seasoning before serving.",
        "Add the finishing touches: fresh herbs, acid, or fat for balance.",
        "Plate with intention — we eat with our eyes first.",
    ],
}

# ---------------------------------------------------------------------------
# Tips and variations banks
# ---------------------------------------------------------------------------

_TIPS_BANK: list[str] = [
    "Always bring ingredients to room temperature before cooking for more even results.",
    "Season your cooking water like the sea — salt is not optional.",
    "High heat for searing, medium for sauces — know your heat zones.",
    "A splash of pasta water fixes almost any sauce that looks broken.",
    "Let meat rest after cooking — minimum 3 minutes, ideally 5-10.",
    "Toast your spices in dry oil for 30 seconds to unlock their full aroma.",
    "Add acid (lemon juice or vinegar) at the end to brighten every dish.",
    "Fresh herbs added at the end preserve their colour and flavour.",
    "Use the fond (browned bits on the pan) — deglaze it for instant flavour.",
    "A knob of cold butter swirled in at the end makes any sauce glossy.",
    "Taste as you cook — adjust seasoning incrementally, not all at once.",
    "Room-temperature eggs incorporate better into batters and doughs.",
]

_VARIATIONS_BANK: list[str] = [
    "Make it spicy: add chilli flakes or fresh chilies at the aromatics stage.",
    "Make it creamy: stir in 2 tbsp of cream or crème fraîche just before serving.",
    "Make it vegan: swap animal protein for tofu, tempeh, or chickpeas.",
    "Make it gluten-free: use your preferred gluten-free swap for flour or pasta.",
    "Make it lower-carb: serve over cauliflower rice or zucchini noodles.",
    "Make it richer: add a splash of white wine when building the sauce.",
    "Meal-prep version: make a double batch and store in airtight containers for 4 days.",
    "Budget version: swap expensive protein for eggs or canned legumes.",
]

# ---------------------------------------------------------------------------
# Beat / visual cue markers
# ---------------------------------------------------------------------------

_BEAT_CUE_TEMPLATES: list[str] = [
    "CUT TO: close-up of ingredients being added",
    "SMASH CUT: sizzle shot — steam rising dramatically",
    "SLOW MO: sauce drizzle or pour moment",
    "MATCH CUT: before → after transformation",
    "CLOSE UP: cross-section reveal of finished dish",
    "OVERHEAD: finished plate from above — money shot",
    "REACTION SHOT: first bite moment",
    "TEXT OVERLAY: key tip or ingredient name",
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _pick_ingredients(topic: str) -> list[str]:
    """Return an appropriate ingredient list for the given topic."""
    topic_lower = topic.lower()
    for keyword, ingredients in _INGREDIENT_BANKS.items():
        if keyword in topic_lower:
            return list(ingredients)
    return list(_INGREDIENT_BANKS["default"])


def _pick_steps(topic: str) -> list[str]:
    """Return step-by-step cooking instructions for the given topic.

    Delegates to :func:`src.realistic_steps_generator.generate_realistic_steps`
    which analyses the topic to produce authentic, topic-specific steps rather
    than recycling generic pre-defined templates.
    """
    return generate_realistic_steps(topic)


def _estimate_timing(topic: str, num_steps: int) -> tuple[int, int, int]:
    """Estimate prep, cook, and total time in minutes for the given topic.

    Returns:
        Tuple of (prep_time, cook_time, total_time) in minutes.
    """
    topic_lower = topic.lower()

    # Quick formats
    if any(k in topic_lower for k in ["quick", "5 minute", "10 minute", "instant", "fast"]):
        return 2, 8, 10

    # Baking
    if any(k in topic_lower for k in ["cake", "bread", "cookies", "biscuits", "pastry"]):
        return 15, 30, 45

    # Slow-cooked
    if any(k in topic_lower for k in ["slow cook", "braise", "stew", "roast"]):
        return 10, 60, 70

    # Default: ~5 min prep + ~15 min cook per step group
    prep = 5 + (num_steps // 4)
    cook = 15 + (num_steps * 2)
    return prep, cook, prep + cook


_OPENROUTER_TIMING_SYSTEM_PROMPT = (
    "You are a culinary expert. "
    "Return ONLY a valid JSON object with integer minute values and no extra text."
)

_OPENROUTER_INGREDIENTS_SYSTEM_PROMPT = (
    "You are a culinary expert. "
    "Return ONLY a valid JSON array of ingredient strings with no extra text, preamble, or markdown fences."
)


def _fetch_timing_via_openrouter(topic: str) -> tuple[int, int, int] | None:
    """Fetch realistic prep, cook, and total time for *topic* from OpenRouter AI.

    Returns:
        Tuple of (prep_time, cook_time, total_time) in minutes, or ``None``
        when the API key is missing or the call fails.
    """
    api_key = getattr(config, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    try:
        import httpx  # type: ignore[import]
    except ImportError:
        return None

    model = getattr(config, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
    base_url = getattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    user_prompt = (
        f"What is the realistic preparation and cooking time for making '{topic}'? "
        f"Return ONLY a JSON object with integer minute values, for example: "
        f'{{"prep_time": 10, "cook_time": 20, "total_time": 30}}'
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
            {"role": "system", "content": _OPENROUTER_TIMING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 100,
    }

    try:
        with httpx.Client(timeout=15.0) as client:  # type: ignore[attr-defined]
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()

        data = resp.json()
        content = _strip_markdown_fences(data["choices"][0]["message"]["content"].strip())
        timing = json.loads(content)

        if isinstance(timing, dict):
            prep = int(timing.get("prep_time", 0))
            cook = int(timing.get("cook_time", 0))
            total = int(timing.get("total_time", 0))
            if prep > 0 and cook > 0:
                # Some models omit total_time or return 0; compute it from parts.
                if total <= 0:
                    total = prep + cook
                logger.info(
                    "Fetched real timing for '%s' from OpenRouter: prep=%d cook=%d total=%d",
                    topic, prep, cook, total,
                )
                return prep, cook, total

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch timing for '%s': %s — falling back to estimated timing",
            topic, exc,
        )

    return None


def _fetch_ingredients_via_openrouter(topic: str) -> list[str] | None:
    """Fetch a real ingredient list for *topic* from OpenRouter AI.

    Returns:
        A list of ingredient strings, or ``None`` when the API key is missing
        or the call fails.
    """
    api_key = getattr(config, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    try:
        import httpx  # type: ignore[import]
    except ImportError:
        return None

    model = getattr(config, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
    base_url = getattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    user_prompt = (
        f"List 6-8 main ingredients with quantities for making '{topic}'. "
        f"Each entry must be a short string naming the ingredient and its amount, "
        f"for example: '400g pasta', '3 cloves garlic, minced'. "
        f"Return ONLY a JSON array of strings."
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
            {"role": "system", "content": _OPENROUTER_INGREDIENTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }

    try:
        with httpx.Client(timeout=15.0) as client:  # type: ignore[attr-defined]
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()

        data = resp.json()
        content = _strip_markdown_fences(data["choices"][0]["message"]["content"].strip())
        ingredients = json.loads(content)

        if isinstance(ingredients, list) and len(ingredients) >= _MIN_AI_INGREDIENTS:
            logger.info(
                "Fetched %d real ingredients for '%s' from OpenRouter",
                len(ingredients), topic,
            )
            return [str(i).strip() for i in ingredients if str(i).strip()]

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch ingredients for '%s': %s — falling back to ingredient bank",
            topic, exc,
        )

    return None


def _build_enhanced_script(
    base_script: str,
    steps: list[str],
    ingredients: list[str],
    tips: list[str],
) -> str:
    """Rebuild the narration script to include step-by-step structure.

    Inserts dynamically-transitioned steps and a selection of tips into the
    existing base script body while preserving the hook, CTAs, and punchline
    structure.  Uses engaging transition phrases instead of flat "Step N:"
    labels for more professional, TTS-friendly narration.

    Args:
        base_script: Original script from generate_script().
        steps:       Step instructions.
        ingredients: Ingredient list.
        tips:        Pro tips.

    Returns:
        Enhanced script string.
    """
    # Dynamic transitions replace flat "Step 1: / Step 2:" labels
    _TRANSITIONS = [
        "First,",
        "Next,",
        "Now,",
        "Then,",
        "Here is the game-changing move:",
        "The finishing touch:",
        "And finally,",
    ]

    # Find the hook (first sentence / first two sentences) and keep it
    sentences = re.split(r"(?<=[.!?])\s+", base_script.strip())
    hook_sentences = sentences[:2] if len(sentences) >= 2 else sentences
    hook_part = " ".join(hook_sentences)

    # Build structured body with dynamic transitions
    step_lines = []
    for i, step in enumerate(steps[:6]):
        transition = _TRANSITIONS[i] if i < len(_TRANSITIONS) else "Also,"
        step_lines.append(f"{transition} {step}")

    step_block = " ".join(step_lines)

    # Pick one tip to weave in
    tip = tips[0] if tips else "Pro tip: season at every stage for best results."

    # Find CTA from the original (look for subscribe/follow/like)
    cta_sentences = [s for s in sentences if any(w in s.lower() for w in
                     ["subscribe", "follow", "like", "comment", "share", "save"])]
    cta_part = " ".join(cta_sentences[-2:]) if cta_sentences else (
        "Subscribe for more recipes like this and share with your foodie friends."
    )

    return f"{hook_part} Here is exactly how to do it. {step_block} {tip} {cta_part}"


_OPENROUTER_ENHANCED_DATA_SYSTEM_PROMPT = (
    "You are a culinary expert. Return ONLY a valid JSON object with no extra text, preamble, or "
    "markdown fences. CRITICAL: All steps, ingredients, and tips must be real, topic-specific, and "
    "concrete — never generic. Steps must name exact techniques, temperatures, and timings unique "
    "to the specific dish. Ingredients must include exact quantities. Tips must be professional "
    "and dish-specific. NEVER output generic advice like 'build flavor in layers', 'cook until "
    "done', or 'add seasoning'."
)


def _fetch_ai_enhanced_data(topic: str) -> dict[str, Any] | None:
    """Fetch all enhanced script data in a single OpenRouter AI call.

    Makes one API call to retrieve structured cooking data for *topic*:
    6-8 detailed topic-specific preparation steps, 6-10 ingredients with
    exact quantities, and 3-4 professional topic-specific cooking tips.

    Args:
        topic: The food topic to research.

    Returns:
        A dict with keys ``steps``, ``ingredients``, and ``tips``, or
        ``None`` when the API key is missing or the call fails.
    """
    api_key = getattr(config, "OPENROUTER_API_KEY", None) or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None

    try:
        import httpx  # type: ignore[import]
    except ImportError:
        return None

    model = getattr(config, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
    base_url = getattr(config, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    user_prompt = (
        f"Provide detailed cooking data for making '{topic}'. "
        f"Return ONLY a JSON object with exactly these three keys:\n"
        f"  \"steps\": array of 6-8 detailed, topic-specific preparation steps — each naming the "
        f"exact technique, temperature, and timing for {topic}.\n"
        f"  \"ingredients\": array of 6-10 ingredients with exact quantities (e.g. '400g pasta', "
        f"'3 cloves garlic, minced') specific to {topic}.\n"
        f"  \"tips\": array of 3-4 professional, topic-specific cooking tips for {topic}.\n"
        f"Example format: {{\"steps\": [...], \"ingredients\": [...], \"tips\": [...]}}"
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
            {"role": "system", "content": _OPENROUTER_ENHANCED_DATA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 900,
    }

    try:
        with httpx.Client(timeout=25.0) as client:  # type: ignore[attr-defined]
            resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()

        data = resp.json()
        content = _strip_markdown_fences(data["choices"][0]["message"]["content"].strip())
        result = json.loads(content)

        if not isinstance(result, dict):
            return None

        steps = result.get("steps")
        ingredients = result.get("ingredients")
        tips = result.get("tips")

        # Validate each field meets minimum quality thresholds
        if (
            isinstance(steps, list) and len(steps) >= _MIN_AI_STEPS
            and isinstance(ingredients, list) and len(ingredients) >= _MIN_AI_INGREDIENTS
            and isinstance(tips, list) and len(tips) >= 1
        ):
            logger.info(
                "Fetched AI-enhanced data for '%s' from OpenRouter: "
                "%d steps, %d ingredients, %d tips",
                topic, len(steps), len(ingredients), len(tips),
            )
            return {
                "steps": [str(s).strip() for s in steps if str(s).strip()],
                "ingredients": [str(i).strip() for i in ingredients if str(i).strip()],
                "tips": [str(t).strip() for t in tips if str(t).strip()],
            }

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to fetch AI-enhanced data for '%s': %s — falling back to templates",
            topic, exc,
        )

    return None


def generate_enhanced_script(topic: str) -> EnhancedScriptData:
    """Generate an enhanced step-by-step food script.

    Calls the base ``generate_script()`` and enriches the output with
    detailed cooking steps, ingredient lists, timing estimates, tips,
    variations, and beat markers.

    When the OpenRouter API key is available, a single
    :func:`_fetch_ai_enhanced_data` call retrieves all three data sets
    (steps, ingredients, tips) in one round-trip.  Individual AI helpers are
    used as a secondary fallback, and keyword-matched templates are used only
    when no API key is configured.

    Args:
        topic: The food topic to generate a script for.

    Returns:
        An :class:`EnhancedScriptData` dict with all base and enhanced keys.
    """
    # Get the base script from the existing scriptwriter
    base_data: dict[str, Any] = dict(generate_script(topic))

    # --- Primary: single AI call for steps + ingredients + tips ---
    ai_data = _fetch_ai_enhanced_data(topic)

    if ai_data is not None:
        steps: list[str] = ai_data["steps"]
        ingredients: list[str] = ai_data["ingredients"]
        tips: list[str] = ai_data["tips"]
    else:
        # Secondary fallback: individual AI calls, then keyword templates
        steps = _fetch_preparation_steps_via_openrouter(topic) or _pick_steps(topic)
        ingredients = _fetch_ingredients_via_openrouter(topic) or _pick_ingredients(topic)
        tips = random.sample(_TIPS_BANK, min(4, len(_TIPS_BANK)))

    # --- Timing: AI-generated first, template fallback ---
    ai_timing = _fetch_timing_via_openrouter(topic)
    if ai_timing is not None:
        prep_time, cook_time, total_time = ai_timing
    else:
        prep_time, cook_time, total_time = _estimate_timing(topic, len(steps))

    # Select 2–3 variations
    variations = random.sample(_VARIATIONS_BANK, min(3, len(_VARIATIONS_BANK)))

    # Build enhanced script body
    enhanced_script = _build_enhanced_script(
        base_data.get("script", ""),
        steps,
        ingredients,
        tips,
    )

    # Generate beat markers tied to the step count
    beat_markers: list[dict[str, Any]] = []
    total_duration = 55  # seconds — standard YouTube Short
    interval = total_duration / max(len(steps), 1)
    for i, cue in enumerate(_BEAT_CUE_TEMPLATES[: len(steps)]):
        beat_markers.append({
            "time_offset": round(i * interval, 1),
            "cue": cue,
            "step": steps[i] if i < len(steps) else "",
        })

    # Update scenes to be step-aware
    step_scenes = [
        f"Step {i + 1}: {step[:60]}" for i, step in enumerate(steps[:6])
    ]
    # Blend with original scenes for visual variety
    original_scenes = base_data.get("scenes", [])
    blended_scenes = step_scenes + original_scenes[len(step_scenes):]

    # Update description to include ingredients, timing, and steps
    base_desc = base_data.get("description", "")
    timing_note = f"⏱️ Prep: {prep_time} min | Cook: {cook_time} min | Total: {total_time} min\n"
    ingredient_note = "🛒 Main ingredients: " + ", ".join(ingredients[:5]) + "\n"
    enhanced_desc = timing_note + ingredient_note + base_desc

    result: EnhancedScriptData = {
        **base_data,  # type: ignore[misc]
        "script": enhanced_script,
        "scenes": blended_scenes,
        "description": enhanced_desc,
        "ingredients": ingredients,
        "steps": steps,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "total_time": total_time,
        "tips": tips,
        "variations": variations,
        "beat_markers": beat_markers,
    }
    return result  # type: ignore[return-value]
