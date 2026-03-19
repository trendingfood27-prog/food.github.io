"""
thumbnail.py — Generate eye-catching food content thumbnails for the
Food Making Videos Factory.

Creates vibrant warm gradient backgrounds with bold food-style title text,
food emoji accents, burst shapes, and recipe/tip overlays — designed to stop
the scroll and signal irresistible food content.
"""

import logging
import math
import random
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Thumbnail dimensions (YouTube standard)
THUMB_W = 1280
THUMB_H = 720

# ---------------------------------------------------------------------------
# Food colour palettes — warm, appetising gradients for food appeal
# ---------------------------------------------------------------------------
_GRADIENT_PALETTES: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = [
    ((255, 140, 0), (200, 50, 0)),       # amber-to-red (spicy and appetising)
    ((255, 200, 50), (220, 80, 0)),      # golden-to-orange (baked and roasted)
    ((180, 255, 100), (0, 180, 80)),     # fresh green (healthy and vibrant)
    ((255, 100, 120), (180, 0, 80)),     # pink-to-red (desserts and berries)
    ((255, 220, 80), (200, 100, 0)),     # yellow-to-amber (sauces and spices)
    ((80, 200, 255), (0, 100, 200)),     # sky blue (clean and fresh)
]

_ACCENT_COLORS: list[tuple[int, int, int]] = [
    (255, 200, 0),   # golden yellow
    (255, 80, 0),    # vivid orange
    (200, 50, 0),    # deep red
    (0, 180, 80),    # fresh green
    (255, 150, 50),  # warm amber
]

_TEXT_COLOR = (255, 255, 255)    # white
_STROKE_COLOR = (0, 0, 0)        # black for outline

# ---------------------------------------------------------------------------
# Food emoji bank — maps topic keywords to food emojis
# ---------------------------------------------------------------------------
_FOOD_TOPIC_EMOJIS: list[tuple[list[str], str]] = [
    (["pasta", "spaghetti", "noodle", "linguine", "penne"], "\U0001f35d"),       # 🍝
    (["pizza"], "\U0001f355"),                                                    # 🍕
    (["chicken", "poultry", "drumstick", "wing"], "\U0001f357"),                  # 🍗
    (["burger", "beef", "ground beef", "patty"], "\U0001f354"),                   # 🍔
    (["sushi", "fish", "salmon", "tuna", "seafood"], "\U0001f363"),               # 🍣
    (["ramen", "noodle soup", "pho", "bowl"], "\U0001f35c"),                      # 🍜
    (["taco", "burrito", "mexican", "salsa"], "\U0001f32e"),                      # 🌮
    (["bread", "baking", "loaf", "sourdough"], "\U0001f35e"),                     # 🍞
    (["cake", "baking", "cupcake", "birthday"], "\U0001f370"),                    # 🍰
    (["chocolate", "dessert", "sweet", "brownie"], "\U0001f36b"),                 # 🍫
    (["egg", "breakfast", "omelette", "scrambled"], "\U0001f373"),                # 🍳
    (["salad", "vegetable", "vegan", "healthy", "green"], "\U0001f957"),          # 🥗
    (["rice", "fried rice", "stir fry", "wok"], "\U0001f35a"),                    # 🍚
    (["steak", "meat", "bbq", "grill"], "\U0001f969"),                            # 🥩
    (["soup", "stew", "broth", "chowder"], "\U0001f372"),                         # 🍲
    (["avocado", "toast", "brunch"], "\U0001f951"),                               # 🥑
    (["ice cream", "frozen", "gelato"], "\U0001f368"),                            # 🍦
    (["cookie", "biscuit", "snack"], "\U0001f36a"),                               # 🍪
    (["pancake", "waffle", "syrup"], "\U0001f95e"),                               # 🥞
    (["smoothie", "juice", "drink", "beverage"], "\U0001f9c3"),                   # 🧃
    (["curry", "indian", "spicy", "sauce"], "\U0001f35b"),                        # 🍛
]

