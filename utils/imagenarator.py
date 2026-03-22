import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont
from rich.progress import track

from TTS.engine_wrapper import process_text
from utils.fonts import getheight, getsize
from utils import settings


def draw_multiple_line_text(
    image, text, font, text_color, padding, wrap=50, transparent=False
) -> None:
    """
    Draw multiline text over given image
    """
    draw = ImageDraw.Draw(image)
    font_height = getheight(font, text)
    image_width, image_height = image.size
    lines = textwrap.wrap(text, width=wrap)
    y = (image_height / 2) - (((font_height + (len(lines) * padding) / len(lines)) * len(lines)) / 2)
    for line in lines:
        line_width, line_height = getsize(font, line)
        if transparent:
            shadowcolor = "black"
            for i in range(1, 5):
                draw.text(
                    ((image_width - line_width) / 2 - i, y - i),
                    line,
                    font=font,
                    fill=shadowcolor,
                )
                draw.text(
                    ((image_width - line_width) / 2 + i, y - i),
                    line,
                    font=font,
                    fill=shadowcolor,
                )
                draw.text(
                    ((image_width - line_width) / 2 - i, y + i),
                    line,
                    font=font,
                    fill=shadowcolor,
                )
                draw.text(
                    ((image_width - line_width) / 2 + i, y + i),
                    line,
                    font=font,
                    fill=shadowcolor,
                )
        draw.text(((image_width - line_width) / 2, y), line, font=font, fill=text_color)
        y += line_height + padding





def draw_single_word_text(image, word, font, text_color, padding, transparent=False) -> None:
    """
    Draw a single word centered on the given image.
    """
    draw = ImageDraw.Draw(image)
    image_width, image_height = image.size
    word_width, word_height = getsize(font, word)
    y = (image_height / 2) - (word_height / 2)
    x = (image_width / 2) - (word_width / 2)
    
    if transparent:
        shadowcolor = "black"
        for i in range(1, 5):
            draw.text((x - i, y - i), word, font=font, fill=shadowcolor)
            draw.text((x + i, y - i), word, font=font, fill=shadowcolor)
            draw.text((x - i, y + i), word, font=font, fill=shadowcolor)
            draw.text((x + i, y + i), word, font=font, fill=shadowcolor)
    
    draw.text((x, y), word, font=font, fill=text_color)






def imagemaker(theme, reddit_obj: dict, txtclr, padding=5, transparent=False) -> None:
    """
    Render Images for video
    """
    texts = reddit_obj["thread_post"]
    id = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])

    manual_enabled = settings.config.get("manual", {}).get("enabled")
    use_api = settings.config["reddit"]["thread"].get("use_api", True)
    use_card_template = manual_enabled or not use_api

    # Base font (will be adjusted for manual mode as needed)
    base_font_path = os.path.join("fonts", "Roboto-Regular.ttf")
    bold_font_path = os.path.join("fonts", "Roboto-Black.ttf")
    if transparent:
        font = ImageFont.truetype(bold_font_path, 100)
    else:
        font = ImageFont.truetype(base_font_path, 100)

    if use_card_template:
        base_image = Image.open("assets/title_template.png").convert("RGBA")
        size = base_image.size
    else:
        size = (1920, 1080)
        base_image = Image.new("RGBA", size, theme)

    for idx, text in track(enumerate(texts), "Rendering Image"):
        image = base_image.copy()
        text = process_text(text, False)

        if use_card_template:
            img_w, img_h = image.size

            # Card geometry (px, measured from title_template.png)
            HEADER_END = 916     # usable body starts after header
            FOOTER_START = 1091  # footer icons begin
            SPLIT_Y = 1000       # expansion cut-point (pure-white body row)
            TEXT_X = 120          # left margin matching the title card
            MAX_TEXT_W = 840      # usable text width inside the card
            BODY_VPAD = 20        # vertical padding above/below text block

            def _wrap(txt, fnt):
                result, cur = [], ""
                for w in txt.split():
                    trial = (cur + " " + w).strip()
                    if getsize(fnt, trial)[0] <= MAX_TEXT_W:
                        cur = trial
                    else:
                        if cur:
                            result.append(cur)
                        cur = w
                if cur:
                    result.append(cur)
                return result

            # Roboto-Regular at the same size tiers the title uses (un-bolded)
            for fsz in (47, 40, 35, 30):
                working_font = ImageFont.truetype(base_font_path, fsz)
                lines = _wrap(text, working_font)
                if len(lines) <= 5 or fsz == 30:
                    break

            line_heights = [getheight(working_font, ln) for ln in lines]
            text_block_h = sum(line_heights) + padding * max(len(lines) - 1, 0)

            # Expand the card body if the text doesn't fit
            original_body_h = FOOTER_START - HEADER_END
            needed_body_h = text_block_h + 2 * BODY_VPAD
            extra = max(0, needed_body_h - original_body_h)

            if extra > 0:
                row_strip = base_image.crop((0, SPLIT_Y, img_w, SPLIT_Y + 1))
                fill = row_strip.resize((img_w, extra), Image.NEAREST)
                expanded = Image.new("RGBA", (img_w, img_h + extra), (0, 0, 0, 0))
                expanded.paste(image.crop((0, 0, img_w, SPLIT_Y)), (0, 0))
                expanded.paste(fill, (0, SPLIT_Y))
                expanded.paste(image.crop((0, SPLIT_Y, img_w, img_h)), (0, SPLIT_Y + extra))
                image = expanded

            body_top = HEADER_END
            body_bottom = FOOTER_START + extra
            y = body_top + (body_bottom - body_top - text_block_h) // 2

            draw = ImageDraw.Draw(image)
            for li, ln in enumerate(lines):
                draw.text((TEXT_X, y), ln, font=working_font, fill="black")
                y += line_heights[li] + padding

            if settings.config["settings"].get("show_real_stats") and "thread_upvotes" in reddit_obj:
                from utils.card_stats import stamp_stats
                stamp_stats(image, reddit_obj["thread_upvotes"], reddit_obj["thread_comments"], y_offset=extra)
        else:
            draw_multiple_line_text(image, text, font, txtclr, padding, wrap=30, transparent=transparent)

        image.save(f"assets/temp/{id}/png/img{idx}.png")




# def imagemaker(theme, reddit_obj: dict, txtclr, padding=5, transparent=False) -> None:
#     """
#     Render Images for video with single-word captions.
#     """
#     texts = reddit_obj["thread_post"]  # This is a list of sentences/phrases
#     id = re.sub(r"[^\w\s-]", "", reddit_obj["thread_id"])

#     # Load the font and increase its size
#     font_size = 150  # Adjust this value to make the font bigger
#     if transparent:
#         font = ImageFont.truetype(os.path.join("fonts", "Roboto-Black.ttf"), font_size)
#     else:
#         font = ImageFont.truetype(os.path.join("fonts", "Roboto-Regular.ttf"), font_size)

#     size = (1920, 1080)  # Image size
#     image = Image.new("RGBA", size, theme)

#     # Split the list of sentences into individual words
#     words = []
#     for sentence in texts:
#         words.extend(sentence.split())  # Split each sentence into words and extend the list

#     # Loop through each word to render an image for it
#     for idx, word in track(enumerate(words), "Rendering Image"):
#         image = Image.new("RGBA", size, theme)
#         processed_word = process_text(word, False)  # Process the word if needed
#         draw_single_word_text(image, processed_word, font, txtclr, padding, transparent=transparent)
#         image.save(f"assets/temp/{id}/png/img{idx}.png")