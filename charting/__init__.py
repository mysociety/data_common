from . import theme as altair_theme
from . import sw_theme as altair_sw_theme
from .chart import Chart, Renderer, ChartEncoding
from .saver import MSSaver, SWSaver, render, sw_render
import altair as alt

alt.themes.register('mysoc_theme', lambda: altair_theme.mysoc_theme)
alt.themes.enable('mysoc_theme')

alt.renderers.register('mysoc_saver', render)
alt.renderers.enable('mysoc_saver')


def enable_sw_charts():
    alt.themes.register('societyworks_theme', lambda: altair_sw_theme.sw_theme)
    alt.themes.enable('societyworks_theme')

    alt.renderers.register('sw_saver', sw_render)
    alt.renderers.enable('sw_saver')
    Renderer.default_renderer = SWSaver


