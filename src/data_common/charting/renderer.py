import base64
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
import vl_convert as vlc
from PIL import Image, ImageDraw, ImageFont

from .str_enum import StrEnum


class Logo(StrEnum):
    MYSOCIETY = (
        "https://research.mysociety.org/sites/foi-monitor/static/img/mysociety-logo.jpg"
    )
    SOCIETYWORKS = "https://blogs.mysociety.org/mysociety/files/2021/04/societyworks-logo-white-background.jpg"
    WRITETOTHEM = "https://www.mysociety.org/files/2014/11/writetothem-logo.jpg"
    NONE = ""


def url_to_temp(file_url: str) -> Path:
    """
    download a logo to a temp file
    """
    # get filename from url
    file_name = file_url.split("/")[-1]
    temp_file = Path(tempfile.gettempdir()) / file_name
    if not temp_file.exists():
        logo = requests.get(file_url)
        with open(temp_file, "wb") as f:
            f.write(logo.content)
    return temp_file


MimeBundle = dict[str, str]


def pil_image_to_mimebundle(img: Image.Image) -> MimeBundle:
    # Convert the PIL image to PNG and store it in a BytesIO buffer
    buffer = BytesIO()
    img.save(buffer, format="PNG")

    # Get the PNG data from the buffer
    png_data = buffer.getvalue()

    # Encode the PNG data in base64
    base64_png = base64.b64encode(png_data).decode("utf-8")

    # Create the MIME bundle dictionary
    mimebundle = {"image/png": base64_png}

    return mimebundle


def render(spec: dict, embed_options: dict[str, Any]) -> MimeBundle:
    display = spec.get("custom", {}).get(
        "_display_options", {"scale_factor": 1, "logo": "", "caption": ""}
    )
    scale_factor = display["scale_factor"]
    logo = display["logo"] or embed_options.get("logo", "")
    caption = display["caption"]
    caption_font_url = embed_options.get("caption_font_url", "")

    format_locale = embed_options.get("formatLocale", {})

    png_data = vlc.vegalite_to_png(
        spec, scale=scale_factor, format_locale=format_locale
    )  # type: ignore

    # load the image from the PNG data
    pil_image = Image.open(BytesIO(png_data))

    if logo or caption:
        # Add a white space to the bottom of the image
        new_image = Image.new(
            "RGB", (pil_image.width, pil_image.height + 100), (255, 255, 255)
        )
        new_image.paste(pil_image, (0, 0))

    else:
        return pil_image_to_mimebundle(pil_image)

    if logo:
        logo_file = url_to_temp(logo)
        logo_image = Image.open(logo_file)

        # Add the logo to the bottom left
        new_logo_height = 100
        new_logo_width = int(logo_image.width * new_logo_height / logo_image.height)
        downsided_logo = logo_image.resize((new_logo_width, new_logo_height))
        new_image.paste(downsided_logo, (0, pil_image.height))
    if caption:
        draw = ImageDraw.Draw(new_image)
        if caption_font_url:
            font_path = url_to_temp(caption_font_url)
            font = ImageFont.truetype(font_path, 30)
        else:
            font = ImageFont.load_default(size=30)
        font_length = font.getlength(caption)

        draw.text(
            (pil_image.width - font_length - 30, pil_image.height + 100 - 50),
            caption,
            (0, 0, 0),
            font=font,
        )

    return pil_image_to_mimebundle(new_image)
