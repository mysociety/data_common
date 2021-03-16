"""
functions to speed up and pretify notebooks
"""

from .exporters import render_to_markdown, render_to_html
from .charting import enable_altair, altair_theme
from .dataframes import markdown_table

import pandas as pd
import altair as alt
from pathlib import Path

import builtins as __builtin__
builtin_print = __builtin__.print


def init():
    enable_altair()


init()