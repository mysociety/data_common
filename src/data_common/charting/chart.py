from __future__ import annotations

import tempfile
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Union

import altair as alt  # type: ignore
import pandas as pd
import requests
import vl_convert as vlc
from IPython.core.display import Image as IIMAGE
from PIL import Image, ImageDraw, ImageFont


def logo_url_to_temp(logo_url: str) -> Path:
    """
    download a logo to a temp file
    """

    # get filename from url
    file_name = logo_url.split("/")[-1]
    temp_file = Path(tempfile.gettempdir()) / file_name
    if not temp_file.exists():
        logo = requests.get(logo_url)
        with open(temp_file, "wb") as f:
            f.write(logo.content)
    return temp_file


def split_text_to_line(text: str, cut_off: int = 60) -> List[str]:
    """
    Split a string to meet line limit
    """
    bits = text.split(" ")
    rows: list[str] = []
    current_item: list[str] = []
    for b in bits:
        if len(" ".join(current_item + [b])) > cut_off:
            rows.append(" ".join(current_item))
            current_item = []
        current_item.append(b)
    rows.append(" ".join(current_item))
    return rows


class ChartTitle(alt.TitleParams):
    """
    Helper function for chart title
    Includes better line wrapping
    """

    def __init__(
        self,
        title: Union[str, List[str]],
        subtitle: Optional[Union[str, List[str]]] = None,
        line_limit: int = 60,
        **kwargs: Any,
    ):

        if isinstance(title, str):
            title_bits = split_text_to_line(title, line_limit)
        else:
            title_bits = title

        if isinstance(subtitle, str):
            subtitle = [subtitle]

        kwargs["text"] = title_bits
        if subtitle:
            kwargs["subtitle"] = subtitle

        super().__init__(**kwargs)  # type: ignore


if TYPE_CHECKING:
    _base = alt.Chart
else:
    _base = object

logo_urls = {
    "mysociety": "https://research.mysociety.org/sites/foi-monitor/static/img/mysociety-logo.jpg",
    "societyworks": "https://blogs.mysociety.org/mysociety/files/2021/04/societyworks-logo-white-background.jpg",
}


