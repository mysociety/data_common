"""
functions to speed up and pretify notebooks
"""

from .exporters import render_to_markdown, render_to_html
from .charting import enable_altair, altair_theme, save_chart
from .dataframes import markdown_table
from .progress import Progress, track_progress
from typing import Union, Optional, List, Callable

import pandas as pd
import numpy as np
import altair as alt
from pathlib import Path
from IPython.display import Markdown as md
import datetime
from dataclasses import dataclass

import builtins as __builtin__
builtin_print = __builtin__.print


pd.options.mode.chained_assignment = None


def notebook_setup():
    enable_altair()


def Date(x):
    return datetime.datetime.fromisoformat(x).date()