_DEFAULT_FOOD_EMOJIS = [
    "\U0001f373",  # 🍳 frying pan
    "\U0001f525",  # 🔥 fire / hot
    "\U0001f60d",  # 😍 heart eyes
    "\u2764\ufe0f", # ❤️ heart
    "\U0001f4af",  # 💯 100
    "\u2728",       # ✨ sparkles
    "\U0001f929",  # 🤩 star-struck
    "\U0001f60e",  # 😎 sunglasses
]

# ---------------------------------------------------------------------------
# Accent text overlays — food content engagement words
# ---------------------------------------------------------------------------
_ACCENT_TEXTS: list[str] = ["VIRAL!", "WOW!", "MUST TRY!", "EASY!", "5-MIN", "SECRET", "HACK"]


def _make_gradient(w: int, h: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """Create a vertical linear gradient image."""
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top[0] + t * (bottom[0] - top[0]))
        g = int(top[1] + t * (bottom[1] - top[1]))
        b = int(top[2] + t * (bottom[2] - top[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Attempt to load a TrueType font; fall back to the default bitmap font."""
    font_candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    logger.warning("No TrueType font found; using default bitmap font")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_width: int) -> list[str]:
    """Break *text* into lines that fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy_img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_with_stroke(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str,
                            font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
                            fill: tuple[int, ...], stroke_fill: tuple[int, ...],
                            stroke_width: int) -> None:
    """Draw text with a thick outline/stroke for readability."""
    try:
        draw.text(xy, text, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
    except TypeError:
        x, y = xy
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx * dx + dy * dy <= stroke_width * stroke_width:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
        draw.text(xy, text, font=font, fill=fill)


def _draw_burst(draw: ImageDraw.ImageDraw, cx: int, cy: int, r_outer: int,
                r_inner: int, points: int, fill: tuple[int, ...]) -> None:
    """Draw a cartoon-style starburst / explosion shape.

    Args:
        draw: ImageDraw context.
        cx, cy: Center coordinates.
        r_outer: Outer radius (spike tips).
        r_inner: Inner radius (spike bases).
        points: Number of spike points.
        fill: Fill colour.
    """
    coords: list[tuple[float, float]] = []
    for i in range(points * 2):
        angle = math.pi * i / points - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(coords, fill=fill)


def _topic_emoji(topic: str) -> str:
    """Return a food-appropriate emoji for the topic."""
    topic_lower = topic.lower()
    for keywords, emoji in _FOOD_TOPIC_EMOJIS:
        if any(kw in topic_lower for kw in keywords):
            return emoji
    # Fall back to a random food emoji seeded on the topic
    seed = sum(ord(c) for c in topic)
    return _DEFAULT_FOOD_EMOJIS[seed % len(_DEFAULT_FOOD_EMOJIS)]


def _truncate_title_lines(lines: list[str], max_lines: int = 3) -> list[str]:
    """Limit title lines and append ellipsis when truncation happens."""
    if len(lines) <= max_lines:
        return lines
    truncated = lines[:max_lines]
    if not truncated[-1].endswith("..."):
        truncated[-1] = f"{truncated[-1]}..."
    return truncated


def create_thumbnail(title: str, topic: str) -> Path:
    """Generate a 1280 × 720 JPEG food content thumbnail for the given video *title*.

    Design language:
    - Warm vibrant gradient background (food-appetising tones)
    - Starburst accent behind the title text
    - Bold white title with thick black stroke
    - Large food emoji accent (context-matched to topic)
    - Recipe/tip accent overlay in the corner (VIRAL! / EASY! / 5-MIN / etc.)
    - Bright accent bar at the bottom with subscribe CTA

    Args:
        title: The video title to display prominently.
        topic: The trending topic (used for emoji and palette selection).

    Returns:
        Path to the saved JPEG thumbnail file.
    """
    # Seed randomness on the topic so thumbnails are consistent per topic
    rng = random.Random(sum(ord(c) for c in topic))

    # Pick gradient palette
    palette = rng.choice(_GRADIENT_PALETTES)
    accent_color = rng.choice(_ACCENT_COLORS)

    img = _make_gradient(THUMB_W, THUMB_H, palette[0], palette[1])
    draw = ImageDraw.Draw(img)

    # Draw cartoon starburst explosion behind the text area
    burst_cx = THUMB_W // 2
    burst_cy = THUMB_H // 2 - 40
    _draw_burst(draw, burst_cx, burst_cy, r_outer=380, r_inner=300, points=12,
                fill=(*accent_color, 180))  # type: ignore[arg-type]

    # Second smaller burst for depth
    _draw_burst(draw, burst_cx - 80, burst_cy + 30, r_outer=260, r_inner=210, points=8,
                fill=(255, 255, 255, 60))  # type: ignore[arg-type]

    # Subtle glow overlay for depth
    glow = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [(THUMB_W // 2 - 450, 30), (THUMB_W // 2 + 450, THUMB_H - 80)],
        fill=(255, 255, 255, 40),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=50))
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, glow)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Large comedy emoji — top left
    emoji = _topic_emoji(topic)
    emoji_font = _load_font(160)
    try:
        draw.text((40, 20), emoji, font=emoji_font, fill=_TEXT_COLOR)
    except Exception:  # noqa: BLE001
        pass

    # Accent text (LOL / WOW / OMG) — top right, rotated feel via bold font
    accent_word = rng.choice(_ACCENT_TEXTS)
    accent_font = _load_font(80)
    try:
        # Position in top right corner
        bbox = draw.textbbox((0, 0), accent_word, font=accent_font)
        aw = bbox[2] - bbox[0]
        _draw_text_with_stroke(
            draw, (THUMB_W - aw - 40, 20), accent_word,
            font=accent_font,
            fill=(255, 255, 0),
            stroke_fill=(0, 0, 0),
            stroke_width=5,
        )
    except Exception:  # noqa: BLE001
        pass

    # Readability overlay — cinematic dark glass behind title zone
    title_overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(title_overlay)
    ov_draw.rounded_rectangle(
        [(30, 130), (THUMB_W - 30, THUMB_H - 115)],
        radius=36,
        fill=(0, 0, 0, 95),
    )
    title_overlay = title_overlay.filter(ImageFilter.GaussianBlur(radius=6))
    img = Image.alpha_composite(img.convert("RGBA"), title_overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Title text — bold, white, large, centred
    title_upper = title.upper()
    title_font = _load_font(100)
    max_text_w = THUMB_W - 120
    lines = _wrap_text(title_upper, title_font, max_text_w)
    lines = _truncate_title_lines(lines, max_lines=3)
    line_height = 120
    total_text_h = len(lines) * line_height
    start_y = max(170, (THUMB_H - total_text_h) // 2 - 10)

    for i, line in enumerate(lines):
        y = start_y + i * line_height
        _draw_text_with_stroke(
            draw, (60, y), line,
            font=title_font,
            fill=_TEXT_COLOR,
            stroke_fill=_STROKE_COLOR,
            stroke_width=6,
        )

    # Bottom accent bar — bright colour with subscribe CTA
    bar_y = THUMB_H - 80
    draw.rounded_rectangle(
        [(20, bar_y), (THUMB_W - 20, THUMB_H - 10)],
        radius=18,
        fill=(0, 0, 0, 180),  # type: ignore[arg-type]
    )

    watermark_font = _load_font(42)
    _draw_text_with_stroke(
        draw, (50, bar_y + 14), "\u25b6 SUBSCRIBE \u2014 NEW FOOD RECIPE EVERY DAY!",
        font=watermark_font,
        fill=(255, 255, 0),
        stroke_fill=(0, 0, 0),
        stroke_width=2,
    )

    # Save
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    thumb_path = Path(tmp.name)
    tmp.close()
    img.save(thumb_path, "JPEG", quality=95, subsampling=0)
    logger.info("Food content thumbnail saved to '%s'", thumb_path)
    return thumb_path