class MSDisplayMixIn(_base):
    """
    mix in that enables a bit more customisation
    of extra display options in the renderer
    """

    ignore_properties = ["_display_options"]
    scale_factor = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._display_options: dict[str, Any] = {
            "scale_factor": self.__class__.scale_factor
        }

    def display_options(self, **kwargs):
        """
        arguments passed will be sent to display process
        """
        self._display_options.update(kwargs)
        return self

    def get_pil_image(self) -> Image.Image:

        logo = self._display_options.get("logo", False)
        caption = self._display_options.get("caption", "")

        png_data = vlc.vegalite_to_png(self.to_json(), scale=2)  # type: ignore

        # load the image from the PNG data
        pil_image = Image.open(BytesIO(png_data))

        if logo or caption:

            # Add a white space to the bottom of the image
            new_image = Image.new(
                "RGB", (pil_image.width, pil_image.height + 100), (255, 255, 255)
            )
            new_image.paste(pil_image, (0, 0))

        else:
            return pil_image

        if logo:
            if logo is True:
                logo_url = logo_urls["mysociety"]
            else:
                logo_url = logo_urls[logo]
            logo_file = logo_url_to_temp(logo_url)
            logo_image = Image.open(logo_file)

            # Add the logo to the bottom left
            new_logo_height = 100
            new_logo_width = int(logo_image.width * new_logo_height / logo_image.height)
            downsided_logo = logo_image.resize((new_logo_width, new_logo_height))
            new_image.paste(downsided_logo, (0, pil_image.height))
        if caption:
            caption = "This is a caption."
            draw = ImageDraw.Draw(new_image)

            font_path = Path("~/.fonts/", "SourceSansPro-Regular.otf").expanduser()
            font = ImageFont.truetype(font_path, 30)
            font_length = font.getlength(caption)

            draw.text(
                (pil_image.width - font_length - 30, pil_image.height + 100 - 50),
                caption,
                (0, 0, 0),
                font=font,
            )

        return new_image

    def save(self, dest: Path):

        pil_image = self.get_pil_image()
        pil_image.save(dest)

    def display(self):
        pil_image = self.get_pil_image()
        output_bytes = BytesIO()
        pil_image.save(output_bytes, format="PNG")
        png_byte_string = output_bytes.getvalue()
        return IIMAGE(png_byte_string)

    def to_dict(self, *args, ignore: Optional[List] = None, **kwargs) -> dict:
        if ignore is None:
            ignore = []
        ignore += self.__class__.ignore_properties
        return super().to_dict(*args, ignore=ignore, **kwargs)

    # Layering and stacking
    def __add__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be layered.")
        return layer(self, other)

    def __and__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be concatenated.")
        return vconcat(self, other)

    def __or__(self, other):
        if not isinstance(other, alt.TopLevelMixin):
            raise ValueError("Only Chart objects can be concatenated.")
        return hconcat(self, other)

    @wraps(alt.Chart.properties)
    def raw_properties(self, *args, **kwargs):
        return super().properties(*args, **kwargs)

    def big_labels(self) -> "Chart":
        """
        quick helper function to add a bigger label limit
        """
        return self.configure_axis(labelLimit=1000)

    def properties(
        self,
        title: Union[str, list, alt.TitleParams, ChartTitle] = "",
        title_line_limit: int = 60,
        subtitle: Optional[Union[str, list]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        aspect: tuple = (16, 9),
        logo: bool = False,
        caption: str = "",
        scale_factor: Optional[int] = None,
        **kwargs,
    ) -> "Chart":

        args = {}
        display_args = {"logo": logo, "caption": caption}
        if scale_factor:
            display_args["scale_factor"] = scale_factor

        if isinstance(title, str) or isinstance(title, list) or subtitle is not None:
            args["title"] = ChartTitle(
                title=str(title), subtitle=subtitle, line_limit=title_line_limit
            )

        if width and not height:
            args["width"] = width
            args["height"] = (width / aspect[0]) * aspect[1]

        if height and not width:
            args["height"] = height
            args["width"] = (height / aspect[1]) * aspect[0]

        if width and height:
            args["height"] = height
            args["width"] = width

        width_offset = 0
        height_offset = 0

        if logo or caption:
            height_offset += 100

        if "width" in args:
            args["width"] -= width_offset
            args["height"] -= height_offset
            args["autosize"] = alt.AutoSizeParams(type="fit", contains="padding")  # type: ignore

        kwargs.update(args)
        return super().properties(**kwargs).display_options(**display_args)


class MSDataManagementMixIn(_base):
    """
    Mixin to manage downloading charts
    from the explorer minisites and making it
    slightly easier to edit the data with pandas

    """

    if TYPE_CHECKING:
        data = {}

    @classmethod
    def from_url(cls, url, n=0):
        from .download import get_chart_from_url

        return get_chart_from_url(url, n)

    def _get_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.datasets[self.data["name"]])

    def update_df(self, df: pd.DataFrame):
        """
        take a new df and update the chart
        """
        self.datasets[self.data["name"]] = df.to_dict("records")
        return self

    @property
    def df(self):
        """
        get the dataset from the chart as a df
        """
        return self._get_df()

    def __setattr__(self, key, value):
        if key == "df":
            self.update_df(value)
        else:
            super().__setattr__(key, value)


class MSAltair(MSDisplayMixIn, MSDataManagementMixIn):
    pass


class Chart(MSAltair, alt.Chart):
    pass


class LayerChart(MSAltair, alt.LayerChart):
    pass


class HConcatChart(MSAltair, alt.HConcatChart):
    pass


class VConcatChart(MSAltair, alt.VConcatChart):
    pass


def layer(*charts, **kwargs):
    """layer multiple charts"""
    return LayerChart(layer=charts, **kwargs)


def hconcat(*charts, **kwargs):
    """Concatenate charts horizontally"""
    return HConcatChart(hconcat=charts, **kwargs)


def vconcat(*charts, **kwargs):
    """Concatenate charts horizontally"""
    return VConcatChart(vconcat=charts, **kwargs)


@wraps(Chart.encode)  # type: ignore
def ChartEncoding(**kwargs: Any):
    """
    Thin wrapper to specify properties we want to use multiple times
    """
    return kwargs
