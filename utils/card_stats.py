"""Draw real upvote / comment counts on the Reddit card template image."""

import os
from PIL import Image, ImageDraw, ImageFont

# Pixel coordinates measured from assets/title_template.png (1080x1920).
# These define the bounding boxes of the static "999+" / "999,999" placeholder
# text that must be painted over before drawing real numbers.

_UPVOTE_TEXT_BOX = (146, 1083, 215, 1107)   # footer-left "999+"
_COMMENT_TEXT_BOX = (253, 1083, 325, 1107)   # footer-right "999+"
_KARMA_TEXT_BOX = (140, 893, 240, 918)        # header karma "999,999" + icon

_STAT_COLOR = (153, 153, 153, 255)            # grey used by the template
_FONT_PATH = os.path.join("fonts", "Roboto-Regular.ttf")
_FONT_SIZE = 18


def format_count(n: int) -> str:
    """Format a number the way Reddit does: 1234 -> '1.2k', 10500 -> '10.5k'."""
    if n < 0:
        return "0"
    if n < 1000:
        return str(n)
    if n < 100_000:
        value = n / 1000
        return f"{value:.1f}k".replace(".0k", "k")
    if n < 1_000_000:
        return f"{n // 1000}k"
    value = n / 1_000_000
    return f"{value:.1f}M".replace(".0M", "M")


def stamp_stats(
    image: Image.Image,
    upvotes: int,
    comments: int,
    y_offset: int = 0,
) -> Image.Image:
    """Paint real numbers over the static placeholders on a card template image.

    Args:
        image:    A copy of the card template (or expanded version).
        upvotes:  Real upvote count from the Reddit JSON.
        comments: Real comment count from the Reddit JSON.
        y_offset: Extra vertical pixels inserted by card expansion (shifts footer).
    """
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_FONT_PATH, _FONT_SIZE)

    def _whiteout_and_draw(box, text, offset_y):
        x0, y0, x1, y1 = box
        y0 += offset_y
        y1 += offset_y
        draw.rectangle([x0, y0, x1, y1], fill="white")
        draw.text((x0 + 2, y0 + 1), text, font=font, fill=_STAT_COLOR)

    _whiteout_and_draw(_UPVOTE_TEXT_BOX, format_count(upvotes), y_offset)
    _whiteout_and_draw(_COMMENT_TEXT_BOX, format_count(comments), y_offset)
    # Karma in the header is above the expansion point, so no y_offset
    _whiteout_and_draw(_KARMA_TEXT_BOX, format_count(upvotes), 0)

    return image
