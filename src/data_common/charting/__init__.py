import altair as alt

from . import sw_theme as altair_sw_theme
from . import theme as altair_theme
from .chart import (
    Chart as Chart,
)
from .chart import (
    ChartEncoding as ChartEncoding,
)
from .chart import (
    ChartTitle as ChartTitle,
)
from .chart import (
    LayerChart as LayerChart,
)
from .renderer import Logo, render

alt.themes.register("mysoc_theme", lambda: altair_theme.mysoc_theme)
alt.themes.enable("mysoc_theme")

gb_format = {"decimal": ".", "thousands": ",", "grouping": [3], "currency": ["£", ""]}

alt.renderers.register("mysoc_saver", render)  # type: ignore
alt.renderers.enable("mysoc_saver")
alt.renderers.set_embed_options(formatLocale=gb_format)


def enable_ms_charts():
    alt.themes.register("mysoc_theme", lambda: altair_theme.mysoc_theme)
    alt.themes.enable("mysoc_theme")
    alt.renderers.set_embed_options(
        formatLocale=gb_format,
        logo=Logo.MYSOCIETY,
        caption_font_url="https://github.com/nteract/assets/raw/master/fonts/source-sans-pro/WOFF/OTF/SourceSansPro-Regular.otf.woff",
    )


def enable_sw_charts():
    alt.themes.register("societyworks_theme", lambda: altair_sw_theme.sw_theme)
    alt.themes.enable("societyworks_theme")
    alt.renderers.set_embed_options(
        formatLocale=gb_format,
        logo=Logo.SOCIETYWORKS,
        caption_font_url="https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf",
    )


enable_ms_charts()
