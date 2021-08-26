from . import theme as altair_theme
from .chart import Chart
from .saver import MSSaver, render
import altair as alt

alt.themes.register('mysoc_theme', lambda: altair_theme.mysoc_theme)
alt.themes.enable('mysoc_theme')

alt.renderers.register('mysoc_saver', render)
alt.renderers.enable('mysoc_saver')
