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

import random
import re
from typing import Any, TypedDict

from src.scriptwriter import generate_script


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


# ---------------------------------------------------------------------------
# Template ingredient banks keyed by topic keyword
# ---------------------------------------------------------------------------

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
    """Return step-by-step cooking instructions for the given topic."""
    topic_lower = topic.lower()
    for keyword, steps in _STEP_TEMPLATES.items():
        if keyword in topic_lower:
            return list(steps)
    return list(_STEP_TEMPLATES["default"])


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


def _build_enhanced_script(
    base_script: str,
    steps: list[str],
    ingredients: list[str],
    tips: list[str],
) -> str:
    """Rebuild the narration script to include step-by-step structure.

    Inserts numbered steps and a selection of tips into the existing base
    script body while preserving the hook, CTAs, and punchline structure.

    Args:
        base_script: Original script from generate_script().
        steps:       Numbered step instructions.
        ingredients: Ingredient list.
        tips:        Pro tips.

    Returns:
        Enhanced script string.
    """
    # Find the hook (first sentence / first two sentences) and keep it
    sentences = re.split(r"(?<=[.!?])\s+", base_script.strip())
    hook_sentences = sentences[:2] if len(sentences) >= 2 else sentences
    hook_part = " ".join(hook_sentences)

    # Build structured body
    step_lines = []
    for i, step in enumerate(steps[:6], 1):
        step_lines.append(f"Step {i}: {step}")

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


def generate_enhanced_script(topic: str) -> EnhancedScriptData:
    """Generate an enhanced step-by-step food script.

    Calls the base ``generate_script()`` and enriches the output with
    detailed cooking steps, ingredient lists, timing estimates, tips,
    variations, and beat markers.

    Args:
        topic: The food topic to generate a script for.

    Returns:
        An :class:`EnhancedScriptData` dict with all base and enhanced keys.
    """
    # Get the base script from the existing scriptwriter
    base_data: dict[str, Any] = dict(generate_script(topic))

    ingredients = _pick_ingredients(topic)
    steps = _pick_steps(topic)
    prep_time, cook_time, total_time = _estimate_timing(topic, len(steps))

    # Select 3–4 relevant tips and 2–3 variations
    tips = random.sample(_TIPS_BANK, min(4, len(_TIPS_BANK)))
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
