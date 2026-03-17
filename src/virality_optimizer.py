"""
virality_optimizer.py — Data-driven virality scoring engine for the Food Making
Videos Factory.

Analyses all key viral factors and returns a structured ``ViralityReport``
with an overall confidence score (0–100 %) and per-factor breakdowns so the
pipeline can log improvement suggestions before uploading.

Factors analysed
----------------
1. **Hook strength** — curiosity-gap detection, pattern-interrupt scoring,
   emotional trigger identification.
2. **CTA effectiveness** — number, type, and strategic placement of calls to
   action throughout the script.
3. **Engagement pattern** — watch-time retention signals, pacing, and
   cliffhanger density.
4. **Thumbnail appeal** — title length, contrast keywords, emoji usage,
   readability scoring.
5. **Audio balance** — estimated narration-to-music volume ratio check.
6. **Keyword density** — SEO term frequency in title + description.
7. **Trending topic boost** — alignment with known high-engagement food topics.
8. **Tag completeness** — count, variety across tiers, character usage.

Usage::

    from src.virality_optimizer import analyze_virality, ViralityReport
    report = analyze_virality(script_data, topic)
    print(report.overall_score)   # 0–100
    print(report.suggestions)     # list of improvement tips
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FactorScore:
    """Score for a single virality factor."""

    name: str
    score: float        # 0.0–1.0
    max_score: float    # always 1.0 (normalised)
    details: str        # human-readable explanation
    suggestions: list[str] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        """Return the score as a percentage (0–100)."""
        return round(self.score * 100, 1)


@dataclass
class ViralityReport:
    """Full virality analysis report for a single video."""

    topic: str
    title: str
    overall_score: float        # 0.0–1.0 weighted average
    factors: list[FactorScore]
    suggestions: list[str]
    generated_at: float = field(default_factory=time.time)

    @property
    def overall_percentage(self) -> float:
        """Overall virality confidence as a percentage (0–100)."""
        return round(self.overall_score * 100, 1)

    def format_report(self) -> str:
        """Return a human-readable multi-line summary of the report."""
        lines = [
            "=" * 60,
            f"🔥 Virality Analysis Report",
            f"   Topic : {self.topic}",
            f"   Title : {self.title}",
            f"   Score : {self.overall_percentage:.1f}% confidence",
            "=" * 60,
        ]
        for factor in self.factors:
            bar_filled = int(factor.score * 20)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            lines.append(f"  {factor.name:<28} [{bar}] {factor.percentage:.0f}%")
            lines.append(f"    → {factor.details}")
        if self.suggestions:
            lines.append("")
            lines.append("💡 Improvement suggestions:")
            for s in self.suggestions:
                lines.append(f"   • {s}")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factor weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_WEIGHTS: dict[str, float] = {
    "hook_strength":     0.22,
    "cta_effectiveness": 0.15,
    "engagement_pattern": 0.15,
    "thumbnail_appeal":  0.12,
    "keyword_density":   0.12,
    "tag_completeness":  0.10,
    "trending_boost":    0.08,
    "audio_balance":     0.06,
}

assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "Factor weights must sum to 1.0"


# ---------------------------------------------------------------------------
# Trend and keyword databases
# ---------------------------------------------------------------------------

_HIGH_ENGAGEMENT_FOOD_TOPICS: frozenset[str] = frozenset({
    "pasta", "chicken", "pizza", "burger", "sushi", "ramen", "curry",
    "tacos", "baking", "bread", "cookies", "cake", "chocolate", "cheese",
    "steak", "salmon", "avocado", "egg", "rice", "noodles", "soup",
    "salad", "smoothie", "coffee", "dessert", "street food", "air fryer",
    "instant pot", "one pot", "meal prep", "5 ingredient", "under 10 minutes",
    "healthy", "keto", "vegan", "gluten free", "carbonara", "biryani",
    "tikka masala", "pad thai", "pho", "dumplings", "gyoza", "falafel",
    "hummus", "guacamole", "kimchi", "focaccia", "croissant", "pancakes",
    "french toast", "omelette", "grilled cheese", "mac and cheese",
})

_CURIOSITY_GAP_PHRASES: frozenset[str] = frozenset({
    "secret", "trick", "hack", "nobody tells you", "chefs won't tell",
    "hiding", "wrong this whole time", "until now", "finally", "real reason",
    "truth about", "science behind", "why your", "never knew", "game changer",
    "you have been making", "this changes everything",
})

_PATTERN_INTERRUPT_PHRASES: frozenset[str] = frozenset({
    "forget everything", "stop", "wait", "this is not what you think",
    "completely different", "not what you expect", "surprising", "shocking",
    "unexpected", "you won't believe",
})

_EMOTIONAL_TRIGGER_PHRASES: frozenset[str] = frozenset({
    "family", "grandma", "memories", "childhood", "love", "comfort",
    "incredible", "amazing", "life changing", "never go back", "obsessed",
    "addicted", "mind-blowing", "crying", "blown away",
})

_CTA_VERBS: frozenset[str] = frozenset({
    "subscribe", "follow", "like", "comment", "share", "save",
    "tag", "drop", "hit", "tap", "smash",
})

_SEO_FOOD_KEYWORDS: frozenset[str] = frozenset({
    "recipe", "cooking", "food", "easy", "quick", "homemade", "best",
    "simple", "delicious", "healthy", "dinner", "lunch", "breakfast",
    "how to", "make", "chef", "kitchen", "restaurant", "gourmet", "viral",
})

_BROAD_TAGS: frozenset[str] = frozenset({
    "food", "recipe", "cooking", "foodie", "kitchen", "chef", "yummy",
    "delicious", "eat", "cook", "meals", "easyrecipe", "homemade",
    "shorts", "viral", "trending",
})


# ---------------------------------------------------------------------------
# Individual factor analysers
# ---------------------------------------------------------------------------

def _analyse_hook_strength(hook: str, script: str) -> FactorScore:
    """Score the hook for curiosity-gap, pattern-interrupt, and emotional triggers."""
    text = (hook + " " + script[:300]).lower()

    curiosity_hits = sum(1 for p in _CURIOSITY_GAP_PHRASES if p in text)
    interrupt_hits = sum(1 for p in _PATTERN_INTERRUPT_PHRASES if p in text)
    emotion_hits = sum(1 for p in _EMOTIONAL_TRIGGER_PHRASES if p in text)

    # Score: each category contributes up to 1/3
    curiosity_score = min(curiosity_hits / 2, 1.0) * 0.4
    interrupt_score = min(interrupt_hits / 1, 1.0) * 0.3
    emotion_score = min(emotion_hits / 2, 1.0) * 0.3
    total = curiosity_score + interrupt_score + emotion_score

    # Bonus: hook opens with a number (listicle pattern is highly viral)
    if re.match(r"^\d+", hook.strip()):
        total = min(1.0, total + 0.1)

    # Bonus: hook asks a question
    if "?" in hook[:120]:
        total = min(1.0, total + 0.05)

    suggestions = []
    if curiosity_hits == 0:
        suggestions.append("Add a curiosity-gap phrase to the hook (e.g. 'secret', 'trick', 'you've been doing this wrong').")
    if interrupt_hits == 0:
        suggestions.append("Open with a pattern interrupt phrase (e.g. 'Stop', 'Forget everything you know about…').")
    if emotion_hits == 0:
        suggestions.append("Include an emotional trigger to build viewer connection.")

    return FactorScore(
        name="Hook Strength",
        score=round(total, 3),
        max_score=1.0,
        details=f"Curiosity: {curiosity_hits}, Interrupt: {interrupt_hits}, Emotion: {emotion_hits}",
        suggestions=suggestions,
    )


def _analyse_cta_effectiveness(script: str) -> FactorScore:
    """Score the number and strategic placement of CTAs in the script."""
    words = script.lower().split()
    total_words = max(len(words), 1)

    cta_positions: list[float] = []
    cta_types: set[str] = set()

    for i, word in enumerate(words):
        clean = re.sub(r"[^a-z]", "", word)
        if clean in _CTA_VERBS:
            cta_positions.append(i / total_words)
            cta_types.add(clean)

    count = len(cta_positions)
    variety = len(cta_types)

    # Ideal: at least 3 CTAs spread across early (~25%), mid (~50%), late (~75%)
    spread_score = 0.0
    zones_hit = {"early": False, "mid": False, "late": False}
    for pos in cta_positions:
        if 0.1 <= pos <= 0.35:
            zones_hit["early"] = True
        elif 0.36 <= pos <= 0.65:
            zones_hit["mid"] = True
        elif 0.66 <= pos <= 0.95:
            zones_hit["late"] = True
    spread_score = sum(zones_hit.values()) / 3

    count_score = min(count / 4, 1.0) * 0.4
    variety_score = min(variety / 3, 1.0) * 0.2
    placement_score = spread_score * 0.4
    total = count_score + variety_score + placement_score

    suggestions = []
    if count < 3:
        suggestions.append(f"Add more CTAs — found {count}, aim for at least 3.")
    for zone, hit in zones_hit.items():
        if not hit:
            suggestions.append(f"Add a CTA in the {zone} portion of the script for better placement.")

    return FactorScore(
        name="CTA Effectiveness",
        score=round(total, 3),
        max_score=1.0,
        details=f"CTAs found: {count} across {variety} verbs; zones hit: {sum(zones_hit.values())}/3",
        suggestions=suggestions,
    )


def _analyse_engagement_pattern(script: str) -> FactorScore:
    """Score watch-time retention signals: pacing, cliffhangers, questions."""
    sentences = re.split(r"[.!?]+", script)
    sentences = [s.strip() for s in sentences if s.strip()]
    n = max(len(sentences), 1)

    # Short punchy sentences → better pacing for Shorts
    short_sentences = sum(1 for s in sentences if len(s.split()) <= 12)
    pacing_score = min(short_sentences / n, 1.0) * 0.3

    # Questions keep viewers engaged (open loops)
    question_count = script.count("?")
    question_score = min(question_count / 2, 1.0) * 0.25

    # Cliffhanger / tension phrases
    cliffhanger_phrases = [
        "but wait", "here is the secret", "the trick is", "you need to see",
        "do not skip", "pay attention", "this is important", "here is why",
        "and that is not all", "but that is not",
    ]
    cliffhanger_count = sum(1 for p in cliffhanger_phrases if p in script.lower())
    cliffhanger_score = min(cliffhanger_count / 2, 1.0) * 0.25

    # Energy words that raise emotional arousal
    energy_words = ["incredible", "amazing", "perfect", "best", "secret", "reveal",
                    "shocking", "viral", "game changer", "unbelievable", "absolutely"]
    energy_count = sum(1 for w in energy_words if w in script.lower())
    energy_score = min(energy_count / 3, 1.0) * 0.2

    total = pacing_score + question_score + cliffhanger_score + energy_score

    suggestions = []
    if pacing_score < 0.2:
        suggestions.append("Break long sentences into shorter punchy ones for better Shorts pacing.")
    if question_count == 0:
        suggestions.append("Add rhetorical questions to create open loops and keep viewers watching.")
    if cliffhanger_count == 0:
        suggestions.append("Add tension phrases like 'But here is the secret…' to prevent drop-off.")

    return FactorScore(
        name="Engagement Pattern",
        score=round(total, 3),
        max_score=1.0,
        details=f"Short sentences: {short_sentences}/{n}; Questions: {question_count}; Cliffhangers: {cliffhanger_count}",
        suggestions=suggestions,
    )


def _analyse_thumbnail_appeal(title: str, topic: str) -> FactorScore:
    """Score the title for thumbnail-readability and visual appeal."""
    # Short title reads better on a thumbnail overlay
    word_count = len(title.split())
    length_score = (1.0 - min(abs(word_count - 6) / 6, 1.0)) * 0.25

    # Numbers in title (e.g. "5 Ingredient") are proven to boost CTR
    has_number = bool(re.search(r"\d", title))
    number_score = 0.2 if has_number else 0.0

    # Emoji presence adds visual appeal to thumbnail overlay text
    emoji_count = len(re.findall(
        r"[\U0001F300-\U0001F9FF\U00002700-\U000027BF\U0000FE00-\U0000FE0F]",
        title,
    ))
    emoji_score = min(emoji_count / 2, 1.0) * 0.15

    # Power words that drive click-through
    power_words = ["secret", "best", "perfect", "easy", "quick", "amazing",
                   "ultimate", "viral", "pro", "restaurant", "hack", "trick"]
    power_count = sum(1 for w in power_words if w in title.lower())
    power_score = min(power_count / 2, 1.0) * 0.25

    # Topic relevance — does the title mention the topic?
    topic_words = topic.lower().split()
    topic_in_title = any(w in title.lower() for w in topic_words if len(w) > 3)
    relevance_score = 0.15 if topic_in_title else 0.0

    total = length_score + number_score + emoji_score + power_score + relevance_score

    suggestions = []
    if word_count > 10:
        suggestions.append(f"Shorten title to 6-9 words for better thumbnail readability (current: {word_count} words).")
    if not has_number:
        suggestions.append("Add a number to the title (e.g. '3 Steps', '5 Ingredients') — numbers boost CTR.")
    if emoji_count == 0:
        suggestions.append("Add 1-2 food emoji to the title for visual thumbnail appeal.")
    if power_count == 0:
        suggestions.append("Include a power word (secret, perfect, best, viral) to increase click-through rate.")

    return FactorScore(
        name="Thumbnail Appeal",
        score=round(total, 3),
        max_score=1.0,
        details=f"Words: {word_count}; Number: {has_number}; Emoji: {emoji_count}; Power words: {power_count}",
        suggestions=suggestions,
    )


def _analyse_keyword_density(title: str, description: str, tags: list[str]) -> FactorScore:
    """Score SEO keyword density across title, description, and tags."""
    combined = (title + " " + description + " " + " ".join(tags)).lower()
    words = re.findall(r"\b\w+\b", combined)
    total_words = max(len(words), 1)

    seo_hits = sum(1 for kw in _SEO_FOOD_KEYWORDS if kw in combined)
    density_ratio = seo_hits / len(_SEO_FOOD_KEYWORDS)

    # Check that keyword appears in title (most important for SEO)
    title_kw_count = sum(1 for kw in _SEO_FOOD_KEYWORDS if kw in title.lower())
    title_score = min(title_kw_count / 3, 1.0) * 0.4

    density_score = min(density_ratio, 1.0) * 0.4

    # Description length (YouTube rewards longer descriptions for search)
    desc_length_score = min(len(description) / 500, 1.0) * 0.2

    total = title_score + density_score + desc_length_score

    suggestions = []
    if title_kw_count < 2:
        suggestions.append("Add more SEO keywords to the title (e.g. 'recipe', 'easy', 'homemade').")
    if len(description) < 200:
        suggestions.append(f"Expand description to 300+ characters for better YouTube SEO (current: {len(description)}).")
    if seo_hits < 8:
        suggestions.append("Increase SEO keyword coverage in description and tags.")

    return FactorScore(
        name="Keyword Density",
        score=round(total, 3),
        max_score=1.0,
        details=f"SEO keywords found: {seo_hits}/{len(_SEO_FOOD_KEYWORDS)}; Title keywords: {title_kw_count}; Desc length: {len(description)}",
        suggestions=suggestions,
    )


def _analyse_trending_boost(topic: str, title: str, tags: list[str]) -> FactorScore:
    """Score alignment with high-engagement food topics."""
    combined = (topic + " " + title + " " + " ".join(tags)).lower()

    hits = sum(1 for t in _HIGH_ENGAGEMENT_FOOD_TOPICS if t in combined)
    total = min(hits / 3, 1.0)

    suggestions = []
    if hits == 0:
        suggestions.append(
            "Topic doesn't match known high-engagement food categories. "
            "Consider angle it toward trending formats like 'air fryer', '5-ingredient', or 'under 10 minutes'."
        )
    elif hits < 2:
        suggestions.append("Incorporate 2-3 trending food topic keywords to boost search discoverability.")

    return FactorScore(
        name="Trending Topic Boost",
        score=round(total, 3),
        max_score=1.0,
        details=f"Trending topic hits: {hits}",
        suggestions=suggestions,
    )


def _analyse_audio_balance(music_path: Any | None, narration_volume: float = 1.0) -> FactorScore:
    """Score narration-to-music balance (heuristic, based on config)."""
    import config as cfg

    music_vol = getattr(cfg, "MUSIC_VOLUME", 0.08)

    # Ideal ratio: music at 5–15% of narration volume
    if music_path is None:
        score = 0.5  # narration-only is acceptable
        details = "No background music — narration only. Score: 50% (music adds engagement)."
        suggestions = ["Add background music at 8–12% volume to increase emotional engagement."]
    elif 0.04 <= music_vol <= 0.15:
        score = 1.0
        details = f"Music volume {music_vol:.0%} is in the optimal 4–15% range."
        suggestions = []
    elif music_vol < 0.04:
        score = 0.6
        details = f"Music volume {music_vol:.0%} may be too low to register."
        suggestions = [f"Raise MUSIC_VOLUME to at least 0.06 (current: {music_vol})."]
    else:
        score = 0.5
        details = f"Music volume {music_vol:.0%} may overpower narration."
        suggestions = [f"Lower MUSIC_VOLUME to 0.08–0.12 range (current: {music_vol})."]

    return FactorScore(
        name="Audio Balance",
        score=score,
        max_score=1.0,
        details=details,
        suggestions=suggestions,
    )


def _analyse_tag_completeness(tags: list[str]) -> FactorScore:
    """Score tag count, variety, and coverage across tagging tiers."""
    tag_count = len(tags)
    tags_lower = [t.lower().strip("#") for t in tags]
    tags_joined = " ".join(tags_lower)

    # YouTube allows up to 500 characters of tags — more is better (up to ~50)
    count_score = min(tag_count / 40, 1.0) * 0.35

    # Broad tier coverage
    broad_hits = sum(1 for t in _BROAD_TAGS if t in tags_joined)
    broad_score = min(broad_hits / 4, 1.0) * 0.25

    # Niche ingredient / technique tags (non-generic words)
    niche_count = sum(1 for t in tags_lower if t not in _BROAD_TAGS and len(t) > 4)
    niche_score = min(niche_count / 10, 1.0) * 0.25

    # Long-tail phrases (multi-word tags)
    long_tail = [t for t in tags_lower if " " in t or len(t) > 15]
    long_tail_score = min(len(long_tail) / 5, 1.0) * 0.15

    total = count_score + broad_score + niche_score + long_tail_score

    suggestions = []
    if tag_count < 20:
        suggestions.append(f"Add more tags — YouTube allows up to 500 characters, aim for 30-50 tags (current: {tag_count}).")
    if broad_hits < 3:
        suggestions.append("Include broad food tags: #food #recipe #cooking #shorts.")
    if niche_count < 5:
        suggestions.append("Add ingredient-specific and technique-specific niche tags.")
    if not long_tail:
        suggestions.append("Add long-tail tags (e.g. 'homemade pasta recipe easy') for better search targeting.")

    return FactorScore(
        name="Tag Completeness",
        score=round(total, 3),
        max_score=1.0,
        details=f"Count: {tag_count}; Broad: {broad_hits}; Niche: {niche_count}; Long-tail: {len(long_tail)}",
        suggestions=suggestions,
    )


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def analyze_virality(
    script_data: dict[str, Any],
    topic: str,
    music_path: Any | None = None,
) -> ViralityReport:
    """Analyse all virality factors and return a comprehensive ``ViralityReport``.

    Args:
        script_data: Output dict from ``scriptwriter.generate_script()``,
                     expected to contain ``title``, ``script``, ``hook``,
                     ``tags``, and ``description`` keys.
        topic:       The food topic string.
        music_path:  Optional path to the selected background music file
                     (used for audio balance scoring).

    Returns:
        A fully populated :class:`ViralityReport`.
    """
    title = script_data.get("title", "")
    script = script_data.get("script", "")
    hook = script_data.get("hook", "")
    tags = script_data.get("tags", [])
    description = script_data.get("description", "")

    factors: list[FactorScore] = [
        _analyse_hook_strength(hook, script),
        _analyse_cta_effectiveness(script),
        _analyse_engagement_pattern(script),
        _analyse_thumbnail_appeal(title, topic),
        _analyse_keyword_density(title, description, tags),
        _analyse_tag_completeness(tags),
        _analyse_trending_boost(topic, title, tags),
        _analyse_audio_balance(music_path),
    ]

    # Map factor name → score for weighted average
    name_to_weight: dict[str, float] = {
        "Hook Strength": _WEIGHTS["hook_strength"],
        "CTA Effectiveness": _WEIGHTS["cta_effectiveness"],
        "Engagement Pattern": _WEIGHTS["engagement_pattern"],
        "Thumbnail Appeal": _WEIGHTS["thumbnail_appeal"],
        "Keyword Density": _WEIGHTS["keyword_density"],
        "Tag Completeness": _WEIGHTS["tag_completeness"],
        "Trending Topic Boost": _WEIGHTS["trending_boost"],
        "Audio Balance": _WEIGHTS["audio_balance"],
    }

    weighted_sum = sum(
        f.score * name_to_weight.get(f.name, 0)
        for f in factors
    )

    all_suggestions = [s for f in factors for s in f.suggestions]

    return ViralityReport(
        topic=topic,
        title=title,
        overall_score=round(weighted_sum, 4),
        factors=factors,
        suggestions=all_suggestions,
    )
