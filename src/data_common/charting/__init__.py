import altair as alt

from . import sw_theme as altair_sw_theme
from . import theme as altair_theme
from .chart import Chart, ChartEncoding, ChartTitle, LayerChart
from .saver import MSSaver, SWSaver, render, sw_render

alt.themes.register("mysoc_theme", lambda: altair_theme.mysoc_theme)
alt.themes.enable("mysoc_theme")

# alt.renderers.register("mysoc_saver", render)  # type: ignore
# alt.renderers.enable("mysoc_saver")

reset_renderer = MSSaver.reset_driver


def enable_sw_charts():
    alt.themes.register("societyworks_theme", lambda: altair_sw_theme.sw_theme)
    alt.themes.enable("societyworks_theme")

    # alt.renderers.register("sw_saver", sw_render)  # type: ignore
    # alt.renderers.enable("sw_saver")
    # Renderer.default_renderer = SWSaver


gb_format = {"decimal": ".", "thousands": ",", "grouping": [3], "currency": ["£", ""]}

alt.renderers.set_embed_options(formatLocale=gb_format)
