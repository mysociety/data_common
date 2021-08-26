"""
functions to speed up and pretify notebooks
"""

from .exporters import render_to_markdown, render_to_html
from .charting import (altair_theme, Chart)
from .progress import Progress, track_progress
from .helpers.pipe import Pipe, iter_format
from typing import Union, Optional, List, Callable
from functools import partial

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

image_dir = Path("_images")
render_dir = Path("_render")

def notebook_setup():
    pass


def Date(x):
    return datetime.datetime.fromisoformat(x).date()
