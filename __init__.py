"""
functions to speed up and pretify notebooks
"""

from .exporters import render_to_markdown, render_to_html
from .charting import enable_altair, altair_theme, save_chart
from .dataframes import markdown_table

import pandas as pd
import altair as alt
from pathlib import Path
from IPython.display import Markdown as md
import datetime

import builtins as __builtin__
builtin_print = __builtin__.print


pd.options.mode.chained_assignment = None


def notebook_setup():
    enable_altair()
